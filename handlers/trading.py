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

# Importamos configuraciones y utilidades existentes
from core.config import SCREENSHOT_API_KEY, ADMIN_CHAT_IDS
from core.api_client import obtener_datos_moneda
from utils.file_manager import (
    add_log_line, check_feature_access, registrar_uso_comando
)
from utils.ads_manager import get_random_ad_text
from core.i18n import _
from core.btc_advanced_analysis import BTCAdvancedAnalyzer

def _take_screenshot_sync(url: str) -> BytesIO | None:
    """
    Captura de pantalla usando ScreenshotOne.
    """
    if not SCREENSHOT_API_KEY:
        print("❌ Error: La SCREENSHOT_API_KEY no está configurada en config.py.")
        return None
    # nueva integracion con ScreenshotOne
    api_url = "https://api.screenshotone.com/take"
    params = {
        "access_key": SCREENSHOT_API_KEY,
        "url": url,
        "format": "png",  # Puedes usar 'png' si prefieres
        "block_ads": "true",
        "block_cookie_banners": "true",
        "block_banners_by_heuristics": "false",
        "block_trackers": "true",
        "delay": "0",
        "timeout": "60",
        "response_type": "by_format",
        "image_quality": "100"
    }

    try:
        response = requests.get(api_url, params=params, timeout=30)
        response.raise_for_status()
        return BytesIO(response.content)

    except requests.exceptions.RequestException as e:
        print(f"❌ Error al llamar a ScreenshotOne: {e}")
        return None
    

async def take_chart_screenshot(url: str) -> BytesIO | None:
    """Ejecuta la función de captura de pantalla en un executor para no bloquear el bucle de asyncio."""
    loop = asyncio.get_running_loop()
    try:
        # Usamos asyncio.to_thread para ejecutar la función síncrona en un hilo separado
        return await asyncio.to_thread(_take_screenshot_sync, url)
    except Exception as e:
        print(f"Error al ejecutar el hilo de la captura de pantalla: {e}")
        return None

async def graf_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Genera una captura de pantalla de un gráfico de TradingView.
    Uso: /graf <MONEDA> [MONEDA_PAR] <TEMPORALIDAD>
    """
    user_id = update.effective_user.id

    if len(context.args) not in [2, 3]:
        mensaje_error_formato = _(
            "⚠️ *Formato incorrecto*.\n\nUso: `/graf <MONEDA> [MONEDA_PAR] <TEMPORALIDAD>`\n"
            "Ejemplos:\n`/graf BTC 15m`\n`/graf BTC USDT 1h`",
            user_id
        )
        await update.message.reply_text(
            mensaje_error_formato,
            parse_mode=ParseMode.MARKDOWN
        )
        return

    if len(context.args) == 2:
        base = context.args[0].upper()
        quote = "USD"
        temporalidad = context.args[1].lower()
    else:
        base = context.args[0].upper()
        quote = context.args[1].upper()
        temporalidad = context.args[2].lower()

    map_temporalidad = {
        "1m": "1", "3m": "3", "5m": "5", "15m": "15", "30m": "30",
        "1h": "60", "2h": "120", "4h": "240",
        "1d": "D", "1w": "W", "1M": "M"
    }

    intervalo = map_temporalidad.get(temporalidad)
    if not intervalo:
        mensaje_error_tiempo = _(
            "⚠️ *Temporalidad no válida*.\n\n"
            "Usa: 1m, 5m, 15m, 1h, 4h, 1d, 1w, 1M.",
            user_id
        )
        await update.message.reply_text(
            mensaje_error_tiempo,
            parse_mode=ParseMode.MARKDOWN
        )
        return

    par = f"{base}{quote}"
    url = f"https://www.tradingview.com/chart/?symbol=BINANCE:{par}&interval={intervalo}"

    mensaje_proceso_base = _(
        "⏳ Generando gráfico para *{base}/{quote}* ({temporalidad})...",
        user_id
    )
    await update.message.reply_text(
        mensaje_proceso_base.format(base=base, quote=quote, temporalidad=temporalidad),
        parse_mode=ParseMode.MARKDOWN
    )

    screenshot_bytes = await take_chart_screenshot(url)

    if screenshot_bytes:
        mensaje_base = _(
            "📈 *Gráfico de {base}/{quote} ({temporalidad})*\n\n[Ver en TradingView]({url})",
            user_id
        )
        mensaje = mensaje_base.format(base=base, quote=quote, temporalidad=temporalidad, url=url)

        await update.message.reply_photo(
            photo=screenshot_bytes,
            caption=mensaje,
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        mensaje_error_grafico = _(
            "❌ Lo siento, no pude generar la captura del gráfico en este momento. Inténtalo de nuevo más tarde.",
            user_id
        )
        await update.message.reply_text(
            mensaje_error_grafico,
            parse_mode=ParseMode.MARKDOWN
        )


async def p_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Muestra el precio y otros datos de una criptomoneda.
    Uso: /p <MONEDA>
    """
    user_id = update.effective_user.id
    
    if not context.args:
        mensaje_error_formato = _(
            "⚠️ *Formato incorrecto*.\n\nUso: `/p <MONEDA>`\n"
            "Ejemplo: `/p BTC`",
            user_id
        )
        await update.message.reply_text(
            mensaje_error_formato,
            parse_mode=ParseMode.MARKDOWN
        )
        return

    moneda = context.args[0].upper()
    datos = obtener_datos_moneda(moneda)

    if not datos:
        mensaje_error_datos = _(
            "😕 No se pudieron obtener los datos para *{moneda}*.",
            user_id
        ).format(moneda=moneda)
        await update.message.reply_text(mensaje_error_datos, parse_mode=ParseMode.MARKDOWN)
        return

    def format_change(change):
        if change > 0.5:
            return f"+{change:.2f}%   😄"
        elif change > -0.5:
            return f"{change:.2f}%   😕"
        elif change > -5:
            return f"{change:.2f}%   😔"
        else:
            return f"{change:.2f}%   😢"
            

    etiqueta_eth = _("Ξ:", user_id)
    etiqueta_btc = _("₿:", user_id)
    etiqueta_cap = _("Cap:", user_id)
    etiqueta_vol = _("Vol:", user_id)

    # Obtenemos high y low del diccionario de datos
    high_24h = datos.get('high_24h', 0)
    low_24h = datos.get('low_24h', 0)

    # Construimos el mensaje agregando la linea de High/Low
    mensaje = (
        f"*{datos['symbol']}*\n—————————————————\n"
        f"💰 *Precio:* ${datos['price']:,.4f}\n"
        f"📈 *24h High:* ${high_24h:,.4f}\n"  # <--- NUEVA LÍNEA
        f"📉 *24h Low:* ${low_24h:,.4f}\n"  # <--- NUEVA LÍNEA
        f"—————————————————\n"
        f"{etiqueta_eth} {datos['price_eth']:.8f}\n"
        f"{etiqueta_btc} {datos['price_btc']:.8f}\n"
        f"1h {format_change(datos['percent_change_1h'])}\n"
        f"24h {format_change(datos['percent_change_24h'])}\n"
        f"7d {format_change(datos['percent_change_7d'])}\n"
        f"{etiqueta_cap} {datos['market_cap_rank']}st | ${datos['market_cap']:,.0f}\n"
        f"{etiqueta_vol} ${datos['volume_24h']:,.0f}"
    )

    # --- INYECCIÓN DE ANUNCIO ---
    mensaje += get_random_ad_text()
    # ----------------------------

    button_text_template = _("🔄 Actualizar /p {symbol}", user_id)
    button_text = button_text_template.format(symbol=datos['symbol'])

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(button_text, callback_data=f"refresh_{datos['symbol']}")]
    ])

    message = update.message or update.callback_query.message
    await message.reply_text(mensaje, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)

async def refresh_command_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    moneda = query.data.replace("refresh_", "").upper()
    context.args = [moneda]
    await p_command(update, context)


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


# === NUEVO COMANDO /ta MEJORADO ===

def get_binance_klines(symbol, interval, limit=500): 
    """
    Obtiene velas de Binance (Global o US). 
    Limit reducido a 500 por defecto para rapidez, el Analyzer usa internamente lo necesario.
    """
    endpoints = [
        "https://api.binance.com/api/v3/klines", 
        "https://api.binance.us/api/v3/klines"
    ]
    for url in endpoints:
        params = {"symbol": symbol, "interval": interval, "limit": limit}
        try:
            response = requests.get(url, params=params, timeout=5)
            response.raise_for_status()
            data = response.json()
            if not data or not isinstance(data, list): continue
            
            df = pd.DataFrame(data, columns=[
                "open_time", "open", "high", "low", "close", "volume",
                "close_time", "quote_asset_volume", "trades", 
                "taker_base", "taker_quote", "ignore"
            ])
            cols = ["open", "high", "low", "close", "volume"]
            df[cols] = df[cols].apply(pd.to_numeric, errors='coerce')
            
            # Convertir tiempo para el Analyzer
            df['time'] = pd.to_datetime(df['open_time'], unit='ms')
            df.set_index('time', inplace=True)
            
            return df
        except Exception:
            continue
    return None

