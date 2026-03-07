# handlers/trading.py

import asyncio
import requests
import json
import pytz
import pandas as pd
import pandas_ta as ta
from io import BytesIO
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from tradingview_ta import TA_Handler, Interval, Exchange
from datetime import timedelta, datetime
from core.ai_logic import get_groq_crypto_analysis
from core.config import ADMIN_CHAT_IDS
from core.api_client import obtener_datos_moneda
from utils.file_manager import (
    add_log_line, check_feature_access, registrar_uso_comando
)
from utils.ads_manager import get_random_ad_text
from utils.chart_generator import generate_ohlcv_chart
from core.i18n import _
from core.btc_advanced_analysis import BTCAdvancedAnalyzer


# ─── CONSTANTES ──────────────────────────────────────────────────────────────

_TF_BINANCE = {
    "1m": "1m",  "3m": "3m",  "5m": "5m",  "15m": "15m", "30m": "30m",
    "1h": "1h",  "2h": "2h",  "4h": "4h",  "6h": "6h",  "12h": "12h",
    "1d": "1d",  "1w": "1w",  "1M": "1M",
}

_TF_TV_URL = {
    "1m": "1",   "3m": "3",   "5m": "5",   "15m": "15",  "30m": "30",
    "1h": "60",  "2h": "120", "4h": "240", "6h": "360",  "12h": "720",
    "1d": "D",   "1w": "W",   "1M": "M",
}

_QUICK_TFS = ["4h", "12h", "1d", "1w"]

_CANDLES_FOR_TF = {
    "1m": 120, "3m": 100, "5m": 100, "15m": 90, "30m": 80,
    "1h": 80,  "2h": 70,  "4h": 70,  "6h": 60,  "12h": 60,
    "1d": 60,  "1w": 52,  "1M": 24,
}


# ─── HELPERS DE DATOS ────────────────────────────────────────────────────────

# Mapeo de intervalos Binance → KuCoin (KuCoin usa formato diferente)
_TF_KUCOIN = {
    "1m": "1min", "3m": "3min", "5m": "5min", "15m": "15min", "30m": "30min",
    "1h": "1hour", "2h": "2hour", "4h": "4hour", "6h": "6hour",
    "1d": "1day", "1w": "1week",
}

def _df_from_rows(rows: list) -> pd.DataFrame:
    """Convierte lista OHLCV normalizada a DataFrame con índice datetime."""
    df = pd.DataFrame(rows, columns=["time", "open", "high", "low", "close", "volume"])
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    df['time'] = pd.to_datetime(df['time'], unit='ms')
    df.set_index('time', inplace=True)
    return df


def _get_klines_binance(symbol: str, interval: str, limit: int) -> pd.DataFrame | None:
    """Intenta obtener velas de Binance Global y Binance US."""
    for url in ["https://api.binance.com/api/v3/klines", "https://api.binance.us/api/v3/klines"]:
        try:
            resp = requests.get(url, params={"symbol": symbol, "interval": interval, "limit": limit}, timeout=5)
            if resp.status_code != 200:
                continue
            data = resp.json()
            if not data or not isinstance(data, list):
                continue
            df = pd.DataFrame(data, columns=[
                "open_time", "open", "high", "low", "close", "volume",
                "close_time", "quote_vol", "trades", "taker_base", "taker_quote", "ignore"
            ])
            for col in ["open", "high", "low", "close", "volume"]:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            df['time'] = pd.to_datetime(df['open_time'], unit='ms')
            df.set_index('time', inplace=True)
            return df
        except Exception:
            continue
    return None


