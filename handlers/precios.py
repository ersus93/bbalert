# handlers/precios.py

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
from utils.file_manager import obtener_monedas_usuario
from core.api_client import obtener_precios_control
from utils.ads_manager import get_random_ad_text
from core.i18n import _


async def show_prices(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Muestra precios de la lista del usuario."""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    # Obtener monedas del usuario
    monedas = obtener_monedas_usuario(chat_id)
    
    if not monedas:
        await update.message.reply_text(
            _(
                "📝 *Tu lista está vacía*\n\n"
                "Añade monedas con:\n"
                "`/precios add BTC,ETH,HIVE`\n\n"
                "O consulta una moneda específica:\n"
                "`/precios BTC`",
                user_id
            ),
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # Notificar que estamos cargando - PROGRESS FEEDBACK
    msg = await update.message.reply_text(
        "⏳ *Consultando precios...*",
        parse_mode=ParseMode.MARKDOWN
    )
    
    # Obtener precios
    try:
        precios = obtener_precios_control(monedas)
    except Exception as e:
        await msg.edit_text(
            f"⚠️ *Error al consultar precios*\n\n"
            f"Detalles: {str(e)[:100]}\n\n"
            f"Intenta de nuevo en unos segundos.",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    if not precios:
        await msg.edit_text(
            "❌ *Sin datos disponibles*\n\n"
            "No se pudieron obtener los precios en este momento.\n\n"
            "Intenta de nuevo más tarde.",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # Construir mensaje con indicadores visuales
    from datetime import datetime
    mensaje = "📊 *Precios Actuales:*\n" + "─" * 20 + "\n\n"
    
    for moneda in monedas:
        p = precios.get(moneda)
        if p:
            # Indicador de precio (flecha hacia arriba, abajo, o estable)
            emoji = "📈"  # default up
            mensaje += f"{emoji} *{moneda}*: `${p:,.4f}`\n"
        else:
            mensaje += f"⚠️ *{moneda}*: N/A\n"
    
    mensaje += "\n" + "─" * 20 + "\n"
    mensaje += f"_🕐 {datetime.now().strftime('%H:%M')}_\n"
    mensaje += get_random_ad_text()
    
    # Añadir botones de acción
    keyboard = [
        [InlineKeyboardButton("➕ Añadir", callback_data="precios_add")],
        [InlineKeyboardButton("📋 Mi Lista", callback_data="precios_lista")]
    ]
    
    await msg.edit_text(
        mensaje,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )