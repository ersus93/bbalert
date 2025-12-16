# handlers/trading.py

import asyncio
import requests # Usaremos requests en lugar de Selenium
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
from core.config import SCREENSHOT_API_KEY, ADMIN_CHAT_IDS # <--- IMPORTANTE: AÑADIDO ADMIN_CHAT_IDS
from core.api_client import obtener_datos_moneda, obtener_tasas_eltoque
from utils.file_manager import (
    add_log_line, load_eltoque_history, save_eltoque_history, 
    check_feature_access, registrar_uso_comando
    )
from utils.ads_manager import get_random_ad_text
from utils.image_generator import generar_imagen_tasas_eltoque
from core.i18n import _

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

    mensaje = (
        f"*{datos['symbol']}*\n—————————————————\n"
        f"${datos['price']:,.4f}\n"
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

# === COMANDO ELTOQUE FUSIONADO (/tasa) ===
async def eltoque_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    #chat_id = update.effective_chat.id 

    # === GUARDIA DE PAGO ===
    # acceso, mensaje = check_feature_access(chat_id, 'tasa_limit')
    #if not acceso:
    #    await update.message.reply_text(mensaje, parse_mode=ParseMode.MARKDOWN)
    #    return
    
    #registrar_uso_comando(chat_id, 'tasa')
    # =======================
    
    # DEBUG: Si ves esto en la consola, el comando está bien registrado.
    print(f"DEBUG: Comando eltoque ejecutado por {user_id}") 

    msg_estado = await update.message.reply_text(_("⏳ Conectando con elToque...", user_id))
    
    loop = asyncio.get_running_loop()
    
    # Usamos run_in_executor para que la petición no congele el bot
    tasas_data = await loop.run_in_executor(None, obtener_tasas_eltoque)

    # Reintentos (también en executor)
    if not tasas_data:
        MAX_RETRIES = 2
        for i in range(MAX_RETRIES):
            try:
                await msg_estado.edit_text(_("⏳ Reintentando conexión ({i}/{max})...", user_id).format(i=i+1, max=MAX_RETRIES))
            except: pass
            
            await asyncio.sleep(2)
            tasas_data = await loop.run_in_executor(None, obtener_tasas_eltoque)
            if tasas_data:
                break
    
    if not tasas_data:
        mensaje_error_usuario = _("⚠️ *Error de Conexión con elToque*.\nInténtalo más tarde.", user_id)
        await msg_estado.edit_text(mensaje_error_usuario, parse_mode=ParseMode.MARKDOWN)
        # Alerta Admin silenciosa
        for admin_id in ADMIN_CHAT_IDS:
            try:
                await context.bot.send_message(chat_id=admin_id, text=f"⚠️ API ElToque falló para user `{user_id}`.", parse_mode=ParseMode.MARKDOWN)
            except: pass
        return 

    try:
        try:
            await msg_estado.edit_text(_("🎨 Generando imagen de tasas...", user_id))
        except: pass

        tasas_actuales = tasas_data.get('tasas')
        tasas_anteriores = load_eltoque_history() 

        save_eltoque_history(tasas_actuales) 

        if not tasas_actuales or not isinstance(tasas_actuales, dict):
            await msg_estado.edit_text(_("😕 Error de formato en datos.", user_id))
            return

        fecha = tasas_data.get('date', '')
        hora = tasas_data.get('hour', 0)
        minutos = tasas_data.get('minutes', 0)
        timestamp_str = f"{fecha} {hora:02d}:{minutos:02d}"

        mensaje_titulo = _("🏦 *Tasas de Cambio* (Informal)\n—————————————————\n\n", user_id)
        mensaje_lineas = []
        monedas_ordenadas = ['ECU', 'USD', 'MLC', 'ZELLE', 'CLA', 'CAD', 'MXN', 'BRL', 'BTC', 'TRX', 'USDT_TRC20']
        TOLERANCIA = 0.0001
            
        for moneda_key in monedas_ordenadas:
            if moneda_key in tasas_actuales:
                tasa_actual = tasas_actuales[moneda_key]
                tasa_anterior = tasas_anteriores.get(moneda_key)
                
                moneda_display = 'USDT' if moneda_key == 'USDT_TRC20' else ('EUR' if moneda_key == 'ECU' else moneda_key)
                
                indicador = ""
                cambio_str = ""
                if tasa_anterior is not None:
                    diferencia = tasa_actual - tasa_anterior
                    if diferencia > TOLERANCIA:
                        indicador = "🔺"
                        cambio_str = f" +{diferencia:,.2f}"
                    elif diferencia < -TOLERANCIA:
                        indicador = "🔻"
                        cambio_str = f" {diferencia:,.2f}"
                    
                linea = f"*{moneda_display}*:  `{tasa_actual:,.2f}`  CUP  {indicador}{cambio_str}"
                mensaje_lineas.append(linea)

        mensaje_texto_final = mensaje_titulo + "\n".join(mensaje_lineas)
        actualizado_label = _("Actualizado:", user_id)
        mensaje_texto_final += f"\n\n—————————————————\n_{actualizado_label} {timestamp_str}\nFuente: elToque.com_"
        mensaje_texto_final += get_random_ad_text()

        image_bio = await asyncio.to_thread(generar_imagen_tasas_eltoque)

        if image_bio:
            await msg_estado.delete()
            await update.message.reply_photo(photo=image_bio, caption=mensaje_texto_final, parse_mode=ParseMode.MARKDOWN)
        else:
            add_log_line("⚠️ Falló generación imagen ElToque, enviando solo texto.")
            await msg_estado.edit_text(mensaje_texto_final, parse_mode=ParseMode.MARKDOWN)

    except Exception as e:
        print(f"Error fatal en /tasa: {e}") # Debug en consola
        add_log_line(f"Error fatal en /tasa: {e}.")
        try:
            await msg_estado.edit_text(_("❌ Ocurrió un error inesperado procesando la solicitud.", user_id), parse_mode=ParseMode.MARKDOWN)
        except: pass

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


# === NUEVO COMANDO /ta (Análisis Técnico) ===
def get_binance_klines(symbol, interval, limit=10000): 
    """Obtiene velas de Binance (Global o US)."""
    endpoints = [
        "https://api.binance.us/api/v3/klines",
        "https://api.binance.com/api/v3/klines" 
        
    ]
    for url in endpoints:
        params = {"symbol": symbol, "interval": interval, "limit": limit}
        try:
            response = requests.get(url, params=params, timeout=5)
            response.raise_for_status()
            data = response.json()
            if not data: continue
            
            df = pd.DataFrame(data, columns=[
                "open_time", "open", "high", "low", "close", "volume",
                "close_time", "quote_asset_volume", "trades", 
                "taker_base", "taker_quote", "ignore"
            ])
            cols = ["open", "high", "low", "close", "volume"]
            df[cols] = df[cols].apply(pd.to_numeric, errors='coerce')
            return df
        except Exception:
            continue
    return None

def calculate_indicators_binance(df):
    """Calcula indicadores de manera segura usando pandas_ta. Si falla alguno, no crashea."""
    
    # Helper para asignar columnas de forma segura
    def safe_indicator(name, indicator_series):
        try:
            if indicator_series is not None and not indicator_series.empty:
                df[name] = indicator_series
            else:
                df[name] = 0.0
        except Exception:
            df[name] = 0.0

    # Indicadores Clásicos
    safe_indicator('RSI', df.ta.rsi(length=14))
    
    try:
        macd = df.ta.macd(fast=12, slow=26, signal=9)
        if macd is not None and not macd.empty:
            df = pd.concat([df, macd], axis=1)
        else:
            df['MACDh_12_26_9'] = 0.0
    except:
        df['MACDh_12_26_9'] = 0.0

    safe_indicator('ATR', df.ta.atr(length=14))
    safe_indicator('MFI', df.ta.mfi(length=14))
    safe_indicator('CCI', df.ta.cci(length=14))
    
    try:
        adx = df.ta.adx(length=14)
        if adx is not None and not adx.empty:
            df = pd.concat([df, adx], axis=1)
        else:
            df['ADX_14'] = 0.0
    except:
        df['ADX_14'] = 0.0
    
    # Indicadores Extra
    safe_indicator('OBV', df.ta.obv())
    safe_indicator('WILLR', df.ta.willr(length=14))
    safe_indicator('MOM', df.ta.mom(length=10))
    
    # Medias y PSAR
    safe_indicator('SMA_50', df.ta.sma(length=50))
    safe_indicator('SMA_200', df.ta.sma(length=200))
    
    try:
        psar = df.ta.psar()
        if psar is not None and not psar.empty:
            df = pd.concat([df, psar], axis=1)
    except:
        pass 

    # --- Lógica Experimental (Divergencias Simplificadas) ---
    divergences = []
    try:
        last_rsi = df['RSI'].iloc[-1]
        prev_rsi = df['RSI'].iloc[-2]
        last_price = df['close'].iloc[-1]
        prev_price = df['close'].iloc[-2]
        
        # RSI Divergence
        if last_price > prev_price and last_rsi < prev_rsi:
            divergences.append("🐻RSI: Bearish div (Weak)")
        elif last_price < prev_price and last_rsi > prev_rsi:
            divergences.append("🐂RSI: Bullish div (Weak)")
            
        # Volume Trend
        vol_sma = df['volume'].rolling(window=20).mean()
        if df['volume'].iloc[-1] > vol_sma.iloc[-1]:
            divergences.append("🐂Volume: High Activity")
    except Exception:
        pass 
    
    # Devolvemos las últimas 3 filas y divergencias
    return df.iloc[-3:], divergences

def get_tradingview_analysis(symbol_pair, interval_str):
    """
    Obtiene análisis técnico básico usando la librería tradingview-ta.
    Actúa como fallback si la API de Binance falla o no tiene el par.
    """
    interval_map = {
        "1m": Interval.INTERVAL_1_MINUTE, "5m": Interval.INTERVAL_5_MINUTES,
        "15m": Interval.INTERVAL_15_MINUTES, "1h": Interval.INTERVAL_1_HOUR,
        "4h": Interval.INTERVAL_4_HOURS, "1d": Interval.INTERVAL_1_DAY,
        "1w": Interval.INTERVAL_1_WEEK, "1M": Interval.INTERVAL_1_MONTH
    }
    tv_interval = interval_map.get(interval_str, Interval.INTERVAL_1_HOUR)
    
    try:
        # Primer intento: Binance
        handler = TA_Handler(symbol=symbol_pair, screener="crypto", exchange="BINANCE", interval=tv_interval)
        analysis = handler.get_analysis()
    except Exception:
        try:
            # Segundo intento: GateIO (alternativa común)
            handler = TA_Handler(symbol=symbol_pair, screener="crypto", exchange="GATEIO", interval=tv_interval)
            analysis = handler.get_analysis()
        except Exception:
            return None

    if not analysis: return None

    ind = analysis.indicators
    
    # Normalizamos la respuesta para que coincida con la estructura que espera el comando
    return {
        'source': 'TradingView',
        'close': ind.get('close', 0),
        'open': ind.get('open', 0),
        'high': ind.get('high', 0),
        'low': ind.get('low', 0),
        'volume': ind.get('volume', 0),
        'RSI': ind.get('RSI', 0),
        'MACD_hist': ind.get('MACD.hist', 0) or ind.get('MACD_hist', 0),
        'MOM': ind.get('Mom', 0),
        'ATR': ind.get('ATR', 0),
        'CCI': ind.get('CCI20', 0),
        'ADX': ind.get('ADX', 0),
        'WR': ind.get('W.R', 0),
        'SMA_50': ind.get('SMA50', 0),
        'PSAR_val': ind.get('P.SAR', 0), # Guardamos directo en PSAR_val
        'Pivot': ind.get('Pivot.M.Classic.Middle', (ind['high'] + ind['low'] + ind['close'])/3),
        'R1': ind.get('Pivot.M.Classic.R1', 0),
        'R2': ind.get('Pivot.M.Classic.R2', 0),
        'S1': ind.get('Pivot.M.Classic.S1', 0),
        'S2': ind.get('Pivot.M.Classic.S2', 0),
    }

async def ta_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id # Usamos chat_id para verificar uso
    message = update.effective_message 

    # === GUARDIA DE PAGO ===
    acceso, mensaje = check_feature_access(chat_id, 'ta_limit')
    if not acceso:
        await message.reply_text(mensaje, parse_mode=ParseMode.MARKDOWN)
        return
    
    registrar_uso_comando(chat_id, 'ta')
    # =======================

    if not context.args:
        await message.reply_text(_("⚠️ Uso: `/ta <SYMBOL> [PAR] [TIME] [TV]`", user_id), parse_mode=ParseMode.MARKDOWN)
        return

    # Parseo de argumentos
    raw_args = [arg.upper() for arg in context.args]
    force_tv = False
    if 'TV' in raw_args:
        force_tv = True
        raw_args.remove('TV')
    
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
    
    msg_wait = await message.reply_text(f"⏳ _Analizando {full_symbol} ({timeframe})..._", parse_mode=ParseMode.MARKDOWN)
    loop = asyncio.get_running_loop()

    final_data = {}
    data_source = ""
    divergences_list = []

    # --- 1. INTENTO CON BINANCE ---
    df_result = None
    if not force_tv:
        try:
            df_result = await loop.run_in_executor(None, get_binance_klines, full_symbol, timeframe)
        except Exception:
            df_result = None
    
    if df_result is not None and not df_result.empty:
        data_source = "Binance"
        try:
            last_3_rows, divergences_list = await loop.run_in_executor(None, calculate_indicators_binance, df_result)
            
            curr = last_3_rows.iloc[-1]
            prev = last_3_rows.iloc[-2]
            pprev = last_3_rows.iloc[-3]
            
            p_close, p_high, p_low = curr['close'], curr['high'], curr['low']
            pivot = (p_high + p_low + p_close) / 3
            
            final_data = {
                'close': curr['close'],
                'volume': curr['volume'],
                'ATR': curr.get('ATR', 0),
                'RSI_list': [curr.get('RSI', 0), prev.get('RSI', 0), pprev.get('RSI', 0)],
                'MFI_list': [curr.get('MFI', 0), prev.get('MFI', 0), pprev.get('MFI', 0)],
                'CCI_list': [curr.get('CCI', 0), prev.get('CCI', 0), pprev.get('CCI', 0)],
                'ADX_list': [curr.get('ADX_14', 0), prev.get('ADX_14', 0), pprev.get('ADX_14', 0)],
                'WR_list':  [curr.get('WILLR', 0), prev.get('WILLR', 0), pprev.get('WILLR', 0)],
                'OBV_list': [curr.get('OBV', 0), prev.get('OBV', 0), pprev.get('OBV', 0)],
                'MACD_hist': curr.get('MACDh_12_26_9', 0),
                'SMA_50': curr.get('SMA_50', 0),
                'MOM': curr.get('MOM', 0),
                'PSAR_val': 0, 
                'Pivot': pivot,
                'R1': (2*pivot) - p_low, 'R2': pivot + (p_high - p_low),
                'S1': (2*pivot) - p_high, 'S2': pivot - (p_high - p_low)
            }
            
            for col in curr.index:
                if str(col).startswith('PSAR'):
                    final_data['PSAR_val'] = curr[col]
                    break
        except Exception:
            df_result = None

    # --- 2. FALLBACK TRADINGVIEW ---
    if df_result is None or df_result.empty:
        if not force_tv:
            try:
                await msg_wait.edit_text(_("⚠️ Binance sin datos. Probando TradingView...", user_id), parse_mode=ParseMode.MARKDOWN)
            except: pass
        
        try:
            tv_data = await loop.run_in_executor(None, get_tradingview_analysis, full_symbol, timeframe)
        except Exception:
            tv_data = None
        
        if tv_data:
            data_source = f"{tv_data['source']} (Fallback)"
            final_data = tv_data
            
            # --- CORRECCIÓN AQUÍ ---
            # Rellenamos con [val, 0, 0] para que salga "Valor | N/A | N/A"
            for k in ['RSI', 'MFI', 'CCI', 'ADX', 'WR']:
                val = final_data.get(k, 0) or 0
                final_data[f'{k}_list'] = [val, 0, 0] 
            
            final_data['OBV_list'] = [0, 0, 0]
            
            # Recalcular pivotes si TV devolvió 0
            if final_data.get('Pivot', 0) == 0 and final_data.get('close', 0) > 0:
                 p = (final_data['high'] + final_data['low'] + final_data['close']) / 3
                 final_data['Pivot'] = p
                 final_data['R1'] = (2*p) - final_data['low']
                 final_data['S1'] = (2*p) - final_data['high']
            
            divergences_list = ["⚠️ TV no entrega historial (solo Actual)."]
        else:
            await msg_wait.edit_text(_("❌ No se encontraron datos para *{s}*.".format(s=full_symbol), user_id), parse_mode=ParseMode.MARKDOWN)
            return

    # --- 3. GENERACIÓN DEL MENSAJE ---
    try:
        # --- NUEVA LÓGICA DE TABLA ---
        
        # Función auxiliar para formatear celdas de la tabla (ancho fijo)
        def fmt_cell(val, width=7):
            """Formatea un valor para que ocupe exactamente 'width' espacios."""
            if val is None or pd.isna(val) or val == 0:
                return "   --  ".center(width)
            try:
                f = float(val)
                # Si el número es muy grande (ej: CCI o OBV > 1000), usar notación 'k'
                if abs(f) > 10000: # 10k
                    return f"{f/1000:.1f}k".rjust(width)
                elif abs(f) > 999: # 3 digitos enteros, quitamos decimales
                    return f"{f:.0f}".rjust(width)
                else:
                    return f"{f:.2f}".rjust(width)
            except:
                return "   --  ".center(width)

        # Preparamos las filas para la tabla
        # (Nombre Indicador, Clave del diccionario)
        rows_config = [
            ("RSI", 'RSI_list'),
            ("MFI", 'MFI_list'),
            ("CCI", 'CCI_list'),
            ("WR%", 'WR_list'),
            ("ADX", 'ADX_list'),
            ("OBV", 'OBV_list')
        ]

        # Construimos la tabla usando Markdown de bloque de código (```) para alineación perfecta
        # Cabecera
        table_msg = "```text\n"
        table_msg += "IND   ACTUAL  PREVIO   ANT.\n"
        table_msg += "────  ─────  ─────  ─────\n"

        for label, key in rows_config:
            vals = final_data.get(key, [0, 0, 0])
            # Aseguramos que haya 3 valores
            if not vals or len(vals) < 3: vals = [0, 0, 0]
            
            # Formateamos cada celda
            c_act = fmt_cell(vals[0])
            c_pre = fmt_cell(vals[1])
            c_ant = fmt_cell(vals[2])
            
            table_msg += f"{label:<6} {c_act}  {c_pre}  {c_ant}\n"
        
        table_msg += "```"
        # -----------------------------

        # Recuperamos valores individuales para el resumen inferior
        curr_rsi = final_data.get('RSI_list', [0])[0]
        curr_macd = final_data.get('MACD_hist', 0)
        curr_mom = final_data.get('MOM', 0)
        price = final_data.get('close', 0)
        
        # SMA Logic
        sma_50 = final_data.get('SMA_50', 0)
        sma_str = "N/A"
        if sma_50 and sma_50 > 0:
            sma_str = 'Price > SMA (Bull)' if price > sma_50 else 'Price < SMA (Bear)'

        # PSAR Logic
        psar_val = final_data.get('PSAR_val', 0)
        psar_str = "Neutral"
        psar_icon = "⚪️"
        if psar_val and not pd.isna(psar_val) and psar_val != 0:
            psar_str = "Bullish" if psar_val < price else "Bearish"
            psar_icon = "✅" if psar_str == "Bullish" else "❌"

        # Función simple para iconos (ya no se usan dentro de la tabla, pero sí abajo)
        def get_icon_simple(val, type_):
            try:
                if val is None or pd.isna(val) or val == 0: return "⚪️"
                val = float(val)
                if type_ == 'RSI': return "⚠️" if val > 70 or val < 30 else "✅"
                if type_ == 'MACD': return "✅" if val > 0 else "🔻"
                if type_ == 'MOM': return "✅" if val > 0 else "🔻"
            except: return "⚪️"
            return "⚪️"

        # Armado del mensaje final
        msg = (
            f"📊 *Análisis Técnico:  {full_symbol}\n*"
            f"—————————————————\n"
            f"*Temporalidad:*  {timeframe}\n"
            f"*Fuente:*  _{data_source}_\n"
            f"•\n"
            f"💰 *Precio:* `${price:,.4f}`\n"
            f"📉 *ATR:* `{final_data.get('ATR', 0) or 0:.4f}`\n•\n"
            f"{table_msg}\n•\n"            
            f"🧐 *Tendencia y Momentum*\n"
            f"{get_icon_simple(curr_mom, 'MOM')} *MOM:* {'Bullish' if (curr_mom or 0) > 0 else 'Bearish'}\n"
            f"📊 *SMA (50):* {sma_str}\n"
            f"{get_icon_simple(curr_macd, 'MACD')} *MACD:* {'Bullish' if (curr_macd or 0) > 0 else 'Bearish'}\n"
            f"{psar_icon} *PSAR:* {psar_str}\n•\n"
            f"🛡 *Soportes y Resistencias*\n"
            f"R2: `${final_data.get('R2', 0) or 0:.4f}`\n"
            f"R1: `${final_data.get('R1', 0) or 0:.4f}`\n"
            f"🎯 Pivot: `${final_data.get('Pivot', 0) or 0:.4f}`\n"
            f"S1: `${final_data.get('S1', 0) or 0:.4f}`\n"
            f"S2: `${final_data.get('S2', 0) or 0:.4f}`\n•"
        )

        msg += "\nEXPERIMENTAL 🧪\n"
        if divergences_list:
            for div in divergences_list:
                msg += f"{div}\n"
        else:
            msg += "⚪️ No major divergences detected\n"

        msg += get_random_ad_text()
        
        await msg_wait.edit_text(msg, parse_mode=ParseMode.MARKDOWN)

    except Exception as e:
        # Es bueno imprimir el error en consola para depurar
        print(f"Error en TA Command Formating: {e}") 
        error_text = _("❌ Error inesperado generando gráfico: {e}", user_id).format(e=e)
        try:
            await msg_wait.edit_text(error_text)
        except:
            await message.reply_text(error_text)