def _get_klines_kucoin(symbol: str, interval: str, limit: int) -> pd.DataFrame | None:
    """Fallback a KuCoin. Formato de símbolo: BTC-USDT."""
    kucoin_tf = _TF_KUCOIN.get(interval)
    if not kucoin_tf:
        return None

    # KuCoin usa guión: BTCUSDT → BTC-USDT
    # Detectar quote a partir de sufijos comunes
    known_quotes = ["USDT", "USDC", "BTC", "ETH", "BNB", "BUSD"]
    base, quote = symbol, "USDT"
    for q in known_quotes:
        if symbol.endswith(q) and len(symbol) > len(q):
            base = symbol[:-len(q)]
            quote = q
            break
    kucoin_symbol = f"{base}-{quote}"

    try:
        url = "https://api.kucoin.com/api/v1/market/candles"
        resp = requests.get(url, params={"symbol": kucoin_symbol, "type": kucoin_tf}, timeout=6)
        if resp.status_code != 200:
            return None
        data = resp.json().get("data", [])
        if not data:
            return None
        # KuCoin devuelve: [time_sec, open, close, high, low, volume, turnover] — orden diferente
        # y en orden DESCENDENTE, hay que invertir
        rows = []
        for c in reversed(data[:limit]):
            rows.append({
                "time": int(c[0]) * 1000,  # seg → ms
                "open": float(c[1]),
                "high": float(c[3]),
                "low":  float(c[4]),
                "close": float(c[2]),
                "volume": float(c[5]),
            })
        df = pd.DataFrame(rows)
        df['time'] = pd.to_datetime(df['time'], unit='ms')
        df.set_index('time', inplace=True)
        return df
    except Exception:
        return None


def _get_klines_bybit(symbol: str, interval: str, limit: int) -> pd.DataFrame | None:
    """Segundo fallback: Bybit (también soporta pares spot)."""
    # Bybit usa intervalos en minutos como string: 1m→1, 1h→60, 1d→D
    bybit_tf_map = {
        "1m": "1", "3m": "3", "5m": "5", "15m": "15", "30m": "30",
        "1h": "60", "2h": "120", "4h": "240", "6h": "360",
        "1d": "D", "1w": "W",
    }
    bybit_tf = bybit_tf_map.get(interval)
    if not bybit_tf:
        return None
    try:
        url = "https://api.bybit.com/v5/market/kline"
        resp = requests.get(url, params={
            "category": "spot", "symbol": symbol,
            "interval": bybit_tf, "limit": str(limit)
        }, timeout=6)
        if resp.status_code != 200:
            return None
        items = resp.json().get("result", {}).get("list", [])
        if not items:
            return None
        rows = []
        for c in reversed(items):
            rows.append({
                "time": int(c[0]),
                "open": float(c[1]),
                "high": float(c[2]),
                "low":  float(c[3]),
                "close": float(c[4]),
                "volume": float(c[5]),
            })
        df = pd.DataFrame(rows)
        df['time'] = pd.to_datetime(df['time'], unit='ms')
        df.set_index('time', inplace=True)
        return df
    except Exception:
        return None


def _get_binance_klines_for_chart(symbol: str, interval: str, limit: int = 120) -> tuple[pd.DataFrame | None, str]:
    """
    Obtiene velas OHLCV con fallback multi-exchange.
    Intenta en orden: Binance → KuCoin → Bybit.
    Devuelve (DataFrame | None, nombre_exchange).
    """
    df = _get_klines_binance(symbol, interval, limit)
    if df is not None and not df.empty:
        return df, "Binance"

    df = _get_klines_kucoin(symbol, interval, limit)
    if df is not None and not df.empty:
        return df, "KuCoin"

    df = _get_klines_bybit(symbol, interval, limit)
    if df is not None and not df.empty:
        return df, "Bybit"

    return None, ""


def _get_tv_signal(symbol: str, interval_str: str) -> dict:
    """Obtiene señal rápida de TradingView (BUY/SELL/NEUTRAL + pivotes)."""
    from handlers.ta import get_tradingview_analysis_enhanced
    try:
        data = get_tradingview_analysis_enhanced(symbol, interval_str)
        return data or {}
    except Exception:
        return {}


def _fmt_price(val: float) -> str:
    if val >= 1000:
        return f"{val:,.2f}"
    if val >= 1:
        return f"{val:.4f}"
    return f"{val:.6f}".rstrip('0')


