# core/sp_loop.py
# Bucle principal del módulo SmartSignals (/sp).
# Ciclo de 45 segundos. Detecta señales de compra/venta con pre-aviso 10-30s antes.
# v2 — Integración SSS: estrategias personalizadas por usuario + quick-notify.

import asyncio
import time
import numpy as np
import pandas as pd
import pandas_ta as ta
import requests
from io import BytesIO
from datetime import datetime
from telegram.constants import ParseMode
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from utils.sp_manager import (
    get_active_sp_pairs,
    get_sp_subscribers,
    can_send_signal,
    update_sp_state,
    record_signal_history,
    estimate_time_to_candle_close,
    SP_TIMEFRAMES,
    pop_quick_notify,
)
from utils.file_manager import add_log_line
from utils.sp_chart import generate_sp_chart

# SSS: estrategias de trading como skills
try:
    from utils.sss_manager import (
        get_user_strategy,
        apply_strategy_filter,
        enrich_signal,
        compute_extended_indicators,
        build_strategy_signal_block,
        init_sss,
    )
    _SSS_AVAILABLE = True
except ImportError:
    _SSS_AVAILABLE = False
    def get_user_strategy(user_id): return None
    def apply_strategy_filter(s, sig, df): return True, "OK"
    def enrich_signal(s, sig, df): return sig
    def compute_extended_indicators(df, s): return df
    def build_strategy_signal_block(sig): return ""
    def init_sss(): pass

# ─── SENDER ───────────────────────────────────────────────────────────────────
_sender_func = None

def set_sp_sender(func):
    global _sender_func
    _sender_func = func

# ─── PARÁMETROS DEL BUCLE ────────────────────────────────────────────────────
LOOP_INTERVAL_S   = 45    # Ciclo base del bucle
MIN_SCORE_SIGNAL  = 4     # Puntuación mínima para emitir señal (escala unificada 0-15)
MIN_SCORE_STRONG  = 6     # Puntuación para señal FUERTE
PRE_ALERT_SECS    = 35    # Umbral para pre-aviso (vela cierra en <N segundos)
PRE_ALERT_MIN_SCORE = 5   # Score mínimo para activar pre-aviso

# Control de pre-avisos ya enviados (evitar spam)
# {key: timestamp_unix} — se limpian entradas con >2h de antigüedad
_pre_alerts_sent: dict[str, float] = {}
_PRE_ALERT_TTL_S = 7200   # 2 horas — vida máxima de un pre-aviso en el cache


def _cleanup_pre_alerts() -> None:
    """Elimina pre-avisos con más de 2 horas de antigüedad."""
    cutoff = time.time() - _PRE_ALERT_TTL_S
    expired = [k for k, ts in _pre_alerts_sent.items() if ts < cutoff]
    for k in expired:
        del _pre_alerts_sent[k]

# ─── OBTENCIÓN DE DATOS ───────────────────────────────────────────────────────

def _get_klines(symbol: str, interval: str, limit: int = 120) -> pd.DataFrame | None:
    """Descarga velas de Binance (con fallback a Binance US)."""
    endpoints = [
        "https://api.binance.com/api/v3/klines",
        "https://api.binance.us/api/v3/klines",
    ]
    params = {"symbol": symbol, "interval": interval, "limit": limit}

    for url in endpoints:
        try:
            r = requests.get(url, params=params, timeout=5)
            if r.status_code != 200:
                continue
            data = r.json()
            if not isinstance(data, list) or len(data) < 30:
                continue

            df = pd.DataFrame(data, columns=[
                "open_time", "open", "high", "low", "close", "volume",
                "close_time", "q_vol", "trades", "tb_base", "tb_quote", "ignore"
            ])
            for col in ["open", "high", "low", "close", "volume"]:
                df[col] = pd.to_numeric(df[col], errors='coerce')

            df['time'] = pd.to_datetime(df['open_time'], unit='ms')
            df.set_index('time', inplace=True)
            return df

        except Exception:
            continue
    return None