def calculate_table_indicators(df):
    """
    Calcula SOLO los indicadores necesarios para la TABLA visual (Historial).
    El análisis lógico (Señales) se delegará al BTCAdvancedAnalyzer.
    """
    # Helper seguro
    def safe_ind(name, series):
        try:
            df[name] = series if series is not None else 0.0
        except:
            df[name] = 0.0

    # Indicadores específicos para la tabla
    safe_ind('RSI', df.ta.rsi(length=14))
    safe_ind('MFI', df.ta.mfi(length=14))
    safe_ind('CCI', df.ta.cci(length=20)) # Estándar suele ser 20 para CCI
    safe_ind('ADX', df.ta.adx(length=14)['ADX_14']) # ADX devuelve DF
    safe_ind('WILLR', df.ta.willr(length=14))
    safe_ind('OBV', df.ta.obv())
    
    # Devolvemos las últimas 3 filas para construir la tabla (Actual, Previo, Ante-previo)
    return df.iloc[-3:]

def get_tradingview_analysis_enhanced(symbol_pair, interval_str):
    """
    Fallback a TradingView mejorado para obtener SCORE y SEÑALES.
    """
    interval_map = {
        "1m": Interval.INTERVAL_1_MINUTE, "5m": Interval.INTERVAL_5_MINUTES,
        "15m": Interval.INTERVAL_15_MINUTES, "1h": Interval.INTERVAL_1_HOUR,
        "4h": Interval.INTERVAL_4_HOURS, "1d": Interval.INTERVAL_1_DAY,
        "1w": Interval.INTERVAL_1_WEEK, "1M": Interval.INTERVAL_1_MONTH
    }
    tv_interval = interval_map.get(interval_str, Interval.INTERVAL_1_HOUR)
    
    try:
        # Intentar Binance primero
        handler = TA_Handler(symbol=symbol_pair, screener="crypto", exchange="BINANCE", interval=tv_interval)
        analysis = handler.get_analysis()
    except:
        try:
            # Fallback a GateIO o genérico
            handler = TA_Handler(symbol=symbol_pair, screener="crypto", exchange="GATEIO", interval=tv_interval)
            analysis = handler.get_analysis()
        except:
            return None

    if not analysis: return None

    ind = analysis.indicators
    summ = analysis.summary # Aquí están los contadores BUY/SELL
    
    return {
        'source': 'TradingView',
        'close': ind.get('close', 0),
        'volume': ind.get('volume', 0),
        # Datos para tabla (TV solo da el actual, rellenaremos ceros en el comando)
        'RSI': ind.get('RSI', 0),
        'MFI': ind.get('MFI', 0) or 0, # TV a veces no da MFI directo en standard
        'CCI': ind.get('CCI20', 0),
        'ADX': ind.get('ADX', 0),
        'WR': ind.get('W.R', 0),
        'OBV': ind.get('OBV', 0) or ind.get('volume', 0), # Fallback to vol
        
        # Datos para Niveles
        'Pivot': ind.get('Pivot.M.Classic.Middle', 0),
        'R1': ind.get('Pivot.M.Classic.R1', 0), 'R2': ind.get('Pivot.M.Classic.R2', 0),
        'S1': ind.get('Pivot.M.Classic.S1', 0), 'S2': ind.get('Pivot.M.Classic.S2', 0),
        
        # Datos para Score/Señal
        'RECOMMENDATION': summ.get('RECOMMENDATION', 'NEUTRAL'),
        'BUY_SCORE': summ.get('BUY', 0),
        'SELL_SCORE': summ.get('SELL', 0),
        'NEUTRAL_SCORE': summ.get('NEUTRAL', 0),
        
        # Extras visuales
        'MACD_hist': ind.get('MACD.hist', 0),
        'SMA_50': ind.get('SMA50', 0),
        'EMA_200': ind.get('EMA200', 0)
    }

