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
    Construye el bloque de texto de estrategia para añadir al mensaje de señal.
    Se añade DEBAJO del bloque estándar del motor SP.
    """
    name   = sig_enriched.get('strategy_name', 'Estrategia')
    emoji  = sig_enriched.get('strategy_emoji', '📊')
    style  = sig_enriched.get('strategy_style', '')
    lev    = sig_enriched.get('sss_leverage', 1)

    sl     = sig_enriched.get('sss_sl', 0)
    sl_pct = sig_enriched.get('sss_sl_pct', '')
    tp1    = sig_enriched.get('sss_tp1', 0)
    tp1p   = sig_enriched.get('sss_tp1_pct', '')
    tp1c   = sig_enriched.get('sss_tp1_close', 50)
    tp2    = sig_enriched.get('sss_tp2', 0)
    tp2p   = sig_enriched.get('sss_tp2_pct', '')
    tp2c   = sig_enriched.get('sss_tp2_close', 30)
    tp3    = sig_enriched.get('sss_tp3', 0)
    tp3p   = sig_enriched.get('sss_tp3_pct', '')
    tp3c   = sig_enriched.get('sss_tp3_close', 20)

    rr1    = sig_enriched.get('sss_rr_tp1', 0)
    rr2    = sig_enriched.get('sss_rr_tp2', 0)
    small  = sig_enriched.get('sss_small_thr', 22)
    trail  = sig_enriched.get('sss_trailing', False)
    tprice = sig_enriched.get('sss_trailing_price')

    lines = [
        f"",
        f"━━━━━━━━━━━━━━━━━━━━",
        f"{emoji} *{name}* · `{style}`",
        f"⚖️ *Apalancamiento sugerido:* `{lev}x`",
        f"",
        f"🛡 *SL:* `${fmt_price(sl)}` (-{sl_pct})",
        f"🎯 *TP1:* `${fmt_price(tp1)}` (+{tp1p}) — cierra `{tp1c}%`",
        f"🎯 *TP2:* `${fmt_price(tp2)}` (+{tp2p}) — cierra `{tp2c}%`",
        f"🎯 *TP3:* `${fmt_price(tp3)}` (+{tp3p}) — cierra `{tp3c}%`",
        f"",
        f"📐 *R:R* → TP1: `1:{rr1:.1f}` · TP2: `1:{rr2:.1f}`",
    ]

    if trail:
        if tprice:
            lines.append(f"🔄 *Trailing stop:* `${fmt_price(tprice)}` (Supertrend -3)")
        else:
            lines.append(f"🔄 *Trailing stop:* activo tras TP1")

    lines.append(f"💡 *Capital <${small}:* salida total en TP1")
    lines.append(f"━━━━━━━━━━━━━━━━━━━━")

    return "\n".join(lines)


def format_strategy_list_item(strategy: dict, is_active: bool = False) -> str:
    """Formato compacto para listado de estrategias."""
    emoji    = strategy.get('emoji', '📊')
    name     = strategy.get('name', 'Sin nombre')
    style    = strategy.get('style', '')
    tier     = strategy.get('tier', 'base')
    tfs      = ", ".join(strategy.get('timeframes', []))
    active_m = " ✅" if is_active else ""
    tier_m   = " 🔒" if tier == 'admin' else (" ⭐" if tier == 'premium' else "")

    return (
        f"{emoji} *{name}*{active_m}{tier_m}\n"
        f"   `{style}` · TF: `{tfs}`\n"
        f"   _{strategy.get('description', '')[:80]}..._"
    )


def format_strategy_detail(strategy: dict) -> str:
    """Texto detallado de una estrategia para el menú."""
    emoji   = strategy.get('emoji', '📊')
    name    = strategy.get('name', '')
    ver     = strategy.get('version', '1.0')
    author  = strategy.get('author', '')
    desc    = strategy.get('description', '')
    style   = strategy.get('style', '')
    tfs     = ", ".join(strategy.get('timeframes', []))
    tier    = strategy.get('tier', 'base').upper()
    meta    = strategy.get('meta', {})

    ef      = strategy.get('entry_filter', {})
    risk    = strategy.get('risk', {})
    lev_cfg = strategy.get('leverage', {})

    tier_label = {'BASE': '🆓 Incluida', 'PREMIUM': '⭐ Premium', 'ADMIN': '🔒 Admin'}.get(tier, tier)

    conditions = []
    if ef.get('supertrend_align'): conditions.append("Supertrend alineado")
    if ef.get('ash_signal'):        conditions.append("ASH signal")
    if ef.get('volume_spike'):      conditions.append(f"Spike vol ×{ef.get('volume_spike_mult',1.5)}")
    if ef.get('adx_min',0) > 0:     conditions.append(f"ADX >{ef.get('adx_min')}")
    if ef.get('macd_cross_required'): conditions.append("Cruce MACD")
    if not conditions:              conditions.append("Score ≥ " + str(ef.get('min_score',4.5)))

    tp1m = risk.get('tp1_atr_mult', 2.0)
    tp2m = risk.get('tp2_atr_mult', 3.5)
    tp3m = risk.get('tp3_atr_mult', 5.5)
    slm  = risk.get('sl_atr_mult', 1.5)

    return (
        f"{emoji} *{name}* v{ver}\n"
        f"—————————————————————\n\n"
        f"👤 Autor: `{author}` · Acceso: {tier_label}\n"
        f"📐 Estilo: `{style}` · TF recomendados: `{tfs}`\n\n"
        f"📝 _{desc}_\n\n"
        f"*Condiciones de entrada:*\n" +
        "\n".join(f"  • {c}" for c in conditions) +
        f"\n\n*Gestión de riesgo (ATR):*\n"
        f"  🛡 Stop Loss: `{slm}× ATR`\n"
        f"  🎯 TP1: `{tp1m}× ATR` → cierra `{risk.get('tp1_close_pct',50)}%`\n"
        f"  🎯 TP2: `{tp2m}× ATR` → cierra `{risk.get('tp2_close_pct',30)}%`\n"
        f"  🎯 TP3: `{tp3m}× ATR` → cierra `{risk.get('tp3_close_pct',20)}%`\n"
        + (f"  🔄 Trailing: `{risk.get('trailing_type','ema')}` tras TP1\n" if risk.get('trailing_after_tp1') else "") +
        f"\n*Apalancamiento:* `{lev_cfg.get('default',1)}x` — max `{lev_cfg.get('max',10)}x`\n\n"
        f"*Estadísticas estimadas:*\n"
        f"  📊 Win rate: `{meta.get('win_rate_est','N/A')}`\n"
        f"  📐 R:R: `{meta.get('rr_ratio','N/A')}`\n"
        f"  ✅ Ideal para: _{meta.get('best_markets','')}_\n"
        f"  ⚠️ Evitar: _{meta.get('avoid_markets','')}_"
    )


# ─── INICIALIZACIÓN ───────────────────────────────────────────────────────────

def init_sss():
    """Crea directorios necesarios si no existen."""
    os.makedirs(SSS_STRAT_DIR, exist_ok=True)
    logger.info(f"[SSS] Inicializado. Directorio: {SSS_STRAT_DIR}")
