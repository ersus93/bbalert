# utils/sss_manager.py
# SmartSignals Strategy (SSS) Manager
# Carga, valida y aplica estrategias de trading sobre señales del motor SP.
#
# Características:
#  - Carga dinámica desde data/sss/strategies/*.json (hot-reload sin reiniciar)
#  - Tres estrategias base incluidas: SASAS Pro, Momentum Scalper, Swing Wave
#  - Indicadores extendidos: Supertrend, ASH, ADX/DI (calculados bajo demanda)
#  - Enriquecimiento de señal: TP1/TP2/TP3, SL dinámico, apalancamiento sugerido
#  - Preferencias por usuario en data/sss/user_prefs.json (gitignored)
#  - Validación de tier: base (todos premium), premium (pago), admin (solo admins)

import json
import os
import time
import logging
import numpy as np
import pandas as pd

try:
    import pandas_ta as pta
except ImportError:
    pta = None

from core.config import DATA_DIR, ADMIN_CHAT_IDS
from utils.file_manager import check_feature_access

logger = logging.getLogger(__name__)

# ─── PATHS ────────────────────────────────────────────────────────────────────

SSS_DIR         = os.path.join(DATA_DIR, "sss")
SSS_STRAT_DIR   = os.path.join(SSS_DIR, "strategies")
SSS_PREFS_PATH  = os.path.join(SSS_DIR, "user_prefs.json")

# ─── CACHE DE ESTRATEGIAS ─────────────────────────────────────────────────────

_strategy_cache: dict = {}        # id -> strategy dict
_cache_mtime:    dict = {}        # filepath -> mtime
_cache_loaded_at: float = 0.0
CACHE_TTL = 60.0                  # refrescar cada 60 segundos o si hay cambios


# ─── TIER HELPERS ─────────────────────────────────────────────────────────────

def _user_tier(user_id: int) -> str:
    """Devuelve 'admin', 'premium' o 'base' según el usuario."""
    if user_id in ADMIN_CHAT_IDS:
        return 'admin'
    ok, _ = check_feature_access(user_id, 'sp_signals')
    return 'premium' if ok else 'base'

_TIER_RANK = {'base': 0, 'premium': 1, 'admin': 2}

def _tier_allows(user_tier: str, strategy_tier: str) -> bool:
    return _TIER_RANK.get(user_tier, 0) >= _TIER_RANK.get(strategy_tier, 0)


# ─── CARGA DE ESTRATEGIAS ─────────────────────────────────────────────────────

def _load_from_disk() -> dict:
    """Carga todas las estrategias del directorio SSS."""
    if not os.path.isdir(SSS_STRAT_DIR):
        return {}

    strategies = {}
    for fname in os.listdir(SSS_STRAT_DIR):
        if not fname.endswith('.json'):
            continue
        fpath = os.path.join(SSS_STRAT_DIR, fname)
        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                strat = json.load(f)
            sid = strat.get('id')
            if not sid:
                logger.warning(f"[SSS] Estrategia sin 'id' en {fname}, ignorada.")
                continue
            strategies[sid] = strat
            _cache_mtime[fpath] = os.path.getmtime(fpath)
        except Exception as e:
            logger.error(f"[SSS] Error cargando {fname}: {e}")
    return strategies


def _has_disk_changes() -> bool:
    """Comprueba si algún fichero ha cambiado desde la última carga."""
    if not os.path.isdir(SSS_STRAT_DIR):
        return False
    for fname in os.listdir(SSS_STRAT_DIR):
        if not fname.endswith('.json'):
            continue
        fpath = os.path.join(SSS_STRAT_DIR, fname)
        mtime = os.path.getmtime(fpath)
        if _cache_mtime.get(fpath) != mtime:
            return True
    return False


def _get_all_strategies() -> dict:
    """Devuelve el dict de estrategias, recargando si es necesario."""
    global _strategy_cache, _cache_loaded_at
    now = time.time()
    if (now - _cache_loaded_at > CACHE_TTL) or _has_disk_changes():
        _strategy_cache = _load_from_disk()
        _cache_loaded_at = now
        logger.info(f"[SSS] {len(_strategy_cache)} estrategia(s) cargadas.")
    return _strategy_cache


def get_available_strategies(user_id: int) -> list:
    """Lista de estrategias disponibles para el usuario, ordenadas por tier."""
    all_strats = _get_all_strategies()
    ut = _user_tier(user_id)
    available = [
        s for s in all_strats.values()
        if _tier_allows(ut, s.get('tier', 'base'))
    ]
    # Ordenar: base primero, luego premium, luego admin; dentro por nombre
    available.sort(key=lambda s: (
        _TIER_RANK.get(s.get('tier', 'base'), 0),
        s.get('name', '')
    ))
    return available


def get_strategy_by_id(strategy_id: str) -> dict | None:
    """Devuelve la estrategia por su ID."""
    return _get_all_strategies().get(strategy_id)


# ─── PREFERENCIAS DE USUARIO ──────────────────────────────────────────────────

def _load_prefs() -> dict:
    if not os.path.exists(SSS_PREFS_PATH):
        return {}
    try:
        with open(SSS_PREFS_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def _save_prefs(data: dict) -> None:
    os.makedirs(SSS_DIR, exist_ok=True)
    tmp = SSS_PREFS_PATH + '.tmp'
    try:
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, SSS_PREFS_PATH)
    except Exception as e:
        logger.error(f"[SSS] Error guardando prefs: {e}")


def get_user_strategy(user_id: int) -> dict | None:
    """Devuelve la estrategia activa del usuario, o None si no tiene."""
    prefs = _load_prefs()
    sid = prefs.get(str(user_id))
    if not sid:
        return None
    strat = get_strategy_by_id(sid)
    # Validar que el usuario sigue teniendo acceso al tier de la estrategia
    if strat and _tier_allows(_user_tier(user_id), strat.get('tier', 'base')):
        return strat
    return None


def set_user_strategy(user_id: int, strategy_id: str | None) -> bool:
    """
    Activa una estrategia para el usuario.
    strategy_id=None desactiva cualquier estrategia activa.
    Devuelve True si se guardó correctamente.
    """
    prefs = _load_prefs()
    uid = str(user_id)
    if strategy_id is None:
        prefs.pop(uid, None)
    else:
        strat = get_strategy_by_id(strategy_id)
        if not strat:
            return False
        if not _tier_allows(_user_tier(user_id), strat.get('tier', 'base')):
            return False
        prefs[uid] = strategy_id
    _save_prefs(prefs)
    return True


# ─── INDICADORES EXTENDIDOS ───────────────────────────────────────────────────