# ─── MOTOR DE SEÑALES ─────────────────────────────────────────────────────────

class SPSignalEngine:
    """
    Motor de análisis multi-indicador para detectar señales de trading.
    Produce un score compuesto (positivo = BUY, negativo = SELL).
    """

    def analyze(self, df: pd.DataFrame) -> dict:
        """
        Analiza el dataframe y devuelve un dict con la señal.
        Usa las velas cerradas (df[:-1]) para indicadores y la última
        vela parcial sólo para confirmar precio y timing.
        """
        try:
            if len(df) < 30:
                return self._empty_result(df)

            # Velas cerradas (confiables para indicadores) — vista sin copia
            df_c = df.iloc[:-1]
            if len(df_c) < 20:
                return self._empty_result(df)

            # Solo copiar las columnas numéricas que realmente se van a mutar
            close_s  = df_c['close'].copy()
            high_s   = df_c['high'].copy()
            low_s    = df_c['low'].copy()
            volume_s = df_c['volume'].copy()

            curr  = df_c.iloc[-1]
            price = float(df.iloc[-1]['close'])  # Precio actual (vela parcial)

            buy_score  = 0.0
            sell_score = 0.0
            reasons    = []

            # GRUPO 1: EMAs (Tendencia) - 1pt cada uno, incluye 200
            ma_bullish = 0
            for span in [9, 20, 50, 200]:
                ema_val = close_s.ewm(span=span, adjust=False).mean().iloc[-1]
                if price > ema_val:
                    buy_score  += 1
                    ma_bullish += 1
                else:
                    sell_score += 1

            # ── GRUPO 2: RSI ───────────────────────────────────────────────
            rsi_series = ta.rsi(close_s, length=14)
            rsi = float(rsi_series.iloc[-1]) if rsi_series is not None else 50.0

            if rsi < 30:
                buy_score += 1
                reasons.append(f"RSI sobrevendido ({rsi:.1f})")
            elif rsi < 50:
                sell_score += 1          # RSI 30-50: presión bajista
            elif rsi < 70:
                buy_score += 1            # RSI 50-70: momentum alcista
            else:
                sell_score += 1
                reasons.append(f"RSI sobrecomprado ({rsi:.1f})")

            # ── GRUPO 3: MACD ──────────────────────────────────────────────
            macd_df = ta.macd(close_s, fast=12, slow=26, signal=9)
            if macd_df is not None and len(macd_df.columns) >= 2:
                hist_series = macd_df.iloc[:, 1]
                hist_curr = float(hist_series.iloc[-1])
                hist_prev = float(hist_series.iloc[-2]) if len(hist_series) > 1 else 0.0

                if hist_curr > 0 and hist_prev <= 0:
                    buy_score += 2.0
                    reasons.append("MACD cruzó al alza")
                elif hist_curr < 0 and hist_prev >= 0:
                    sell_score += 2.0
                    reasons.append("MACD cruzó a la baja")
                elif hist_curr > 0:
                    buy_score += 1
                else:
                    sell_score += 1

            # ── GRUPO 4: Stochastic ────────────────────────────────────────
            stoch = ta.stoch(high_s, low_s, close_s, k=14, d=3, smooth_k=3)
            if stoch is not None and len(stoch.columns) >= 2:
                k_curr = float(stoch.iloc[-1, 0])
                d_curr = float(stoch.iloc[-1, 1])
                k_prev = float(stoch.iloc[-2, 0]) if len(stoch) > 1 else k_curr
                d_prev = float(stoch.iloc[-2, 1]) if len(stoch) > 1 else d_curr

                if k_curr < 20 and d_curr < 20:
                    buy_score += 1.0
                    reasons.append(f"Estocástico sobrevendido ({k_curr:.1f})")
                elif k_curr > 80 and d_curr > 80:
                    sell_score += 1.0
                    reasons.append(f"Estocástico sobrecomprado ({k_curr:.1f})")

                # Cruce de K sobre D
                if k_prev <= d_prev and k_curr > d_curr and k_curr < 50:
                    buy_score += 1
                elif k_prev >= d_prev and k_curr < d_curr and k_curr > 50:
                    sell_score += 1

            # ── GRUPO 5: CCI ───────────────────────────────────────────────
            cci_series = ta.cci(high_s, low_s, close_s, length=20)
            if cci_series is not None:
                cci = float(cci_series.iloc[-1])
                cci_prev = float(cci_series.iloc[-2]) if len(cci_series) > 1 else 0.0

                if cci < -100 and cci > cci_prev:
                    buy_score += 1.0
                    reasons.append(f"CCI en zona de rebote ({cci:.0f})")
                elif cci > 100 and cci < cci_prev:
                    sell_score += 1.0

            # ── GRUPO 6: Bollinger Bands ───────────────────────────────────
            bb_mid = close_s.rolling(20).mean()
            bb_std = close_s.rolling(20).std()
            bb_up_val = float((bb_mid + 2 * bb_std).iloc[-1])
            bb_lo_val = float((bb_mid - 2 * bb_std).iloc[-1])

            if price <= bb_lo_val * 1.005:
                buy_score += 1.0
                reasons.append("Precio en banda inferior BB")
            elif price >= bb_up_val * 0.995:
                sell_score += 1.0
                reasons.append("Precio en banda superior BB")

            # ── GRUPO 7: Volumen (MFI) ────────────────────────────────────
            mfi_series = ta.mfi(high_s, low_s, close_s, volume_s, length=14)
            if mfi_series is not None:
                mfi = float(mfi_series.iloc[-1])
                if mfi < 20:
                    buy_score += 1
                elif mfi > 80:
                    sell_score += 1

            # GRUPO 8: Awesome Oscillator (AO)
            ao_series = ta.ao(high_s, low_s)
            if ao_series is not None:
                ao_val = float(ao_series.iloc[-1])
                if ao_val > 0:
                    buy_score += 1
                else:
                    sell_score += 1

            # GRUPO 9: ADX (fuerza de tendencia) - 2pts si tendencia fuerte
            adx_df = ta.adx(high_s, low_s, close_s, length=14)
            if adx_df is not None and len(adx_df.columns) >= 3:
                adx_val = float(adx_df.iloc[-1, 0])
                if adx_val > 25:
                    if ma_bullish >= 3:
                        buy_score += 2
                        reasons.append(f"ADX fuerte ({adx_val:.1f}) confirma alza")
                    elif ma_bullish <= 1:
                        sell_score += 2
                        reasons.append(f"ADX fuerte ({adx_val:.1f}) confirma baja")

            # CÁLCULO FINAL
            net = buy_score - sell_score
            score_abs = abs(net)

            # Umbrales unificados con _bt_analyze_signal
            direction = 'NEUTRAL'
            if net >= 2:
                direction = 'BUY'
            elif net <= -2:
                direction = 'SELL'

            # Umbrales unificados (escala 0-15 aprox)
            if score_abs >= 6:
                strength = 'STRONG'
            elif score_abs >= 4:
                strength = 'MODERATE'
            else:
                strength = 'WEAK'

            # ── ATR ────────────────────────────────────────────────────────
            atr_series = ta.atr(high_s, low_s, close_s, length=14)
            atr = float(atr_series.iloc[-1]) if atr_series is not None else price * 0.002

            # ── NIVELES ────────────────────────────────────────────────────
            if direction == 'BUY':
                stop_loss = price - atr * 1.5
                target1   = price + atr * 2.0
                target2   = price + atr * 3.5
            elif direction == 'SELL':
                stop_loss = price + atr * 1.5
                target1   = price - atr * 2.0
                target2   = price - atr * 3.5
            else:
                stop_loss = price - atr
                target1   = price + atr
                target2   = price + atr * 2

            # Tiempo hasta cierre de vela
            try:
                open_time_ms = int(df.iloc[-1]['open_time'])
            except Exception:
                open_time_ms = int(time.time() * 1000) - 30000

            return {
                'direction': direction,
                'score':     round(net, 2),
                'score_buy': round(buy_score, 2),
                'score_sell': round(sell_score, 2),
                'score_abs': round(score_abs, 2),
                'strength':  strength,
                'price':     round(price, 8),
                'stop':      round(stop_loss, 8),
                'target1':   round(target1, 8),
                'target2':   round(target2, 8),
                'atr':       round(atr, 8),
                'rsi':       round(rsi, 2),
                'reasons':   reasons[:4],          # Máximo 4 razones
                'open_time': open_time_ms,
            }

        except Exception as e:
            add_log_line(f"[SP Engine] Error en analyze(): {e}")
            return self._empty_result(df)

    def _empty_result(self, df: pd.DataFrame) -> dict:
        price = float(df.iloc[-1]['close']) if len(df) > 0 else 0
        return {
            'direction': 'NEUTRAL', 'score': 0, 'score_buy': 0,
            'score_sell': 0, 'score_abs': 0, 'strength': 'WEAK',
            'price': price, 'stop': 0, 'target1': 0, 'target2': 0,
            'atr': 0, 'rsi': 50, 'reasons': [], 'open_time': 0,
            'has_macd_cross': False,
        }


