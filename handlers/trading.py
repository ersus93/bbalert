# handlers/trading.py

import asyncio
import requests # Usaremos requests en lugar de Selenium
import json
import pytz 
from io import BytesIO
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from datetime import timedelta, datetime
from core.config import SCREENSHOT_API_KEY, ADMIN_CHAT_IDS # <--- IMPORTANTE: AÑADIDO ADMIN_CHAT_IDS
from core.api_client import obtener_datos_moneda, obtener_tasas_eltoque
from utils.file_manager import add_log_line, load_eltoque_history, save_eltoque_history
from utils.ads_manager import get_random_ad_text
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


# Nuevo comando para mostrar tasas de ElToque con Lógica de Reintento
async def eltoque_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Muestra las tasas de cambio de eltoque.com.
    Maneja reintentos si la API está saturada.
    """
    user_id = update.effective_user.id
    
    # 1. Primer intento de llamada a la API
    tasas_data = obtener_tasas_eltoque()
    mensaje_espera = None # Variable para guardar el mensaje temporal

    # 2. ### NUEVO: Si falla el primer intento, entramos en modo reintento
    if not tasas_data:
        # Enviamos mensaje de "Conectando..."
        texto_conectando = _("⏳ Estamos conectando con elToque...", user_id)
        mensaje_espera = await update.message.reply_text(texto_conectando)
        
        # Intentamos 3 veces más, esperando 2 segundos entre cada una
        MAX_RETRIES = 3
        for i in range(MAX_RETRIES):
            await asyncio.sleep(2) # Espera 2 segundos
            tasas_data = obtener_tasas_eltoque()
            
            # Si obtenemos datos, rompemos el bucle
            if tasas_data:
                break
    
    # 3. ### NUEVO: Evaluación Final tras los intentos
    if not tasas_data:
        # --- CASO DE FALLO TOTAL ---
        
        # Mensaje amigable para el usuario
        mensaje_error_usuario = _(
            "⚠️ *Error de Conexión*\n\n"
            "No pudimos conectar con elToque en este momento.\n"
            "Posiblemente su servidor esté saturado o caído.\n\n"
            "👮‍♂️ _Los administradores han sido notificados._",
            user_id
        )
        
        # Si ya había mensaje de espera, lo editamos. Si no, enviamos uno nuevo.
        if mensaje_espera:
            await mensaje_espera.edit_text(mensaje_error_usuario, parse_mode=ParseMode.MARKDOWN)
        else:
            await update.message.reply_text(mensaje_error_usuario, parse_mode=ParseMode.MARKDOWN)

        # Mensaje Técnico para los ADMINISTRADORES
        mensaje_admin = (
            f"⚠️ *Alerta de API ElToque*\n\n"
            f"El usuario `{user_id}` intentó usar /tasa y falló tras 4 intentos (1 inicial + 3 reintentos).\n"
            f"Causa probable: API caída, Timeout o Rate Limit."
        )
        
        # Enviar alerta a todos los admins
        for admin_id in ADMIN_CHAT_IDS:
            try:
                await context.bot.send_message(chat_id=admin_id, text=mensaje_admin, parse_mode=ParseMode.MARKDOWN)
            except Exception:
                pass # Si falla enviar al admin, no detenemos el flujo
        
        return # Terminamos aquí si falló

    # --- CASO DE ÉXITO ---
    
    # Si teníamos un mensaje de "Conectando...", lo borramos para limpiar el chat
    if mensaje_espera:
        try:
            await mensaje_espera.delete()
        except Exception:
            pass # Si no se puede borrar (raro), no importa

    # A partir de aquí sigue la lógica normal de formateo y guardado
    try:
        tasas_actuales = tasas_data.get('tasas')
        tasas_anteriores = load_eltoque_history()

        if not tasas_actuales or not isinstance(tasas_actuales, dict):
            # Error de formato en la respuesta JSON
            await update.message.reply_text(_("😕 Error de formato en datos de ElToque.", user_id))
            return

        fecha = tasas_data.get('date', '')
        hora = tasas_data.get('hour', 0)
        minutos = tasas_data.get('minutes', 0)
        timestamp_str = f"{fecha} {hora:02d}:{minutos:02d}"

        mensaje_titulo = _("🏦 *Tasas de Cambio* (Informal)\n—————————————————\n\n", user_id)
        mensaje_lineas = []
            
        monedas_ordenadas = [
              'ECU', 'USD', 'MLC', 'ZELLE', 'CLA', 
              'CAD', 'MXN', 'BRL', 'BTC', 'TRX', 'USDT_TRC20'
          ]
            
        TOLERANCIA = 0.0001
            
        for moneda_key in monedas_ordenadas:
            if moneda_key in tasas_actuales:
                tasa_actual = tasas_actuales[moneda_key]
                tasa_anterior = tasas_anteriores.get(moneda_key)
                    
                if moneda_key == 'USDT_TRC20':
                 moneda_display = 'USDT'
                elif moneda_key == 'ECU':
                    moneda_display = 'EUR'
                else:
                    moneda_display = moneda_key
                    
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

        if not mensaje_lineas:
            return

        mensaje_final = mensaje_titulo + "\n".join(mensaje_lineas)

        actualizado_label = _("Actualizado:", user_id)
        fuente_label = _("Fuente: elTOQUE.com", user_id)

        mensaje_final += f"\n\n—————————————————\n_{actualizado_label} {timestamp_str}_\n_{fuente_label}_"
        
        # --- INYECCIÓN DE ANUNCIO ---
        mensaje_final += get_random_ad_text()
        # ----------------------------

        await update.message.reply_text(mensaje_final, parse_mode=ParseMode.MARKDOWN)

        save_eltoque_history(tasas_actuales)

    except Exception as e:
        add_log_line(f"Error fatal procesando datos de ElToque con historial: {e}.")
        mensaje_error_inesperado = _("❌ Ocurrió un error inesperado procesando los datos.", user_id)
        await update.message.reply_text(mensaje_error_inesperado, parse_mode=ParseMode.MARKDOWN)

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