# ─── CALLBACK DE TEMPORALIDAD ─────────────────────────────────────────────────

async def graf_timeframe_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Callback para los botones de cambio de temporalidad del /graf.
    Formato: graf_tf|BASE|QUOTE|TIMEFRAME
    """
    query = update.callback_query
    await query.answer("⏳ Cargando...")
    try:
        _, base, quote, tf = query.data.split("|")
        context.args = [base, quote, tf]
        await _do_graf(update, context, base=base, quote=quote, timeframe=tf, is_callback=True)
    except Exception as e:
        print(f"Error en graf_timeframe_callback: {e}")
        await query.answer("❌ Error al cambiar temporalidad", show_alert=True)


# ─── COMANDO PRINCIPAL ────────────────────────────────────────────────────────

async def graf_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /graf <MONEDA> [PAR] <TEMPORALIDAD>

    Genera un gráfico OHLCV profesional con velas japonesas, EMAs,
    RSI, volumen y niveles S/R. Sin dependencias externas de captura.
    """
    user_id = update.effective_user.id

    if not context.args or len(context.args) not in [2, 3]:
        await update.message.reply_text(
            _(
                "⚠️ *Formato incorrecto*\n\n"
                "Uso: `/graf <MONEDA> [PAR] <TEMPORALIDAD>`\n\n"
                "Ejemplos:\n"
                "`/graf BTC 4h`\n"
                "`/graf BTC USDT 1h`\n"
                "`/graf ETH USDT 1d`\n\n"
                "Temporalidades: `1m 5m 15m 30m 1h 2h 4h 1d 1w`",
                user_id
            ),
            parse_mode=ParseMode.MARKDOWN
        )
        return

    if len(context.args) == 2:
        base, timeframe = context.args[0].upper(), context.args[1].lower()
        quote = "USDT"
    else:
        base, quote, timeframe = (
            context.args[0].upper(),
            context.args[1].upper(),
            context.args[2].lower(),
        )

    if timeframe not in _TF_BINANCE:
        await update.message.reply_text(
            _("⚠️ *Temporalidad no válida*\n\nUsa: `1m 5m 15m 30m 1h 2h 4h 1d 1w 1M`", user_id),
            parse_mode=ParseMode.MARKDOWN
        )
        return

    await _do_graf(update, context, base=base, quote=quote, timeframe=timeframe, is_callback=False)


