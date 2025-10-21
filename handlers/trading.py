# handlers/trading.py

import asyncio
import requests # Usaremos requests en lugar de Selenium
from io import BytesIO
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from core.config import SCREENSHOT_API_KEY # Importamos nuestra nueva API Key

def _take_screenshot_sync(url: str) -> BytesIO | None:
    """
    Función síncrona que toma la captura de pantalla usando screenshotapi.net.
    """
    if not SCREENSHOT_API_KEY:
        print("❌ Error: La SCREENSHOT_API_KEY no está configurada en config.py.")
        return None

    # Parámetros para la API de captura de pantalla
    api_url = "https://shot.screenshotapi.net/screenshot"
    params = {
        "token": SCREENSHOT_API_KEY,
        "url": url,
        "width": 1280,
        "height": 720,
        "output": "image",
        "file_type": "png",
        "wait_for_event": "load",
        # Este selector ayuda a la API a esperar a que el gráfico cargue
        "selector": "div.chart-widget"
    }

    try:
        # Hacemos la petición a la API
        response = requests.get(api_url, params=params, timeout=30) # Aumentamos el timeout
        response.raise_for_status() # Lanza un error si la petición falló (ej. 4xx, 5xx)

        # La respuesta de la API es la imagen directamente
        return BytesIO(response.content)

    except requests.exceptions.RequestException as e:
        print(f"Error al llamar a la API de capturas de pantalla: {e}")
        return None

async def take_chart_screenshot(url: str) -> BytesIO | None:
    """Ejecuta la función de captura de pantalla en un executor para no bloquear el bucle de asyncio."""
    loop = asyncio.get_running_loop()
    try:
        # to_thread es la forma moderna de hacerlo en Python 3.9+
        return await asyncio.to_thread(_take_screenshot_sync, url)
    except Exception as e:
        print(f"Error al ejecutar el hilo de la captura de pantalla: {e}")
        return None

async def graf_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Genera una captura de pantalla de un gráfico de TradingView.
    Uso: /graf <MONEDA> <TEMPORALIDAD>
    Ejemplo: /graf BTC 1h
    """
    
    # --- CORRECCIÓN ---
    # La importación de 'obtener_datos_moneda' se eliminó de aquí.
    
    if len(context.args) != 2:
        await update.message.reply_text(
            "⚠️ *Formato incorrecto*.\n\nUso: `/graf <MONEDA> <TEMPORALIDAD>`\n"
            "Ejemplo: `/graf BTC 15m`",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    moneda = context.args[0].upper()
    temporalidad = context.args[1].lower()

    map_temporalidad = {
        "1m": "1", "3m": "3", "5m": "5", "15m": "15", "30m": "30",
        "1h": "60", "2h": "120", "4h": "240",
        "1d": "D", "1w": "W", "1M": "M"
    }

    intervalo = map_temporalidad.get(temporalidad)
    if not intervalo:
        await update.message.reply_text(
            "⚠️ *Temporalidad no válida*.\n\n"
            "Usa: 1m, 5m, 15m, 1h, 4h, 1d, 1w, 1M.",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    url = f"https://www.tradingview.com/chart/?symbol=BINANCE:{moneda}USDT&interval={intervalo}"
    
    await update.message.reply_text(f"⏳ Generando gráfico para *{moneda}* ({temporalidad})...", parse_mode=ParseMode.MARKDOWN)

    screenshot_bytes = await take_chart_screenshot(url)
    
    if screenshot_bytes:
        mensaje = f"📈 *Gráfico de {moneda}/USDT ({temporalidad})*\n\n[Ver en TradingView]({url})"
        await update.message.reply_photo(
            photo=screenshot_bytes,
            caption=mensaje,
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await update.message.reply_text(
            "❌ Lo siento, no pude generar la captura del gráfico en este momento. Inténtalo de nuevo más tarde.",
            parse_mode=ParseMode.MARKDOWN
        )

async def p_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Muestra el precio y otros datos de una criptomoneda.
    Uso: /p <MONEDA>
    Ejemplo: /p BTC
    """
    
    # --- CORRECCIÓN ---
    # La importación se movió aquí para evitar la dependencia circular.
    from core.api_client import obtener_datos_moneda
    
    if not context.args:
        await update.message.reply_text(
            "⚠️ *Formato incorrecto*.\n\nUso: `/p <MONEDA>`\n"
            "Ejemplo: `/p BTC`",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    moneda = context.args[0].upper()
    datos = obtener_datos_moneda(moneda)

    if not datos:
        await update.message.reply_text(f"😕 No se pudieron obtener los datos para *{moneda}*.", parse_mode=ParseMode.MARKDOWN)
        return

    def format_change(change):
        if change > 0.5:
            return f"+{change:.2f}%   😄"
        elif change > -0.5:
            return f"{change:.2f}%   😕"
        elif change > -5:
            return f"{change:.2f}%   😔"
        else:
            return f"{change:.2f}%   😢"

    mensaje = (
        f"*{datos['symbol']}*\n"
        f"${datos['price']:,.2f}\n"
        f"Ξ: {datos['price_eth']:.8f}\n"
        f"H|L: {datos['high_24h']:,.2f}|{datos['low_24h']:,.2f}\n"
        f"1h {format_change(datos['percent_change_1h'])}\n"
        f"24h {format_change(datos['percent_change_24h'])}\n"
        f"7d {format_change(datos['percent_change_7d'])}\n"
        f"Cap: {datos['market_cap_rank']}st | ${datos['market_cap']:,.0f}\n"
        f"Vol: ${datos['volume_24h']:,.0f}"
    )

    await update.message.reply_text(f"{mensaje}", parse_mode=ParseMode.MARKDOWN)