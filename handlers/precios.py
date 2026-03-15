# handlers/precios.py

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
from utils.user_data import obtener_monedAS_usuario, actualizar_monedAS
from core.api_client import obtener_precios_control
from utils.ads_manager import get_random_ad_text
from core.i18n import _


async def show_prices(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Muestra precios de la lista del usuario."""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    # Obtener monedas del usuario
    monedas = obtener_monedAS_usuario(chat_id)
    
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


async def show_specific_price(update: Update, context: ContextTypes.DEFAULT_TYPE, symbol: str) -> None:
    """Muestra el precio de una moneda específica."""
    user_id = update.effective_user.id
    
    msg = await update.message.reply_text(
        _(f"⏳ Consultando {symbol}...", user_id)
    )
    
    precios = obtener_precios_control([symbol])
    precio = precios.get(symbol) if precios else None
    
    if precio:
        await msg.edit_text(
            f"💰 *{symbol}/USD*: ${precio:,.4f}",
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await msg.edit_text(
            _(f"❌ No se pudo obtener el precio de {symbol}", user_id),
            parse_mode=ParseMode.MARKDOWN
        )


async def show_price_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Muestra la lista de monedas del usuario."""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    monedas = obtener_monedAS_usuario(chat_id)
    
    if not monedas:
        await update.message.reply_text(
            _(
                "📝 *Tu lista está vacía*\n\n"
                "Usa `/precios add BTC,ETH` para añadir",
                user_id
            ),
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    mensaje = _("📋 *Tu Lista de Monedas:*\n\n", user_id)
    mensaje += " • ".join(moneda)
    mensaje += f"\n\n_Edita con: /precios add/rem_"
    
    await update.message.reply_text(
        mensaje,
        parse_mode=ParseMode.MARKDOWN
    )


async def add_prices(update: Update, context: ContextTypes.DEFAULT_TYPE, coins: list) -> None:
    """Añade monedas a la lista del usuario."""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    if not coins:
        await update.message.reply_text(
            _(
                "⚠️ *Uso incorrecto*\n\n"
                "Usa: `/precios add BTC,ETH,HIVE`",
                user_id
            ),
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    nuevas = []
    for coin_arg in coins:
        nuevas.extend([c.strip().upper() for c in coin_arg.split(",") if c.strip()])
    
    actuales = obtener_monedAS_usuario(chat_id)
    
    añadidas = []
    for m in nuevas:
        if m not in actuales:
            actuales.append(m)
            añadidas.append(m)
    
    actualizar_monedAS(chat_id, actuales)
    
    if añadidas:
        await update.message.reply_text(
            _(f"✅ *Añadidas:* {', '.join(añadidas)}\n\n"
              f"📋 *Tu lista:* {', '.join(actuales)}",
              user_id),
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await update.message.reply_text(
            _(f"ℹ️ *Ya estaban en tu lista:* {', '.join(nuevas)}",
              user_id),
            parse_mode=ParseMode.MARKDOWN
        )


async def remove_prices(update: Update, context: ContextTypes.DEFAULT_TYPE, coins: list) -> None:
    """Quita monedas de la lista del usuario."""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    if not coins:
        await update.message.reply_text(
            _(
                "⚠️ *Uso incorrecto*\n\n"
                "Usa: `/precios remove BTC`",
                user_id
            ),
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    quitar = []
    for coin_arg in coins:
        quitar.extend([c.strip().upper() for c in coin_arg.split(",") if c.strip()])
    
    actuales = obtener_monedAS_usuario(chat_id)
    
    eliminadas = []
    for m in quitar:
        if m in actuales:
            actuales.remove(m)
            eliminadas.append(m)
    
    actualizar_monedAS(chat_id, actuales)
    
    if eliminadas:
        await update.message.reply_text(
            _(f"✅ *Eliminadas:* {', '.join(eliminadas)}\n\n"
              f"📋 *Tu lista:* {', '.join(actuales) if actuales else '(vacía)'}",
              user_id),
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await update.message.reply_text(
            _(f"ℹ️ *No estaban en tu lista:* {', '.join(quitar)}",
              user_id),
            parse_mode=ParseMode.MARKDOWN
        )


async def precios_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Maneja callbacks de los botones inline de precios."""
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data == "precios_add":
        await query.edit_message_text(
            "➕ *Añadir Monedas*\n\n"
            "Usa: `/precios add BTC,ETH,HIVE`",
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "precios_lista":
        await show_price_list(update, context)
