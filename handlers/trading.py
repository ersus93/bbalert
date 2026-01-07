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
        await update.message.reply_text(
            _("⚠️ *Formato incorrecto*.\nUso: `/p <MONEDA>` (ej: `/p BTC`)", user_id),
            parse_mode=ParseMode.MARKDOWN
        )
        return

    moneda = context.args[0].upper()
    
    # Notificar que estamos 'escribiendo' para dar feedback visual si tarda la API
    await update.message.reply_chat_action("typing")
    
    datos = obtener_datos_moneda(moneda)

    if not datos:
        await update.message.reply_text(
            _("😕 No se pudieron obtener los datos para *{moneda}*.", user_id).format(moneda=moneda),
            parse_mode=ParseMode.MARKDOWN
        )
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

    # Botón de actualizar
    btn_text = _("🔄 Actualizar /p {symbol}", user_id).format(symbol=datos['symbol'])
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(btn_text, callback_data=f"refresh_{datos['symbol']}")]
    ])

    message = update.message or update.callback_query.message
    
    # Enviar o Editar (si viene de un botón refresh)
    # Nota: Si es nuevo mensaje usa reply_text, si es refresh a veces es mejor editar, 
    # pero reply_text es más seguro para evitar errores de "mensaje no modificado".
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