async def _do_graf(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    base: str,
    quote: str,
    timeframe: str,
    is_callback: bool = False,
):
    """Lógica central del comando /graf. Reutilizable desde callbacks."""
    user_id = update.effective_user.id
    symbol  = f"{base}{quote}"

    # Mensaje de espera
    msg_wait = None
    if not is_callback:
        msg_wait = await update.message.reply_text(
            _(f"📊 _Generando gráfico de *{symbol}* ({timeframe})..._", user_id),
            parse_mode=ParseMode.MARKDOWN
        )

    loop = asyncio.get_running_loop()
    binance_interval = _TF_BINANCE[timeframe]
    candles_needed   = _CANDLES_FOR_TF.get(timeframe, 80) + 210

    # Obtener velas — con fallback multi-exchange
    df, exchange_name = await loop.run_in_executor(
        None, _get_binance_klines_for_chart, symbol, binance_interval, candles_needed
    )

    if df is None or df.empty:
        err_msg = _(
            f"❌ No se encontraron datos para *{symbol}*\n"
            f"No está disponible en Binance, KuCoin ni Bybit.\n\n"
            f"Verifica que el par sea correcto (ej: `SOLUSDT`, `ETHBTC`).",
            user_id
        )
        if msg_wait:
            await msg_wait.edit_text(err_msg, parse_mode=ParseMode.MARKDOWN)
        elif update.callback_query:
            await update.callback_query.answer("❌ Par no encontrado en ningún exchange", show_alert=True)
        return

    # Obtener señal TV (en paralelo no bloqueante)
    tv_data = await loop.run_in_executor(None, _get_tv_signal, symbol, timeframe)

    # Interpretar señal
    rec = tv_data.get('RECOMMENDATION', 'NEUTRAL') if tv_data else 'NEUTRAL'
    if   'STRONG_BUY'  in rec: signal, sig_emoji = 'COMPRA FUERTE',  '🚀'
    elif 'BUY'         in rec: signal, sig_emoji = 'COMPRA',         '🐂'
    elif 'STRONG_SELL' in rec: signal, sig_emoji = 'VENTA FUERTE',   '🐻'
    elif 'SELL'        in rec: signal, sig_emoji = 'VENTA',          '📉'
    else:                       signal, sig_emoji = 'NEUTRAL',        '⚖️'

    pivot = tv_data.get('Pivot', 0) if tv_data else 0
    r1    = tv_data.get('R1',    0) if tv_data else 0
    s1    = tv_data.get('S1',    0) if tv_data else 0

    # Calcular niveles locales si TV no los provee
    if pivot == 0 and not df.empty:
        last10 = df.tail(10)
        h, l, c = last10['high'].max(), last10['low'].min(), df['close'].iloc[-1]
        pivot  = (h + l + c) / 3
        rng    = h - l
        r1     = pivot + rng * 0.382
        s1     = pivot - rng * 0.382

    # Generar gráfico
    candles_display = _CANDLES_FOR_TF.get(timeframe, 80)
    show_bb = timeframe in ('1h', '4h', '1d', '1w')

    chart_bytes = await loop.run_in_executor(
        None,
        generate_ohlcv_chart,
        df, symbol, timeframe,
        True,        # show_ema
        show_bb,     # show_bb
        True,        # show_rsi
        candles_display,
        signal, sig_emoji,
        pivot, r1, s1,
    )

    if chart_bytes is None:
        err_msg = _("❌ Error interno al generar el gráfico. Intenta de nuevo.", user_id)
        if msg_wait:
            await msg_wait.edit_text(err_msg, parse_mode=ParseMode.MARKDOWN)
        elif update.callback_query:
            await update.callback_query.answer("❌ Error al generar gráfico", show_alert=True)
        return

    # Construir caption
    last_price = df['close'].iloc[-1]
    prev_price = df['close'].iloc[-2] if len(df) > 1 else last_price
    pct_change = ((last_price - prev_price) / prev_price * 100) if prev_price else 0
    pct_icon   = '📈' if pct_change >= 0 else '📉'
    pct_sign   = '+' if pct_change >= 0 else ''
    buy_score  = tv_data.get('BUY_SCORE',  0) if tv_data else 0
    sell_score = tv_data.get('SELL_SCORE', 0) if tv_data else 0

    exch_label = f" · _{exchange_name}_" if exchange_name else ""
    caption = (
        f"📊 *{symbol}* · `{timeframe.upper()}`{exch_label}\n"
        f"——————————————————\n"
        f"💰 *Precio:* `${_fmt_price(last_price)}`  "
        f"{pct_icon} `{pct_sign}{pct_change:.2f}%`\n"
        f"{sig_emoji} *Señal:* `{signal}`\n"
        f"⚖️ *Score:* {buy_score} 🐂 · {sell_score} 🐻\n"
        f"——————————————————\n"
        f"🎯 *Pivot:* `${_fmt_price(pivot)}`\n"
        f"🔴 *R1:* `${_fmt_price(r1)}`  |  🟢 *S1:* `${_fmt_price(s1)}`\n"
        f"——————————————————\n"
        f"📌 _EMA20 · EMA50 · EMA200 · RSI · Vol_"
    )
    caption += get_random_ad_text()

    # Botones inline
    tf_row = []
    for tf_opt in _QUICK_TFS:
        label = f"▶ {tf_opt}" if tf_opt == timeframe else tf_opt
        tf_row.append(InlineKeyboardButton(label, callback_data=f"graf_tf|{base}|{quote}|{tf_opt}"))

    tv_url = (
        f"https://www.tradingview.com/chart/"
        f"?symbol=BINANCE:{symbol}&interval={_TF_TV_URL.get(timeframe, '60')}"
    )
    action_row = [
        InlineKeyboardButton("📊 TradingView ↗", url=tv_url),
        InlineKeyboardButton("📈 Análisis /ta",  callback_data=f"ta_quick|{base}|{timeframe}"),
    ]

    keyboard = InlineKeyboardMarkup([tf_row, action_row])

    # Enviar
    if is_callback:
        await update.callback_query.message.reply_photo(
            photo=chart_bytes,
            caption=caption,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard,
        )
    else:
        if msg_wait:
            try:
                await msg_wait.delete()
            except Exception:
                pass
        await update.message.reply_photo(
            photo=chart_bytes,
            caption=caption,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard,
        )