# ─── FORMATEO DE MENSAJES ─────────────────────────────────────────────────────

def _fmt_price(p: float) -> str:
    if p <= 0: return "0"
    if p >= 10000: return f"{p:,.2f}"
    if p >= 100:   return f"{p:,.3f}"
    if p >= 1:     return f"{p:,.4f}"
    return f"{p:.8f}".rstrip('0')

def _pct(a: float, b: float) -> str:
    if a <= 0 or b <= 0: return "N/A"
    pct = ((b - a) / a) * 100
    sign = '+' if pct >= 0 else ''
    return f"{sign}{pct:.2f}%"

def build_signal_message(symbol: str, tf: str, sig: dict) -> str:
    """
    Construye el mensaje de señal para enviar al usuario.
    FIX #9:  NEUTRAL ya no se muestra como SELL (rama propia).
    FIX #11: score_label definido en todas las ramas (evita NameError).
    FIX #10: el llamador trunca a 1024 chars si es caption de foto.
    """
    direction = sig['direction']
    strength  = sig['strength']

    # FIX #9 y #11: tres ramas independientes, score_label siempre definido
    if direction == 'BUY':
        dir_emoji   = "🟢"
        dir_text    = "SEÑAL DE COMPRA"
        score_label = f"Score: `{sig['score_buy']:.1f} BUY` vs `{sig['score_sell']:.1f} SELL`"
    elif direction == 'SELL':
        dir_emoji   = "🔴"
        dir_text    = "SEÑAL DE VENTA"
        score_label = f"Score: `{sig['score_sell']:.1f} SELL` vs `{sig['score_buy']:.1f} BUY`"
    else:
        # FIX #9: NEUTRAL tiene su propia representación
        dir_emoji   = "⚖️"
        dir_text    = "SIN SEÑAL CLARA"
        score_label = (
            f"Score: `{sig.get('score_buy', 0):.1f} BUY`"
            f" vs `{sig.get('score_sell', 0):.1f} SELL`"
        )

    strength_labels = {
        'STRONG':   '🔥 FUERTE',
        'MODERATE': '⚡ MODERADA',
        'WEAK':     '👀 DÉBIL',
    }
    strength_text = strength_labels.get(strength, '👀 DÉBIL')

    coin = symbol.replace('USDT', '').replace('BTC', 'BTC')
    price  = sig['price']
    t1     = sig['target1']
    t2     = sig['target2']
    sl     = sig['stop']
    rsi    = sig['rsi']
    ttc    = sig.get('time_to_close', 0)

    reasons_text = ""
    for r in sig['reasons']:
        reasons_text += f"  • _{r}_\n"

    ttc_text = f"⏱ *Vela cierra en:* `~{ttc}s`\n" if ttc > 0 else ""

    msg = (
        f"📡 *SmartSignals — {coin}* (`{tf}`)\n"
        f"—————————————————\n\n"
        f"{dir_emoji} *{dir_text}*\n"
        f"⚡ *Fuerza:* {strength_text}\n"
        f"📊 {score_label}\n\n"
        f"💰 *Precio actual:* `${_fmt_price(price)}`\n"
        f"🎯 *Zona de entrada:* `${_fmt_price(sl)}` — `${_fmt_price(t1)}`\n"
        f"🛡 *Stop sugerido:* `${_fmt_price(sl)}` ({_pct(price, sl)})\n"
        f"📈 *Objetivo 1:* `${_fmt_price(t1)}` ({_pct(price, t1)})\n"
        f"📈 *Objetivo 2:* `${_fmt_price(t2)}` ({_pct(price, t2)})\n\n"
    )

    if reasons_text:
        msg += f"📋 *Indicadores activos:*\n{reasons_text}\n"

    if rsi > 0:
        rsi_note = ""
        if rsi < 30:
            rsi_note = "zona de sobreventa"
        elif rsi > 70:
            rsi_note = "zona de sobrecompra"
        if rsi_note:
            msg += f"  • _RSI {rsi:.1f} — {rsi_note}_\n\n"

    msg += ttc_text
    msg += (
        f"—————————————————\n"
        f"💡 _Señal informativa. Evalúa siempre el contexto._"
    )
    return msg