def _compute_supertrend(df: pd.DataFrame, period: int = 14, multiplier: float = 1.8) -> pd.DataFrame:
    """
    Calcula Supertrend usando pandas_ta ATR.
    Agrega columnas: supertrend, supertrend_direction (1=bull, -1=bear).
    """
    result = df.copy()
    n = len(result)
    result['supertrend'] = np.nan
    result['supertrend_direction'] = 0

    if n < period + 2 or pta is None:
        return result

    try:
        atr = pta.atr(result['high'], result['low'], result['close'], length=period)
        if atr is None or atr.isna().all():
            return result

        hl2 = (result['high'] + result['low']) / 2
        upper = (hl2 + multiplier * atr).values
        lower = (hl2 - multiplier * atr).values
        close = result['close'].values

        trend = np.zeros(n)
        direction = np.zeros(n)

        # Inicializar
        trend[0] = lower[0] if not np.isnan(lower[0]) else 0
        direction[0] = 1

        for i in range(1, n):
            prev_upper = upper[i - 1] if not np.isnan(upper[i - 1]) else upper[i]
            prev_lower = lower[i - 1] if not np.isnan(lower[i - 1]) else lower[i]

            if close[i] > prev_upper:
                direction[i] = 1
                trend[i] = lower[i]
            elif close[i] < prev_lower:
                direction[i] = -1
                trend[i] = upper[i]
            else:
                direction[i] = direction[i - 1]
                trend[i] = trend[i - 1]
                if direction[i] == 1 and not np.isnan(lower[i]) and lower[i] > trend[i]:
                    trend[i] = lower[i]
                if direction[i] == -1 and not np.isnan(upper[i]) and upper[i] < trend[i]:
                    trend[i] = upper[i]

        result['supertrend']           = trend
        result['supertrend_direction'] = direction

    except Exception as e:
        logger.error(f"[SSS] Error en _compute_supertrend: {e}")

    return result


def _compute_ash(df: pd.DataFrame, length: int = 16, smooth: int = 4) -> pd.DataFrame:
    """
    Calcula Absolute Strength Histogram simplificado.
    Señal alcista: bulls > bears y creciendo.
    Agrega columnas: ash_bulls, ash_bears, ash_bull_signal, ash_bear_signal.
    """
    result = df.copy()
    n = len(result)
    result['ash_bulls'] = np.nan
    result['ash_bears'] = np.nan
    result['ash_bull_signal'] = False
    result['ash_bear_signal'] = False

    if n < length + smooth + 2 or pta is None:
        return result

    try:
        close = result['close']
        prev_close = close.shift(1)

        bull_raw = np.abs(close - close.shift(1).clip(upper=close))
        bear_raw = np.abs(close - close.shift(1).clip(lower=close))

        # EMA smoothing
        bulls = bull_raw.ewm(span=length, adjust=False).mean()
        bears = bear_raw.ewm(span=length, adjust=False).mean()

        # Suavizado secundario
        bulls_s = bulls.ewm(span=smooth, adjust=False).mean()
        bears_s = bears.ewm(span=smooth, adjust=False).mean()

        result['ash_bulls'] = bulls_s
        result['ash_bears'] = bears_s

        # Señal de cruce con confirmación
        bull_cross = (
            (bulls_s > bears_s) &
            (bulls_s.shift(1) <= bears_s.shift(1))
        )
        bear_cross = (
            (bears_s > bulls_s) &
            (bears_s.shift(1) <= bulls_s.shift(1))
        )

        result['ash_bull_signal'] = bull_cross
        result['ash_bear_signal'] = bear_cross

    except Exception as e:
        logger.error(f"[SSS] Error en _compute_ash: {e}")

    return result