def get_binance_klines(symbol, interval, limit=500): 
    """Obtiene velas de Binance (Global o US)."""
    endpoints = [
        "https://api.binance.com/api/v3/klines", 
        "https://api.binance.us/api/v3/klines"
    ]
    for url in endpoints:
        params = {"symbol": symbol, "interval": interval, "limit": limit}
        try:
            response = requests.get(url, params=params, timeout=3) # Timeout rápido para UX
            if response.status_code != 200: continue
            data = response.json()
            if not data or not isinstance(data, list): continue
            
            df = pd.DataFrame(data, columns=[
                "open_time", "open", "high", "low", "close", "volume",
                "close_time", "quote_asset_volume", "trades", 
                "taker_base", "taker_quote", "ignore"
            ])
            cols = ["open", "high", "low", "close", "volume"]
            df[cols] = df[cols].apply(pd.to_numeric, errors='coerce')
            df['time'] = pd.to_datetime(df['open_time'], unit='ms')
            df.set_index('time', inplace=True)
            return df
        except Exception:
            continue
    return None

def calculate_table_indicators(df):
    """Calcula indicadores visuales para la tabla."""
    def safe_ind(name, series):
        try: df[name] = series if series is not None else 0.0
        except: df[name] = 0.0

    safe_ind('RSI', df.ta.rsi(length=14))
    safe_ind('MFI', df.ta.mfi(length=14))
    safe_ind('CCI', df.ta.cci(length=20))
    try: safe_ind('ADX', df.ta.adx(length=14)['ADX_14'])
    except: df['ADX'] = 0.0
    safe_ind('WILLR', df.ta.willr(length=14))
    safe_ind('OBV', df.ta.obv())
    return df.iloc[-3:]

def get_tradingview_analysis_enhanced(symbol_pair, interval_str):
    """Fallback a TradingView para obtener Score y Señales."""
    interval_map = {
        "1m": Interval.INTERVAL_1_MINUTE, "5m": Interval.INTERVAL_5_MINUTES,
        "15m": Interval.INTERVAL_15_MINUTES, "1h": Interval.INTERVAL_1_HOUR,
        "4h": Interval.INTERVAL_4_HOURS, "1d": Interval.INTERVAL_1_DAY,
        "1w": Interval.INTERVAL_1_WEEK, "1M": Interval.INTERVAL_1_MONTH
    }
    tv_interval = interval_map.get(interval_str, Interval.INTERVAL_1_HOUR)
    
    try:
        handler = TA_Handler(symbol=symbol_pair, screener="crypto", exchange="BINANCE", interval=tv_interval)
        analysis = handler.get_analysis()
    except:
        try:
            handler = TA_Handler(symbol=symbol_pair, screener="crypto", exchange="GATEIO", interval=tv_interval)
            analysis = handler.get_analysis()
        except:
            return None

    if not analysis: return None
    ind = analysis.indicators
    summ = analysis.summary 
    return {
        'source': 'TradingView',
        'close': ind.get('close', 0),
        'volume': ind.get('volume', 0),
        'RSI': ind.get('RSI', 0),
        'MFI': ind.get('MFI', 0) or 0,
        'CCI': ind.get('CCI20', 0),
        'ADX': ind.get('ADX', 0),
        'WR': ind.get('W.R', 0),
        'OBV': ind.get('OBV', 0) or ind.get('volume', 0),
        'Pivot': ind.get('Pivot.M.Classic.Middle', 0),
        'R1': ind.get('Pivot.M.Classic.R1', 0), 'R2': ind.get('Pivot.M.Classic.R2', 0),
        'S1': ind.get('Pivot.M.Classic.S1', 0), 'S2': ind.get('Pivot.M.Classic.S2', 0),
        'RECOMMENDATION': summ.get('RECOMMENDATION', 'NEUTRAL'),
        'BUY_SCORE': summ.get('BUY', 0),
        'SELL_SCORE': summ.get('SELL', 0),
        'MACD_hist': ind.get('MACD.hist', 0),
        'SMA_50': ind.get('SMA50', 0),
        'ATR': ind.get('ATR', 0)
    }