def build_pre_alert_message(symbol: str, tf: str, sig: dict) -> str:
    """Mensaje corto de pre-aviso (sin gráfico)."""
    direction = sig['direction']
    is_buy    = direction == 'BUY'
    coin      = symbol.replace('USDT', '')
    ttc       = sig.get('time_to_close', 0)

    dir_emoji = "🟢" if is_buy else "🔴"
    dir_text  = "COMPRA" if is_buy else "VENTA"

    return (
        f"⚡ *BitBread · Pre-señal {coin}*\n"
        f"—————————————————\n\n"
        f"Una señal de {dir_emoji} *{dir_text}* se está formando en `{tf}`.\n"
        f"Cierre de vela en aprox. *{ttc}s*.\n\n"
        f"Score: `{abs(sig['score']):.1f}/8` — "
        f"Precio: `${_fmt_price(sig['price'])}`\n\n"
        f"_Espera confirmación al cierre de vela._"
    )

def _get_signal_keyboard(symbol: str, tf: str) -> InlineKeyboardMarkup:
    """Teclado inline adjunto al mensaje de señal."""
    coin = symbol.replace('USDT', '')
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔄 Actualizar", callback_data=f"sp_refresh|{symbol}|{tf}"),
            InlineKeyboardButton("🔕 Desactivar", callback_data=f"sp_toggle|{symbol}|{tf}"),
        ],
        [
            InlineKeyboardButton("📊 Ver Gráfico TA", callback_data=f"ta_switch|BINANCE|{coin}|USDT|{tf}"),
        ],
    ])