async def p_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Muestra el precio y otros datos de una criptomoneda.
    Uso: /p <MONEDA>
    """
    user_id = update.effective_user.id
    
    if not context.args:
        error_msg = _("⚠️ *Formato incorrecto*.\nUso: `/p <MONEDA>` (ej: `/p BTC`)", user_id)
        if update.callback_query:
            await update.callback_query.edit_message_text(error_msg, parse_mode=ParseMode.MARKDOWN)
        else:
            await update.message.reply_text(error_msg, parse_mode=ParseMode.MARKDOWN)
        return

    moneda = context.args[0].upper()
    
    # Notificar que estamos 'escribiendo' para dar feedback visual si tarda la API
    # Solo si es un mensaje nuevo (no un callback de refresh)
    if update.message:
        await update.message.reply_chat_action("typing")
    
    datos = obtener_datos_moneda(moneda)

    if not datos:
        error_msg = _("😕 No se pudieron obtener los datos para *{moneda}*.", user_id).format(moneda=moneda)
        if update.callback_query:
            await update.callback_query.edit_message_text(error_msg, parse_mode=ParseMode.MARKDOWN)
        else:
            await update.message.reply_text(error_msg, parse_mode=ParseMode.MARKDOWN)
        return

    # Helper para formatear cambios porcentuales
    def format_change(change):
        if change is None: return "0.00%"
        icon = "😄" if change > 0.5 else ("😕" if change > -0.5 else ("😔" if change > -5 else "😢"))
        sign = "+" if change > 0 else ""
        return f"{sign}{change:.2f}%  {icon}"

    # Helpers de etiquetas
    lbl_eth = _("Ξ:", user_id)
    lbl_btc = _("₿:", user_id)
    lbl_cap = _("Cap:", user_id)
    lbl_vol = _("Vol:", user_id)

    # --- LÓGICA HIGH / LOW ---
    high_24h = datos.get('high_24h', 0)
    low_24h = datos.get('low_24h', 0)
    
    # Si high es 0, asumimos que no hay datos disponibles y mostramos N/A
    if high_24h > 0:
        str_high = f"${high_24h:,.4f}"
        str_low = f"${low_24h:,.4f}"
    else:
        str_high = "N/A"
        str_low = "N/A"

    # Construcción del Mensaje
    mensaje = (
        f"*{datos['symbol']}*\n—————————————————\n"
        f"💰 *Precio:* ${datos['price']:,.4f}\n"
        f"📈 *High 24h:* {str_high}\n"
        f"📉 *Low 24h:* {str_low}\n"
        f"—————————————————\n"
        f"{lbl_eth} {datos['price_eth']:.8f}\n"
        f"{lbl_btc} {datos['price_btc']:.8f}\n"
        f"1h  {format_change(datos['percent_change_1h'])}\n"
        f"24h {format_change(datos['percent_change_24h'])}\n"
        f"7d  {format_change(datos['percent_change_7d'])}\n"
        f"{lbl_cap} #{datos['market_cap_rank']} | ${datos['market_cap']:,.0f}\n"
        f"{lbl_vol} ${datos['volume_24h']:,.0f}"
    )

    # Inyección de publicidad
    mensaje += get_random_ad_text()

    # Botones de actualizar y análisis técnico
    btn_refresh = _("🔄 Actualizar /p {symbol}", user_id).format(symbol=datos['symbol'])
    btn_ta = _("📊 Ver Análisis Técnico (4H)", user_id)
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(btn_refresh, callback_data=f"refresh_{datos['symbol']}")],
        [InlineKeyboardButton(btn_ta, callback_data=f"ta_quick|{datos['symbol']}|4h")]
    ])

    # Detectar si es un callback (refresh) o un comando nuevo
    # Si es callback, editamos el mensaje existente; si es nuevo, enviamos uno nuevo
    if update.callback_query:
        query = update.callback_query
        try:
            await query.edit_message_text(
                mensaje,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard
            )
        except Exception as e:
            # Si el mensaje no cambió (mismo contenido), Telegram lanza error
            # En ese caso, simplemente notificamos al usuario
            if "Message is not modified" in str(e):
                await query.answer("Los datos ya están actualizados")
            else:
                raise
    else:
        await update.message.reply_text(
            mensaje,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard
        )

async def refresh_command_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    moneda = query.data.replace("refresh_", "").upper()
    context.args = [moneda]
    await p_command(update, context)

async def ta_quick_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Callback para el botón 'Ver Análisis Técnico'.
    Usado desde /p (mensaje texto) y /graf (mensaje foto).

    Formatos:
      /p    -> ta_quick|BTCUSDT|4h   (símbolo completo)
      /graf -> ta_quick|BTC|4h       (solo base)

    Llama al ta_command REAL usando force_new_message=True cuando el mensaje
    origen es una foto (caso /graf), evitando el edit_message_text sobre foto.
    """
    query = update.callback_query
    await query.answer("📊 Cargando análisis...")

    parts = query.data.split("|")
    if len(parts) < 2:
        await query.answer("❌ Datos inválidos", show_alert=True)
        return

    raw_symbol = parts[1].upper()
    timeframe  = parts[2].lower() if len(parts) >= 3 else "4h"

    # Detectar si viene símbolo completo (BTCUSDT) o solo base (BTC)
    known_quotes = ("USDT", "BUSD", "BTC", "ETH", "BNB", "USD")
    pair = "USDT"
    base = raw_symbol
    for q in known_quotes:
        if raw_symbol.endswith(q) and len(raw_symbol) > len(q):
            pair = q
            base = raw_symbol[: len(raw_symbol) - len(pair)]
            break

    # Detectar si el mensaje origen es una foto (viene de /graf)
    msg = query.message
    is_photo_message = bool(msg.photo or msg.document)

    from handlers.ta import ta_command
    await ta_command(
        update, context,
        override_source="BINANCE",
        override_args=[base, pair, timeframe],
        skip_binance_check=True,
        force_new_message=is_photo_message,  # ← CLAVE: fuerza reply nuevo si es foto
    )