async def ta_command(update: Update, context: ContextTypes.DEFAULT_TYPE, override_source=None, override_args=None):
    """
    Controlador maestro de Análisis Técnico con soporte para Switch de Fuente.
    """
    user_id = update.effective_user.id
    is_callback = update.callback_query is not None
    message = update.effective_message

    # === ARGUMENT PARSING ===
    if is_callback and override_args:
        # Formato args: [SYMBOL, PAIR, TIME]
        symbol_base, pair, timeframe = override_args
        full_symbol = f"{symbol_base}{pair}"
        target_source = override_source # BINANCE o TV
    else:
        # Comando normal: /ta BTC USDT 4h TV
        if not context.args:
            await message.reply_text(_("⚠️ Uso: `/ta <SYMBOL> [PAR] [TIME] [TV]`", user_id), parse_mode=ParseMode.MARKDOWN)
            return
        
        raw_args = [arg.upper() for arg in context.args]
        target_source = "TV" if "TV" in raw_args else "BINANCE"
        if "TV" in raw_args: raw_args.remove("TV")
        
        symbol_base = raw_args[0]
        pair = "USDT"
        timeframe = "1h"
        
        if len(raw_args) > 1:
            for arg in raw_args[1:]:
                if arg[-1].lower() in ['m', 'h', 'd', 'w']:
                    timeframe = arg.lower()
                else:
                    pair = arg
        full_symbol = f"{symbol_base}{pair}"

    # === MENSAJE DE ESPERA ===
    if is_callback:
        # Si es callback, no mandamos mensaje nuevo, editaremos el existente.
        # Pero primero validamos disponibilidad si se pide LOCAL
        if target_source == "BINANCE":
            # Chequeo rápido de existencia
            # NOTA: Hacemos esto antes de borrar nada para poder cancelar si falla
            loop = asyncio.get_running_loop()
            check_df = await loop.run_in_executor(None, get_binance_klines, full_symbol, timeframe, 50)
            if check_df is None or check_df.empty:
                await update.callback_query.answer("❌ No disponible en Binance Local", show_alert=True)
                return # IMPORTANTE: Detenemos ejecución aquí, el mensaje anterior se mantiene intacto
    else:
        msg_wait = await message.reply_text(f"⏳ _Analizando {full_symbol} ({timeframe})..._", parse_mode=ParseMode.MARKDOWN)

    # === LÓGICA DE OBTENCIÓN DE DATOS ===
    loop = asyncio.get_running_loop()
    final_data = {}
    data_source_display = ""
    reasons_list = []
    
    # Valores por defecto
    signal_emoji, signal_text = "⚖️", "NEUTRAL"
    score_buy, score_sell = 0, 0
    
    df_result = None

    # 1. INTENTO BINANCE (Si se solicitó)
    if target_source == "BINANCE":
        df_result = await loop.run_in_executor(None, get_binance_klines, full_symbol, timeframe)
        
        if df_result is not None:
            data_source_display = "Binance (Local PRO)"
            # A) TABLA
            last_3 = await loop.run_in_executor(None, calculate_table_indicators, df_result.copy())
            
            # B) ANÁLISIS
            analyzer = BTCAdvancedAnalyzer(df_result)
            sig, emo, (sb, ss), reasons = analyzer.get_momentum_signal()
            curr_vals = analyzer.get_current_values()
            
            signal_emoji, signal_text = emo, sig
            score_buy, score_sell = sb, ss
            reasons_list = reasons
            
            curr = last_3.iloc[-1]
            prev = last_3.iloc[-2]
            pprev = last_3.iloc[-3]
            
            final_data = {
                'close': curr['close'], 'volume': curr['volume'], 'ATR': curr_vals.get('ATR', 0),
                'RSI_list': [curr.get('RSI', 0), prev.get('RSI', 0), pprev.get('RSI', 0)],
                'MFI_list': [curr.get('MFI', 0), prev.get('MFI', 0), pprev.get('MFI', 0)],
                'CCI_list': [curr.get('CCI', 0), prev.get('CCI', 0), pprev.get('CCI', 0)],
                'ADX_list': [curr.get('ADX', 0), prev.get('ADX', 0), pprev.get('ADX', 0)],
                'WR_list':  [curr.get('WILLR', 0), prev.get('WILLR', 0), pprev.get('WILLR', 0)],
                'OBV_list': [curr.get('OBV', 0), prev.get('OBV', 0), pprev.get('OBV', 0)],
                'MACD_hist': curr_vals.get('MACD_HIST', 0),
                'SMA_50': curr_vals.get('EMA_50', 0),
                # Pivotes Calculados
                'Pivot': (curr['high']+curr['low']+curr['close'])/3
            }
            p = final_data['Pivot']
            final_data.update({
                'R1': (2*p)-curr['low'], 'R2': p+(curr['high']-curr['low']),
                'S1': (2*p)-curr['high'], 'S2': p-(curr['high']-curr['low'])
            })

    # 2. INTENTO TRADINGVIEW (Fallback o Solicitud Directa)
    used_tv = False
    if df_result is None:
        # Si falló Binance (o se pidió TV), vamos a TV
        used_tv = True
        tv_data = await loop.run_in_executor(None, get_tradingview_analysis_enhanced, full_symbol, timeframe)
        
        if tv_data:
            data_source_display = "TradingView API"
            final_data = tv_data
            
            # Interpretar señales TV
            rec = final_data.get('RECOMMENDATION', '')
            if "STRONG_BUY" in rec: signal_emoji, signal_text = "🚀", "COMPRA FUERTE"
            elif "BUY" in rec: signal_emoji, signal_text = "🐂", "COMPRA"
            elif "STRONG_SELL" in rec: signal_emoji, signal_text = "🐻", "VENTA FUERTE"
            elif "SELL" in rec: signal_emoji, signal_text = "📉", "VENTA"
            
            score_buy = final_data.get('BUY_SCORE', 0)
            score_sell = final_data.get('SELL_SCORE', 0)
            
            # Rellenar listas con ceros
            for k in ['RSI', 'MFI', 'CCI', 'ADX', 'WR', 'OBV']:
                val = final_data.get(k, 0) or 0
                final_data[f'{k}_list'] = [val, 0, 0]
        else:
            err_txt = _("❌ No se encontraron datos para *{s}* ni en Binance ni en TV.", user_id).format(s=full_symbol)
            if is_callback:
                await update.callback_query.answer("❌ Datos no encontrados", show_alert=True)
            else:
                await msg_wait.edit_text(err_txt, parse_mode=ParseMode.MARKDOWN)
            return
    
    

    # === CONSTRUCCIÓN DEL MENSAJE ===
    def fmt_cell(val, width=7):
        if val is None or pd.isna(val) or val == 0: return "   --  ".center(width)
        try:
            f = float(val)
            if abs(f) > 10000: return f"{f/1000:.1f}k".rjust(width)
            elif abs(f) > 999: return f"{f:.0f}".rjust(width)
            else: return f"{f:.2f}".rjust(width)
        except: return "   --  ".center(width)

    table_msg = "```text\nIND     ACTUAL   PREVIO     ANT.\n──────  ───────  ───────  ───────\n"
    rows = [("RSI", 'RSI_list'), ("MFI", 'MFI_list'), ("CCI", 'CCI_list'), ("WR%", 'WR_list'), ("ADX", 'ADX_list'), ("OBV", 'OBV_list')]
    for l, k in rows:
        v = final_data.get(k, [0,0,0])
        table_msg += f"{l:<6} {fmt_cell(v[0])}  {fmt_cell(v[1])}  {fmt_cell(v[2])}\n"
    table_msg += "```"

    # 1. Definimos el precio ANTES de usarlo en los if
    price = final_data.get('close', 0)

    # 2. Inicializamos valores por defecto (para evitar errores si usamos TV)
    sr = {}
    kijun_val = 0
    fib_val = 0
    zone = "⚖️ NEUTRAL (TV)"
    kijun_icon = "➖"
    kijun_label = "N/A"
    fib_label = "N/A"

    # 3. Solo calculamos lógica avanzada si 'analyzer' existe (Modo Binance Local)
    if 'analyzer' in locals():
        sr = analyzer.get_support_resistance_dynamic()
        
        # Ichimoku Kijun
        kijun_val = sr.get('KIJUN', 0)
        if price > kijun_val:
            kijun_label = "Soporte Dinámico" 
            kijun_icon = "🛡️"
        else:
            kijun_label = "Resistencia Dinámica"
            kijun_icon = "🚧"

        # Fibonacci 0.618
        fib_val = sr.get('FIB_618', 0)
        if price > fib_val:
            fib_label = "Zona de Rebote (Bullish)"
        else:
            fib_label = "Techo de Tendencia (Bearish)"

        # Zona General
        zone = sr.get('status_zone', "⚖️ NEUTRAL")


    price = final_data.get('close', 0)
    macd_s = "Bullish 🟢" if final_data.get('MACD_hist', 0) > 0 else "Bearish 🔴"
    trend_s = "Alcista" if price > final_data.get('SMA_50', 0) else "Bajista"

    msg = (
        f"📊 *Análisis Técnico: {full_symbol}*\n"
        f"—————————————————\n"
        f"⏱ *{timeframe}* | 📡 *{data_source_display}*\n\n"
        f"{signal_emoji} *SEÑAL:* `{signal_text}`\n"
        f"⚖️ *Score:* {score_buy} Compra 🆚 {score_sell} Venta\n\n"
        f"💰 *Precio:* `${price:,.4f}`\n"
        f"📉 *ATR:* `{final_data.get('ATR', 0) or 0:.4f}`\n"
        f"•\n{table_msg}•\n"
        f"🧐 *Diagnóstico de Momentum*\n"
        f"🌊 *Tendencia:* {trend_s}\n"
        f"❌ *MACD:* {macd_s}\n"
        f"*Confluencia y Estado:*\n"
        f"📍 *Zona:* `{zone}`\n"
        f"☁️ *Ichimoku:* `${kijun_val:,.0f}`\n"
        f"   ↳ _{kijun_icon} {kijun_label}_\n"
        f"🟡 *FIB 0.618:* `${fib_val:,.0f}`\n"
        f"   ↳ _📐 {fib_label}_\n\n"
    )
    if reasons_list: msg += f"💡 *Nota:* _{reasons_list[0]}_\n"
    
    msg += (
        f"•\n🛡 *Niveles (Pivotes)*\n"
        f"R2: `${final_data.get('R2', 0):,.4f}`\n"
        f"R1: `${final_data.get('R1', 0):,.4f}`\n"
        f"🎯 *Pivot: ${final_data.get('Pivot', 0):,.4f}*\n"
        f"S1: `${final_data.get('S1', 0):,.4f}`\n"
        f"S2: `${final_data.get('S2', 0):,.4f}`\n"
    )
    msg += f"\n_v2.1 Experimental_\n{get_random_ad_text()}"

    # === CONSTRUCCIÓN DEL BOTÓN SWITCH ===
    kb = []
    
    # Callback Data Structure: ta_switch|TARGET_SOURCE|SYMBOL|PAIR|TIMEFRAME
    # Nota: Si used_tv es True, el botón debe ofrecer ir a BINANCE.
    # Si used_tv es False (usó Binance), el botón debe ofrecer ir a TV.
    
    if used_tv:
        # Estamos en TV -> Ofrecer Local
        # Datos: ta_switch|BINANCE|BTC|USDT|4h
        btn_data = f"ta_switch|BINANCE|{symbol_base}|{pair}|{timeframe}"
        kb.append([InlineKeyboardButton("🦁 Ver Local (Binance)", callback_data=btn_data)])
    else:
        # Estamos en Local -> Ofrecer TV
        # Datos: ta_switch|TV|BTC|USDT|4h
        btn_data = f"ta_switch|TV|{symbol_base}|{pair}|{timeframe}"
        kb.append([InlineKeyboardButton("📊 Ver en TradingView", callback_data=btn_data)])

    reply_markup = InlineKeyboardMarkup(kb)

    # === ENVÍO / EDICIÓN ===
    if is_callback:
        try:
            # Editamos el mensaje original con el nuevo contenido y teclado
            await update.callback_query.edit_message_text(
                text=msg, 
                parse_mode=ParseMode.MARKDOWN, 
                reply_markup=reply_markup
            )
        except Exception as e:
            # Si el mensaje es idéntico, Telegram lanza error, lo ignoramos
            pass
    else:
        await msg_wait.edit_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)


# === HANDLER DEL BOTÓN ===

async def ta_switch_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Maneja el clic en el botón de cambio de vista.
    Formato data: ta_switch|TARGET|SYMBOL|PAIR|TIMEFRAME
    """
    query = update.callback_query
    # No hacemos answer() aquí todavía, lo hacemos dentro de ta_command o si fallamos
    
    data = query.data.split("|")
    if len(data) < 5:
        await query.answer("❌ Datos corruptos", show_alert=True)
        return

    target = data[1]    # BINANCE o TV
    symbol = data[2]
    pair = data[3]
    timeframe = data[4]
    
    # Llamamos a la función principal pasándole los datos override
    # Esto permite reutilizar toda la lógica
    await ta_command(
        update, 
        context, 
        override_source=target, 
        override_args=[symbol, pair, timeframe]
    )