# ─── BUCLE PRINCIPAL ──────────────────────────────────────────────────────────

async def sp_monitor_loop(bot):
    """
    Loop principal de SmartSignals.
    Ciclo: 45 segundos.
    """
    add_log_line("📡 Iniciando SmartSignals Monitor (ciclo 45s)...")
    init_sss()
    engine = SPSignalEngine()

    while True:
        try:
            pairs = get_active_sp_pairs()

            # Limpieza periódica de pre-avisos expirados
            _cleanup_pre_alerts()

            if not pairs:
                await asyncio.sleep(30)
                continue

            for symbol, tf in pairs:
                try:
                    await _process_pair(bot, engine, symbol, tf)
                except Exception as e:
                    add_log_line(f"[SP Loop] Error procesando {symbol}/{tf}: {e}")

                # Pausa pequeña entre pares para no saturar la API
                await asyncio.sleep(1.2)

        except Exception as e:
            add_log_line(f"[SP Loop] Error general: {e}")

        await asyncio.sleep(LOOP_INTERVAL_S)


async def _process_pair(bot, engine: SPSignalEngine, symbol: str, tf: str) -> None:
    """
    Procesa un par/TF: descarga datos, analiza y envía señal si corresponde.
    v2: aplica estrategia SSS por usuario y soporta quick-notify.
    """

    # 1. Descargar velas
    loop = asyncio.get_running_loop()
    df = await loop.run_in_executor(None, _get_klines, symbol, tf, 120)
    if df is None or len(df) < 30:
        return

    # 2. Analizar señal base
    sig = engine.analyze(df)

    # 3. Manejar quick-notify (usuarios que acaban de suscribirse)
    quick_users = pop_quick_notify(symbol, tf)
    if quick_users:
        await _send_quick_notify(bot, quick_users, symbol, tf, sig, df, loop)

    # 4. Señal demasiado débil — solo pre-aviso
    if sig['direction'] == 'NEUTRAL' or sig['score_abs'] < MIN_SCORE_SIGNAL:
        await _check_pre_alert(bot, symbol, tf, sig, df)
        return

    # 5. Verificar cooldown
    if not can_send_signal(symbol, tf):
        await _check_pre_alert(bot, symbol, tf, sig, df)
        return

    # 6. Calcular tiempo hasta cierre de vela
    try:
        open_time_ms = int(df.iloc[-1]['open_time'])
    except Exception:
        open_time_ms = int(time.time() * 1000)

    sig['time_to_close'] = estimate_time_to_candle_close(open_time_ms, tf)

    # 7. Obtener suscriptores
    subscribers = get_sp_subscribers(symbol, tf)
    if not subscribers:
        return

    # 8. Generar gráfico base
    chart_buf = await loop.run_in_executor(None, generate_sp_chart, df, symbol, tf, sig, 60)

    # 9. Agrupar suscriptores por estrategia (personalización de mensaje)
    # Cada grupo recibe un mensaje ligeramente diferente
    groups: dict[str, list] = {}   # strategy_id_or_none -> [uid, ...]
    for uid in subscribers:
        strat = get_user_strategy(int(uid)) if _SSS_AVAILABLE else None
        gkey  = strat['id'] if strat else '__base__'
        groups.setdefault(gkey, []).append(uid)

    # 10. Enviar a cada grupo
    sent_count = 0
    for gkey, uids in groups.items():
        if gkey == '__base__':
            # Mensaje estándar sin estrategia
            msg_text = build_signal_message(symbol, tf, sig)
            keyboard = _get_signal_keyboard(symbol, tf)
        else:
            # Mensaje enriquecido con estrategia SSS
            strat = get_user_strategy(int(uids[0]))
            if strat is None:
                msg_text = build_signal_message(symbol, tf, sig)
                keyboard = _get_signal_keyboard(symbol, tf)
            else:
                df_ext = await loop.run_in_executor(
                    None, compute_extended_indicators, df, strat
                )
                passes, reason = apply_strategy_filter(strat, sig, df_ext)
                if not passes:
                    # Estrategia filtra la señal — no enviar a este grupo
                    continue
                sig_enriched = enrich_signal(strat, sig, df_ext)
                base_msg     = build_signal_message(symbol, tf, sig)
                strat_block  = build_strategy_signal_block(sig_enriched)
                msg_text     = base_msg + "\n" + strat_block
                keyboard     = _get_signal_keyboard(symbol, tf)

        # FIX caption: Telegram limita captions a 1024 chars
        if chart_buf and len(msg_text) > 1024:
            msg_text = msg_text[:1020] + "…`"

        for uid in uids:
            try:
                if chart_buf:
                    chart_buf.seek(0)
                    await bot.send_photo(
                        chat_id=int(uid),
                        photo=chart_buf,
                        caption=msg_text,
                        parse_mode=ParseMode.MARKDOWN,
                        reply_markup=keyboard,
                    )
                else:
                    await bot.send_message(
                        chat_id=int(uid),
                        text=msg_text,
                        parse_mode=ParseMode.MARKDOWN,
                        reply_markup=keyboard,
                    )
                sent_count += 1
                await asyncio.sleep(0.05)
            except Exception as e:
                add_log_line(f"[SP Loop] Error enviando a {uid}: {e}")

    if sent_count > 0:
        # 11. Registrar señal
        update_sp_state(symbol, tf, sig)
        record_signal_history(symbol, tf, sig)
        coin = symbol.replace('USDT', '')
        add_log_line(f"📡 SP señal {sig['direction']} {coin}/{tf} — "
                     f"score {sig['score']:.1f} — enviada a {sent_count} usuarios")


