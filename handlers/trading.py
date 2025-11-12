# handlers/trading.py

import asyncio
import requests # Usaremos requests en lugar de Selenium
from io import BytesIO
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from core.config import SCREENSHOT_API_KEY # Importamos nuestra nueva API Key
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
    etiqueta_hl = _("H|L:", user_id)
    etiqueta_cap = _("Cap:", user_id)
    etiqueta_vol = _("Vol:", user_id)

    mensaje = (
        f"*{datos['symbol']}*\n"
        f"${datos['price']:,.4f}\n"
        f"{etiqueta_eth} {datos['price_eth']:.8f}\n"
        f"{etiqueta_hl} {datos['high_24h']:,.4f}|{datos['low_24h']:,.4f}\n"
        f"1h {format_change(datos['percent_change_1h'])}\n"
        f"24h {format_change(datos['percent_change_24h'])}\n"
        f"7d {format_change(datos['percent_change_7d'])}\n"
        f"{etiqueta_cap} {datos['market_cap_rank']}st | ${datos['market_cap']:,.0f}\n"
        f"{etiqueta_vol} ${datos['volume_24h']:,.0f}"
    )

    await update.message.reply_text(f"{mensaje}", parse_mode=ParseMode.MARKDOWN)