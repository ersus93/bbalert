# handlers/trading.py

import asyncio
import requests # Usaremos requests en lugar de Selenium
import json
from io import BytesIO
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from core.config import SCREENSHOT_API_KEY # Importamos nuestra nueva API Key
from core.api_client import obtener_datos_moneda, obtener_tasas_eltoque
from utils.file_manager import add_log_line, load_eltoque_history, save_eltoque_history
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
    Ejemplos:
        /graf BTC 1h
        /graf BTC USDT 1h
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
    Ejemplo: /p BTC
    """
    user_id = update.effective_user.id
    
    
    from core.api_client import obtener_datos_moneda
    
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
    # etiqueta_hl = _("H|L:", user_id)
    etiqueta_cap = _("Cap:", user_id)
    etiqueta_vol = _("Vol:", user_id)

    mensaje = (
        f"*{datos['symbol']}*\n"
        f"${datos['price']:,.4f}\n"
        f"{etiqueta_eth} {datos['price_eth']:.8f}\n"
        f"{etiqueta_btc} {datos['price_btc']:.8f}\n"
        # f"{etiqueta_hl} {datos['high_24h']:,.4f}|{datos['low_24h']:,.4f}\n"
        f"1h {format_change(datos['percent_change_1h'])}\n"
        f"24h {format_change(datos['percent_change_24h'])}\n"
        f"7d {format_change(datos['percent_change_7d'])}\n"
        f"{etiqueta_cap} {datos['market_cap_rank']}st | ${datos['market_cap']:,.0f}\n"
        f"{etiqueta_vol} ${datos['volume_24h']:,.0f}\n"
    )

    # 🔘 Botón para relanzar el comando
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


# Nuevo comando para mostrar tasas de ElToque
async def eltoque_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Muestra las tasas de cambio de eltoque.com.
    Comando: /tasa
    """
    user_id = update.effective_user.id

    # 1. Llamar a la API
    tasas_data = obtener_tasas_eltoque()

    # 2. Manejar si la API falla
    if not tasas_data:
        mensaje_error = _(
            "❌ *FALLO TOTAL*\n\n"
            "La API de ElToque no devolvió ningún dato (`None`).\n\n"
            "**Causas probables:**\n"
            "1. La `ELTOQUE_API_KEY` en tu archivo `apit.env` es incorrecta o está vacía.\n"
            "2. La API de ElToque está caída o bloqueó tu solicitud.",
            user_id
        )
        await update.message.reply_text(mensaje_error, parse_mode=ParseMode.MARKDOWN)
        return

    # --- INICIO DE LA LÓGICA CON HISTORIAL ---
    try:
        # 3. Cargar tasas actuales y anteriores
        tasas_actuales = tasas_data.get('tasas')
        tasas_anteriores = load_eltoque_history() # ¡Cargamos el historial!

        if not tasas_actuales or not isinstance(tasas_actuales, dict):
            mensaje_error_formato = _(
                "😕 Se obtuvieron datos de ElToque, pero no se encontró el diccionario 'tasas' esperado.",
                user_id
            )
            await update.message.reply_text(mensaje_error_formato, parse_mode=ParseMode.MARKDOWN)
            return

        # Extraer la fecha y hora de la actualización
        fecha = tasas_data.get('date', '')
        hora = tasas_data.get('hour', 0)
        minutos = tasas_data.get('minutes', 0)
        timestamp_str = f"{fecha} {hora:02d}:{minutos:02d}"

        # --- 4. Formateo del mensaje ---
        mensaje_titulo = _("🏦 *Tasas de Cambio CUP*\n\n", user_id)
        mensaje_lineas = []
            
        # Lista de monedas en el orden deseado por el usuario
        monedas_ordenadas = [
              'ECU', 'USD', 'MLC', 'ZELLE', 'CLA', 
              'CAD', 'MXN', 'BRL', 'BTC', 'TRX', 'USDT_TRC20'
          ]
            
        TOLERANCIA = 0.0001 # Para evitar cambios por ruido
            
        for moneda_key in monedas_ordenadas:
            if moneda_key in tasas_actuales:
                tasa_actual = tasas_actuales[moneda_key]
                tasa_anterior = tasas_anteriores.get(moneda_key)
                    
                # --- INICIO DE LA MODIFICACIÓN ---
                # Renombrar 'USDT_TRC20' a 'USDT' y 'ECU' a 'EUR'
                if moneda_key == 'USDT_TRC20':
                 moneda_display = 'USDT'
                elif moneda_key == 'ECU':
                    moneda_display = 'EUR'
                else:
                    moneda_display = moneda_key
                # --- FIN DE LA MODIFICACIÓN ---
                    
                indicador = ""
                cambio_str = ""

                if tasa_anterior is not None:
                    diferencia = tasa_actual - tasa_anterior
                      
                    if diferencia > TOLERANCIA:
                        indicador = "🔺"
                        cambio_str = f" +{diferencia:,.2f}"
                    elif diferencia < -TOLERANCIA:
                        indicador = "🔻"
                        cambio_str = f" {diferencia:,.2f}" # Ya tiene el '-'
                    
                # Formato: EUR:   500.00 CUP
                linea = f"*{moneda_display}*:  `{tasa_actual:,.2f}`  CUP  {indicador}{cambio_str}"
                mensaje_lineas.append(linea)

        if not mensaje_lineas:
            # ... (Manejo de error si 'tasas' estaba vacío) ...
            return

        mensaje_final = mensaje_titulo + "\n".join(mensaje_lineas)

        # 5. Añadir pie de página
        actualizado_label = _("Actualizado:", user_id)
        fuente_label = _("Fuente: elTOQUE.com", user_id)

        mensaje_final += f"\n\n_{actualizado_label} {timestamp_str}_\n_{fuente_label}_"

        await update.message.reply_text(mensaje_final, parse_mode=ParseMode.MARKDOWN)

        # 6. ¡GUARDAR LAS NUEVAS TASAS!
        save_eltoque_history(tasas_actuales)

    except Exception as e:
        add_log_line(f"Error fatal procesando datos de ElToque con historial: {e}. Datos: {tasas_data}")
        mensaje_error_inesperado = _("❌ Ocurrió un error inesperado procesando los datos de ElToque.", user_id)
        await update.message.reply_text(mensaje_error_inesperADO, parse_mode=ParseMode.MARKDOWN)