async def _send_quick_notify(
    bot, users: list, symbol: str, tf: str,
    sig: dict, df: pd.DataFrame, loop
) -> None:
    """
    Envía señal inmediata a usuarios recién suscritos (quick-notify).
    No respeta cooldown ni score mínimo — solo informa del estado actual.
    """
    if not users:
        return

    try:
        open_time_ms = int(df.iloc[-1]['open_time'])
    except Exception:
        open_time_ms = int(time.time() * 1000)

    sig_copy = dict(sig)
    sig_copy['time_to_close'] = estimate_time_to_candle_close(open_time_ms, tf)

    chart_buf = await loop.run_in_executor(None, generate_sp_chart, df, symbol, tf, sig_copy, 60)
    coin      = symbol.replace('USDT', '')

    intro = (
        f"📡 *SmartSignals activo!* \\— `{coin}` (`{tf}`)\n"
        f"_Esta es la señal actual en el momento de tu suscripción:_\n\n"
    )
    msg_text = intro + build_signal_message(symbol, tf, sig_copy)
    keyboard = _get_signal_keyboard(symbol, tf)

    if chart_buf and len(msg_text) > 1024:
        msg_text = msg_text[:1020] + "…`"

    for uid in users:
        try:
            if chart_buf:
                chart_buf.seek(0)
                await bot.send_photo(
                    chat_id=int(uid),
                    photo=chart_buf,
                    caption=msg_text,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=keyboard,
                )
            else:
                await bot.send_message(
                    chat_id=int(uid),
                    text=msg_text,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=keyboard,
                )
            await asyncio.sleep(0.05)
        except Exception as e:
            add_log_line(f"[SP Quick] Error enviando a {uid}: {e}")