# === NUEVA LÓGICA PARA /MK ===

def get_time_str(minutes_delta):
    """Convierte minutos a formato legible (ej: 'in an hour', 'in 2 hours')."""
    hours = int(minutes_delta // 60)
    minutes = int(minutes_delta % 60)
    
    if hours == 0:
        return f"in {minutes} minutes"
    elif hours == 1:
        return "in an hour"
    else:
        return f"in {hours} hours"

async def mk_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Muestra el estado de los mercados globales (Abierto/Cerrado).
    """
    user_id = update.effective_user.id

    # Configuración de Mercados: (Nombre, Emoji, Timezone, Hora Apertura, Hora Cierre)
    # Horas en formato 24h local
    markets = [
        {"name": "NYC", "flag": "🇺🇸", "tz": "America/New_York", "open": 9.5, "close": 16.0}, # 9:30 - 16:00
        {"name": "Hong Kong", "flag": "🇭🇰", "tz": "Asia/Hong_Kong", "open": 9.5, "close": 16.0},
        {"name": "Tokyo", "flag": "🇯🇵", "tz": "Asia/Tokyo", "open": 9.0, "close": 15.0},
        {"name": "Seoul", "flag": "🇰🇷", "tz": "Asia/Seoul", "open": 9.0, "close": 15.5},
        {"name": "London", "flag": "🇬🇧", "tz": "Europe/London", "open": 8.0, "close": 16.5},
        {"name": "Shanghai", "flag": "🇨🇳", "tz": "Asia/Shanghai", "open": 9.5, "close": 15.0},
        {"name": "South Africa", "flag": "🇿🇦", "tz": "Africa/Johannesburg", "open": 9.0, "close": 17.0},
        {"name": "Dubai", "flag": "🇦🇪", "tz": "Asia/Dubai", "open": 10.0, "close": 15.0},
        {"name": "Australia", "flag": "🇦🇺", "tz": "Australia/Sydney", "open": 10.0, "close": 16.0},
        {"name": "India", "flag": "🇮🇳", "tz": "Asia/Kolkata", "open": 9.25, "close": 15.5}, # 9:15
        {"name": "Russia", "flag": "🇷🇺", "tz": "Europe/Moscow", "open": 10.0, "close": 18.75}, # 18:45
        {"name": "Germany", "flag": "🇩🇪", "tz": "Europe/Berlin", "open": 9.0, "close": 17.5}, # 17:30
        {"name": "Canada", "flag": "🇨🇦", "tz": "America/Toronto", "open": 9.5, "close": 16.0},
        {"name": "Brazil", "flag": "🇧🇷", "tz": "America/Sao_Paulo", "open": 10.0, "close": 17.0},
    ]

    lines = []
    now_utc = datetime.now(pytz.utc)

    for m in markets:
        try:
            tz = pytz.timezone(m["tz"])
            now_local = now_utc.astimezone(tz)
            
            # Convertir hora actual a float para comparar fácil (ej: 9:30 = 9.5)
            current_float = now_local.hour + (now_local.minute / 60.0)
            
            # Determinar si es fin de semana (Saturday=5, Sunday=6)
            is_weekend = now_local.weekday() >= 5
            
            # Estado base
            is_open = False
            msg_status = ""
            
            if not is_weekend and m["open"] <= current_float < m["close"]:
                is_open = True
                
                # Calcular tiempo para cerrar
                minutes_to_close = (m["close"] - current_float) * 60
                time_str = get_time_str(minutes_to_close)
                msg_status = f"Open ✅ closes {time_str}"
            else:
                is_open = False
                
                # Calcular tiempo para abrir
                if is_weekend:
                    # Si es finde, abre el Lunes (calculo aproximado sumando días)
                    days_ahead = 7 - now_local.weekday() # 7 - 5(Sab) = 2 dias
                    if days_ahead == 0: days_ahead = 1 # Si es Domingo noche y ya pasó la hora 0
                    # Simplificación: "Opens on Monday" o calcular horas reales es complejo
                    msg_status = "Closed ❌ opens Monday"
                elif current_float < m["open"]:
                    # Abre hoy más tarde
                    minutes_to_open = (m["open"] - current_float) * 60
                    time_str = get_time_str(minutes_to_open)
                    msg_status = f"Closed ❌ opens {time_str}"
                else:
                    # Ya cerró hoy, abre mañana
                    # Calculamos horas hasta la medianoche + hora de apertura
                    hours_remaining_today = 24.0 - current_float
                    total_hours = hours_remaining_today + m["open"]
                    time_str = get_time_str(total_hours * 60)
                    msg_status = f"Closed ❌ opens {time_str}"

            lines.append(f"{m['flag']}*{m['name']}*: {msg_status}")

        except Exception as e:
            print(f"Error procesando {m['name']}: {e}")
            lines.append(f"{m['flag']}*{m['name']}*: Error Data")

    # Construir mensaje final con estética del bot
    header = _("🌍 *Estado de Mercados Globales*\n—————————————————\n\n", user_id)
    body = "\n".join(lines)
    footer = get_random_ad_text()

    full_message = header + body + footer

    await update.message.reply_text(full_message, parse_mode=ParseMode.MARKDOWN)