def _compute_adx(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """Calcula ADX, DI+ y DI- usando pandas_ta."""
    result = df.copy()
    result['sss_adx'] = np.nan
    result['sss_plus_di'] = np.nan
    result['sss_minus_di'] = np.nan

    if pta is None:
        return result

    try:
        adx_df = pta.adx(result['high'], result['low'], result['close'], length=period)
        if adx_df is not None and len(adx_df.columns) >= 3:
            cols = adx_df.columns.tolist()
            result['sss_adx']      = adx_df[cols[0]]
            result['sss_plus_di']  = adx_df[cols[1]] if len(cols) > 1 else np.nan
            result['sss_minus_di'] = adx_df[cols[2]] if len(cols) > 2 else np.nan
    except Exception as e:
        logger.error(f"[SSS] Error en _compute_adx: {e}")

    return result


def _compute_volatility(df: pd.DataFrame) -> float:
    """Retorna la volatilidad reciente como porcentaje del precio."""
    try:
        returns = df['close'].pct_change().dropna()
        if len(returns) < 5:
            return 0.02
        return float(returns.tail(20).std())
    except Exception:
        return 0.02


def compute_extended_indicators(df: pd.DataFrame, strategy: dict) -> pd.DataFrame:
    """
    Calcula los indicadores adicionales que la estrategia necesita.
    Solo calcula lo necesario según entry_filter de la estrategia.
    """
    ef = strategy.get('entry_filter', {})
    df_ext = df.copy()

    if ef.get('supertrend_align') or ef.get('trailing_type') == 'supertrend':
        df_ext = _compute_supertrend(df_ext)

    if ef.get('ash_signal'):
        df_ext = _compute_ash(df_ext)

    adx_min = ef.get('adx_min', 0)
    if adx_min > 0 or ef.get('adx_di_confirm'):
        df_ext = _compute_adx(df_ext)

    return df_ext


# ─── FILTRO DE ENTRADA ────────────────────────────────────────────────────────

def apply_strategy_filter(strategy: dict, sig: dict, df_ext: pd.DataFrame) -> tuple[bool, str]:
    """
    Aplica los filtros de entrada de la estrategia sobre la señal base.
    Devuelve (pasa: bool, razón: str).
    """
    ef      = strategy.get('entry_filter', {})
    last    = df_ext.iloc[-2] if len(df_ext) >= 2 else df_ext.iloc[-1]
    direction = sig.get('direction', 'NEUTRAL')

    if direction == 'NEUTRAL':
        return False, "Señal neutral"

    is_long = direction == 'BUY'

    # ── Score mínimo ──────────────────────────────────────────────────────────
    min_score = ef.get('min_score', 4.5)
    if sig.get('score_abs', 0) < min_score:
        return False, f"Score {sig.get('score_abs',0):.1f} < {min_score}"

    # ── Supertrend align ──────────────────────────────────────────────────────
    if ef.get('supertrend_align'):
        st_dir = last.get('supertrend_direction', 0) if hasattr(last, 'get') else last.get('supertrend_direction', 0) if hasattr(last, 'get') else 0
        if pd.isna(st_dir) or st_dir == 0:
            return False, "Supertrend no calculado"
        if is_long and st_dir != 1:
            return False, "Supertrend bajista en compra"
        if not is_long and st_dir != -1:
            return False, "Supertrend alcista en venta"

    # ── ASH signal ────────────────────────────────────────────────────────────
    if ef.get('ash_signal'):
        if is_long:
            # Verificar que bulls > bears en la última vela cerrada
            bulls = last.get('ash_bulls', np.nan) if hasattr(last, 'get') else getattr(last, 'ash_bulls', np.nan)
            bears = last.get('ash_bears', np.nan) if hasattr(last, 'get') else getattr(last, 'ash_bears', np.nan)
            if not (pd.notna(bulls) and pd.notna(bears) and bulls > bears):
                return False, "ASH no confirma compra"
        else:
            bulls = last.get('ash_bulls', np.nan) if hasattr(last, 'get') else getattr(last, 'ash_bulls', np.nan)
            bears = last.get('ash_bears', np.nan) if hasattr(last, 'get') else getattr(last, 'ash_bears', np.nan)
            if not (pd.notna(bulls) and pd.notna(bears) and bears > bulls):
                return False, "ASH no confirma venta"

    # ── ADX mínimo ────────────────────────────────────────────────────────────
    adx_min = ef.get('adx_min', 0)
    if adx_min > 0:
        adx_val = last.get('sss_adx', np.nan) if hasattr(last, 'get') else getattr(last, 'sss_adx', np.nan)
        if pd.notna(adx_val) and adx_val < adx_min:
            return False, f"ADX {adx_val:.1f} < {adx_min} (mercado lateral)"

    # ── ADX DI confirmation ───────────────────────────────────────────────────
    if ef.get('adx_di_confirm'):
        plus_di  = last.get('sss_plus_di', np.nan)  if hasattr(last, 'get') else getattr(last, 'sss_plus_di', np.nan)
        minus_di = last.get('sss_minus_di', np.nan) if hasattr(last, 'get') else getattr(last, 'sss_minus_di', np.nan)
        if pd.notna(plus_di) and pd.notna(minus_di):
            if is_long and plus_di <= minus_di:
                return False, "DI+ ≤ DI- en compra"
            if not is_long and minus_di <= plus_di:
                return False, "DI- ≤ DI+ en venta"

    # ── Volume spike ──────────────────────────────────────────────────────────
    if ef.get('volume_spike'):
        mult = ef.get('volume_spike_mult', 1.5)
        try:
            vol_current = float(df_ext.iloc[-2]['volume'])
            vol_avg     = float(df_ext['volume'].tail(20).mean())
            if vol_avg > 0 and vol_current < vol_avg * mult:
                return False, f"Volumen bajo ({vol_current/vol_avg:.1f}x < {mult}x)"
        except Exception:
            pass

    # ── MACD cross required ───────────────────────────────────────────────────
    if ef.get('macd_cross_required'):
        reasons = sig.get('reasons', [])
        has_macd = any('MACD' in r for r in reasons)
        if not has_macd:
            return False, "Sin cruce MACD confirmado"

    # ── RSI extremes ──────────────────────────────────────────────────────────
    rsi = sig.get('rsi', 50)
    if is_long:
        rsi_limit = ef.get('rsi_oversold_buy', 100)
        if rsi > rsi_limit:
            return False, f"RSI {rsi:.1f} no en zona de compra (>{rsi_limit})"
    else:
        rsi_limit = ef.get('rsi_overbought_sell', 0)
        if rsi_limit > 0 and rsi < rsi_limit:
            return False, f"RSI {rsi:.1f} no en zona de venta (<{rsi_limit})"

    return True, "OK"


# ─── ENRIQUECIMIENTO DE SEÑAL ─────────────────────────────────────────────────

def enrich_signal(strategy: dict, sig: dict, df_ext: pd.DataFrame) -> dict:
    """
    Enriquece la señal con TP/SL/leverage de la estrategia.
    Devuelve un dict con campos adicionales.
    """
    enriched = dict(sig)
    risk     = strategy.get('risk', {})
    lev_cfg  = strategy.get('leverage', {})
    direction = sig.get('direction', 'NEUTRAL')
    is_long   = direction == 'BUY'
    price     = sig.get('price', 0)
    atr       = sig.get('atr', price * 0.002)

    if atr == 0:
        atr = price * 0.002

    # ── Stop Loss ─────────────────────────────────────────────────────────────
    sl_type  = risk.get('sl_type', 'atr')
    sl_mult  = risk.get('sl_atr_mult', 1.5)

    if sl_type == 'atr':
        sl_dist = atr * sl_mult
    else:
        sl_dist = atr * sl_mult   # Fallback

    if is_long:
        sl_price = price - sl_dist
    else:
        sl_price = price + sl_dist

    # ── Take Profits ──────────────────────────────────────────────────────────
    def _tp(mult: float) -> float:
        dist = atr * mult
        return (price + dist) if is_long else (price - dist)

    tp1_price = _tp(risk.get('tp1_atr_mult', 2.0))
    tp2_price = _tp(risk.get('tp2_atr_mult', 3.5))
    tp3_price = _tp(risk.get('tp3_atr_mult', 5.5))

    tp1_pct   = risk.get('tp1_close_pct', 50)
    tp2_pct   = risk.get('tp2_close_pct', 30)
    tp3_pct   = risk.get('tp3_close_pct', 20)

    # ── Apalancamiento ────────────────────────────────────────────────────────
    base_lev = lev_cfg.get('default', 5)
    max_lev  = lev_cfg.get('max', 20)

    if lev_cfg.get('volatile_reduce'):
        volatility = _compute_volatility(df_ext)
        vol_thresh = lev_cfg.get('volatile_threshold', 0.03)
        if volatility > vol_thresh:
            base_lev = min(base_lev, lev_cfg.get('volatile_max', max_lev // 2))

    leverage = max(1, min(base_lev, max_lev))

    # ── R:R ratio ─────────────────────────────────────────────────────────────
    def _pct(a: float, b: float) -> str:
        if a <= 0 or b <= 0:
            return "N/A"
        pct = abs((b - a) / a) * 100
        return f"{pct:.1f}%"

    sl_pct_str  = _pct(price, sl_price)
    tp1_pct_str = _pct(price, tp1_price)
    tp2_pct_str = _pct(price, tp2_price)
    tp3_pct_str = _pct(price, tp3_price)

    rr_tp1 = (atr * risk.get('tp1_atr_mult', 2.0)) / sl_dist if sl_dist > 0 else 0
    rr_tp2 = (atr * risk.get('tp2_atr_mult', 3.5)) / sl_dist if sl_dist > 0 else 0

    # ── Capital logic ─────────────────────────────────────────────────────────
    cap_cfg     = strategy.get('capital', {})
    small_thr   = cap_cfg.get('small_threshold', 22)
    small_exit  = cap_cfg.get('small_exit', 'full_tp1')
    large_exit  = cap_cfg.get('large_exit', 'partial_trail')
    trailing    = risk.get('trailing_after_tp1', False)

    # ── Supertrend trailing level ─────────────────────────────────────────────
    trailing_price = None
    if trailing and risk.get('trailing_type') == 'supertrend':
        try:
            if len(df_ext) >= 3 and 'supertrend' in df_ext.columns:
                st_val = float(df_ext['supertrend'].iloc[-3])
                if not np.isnan(st_val):
                    trailing_price = st_val
        except Exception:
            pass

    # ── Style emoji ───────────────────────────────────────────────────────────
    style = strategy.get('style', 'swing')
    style_emojis = {'scalping': '⚡', 'swing': '🔄', 'position': '🌊'}
    style_emoji = style_emojis.get(style, '📊')

    enriched.update({
        # Strategy meta
        'strategy_id':    strategy.get('id', ''),
        'strategy_name':  strategy.get('name', ''),
        'strategy_emoji': strategy.get('emoji', '📊'),
        'strategy_style': style,
        'style_emoji':    style_emoji,

        # Risk levels
        'sss_sl':         round(sl_price, 8),
        'sss_sl_pct':     sl_pct_str,
        'sss_tp1':        round(tp1_price, 8),
        'sss_tp1_pct':    tp1_pct_str,
        'sss_tp1_close':  tp1_pct,
        'sss_tp2':        round(tp2_price, 8),
        'sss_tp2_pct':    tp2_pct_str,
        'sss_tp2_close':  tp2_pct,
        'sss_tp3':        round(tp3_price, 8),
        'sss_tp3_pct':    tp3_pct_str,
        'sss_tp3_close':  tp3_pct,

        # Trailing
        'sss_trailing':       trailing,
        'sss_trailing_price': round(trailing_price, 8) if trailing_price else None,

        # Leverage
        'sss_leverage': leverage,

        # Capital logic
        'sss_small_thr':   small_thr,
        'sss_small_exit':  small_exit,
        'sss_large_exit':  large_exit,

        # R:R
        'sss_rr_tp1': round(rr_tp1, 2),
        'sss_rr_tp2': round(rr_tp2, 2),
    })

    return enriched


# ─── FORMATO PARA MENSAJES ────────────────────────────────────────────────────

def fmt_price(p: float) -> str:
    """Formatea precio de forma legible."""
    if p <= 0: return "0"
    if p >= 10000: return f"{p:,.2f}"
    if p >= 100:   return f"{p:,.3f}"
    if p >= 1:     return f"{p:,.4f}"
    return f"{p:.8f}".rstrip('0')


def build_strategy_signal_block(sig_enriched: dict) -> str:
    """
    Bloque de estrategia SSS para añadir al mensaje de señal.
    Fix #18: líneas cortas, consistentes con el estilo del bot.
    """
    name  = sig_enriched.get('strategy_name', 'Estrategia')[:22]
    emoji = sig_enriched.get('strategy_emoji', '📊')
    lev   = sig_enriched.get('sss_leverage', 1)

    sl    = sig_enriched.get('sss_sl', 0)
    slp   = sig_enriched.get('sss_sl_pct', '')
    tp1   = sig_enriched.get('sss_tp1', 0)
    tp1p  = sig_enriched.get('sss_tp1_pct', '')
    tp1c  = sig_enriched.get('sss_tp1_close', 50)
    tp2   = sig_enriched.get('sss_tp2', 0)
    tp2p  = sig_enriched.get('sss_tp2_pct', '')
    tp2c  = sig_enriched.get('sss_tp2_close', 30)
    tp3   = sig_enriched.get('sss_tp3', 0)
    tp3p  = sig_enriched.get('sss_tp3_pct', '')
    tp3c  = sig_enriched.get('sss_tp3_close', 20)
    rr1   = sig_enriched.get('sss_rr_tp1', 0)
    rr2   = sig_enriched.get('sss_rr_tp2', 0)
    small = sig_enriched.get('sss_small_thr', 22)
    trail = sig_enriched.get('sss_trailing', False)
    tprce = sig_enriched.get('sss_trailing_price')

    lines = [
        "────────────────────",
        f"{emoji} *{name}* · `{lev}x apal.`",
        "",
        f"🛡 *SL:* `${fmt_price(sl)}` _{slp}_",
        f"🎯 *TP1:* `${fmt_price(tp1)}` _{tp1p}_ → `{tp1c}%`",
        f"🎯 *TP2:* `${fmt_price(tp2)}` _{tp2p}_ → `{tp2c}%`",
        f"🎯 *TP3:* `${fmt_price(tp3)}` _{tp3p}_ → `{tp3c}%`",
        f"📐 *R:R* TP1: `1:{rr1:.1f}` · TP2: `1:{rr2:.1f}`",
    ]

    if trail:
        if tprce:
            lines.append(f"🔄 *Trail:* `${fmt_price(tprce)}` (ST)")
        else:
            lines.append("🔄 *Trailing* activo tras TP1")

    lines.append(f"💡 _Capital <${small}: salida total en TP1_")
    lines.append("────────────────────")

    return "\n".join(lines)


def format_strategy_list_item(strategy: dict, is_active: bool = False) -> str:
    """Formato compacto para listado de estrategias."""
    emoji  = strategy.get('emoji', '📊')
    name   = strategy.get('name', 'Sin nombre')
    style  = strategy.get('style', '')
    tier   = strategy.get('tier', 'base')
    tfs    = ", ".join(strategy.get('timeframes', []))
    act_m  = " ✅" if is_active else ""
    tier_m = " 🔒" if tier == 'admin' else (" ⭐" if tier == 'premium' else "")
    desc   = strategy.get('description', '')[:60]

    return (
        f"{emoji} *{name}*{act_m}{tier_m}\n"
        f"   `{style}` · `{tfs}`\n"
        f"   _{desc}…_"
    )


def format_strategy_detail(strategy: dict) -> str:
    """
    Texto detallado de una estrategia para el menú.
    Fix #18: líneas cortas, truncadas, sin desbordamiento.
    """
    emoji  = strategy.get('emoji', '📊')
    name   = strategy.get('name', '')[:24]
    ver    = strategy.get('version', '1.0')
    author = strategy.get('author', '')[:16]
    desc   = strategy.get('description', '')
    style  = strategy.get('style', '')
    tfs    = ", ".join(strategy.get('timeframes', []))
    tier   = strategy.get('tier', 'base').upper()
    meta   = strategy.get('meta', {})
    ef     = strategy.get('entry_filter', {})
    risk   = strategy.get('risk', {})
    lev    = strategy.get('leverage', {})

    tier_lbl = {
        'BASE':    '🆓 Incluida',
        'PREMIUM': '⭐ Premium',
        'ADMIN':   '🔒 Admin',
    }.get(tier, tier)

    # Descripción en máximo 2 líneas ≈ 80 chars
    desc_short = desc[:90] + ("…" if len(desc) > 90 else "")

    conditions = []
    if ef.get('supertrend_align'):    conditions.append("Supertrend alineado")
    if ef.get('ash_signal'):           conditions.append("ASH signal")
    if ef.get('volume_spike'):         conditions.append(f"Vol spike ×{ef.get('volume_spike_mult',1.5)}")
    if ef.get('adx_min', 0) > 0:       conditions.append(f"ADX >{ef.get('adx_min')}")
    if ef.get('macd_cross_required'):  conditions.append("Cruce MACD")
    if not conditions:                 conditions.append(f"Score ≥ {ef.get('min_score',4.5)}")

    slm  = risk.get('sl_atr_mult', 1.5)
    tp1m = risk.get('tp1_atr_mult', 2.0)
    tp2m = risk.get('tp2_atr_mult', 3.5)
    tp3m = risk.get('tp3_atr_mult', 5.5)

    best   = meta.get('best_markets', '')[:45]
    avoid  = meta.get('avoid_markets', '')[:45]
    trail_txt = (
        f"  🔄 Trailing: `{risk.get('trailing_type','ema')}` tras TP1\n"
        if risk.get('trailing_after_tp1') else ""
    )

    return (
        f"{emoji} *{name}* v{ver}\n"
        f"————————————————————\n\n"
        f"👤 `{author}` · {tier_lbl}\n"
        f"📐 `{style}` · TF: `{tfs}`\n\n"
        f"_{desc_short}_\n\n"
        f"*Entrada:*\n" +
        "\n".join(f"  • {c}" for c in conditions) +
        f"\n\n*Riesgo (ATR):*\n"
        f"  🛡 SL: `{slm}×`\n"
        f"  🎯 TP1: `{tp1m}×` → `{risk.get('tp1_close_pct',50)}%`\n"
        f"  🎯 TP2: `{tp2m}×` → `{risk.get('tp2_close_pct',30)}%`\n"
        f"  🎯 TP3: `{tp3m}×` → `{risk.get('tp3_close_pct',20)}%`\n"
        + trail_txt +
        f"\n*Apalancamiento:* `{lev.get('default',1)}x` / max `{lev.get('max',10)}x`\n\n"
        f"*Stats estimadas:*\n"
        f"  📊 Win rate: `{meta.get('win_rate_est','N/A')}`\n"
        f"  📐 R:R: `{meta.get('rr_ratio','N/A')}`\n"
        f"  ✅ _{best}_\n"
        f"  ⚠️ _{avoid}_"
    )


# ─── UPLOAD Y VALIDACIÓN DE ESTRATEGIAS DE USUARIO ───────────────────────────

# Campos obligatorios y sus tipos esperados
_REQUIRED_FIELDS = {
    'id':           str,
    'name':         str,
    'timeframes':   list,
    'entry_filter': dict,
    'risk':         dict,
    'leverage':     dict,
}

_VALID_TIMEFRAMES = {'1m', '5m', '15m', '1h', '4h'}

_RISK_REQUIRED = ['sl_atr_mult', 'tp1_atr_mult', 'tp2_atr_mult']
_LEV_REQUIRED  = ['default', 'max']


def validate_strategy_json(data: dict) -> tuple[bool, str]:
    """
    Valida el esquema de una estrategia JSON subida por usuario.
    Devuelve (ok: bool, error_message: str).
    """
    if not isinstance(data, dict):
        return False, "El archivo debe ser un objeto JSON."

    # Campos obligatorios
    for field, expected_type in _REQUIRED_FIELDS.items():
        if field not in data:
            return False, f"Campo obligatorio ausente: '{field}'"
        if not isinstance(data[field], expected_type):
            return False, f"'{field}' debe ser {expected_type.__name__}"

    # ID sin espacios ni caracteres problemáticos
    sid = data['id']
    if not sid or len(sid) > 60:
        return False, "'id' debe tener entre 1 y 60 caracteres"
    if any(c in sid for c in ' /\\:*?"<>|'):
        return False, f"'id' contiene caracteres no permitidos"

    # Name
    if not data['name'] or len(data['name']) > 40:
        return False, "'name' debe tener entre 1 y 40 caracteres"

    # Timeframes válidos
    tfs = data['timeframes']
    if not tfs:
        return False, "'timeframes' no puede estar vacío"
    for tf in tfs:
        if tf not in _VALID_TIMEFRAMES:
            return False, f"Temporalidad inválida: '{tf}'. Válidas: {', '.join(sorted(_VALID_TIMEFRAMES))}"

    # Risk: campos numéricos requeridos
    risk = data['risk']
    for field in _RISK_REQUIRED:
        if field not in risk:
            return False, f"'risk.{field}' es obligatorio"
        try:
            val = float(risk[field])
            if val <= 0 or val > 20:
                return False, f"'risk.{field}' debe estar entre 0.1 y 20 (actual: {val})"
        except (TypeError, ValueError):
            return False, f"'risk.{field}' debe ser un número"

    # Leverage
    lev = data['leverage']
    for field in _LEV_REQUIRED:
        if field not in lev:
            return False, f"'leverage.{field}' es obligatorio"
        try:
            val = int(lev[field])
            if val < 1 or val > 125:
                return False, f"'leverage.{field}' debe estar entre 1 y 125"
        except (TypeError, ValueError):
            return False, f"'leverage.{field}' debe ser un número entero"

    # Apalancamiento default <= max
    if int(lev.get('default', 1)) > int(lev.get('max', 1)):
        return False, "'leverage.default' no puede ser mayor que 'leverage.max'"

    # Tier: solo base o premium (usuarios no pueden crear admin)
    tier = data.get('tier', 'base')
    if tier not in ('base', 'premium'):
        data['tier'] = 'base'   # Forzar a base por seguridad

    return True, ""


def save_user_strategy_file(user_id: int, data: dict) -> str | None:
    """
    Guarda la estrategia de usuario en data/sss/strategies/.
    El nombre del archivo es user_{uid}_{id}.json.
    Devuelve la ruta guardada o None si falla.
    """
    os.makedirs(SSS_STRAT_DIR, exist_ok=True)

    # Forzar tier a base (nunca admin)
    data['tier']   = data.get('tier', 'base')
    data['author'] = data.get('author', f'user_{user_id}')[:32]

    # Sanitizar id para usar en nombre de archivo
    safe_id = "".join(c if c.isalnum() or c in '-_' else '_' for c in data['id'])
    fname   = f"user_{user_id}_{safe_id}.json"
    fpath   = os.path.join(SSS_STRAT_DIR, fname)

    try:
        tmp = fpath + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, fpath)
        # Invalidar caché para que se cargue en el próximo ciclo
        global _cache_loaded_at
        _cache_loaded_at = 0.0
        logger.info(f"[SSS Upload] Estrategia guardada: {fpath}")
        return fpath
    except Exception as e:
        logger.error(f"[SSS Upload] Error guardando estrategia de {user_id}: {e}")
        return None


# ─── BACKTESTING ENGINE ───────────────────────────────────────────────────────
# NOTA: Motor de señales inlinado aquí (sin importar sp_loop) para
# evitar la importación circular sp_loop → sss_manager → sp_loop.

def _bt_download_candles(symbol: str, interval: str, limit: int = 500):
    """Descarga velas de Binance para el backtest."""
    import requests as _req
    endpoints = [
        "https://api.binance.com/api/v3/klines",
        "https://api.binance.us/api/v3/klines",
    ]
    for url in endpoints:
        try:
            r = _req.get(url, params={"symbol": symbol, "interval": interval, "limit": limit}, timeout=10)
            if r.status_code != 200:
                continue
            data = r.json()
            if not isinstance(data, list) or len(data) < 50:
                continue
            df = pd.DataFrame(data, columns=[
                "open_time","open","high","low","close","volume",
                "close_time","q_vol","trades","tb_base","tb_quote","ignore"
            ])
            for col in ["open","high","low","close","volume"]:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            df['time'] = pd.to_datetime(df['open_time'], unit='ms')
            df.set_index('time', inplace=True)
            return df
        except Exception as e:
            logger.debug(f"[BT] Endpoint falló: {e}")
    return None


def _bt_analyze_signal(df_c: pd.DataFrame, price: float) -> dict:
    """
    Motor de señales inlinado — lógica idéntica a SPSignalEngine.analyze().
    Evita importación circular. Usa velas cerradas df_c.
    """
    buy_score = sell_score = 0.0
    reasons   = []
    rsi_val   = 50.0
    has_macd_cross = False

    try:
        # EMAs
        for span in [9, 20, 50]:
            ema = df_c['close'].ewm(span=span, adjust=False).mean().iloc[-1]
            if price > ema: buy_score  += 0.5
            else:           sell_score += 0.5
        ema50 = df_c['close'].ewm(span=50, adjust=False).mean().iloc[-1]
        if price > ema50: buy_score  += 0.5
        else:             sell_score += 0.5

        # RSI
        if pta:
            rsi_s = pta.rsi(df_c['close'], length=14)
            if rsi_s is not None:
                rsi_val = float(rsi_s.iloc[-1])
        if rsi_val < 30:   buy_score  += 1.5; reasons.append(f"RSI sobrevendido ({rsi_val:.1f})")
        elif rsi_val < 45: buy_score  += 0.75
        elif rsi_val > 70: sell_score += 1.5; reasons.append(f"RSI sobrecomprado ({rsi_val:.1f})")
        elif rsi_val > 55: sell_score += 0.75

        # MACD
        if pta:
            macd_df = pta.macd(df_c['close'], fast=12, slow=26, signal=9)
            if macd_df is not None and len(macd_df.columns) >= 2:
                hist = macd_df.iloc[:, 1]
                h = float(hist.iloc[-1]); hp = float(hist.iloc[-2]) if len(hist) > 1 else 0.0
                if h > 0 and hp <= 0:   buy_score += 2.0; reasons.append("MACD cruzó al alza"); has_macd_cross = True
                elif h < 0 and hp >= 0: sell_score += 2.0; reasons.append("MACD cruzó a la baja"); has_macd_cross = True
                elif h > 0: buy_score  += 0.75
                else:       sell_score += 0.75

        # Stochastic
        if pta:
            stoch = pta.stoch(df_c['high'], df_c['low'], df_c['close'], k=14, d=3, smooth_k=3)
            if stoch is not None and len(stoch.columns) >= 2:
                k = float(stoch.iloc[-1, 0]); d = float(stoch.iloc[-1, 1])
                kp = float(stoch.iloc[-2, 0]) if len(stoch)>1 else k
                dp = float(stoch.iloc[-2, 1]) if len(stoch)>1 else d
                if k < 20 and d < 20:   buy_score  += 1.0; reasons.append(f"Estocástico sobrevendido ({k:.1f})")
                elif k > 80 and d > 80: sell_score += 1.0; reasons.append(f"Estocástico sobrecomprado ({k:.1f})")
                if kp <= dp and k > d and k < 50:   buy_score  += 0.75
                elif kp >= dp and k < d and k > 50: sell_score += 0.75

        # CCI
        if pta:
            cci_s = pta.cci(df_c['high'], df_c['low'], df_c['close'], length=20)
            if cci_s is not None:
                cci = float(cci_s.iloc[-1]); ccp = float(cci_s.iloc[-2]) if len(cci_s)>1 else 0
                if cci < -100 and cci > ccp: buy_score  += 1.0; reasons.append(f"CCI rebote ({cci:.0f})")
                elif cci > 100 and cci < ccp: sell_score += 1.0

        # Bollinger Bands
        bb_up = df_c['close'].rolling(20).mean() + 2*df_c['close'].rolling(20).std()
        bb_lo = df_c['close'].rolling(20).mean() - 2*df_c['close'].rolling(20).std()
        if price <= float(bb_lo.iloc[-1]) * 1.005: buy_score  += 1.0; reasons.append("Banda inferior BB")
        elif price >= float(bb_up.iloc[-1]) * 0.995: sell_score += 1.0; reasons.append("Banda superior BB")

        # MFI
        if pta:
            mfi = pta.mfi(df_c['high'], df_c['low'], df_c['close'], df_c['volume'], length=14)
            if mfi is not None:
                mv = float(mfi.iloc[-1])
                if mv < 20: buy_score  += 0.75
                elif mv > 80: sell_score += 0.75

    except Exception as e:
        logger.error(f"[BT] Error en _bt_analyze_signal: {e}")

    net       = buy_score - sell_score
    score_abs = abs(net)
    direction = 'NEUTRAL'
    if net > 0.5:    direction = 'BUY'
    elif net < -0.5: direction = 'SELL'

    # ATR
    atr = price * 0.002
    try:
        if pta:
            atr_s = pta.atr(df_c['high'], df_c['low'], df_c['close'], length=14)
            if atr_s is not None and not pd.isna(atr_s.iloc[-1]):
                atr = float(atr_s.iloc[-1])
    except Exception:
        pass

    return {
        'direction':       direction,
        'score':           round(net, 2),
        'score_buy':       round(buy_score, 2),
        'score_sell':      round(sell_score, 2),
        'score_abs':       round(score_abs, 2),
        'strength':        'STRONG' if score_abs >= 6.5 else ('MODERATE' if score_abs >= 4.5 else 'WEAK'),
        'price':           round(price, 8),
        'atr':             round(atr, 8),
        'rsi':             round(rsi_val, 2),
        'reasons':         reasons[:4],
        'has_macd_cross':  has_macd_cross,
        # campos dummy para compatibilidad con enrich_signal
        'stop': 0, 'target1': 0, 'target2': 0, 'open_time': 0,
    }


def _bt_compute_indicators(df_slice: pd.DataFrame, strategy: dict) -> pd.DataFrame:
    """Calcula indicadores extendidos con manejo de errores robusto."""
    ef     = strategy.get('entry_filter', {})
    df_ext = df_slice.copy()

    if pta is None:
        df_ext['supertrend_direction'] = 0
        df_ext['ash_bulls']  = np.nan
        df_ext['ash_bears']  = np.nan
        df_ext['sss_adx']    = np.nan
        df_ext['sss_plus_di']  = np.nan
        df_ext['sss_minus_di'] = np.nan
        return df_ext

    try:
        if ef.get('supertrend_align') or ef.get('trailing_type') == 'supertrend':
            df_ext = _compute_supertrend(df_ext)
    except Exception as e:
        logger.warning(f"[BT] Supertrend falló: {e}")
        df_ext['supertrend_direction'] = 0

    try:
        if ef.get('ash_signal'):
            df_ext = _compute_ash(df_ext)
    except Exception as e:
        logger.warning(f"[BT] ASH falló: {e}")

    try:
        if ef.get('adx_min', 0) > 0 or ef.get('adx_di_confirm'):
            df_ext = _compute_adx(df_ext)
    except Exception as e:
        logger.warning(f"[BT] ADX falló: {e}")

    return df_ext


def _bt_apply_filter(strategy: dict, sig: dict, df_ext: pd.DataFrame) -> tuple[bool, str]:
    """
    Filtro de estrategia para backtest.
    Degrada graciosamente si columnas no están disponibles:
    en lugar de rechazar, omite el filtro específico.
    """
    ef        = strategy.get('entry_filter', {})
    direction = sig.get('direction', 'NEUTRAL')
    if direction == 'NEUTRAL':
        return False, "NEUTRAL"

    is_long = direction == 'BUY'

    # ── Score mínimo ──────────────────────────────────────────────────────────
    min_score = ef.get('min_score', 4.5)
    if sig.get('score_abs', 0) < min_score:
        return False, f"score<{min_score:.1f}"

    # Helper para leer columna de forma segura
    def _col(col, default=np.nan):
        try:
            if col not in df_ext.columns: return default
            v = df_ext.iloc[-2][col] if len(df_ext) >= 2 else df_ext.iloc[-1][col]
            return default if pd.isna(v) else float(v)
        except Exception:
            return default

    # ── Supertrend: solo filtra si la columna existe y no es 0 ────────────────
    if ef.get('supertrend_align'):
        st_dir = _col('supertrend_direction', 0)
        if st_dir != 0:   # 0 = no calculado → omitir filtro
            if is_long and st_dir != 1:   return False, "ST_bajista_compra"
            if not is_long and st_dir != -1: return False, "ST_alcista_venta"

    # ── ASH: solo filtra si bulls/bears disponibles ───────────────────────────
    if ef.get('ash_signal'):
        bulls = _col('ash_bulls'); bears = _col('ash_bears')
        if not (np.isnan(bulls) or np.isnan(bears)):
            if is_long and bulls <= bears:   return False, "ASH_no_compra"
            if not is_long and bears <= bulls: return False, "ASH_no_venta"

    # ── ADX ───────────────────────────────────────────────────────────────────
    adx_min = ef.get('adx_min', 0)
    if adx_min > 0:
        adx = _col('sss_adx')
        if not np.isnan(adx) and adx < adx_min:
            return False, f"ADX<{adx_min}"

    # ── DI confirmation ───────────────────────────────────────────────────────
    if ef.get('adx_di_confirm'):
        pdi = _col('sss_plus_di'); mdi = _col('sss_minus_di')
        if not (np.isnan(pdi) or np.isnan(mdi)):
            if is_long and pdi <= mdi:    return False, "DI+<=DI-"
            if not is_long and mdi <= pdi: return False, "DI-<=DI+"

    # ── Volume spike ──────────────────────────────────────────────────────────
    if ef.get('volume_spike'):
        mult = ef.get('volume_spike_mult', 1.5)
        try:
            vol_cur = float(df_ext.iloc[-2]['volume'])
            vol_avg = float(df_ext['volume'].tail(20).mean())
            if vol_avg > 0 and vol_cur < vol_avg * mult:
                return False, f"vol<{mult}x"
        except Exception:
            pass

    # ── MACD cross ────────────────────────────────────────────────────────────
    if ef.get('macd_cross_required'):
        if not sig.get('has_macd_cross', False):
            return False, "sin_MACD_cross"

    # ── RSI extremes ──────────────────────────────────────────────────────────
    rsi = sig.get('rsi', 50)
    if is_long:
        rl = ef.get('rsi_oversold_buy', 100)
        if rl < 100 and rsi > rl: return False, f"RSI{rsi:.0f}>{rl}"
    else:
        rl = ef.get('rsi_overbought_sell', 0)
        if rl > 0 and rsi < rl: return False, f"RSI{rsi:.0f}<{rl}"

    return True, "OK"


def _bt_sim_trade(
    df: pd.DataFrame,
    entry_bar: int,
    entry_price: float,
    sl: float,
    tp1: float,
    tp2: float,
    tp3: float,
    direction: str,
    max_bars: int = 80,
) -> dict:
    """Simula operación avanzando vela a vela. Detecta SL/TP1/TP2/TP3."""
    is_long     = direction == 'BUY'
    n           = len(df)
    best_tp     = 0
    sl_hit      = False
    close_bar   = None
    close_price = entry_price

    for i in range(entry_bar + 1, min(entry_bar + max_bars + 1, n)):
        hi = float(df.iloc[i]['high'])
        lo = float(df.iloc[i]['low'])

        if is_long:
            if lo <= sl:               sl_hit = True; close_bar = i; close_price = sl; break
            if hi >= tp3 and best_tp < 3: best_tp = 3; close_bar = i; close_price = tp3; break
            if hi >= tp2 and best_tp < 2: best_tp = 2; close_bar = i; close_price = tp2; break
            if hi >= tp1 and best_tp < 1: best_tp = 1
        else:
            if hi >= sl:               sl_hit = True; close_bar = i; close_price = sl; break
            if lo <= tp3 and best_tp < 3: best_tp = 3; close_bar = i; close_price = tp3; break
            if lo <= tp2 and best_tp < 2: best_tp = 2; close_bar = i; close_price = tp2; break
            if lo <= tp1 and best_tp < 1: best_tp = 1

        # Cerrar en TP1 si pasaron ≥5 velas y no hay movimiento mayor
        if best_tp == 1 and (i - entry_bar) >= 5:
            close_bar = i; close_price = tp1; break

    if sl_hit:
        result  = 'SL';  pnl_pct = abs((sl - entry_price) / entry_price) * -100
    elif best_tp == 3:
        result  = 'TP3'; pnl_pct = abs((tp3 - entry_price) / entry_price) * 100
    elif best_tp == 2:
        result  = 'TP2'; pnl_pct = abs((tp2 - entry_price) / entry_price) * 100
    elif best_tp == 1:
        result  = 'TP1'; pnl_pct = abs((tp1 - entry_price) / entry_price) * 100
    else:
        result  = 'OPEN'; pnl_pct = 0.0

    return {
        'result': result, 'pnl_pct': round(pnl_pct, 3),
        'entry_bar': entry_bar, 'close_bar': close_bar,
        'direction': direction, 'entry_price': entry_price,
        'sl': sl, 'tp1': tp1, 'tp2': tp2, 'tp3': tp3,
    }


def run_strategy_backtest(
    strategy: dict,
    symbol: str = "BTCUSDT",
    candle_limit: int = 500,
) -> dict:
    """
    Backtest de la estrategia sobre velas históricas de Binance.
    Motor de señales inlinado — sin importar sp_loop (evita circular).
    """
    tfs = strategy.get('timeframes', ['5m'])
    tf  = tfs[0] if tfs else '5m'

    df = _bt_download_candles(symbol, tf, candle_limit)
    if df is None or len(df) < 80:
        return {
            'error': f'No se pudieron descargar velas de {symbol}/{tf}.',
            'trades': [], 'stats': {}, 'symbol': symbol, 'tf': tf,
            'diagnostics': {}
        }

    n_total     = len(df)
    min_bars    = 60
    max_fwd     = 80
    trades      = []
    next_bar    = min_bars
    n_neutral   = 0
    n_rejected  = 0
    n_no_levels = 0
    rej_counts  = {}

    logger.info(f"[BT] Iniciando backtest '{strategy.get('id')}' en {symbol}/{tf}, {n_total} velas")

    for bar_idx in range(min_bars, n_total - 5):
        if bar_idx < next_bar:
            continue

        df_slice = df.iloc[:bar_idx + 1].copy()
        df_c     = df_slice.iloc[:-1]
        price    = float(df_slice.iloc[-1]['close'])

        try:
            sig = _bt_analyze_signal(df_c, price)
        except Exception as e:
            logger.warning(f"[BT] analyze error bar {bar_idx}: {e}")
            continue

        if sig['direction'] == 'NEUTRAL':
            n_neutral += 1
            continue

        try:
            df_ext = _bt_compute_indicators(df_slice, strategy)
        except Exception:
            df_ext = df_slice

        passes, reason = _bt_apply_filter(strategy, sig, df_ext)
        if not passes:
            n_rejected += 1
            rej_counts[reason] = rej_counts.get(reason, 0) + 1
            continue

        try:
            sig_e = enrich_signal(strategy, sig, df_ext)
        except Exception as e:
            logger.warning(f"[BT] enrich error: {e}")
            continue

        e_p   = sig_e.get('price', 0)
        sl_p  = sig_e.get('sss_sl', 0)
        tp1_p = sig_e.get('sss_tp1', 0)
        tp2_p = sig_e.get('sss_tp2', 0)
        tp3_p = sig_e.get('sss_tp3', 0)
        direc = sig_e.get('direction', 'NEUTRAL')

        if not all([e_p > 0, sl_p > 0, tp1_p > 0]):
            n_no_levels += 1
            continue

        trade = _bt_sim_trade(df, bar_idx, e_p, sl_p, tp1_p, tp2_p, tp3_p, direc, max_fwd)
        trade['bar_idx']  = bar_idx
        trade['time_str'] = str(df.index[bar_idx])[:16]
        trade['score']    = sig.get('score_abs', 0)
        trade['leverage'] = sig_e.get('sss_leverage', 1)
        trade['rr1']      = sig_e.get('sss_rr_tp1', 0)
        trade['rr2']      = sig_e.get('sss_rr_tp2', 0)
        trades.append(trade)

        next_bar = (trade['close_bar'] + 1) if trade.get('close_bar') else bar_idx + 5

    # ── Estadísticas ──────────────────────────────────────────────────────────
    total    = len(trades)
    tp1_hits = sum(1 for t in trades if t['result'] == 'TP1')
    tp2_hits = sum(1 for t in trades if t['result'] == 'TP2')
    tp3_hits = sum(1 for t in trades if t['result'] == 'TP3')
    sl_hits  = sum(1 for t in trades if t['result'] == 'SL')
    open_cnt = sum(1 for t in trades if t['result'] == 'OPEN')
    wins     = tp1_hits + tp2_hits + tp3_hits
    resolved = wins + sl_hits

    wr       = round(wins / resolved * 100, 1) if resolved > 0 else 0.0
    lr       = round(sl_hits / resolved * 100, 1) if resolved > 0 else 0.0
    avg_win  = round(sum(t['pnl_pct'] for t in trades if t['result'] in ('TP1','TP2','TP3')) / wins, 2) if wins > 0 else 0.0
    avg_loss = round(sum(abs(t['pnl_pct']) for t in trades if t['result'] == 'SL') / sl_hits, 2) if sl_hits > 0 else 0.0
    ev       = round((wr/100 * avg_win) - (lr/100 * avg_loss), 2) if resolved > 0 else 0.0

    top_rej = sorted(rej_counts.items(), key=lambda x: -x[1])[:4]

    logger.info(
        f"[BT] {symbol}/{tf}: {total} ops, {n_neutral} neutral, "
        f"{n_rejected} rechazadas, top_rej={dict(top_rej)}, WR={wr}%"
    )

    return {
        'trades':       trades,
        'stats': {
            'total': total, 'tp1_hits': tp1_hits, 'tp2_hits': tp2_hits,
            'tp3_hits': tp3_hits, 'sl_hits': sl_hits, 'open_count': open_cnt,
            'wins': wins, 'resolved': resolved, 'win_rate': wr, 'loss_rate': lr,
            'avg_win_pct': avg_win, 'avg_loss_pct': avg_loss, 'ev': ev,
        },
        'diagnostics': {
            'n_neutral':   n_neutral,
            'n_rejected':  n_rejected,
            'n_no_levels': n_no_levels,
            'top_reasons': top_rej,
            'pta_ok':      pta is not None,
        },
        'symbol':       symbol,
        'tf':           tf,
        'candles_used': n_total,
        'error':        None,
    }


def format_backtest_result(result: dict, strategy: dict) -> str:
    """Formatea resultado del backtest para Telegram. Incluye diagnóstico si 0 ops."""
    if result.get('error'):
        return (
            "❌ *Error en el backtest*\n"
            f"────────────────────\n_{result['error']}_\n\n"
            "_Comprueba que el par esté activo en Binance._"
        )

    s     = result.get('stats', {})
    diag  = result.get('diagnostics', {})
    total = s.get('total', 0)
    name  = strategy.get('name', '?')[:20]
    emoji = strategy.get('emoji', '📊')
    sym   = result.get('symbol', '?')
    tf    = result.get('tf', '?')
    cand  = result.get('candles_used', 0)

    tf_h = {'1m': 1/60, '5m': 5/60, '15m': 0.25, '1h': 1, '4h': 4}.get(tf, 1)
    span = cand * tf_h
    span_str = f"~{span:.0f}h" if span < 48 else f"~{span/24:.0f}d"

    header = (
        f"{emoji} *Backtest — {name}*\n"
        f"————————————————————\n\n"
        f"📡 `{sym}` · `{tf}` · {cand} velas ({span_str})\n"
    )

    # ── Sin operaciones → diagnóstico ────────────────────────────────────────
    if total == 0:
        n_neutral  = diag.get('n_neutral', 0)
        n_rejected = diag.get('n_rejected', 0)
        reasons    = diag.get('top_reasons', [])
        pta_ok     = diag.get('pta_ok', True)

        lines = [
            f"  📊 Señales encontradas: `{n_neutral + n_rejected}`",
            f"  🔵 Sin dirección (neutral): `{n_neutral}`",
            f"  🔴 Filtradas por estrategia: `{n_rejected}`",
        ]
        if not pta_ok:
            lines.append("  ⚠️ _pandas\\_ta no instalado_")
        if reasons:
            lines.append("\n  *Filtros más activos:*")
            for r, cnt in reasons:
                lines.append(f"    • `{r}` — {cnt}×")

        # Sugerencia contextual
        ef = strategy.get('entry_filter', {})
        hint = ""
        if not pta_ok and (ef.get('supertrend_align') or ef.get('ash_signal')):
            hint = "\n\n💡 _Instala `pandas_ta` para usar Supertrend/ASH._"
        elif ef.get('min_score', 0) >= 6.5:
            hint = "\n\n💡 _Score mínimo muy alto (≥6.5). Prueba bajar a 5.0 en tu estrategia._"
        elif ef.get('macd_cross_required') and ef.get('volume_spike'):
            hint = "\n\n💡 _MACD cross + spike de volumen juntos son raros. Intenta solo uno._"
        elif n_neutral > n_rejected:
            hint = "\n\n💡 _Mercado sin tendencia clara en este período. Prueba otro par._"

        return (
            header +
            "\n⚠️ *Sin operaciones encontradas*\n\n"
            "*Diagnóstico:*\n" +
            "\n".join(lines) + hint + "\n\n"
            "────────────────────\n"
            "💡 _Prueba BTC, ETH o SOL con el mismo período._"
        )

    # ── Con operaciones → estadísticas ───────────────────────────────────────
    tp1 = s['tp1_hits']; tp2 = s['tp2_hits']
    tp3 = s['tp3_hits']; sl  = s['sl_hits']
    op  = s['open_count']; wr = s['win_rate']
    ev  = s.get('ev', 0)

    tot_v  = max(tp1+tp2+tp3+sl, 1)
    b_win  = round((tp1+tp2+tp3) / tot_v * 10)
    b_sl   = round(sl / tot_v * 10)
    bar    = "🟢"*b_win + "🔴"*b_sl + "⬜"*max(0, 10-b_win-b_sl)

    wr_b  = "🌟 Alta" if wr>=65 else ("✅ Buena" if wr>=50 else ("⚠️ Moderada" if wr>=40 else "❌ Baja"))
    ev_s  = f"+{ev:.2f}%" if ev >= 0 else f"{ev:.2f}%"
    ev_e  = "📈" if ev > 0 else ("📉" if ev < 0 else "➡️")

    all_trades = result.get('trades', [])
    icons = {'TP1':'🟢','TP2':'🟩','TP3':'💚','SL':'🔴','OPEN':'🔵'}
    last_lines = []
    for t in all_trades[-5:]:
        ico = icons.get(t['result'], '⚪')
        d   = "↑" if t['direction']=='BUY' else "↓"
        pnl = f"+{t['pnl_pct']:.1f}%" if t['result']!='SL' else f"-{abs(t['pnl_pct']):.1f}%"
        ts  = t.get('time_str', '')
        last_lines.append(f"  {ico} `{ts[5:16]}` {d} `{t['result']}` {pnl}")

    n_det = diag.get('n_neutral', 0) + diag.get('n_rejected', 0) + total
    n_rej = diag.get('n_rejected', 0)

    return (
        header +
        f"\n{bar}\n\n"
        f"*{total} ops* · {s['resolved']} resueltas · {op} abiertas\n"
        f"_({n_det} señales, {n_rej} filtradas)_\n\n"
        f"  🟢 TP1: *{tp1}*  🟩 TP2: *{tp2}*  💚 TP3: *{tp3}*\n"
        f"  🔴 SL:  *{sl}*\n\n"
        f"📊 *Fiabilidad: {wr}%* — {wr_b}\n"
        f"  Ganancia media: `+{s['avg_win_pct']:.1f}%`\n"
        f"  Pérdida media:  `-{s['avg_loss_pct']:.1f}%`\n"
        f"  {ev_e} Valor esp.: `{ev_s}` / op\n\n"
        f"🕐 *Últimas operaciones:*\n"
        + "\n".join(last_lines) + "\n\n"
        "────────────────────\n"
        "💡 _Backtest histórico — no garantiza resultados futuros._"
    )


# ─── INICIALIZACIÓN ───────────────────────────────────────────────────────────

def init_sss():
    """Crea directorios necesarios si no existen."""
    os.makedirs(SSS_STRAT_DIR, exist_ok=True)
    logger.info(f"[SSS] Inicializado. Directorio: {SSS_STRAT_DIR}")