async def _check_pre_alert(bot, symbol: str, tf: str, sig: dict, df: pd.DataFrame) -> None:
    """
    Verifica si procede enviar un pre-aviso (señal en formación, vela a punto de cerrar).
    """
    if sig['score_abs'] < PRE_ALERT_MIN_SCORE:
        return
    if sig['direction'] == 'NEUTRAL':
        return

    try:
        open_time_ms = int(df.iloc[-1]['open_time'])
    except Exception:
        return

    time_to_close = estimate_time_to_candle_close(open_time_ms, tf)
    if time_to_close > PRE_ALERT_SECS:
        return

    # Evitar pre-avisos duplicados para la misma vela
    pre_key = f"{symbol}_{tf}_{open_time_ms}"
    if pre_key in _pre_alerts_sent:
        return

    subscribers = get_sp_subscribers(symbol, tf)
    if not subscribers:
        return

    sig['time_to_close'] = time_to_close
    msg = build_pre_alert_message(symbol, tf, sig)

    sent = 0
    for uid in subscribers:
        try:
            await bot.send_message(
                chat_id=int(uid),
                text=msg,
                parse_mode=ParseMode.MARKDOWN,
            )
            sent += 1
            await asyncio.sleep(0.05)
        except Exception:
            pass

    if sent > 0:
        _pre_alerts_sent[pre_key] = time.time()
        # Limpiar entradas expiradas (>2h) periódicamente
        if len(_pre_alerts_sent) > 100:
            _cleanup_pre_alerts()

        coin = symbol.replace('USDT', '')
        add_log_line(f"⚡ SP pre-aviso {sig['direction']} {coin}/{tf} — "
                     f"{time_to_close}s para cierre — {sent} usuarios")