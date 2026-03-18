# handlers/alertas.py
"""
Handler unificado para comandos de alertas.
Unifica: /alerta, /valerts, /btcalerts

Sintaxis:
  /alertas              - Ver mis alertas
  /alertas add BTC 50000 - Crear alerta
  /alertas remove 1     - Eliminar alerta
  /alertas clear        - Eliminar todas
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from telegram.constants import ParseMode

from utils.file_manager import delete_all_alerts
from utils.alert_manager import (
    add_price_alert,
    get_user_alerts,
    delete_price_alert,
)
from utils.user_data import registrar_usuario
from utils.logger import logger
from core.i18n import _


async def alertas_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Comando unificado /alertas.
    """
    user_id = update.effective_user.id
    args = context.args
    
    # Registrar usuario
    registrar_usuario(user_id, update.effective_user.language_code)
    
    # Obtener acción
    action = args[0].lower() if args else None
    
    if action == "add":
        # /alertas add BTC 50000
        await create_alert(update, context, args[1:] if len(args) > 1 else [])
        return
    
    if action == "remove" or action == "del":
        # /alertas remove 1
        await remove_alert(update, context, args[1:] if len(args) > 1 else [])
        return
    
    if action == "clear" or action == "borrar":
        # /alertas clear - eliminar todas
        await clear_alerts(update, context)
        return
    
    # Sin argumentos - mostrar alertas
    await show_alerts(update, context)


async def show_alerts(update: Update, context: ContextTypes.DEFAULT_TYPE, query=None) -> None:
    """Muestra las alertas del usuario con botones inline para eliminar."""
    user_id = update.effective_user.id

    alertas = get_user_alerts(user_id)

    if not alertas:
        keyboard = [[
            InlineKeyboardButton(
                "➕ Crear mi primera alerta",
                callback_data="alertas_add_help"
            )
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        text = _(
            "🔔 *Sin alertas*\n\n"
            "Crea una alerta fácilmente:\n"
            "`/alertas add BTC 50000`\n\n"
            "O usa el botón de abajo para más ayuda.",
            user_id
        )
        if query:
            await query.edit_message_text(
                text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await update.message.reply_text(
                text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
        return

    mensaje = _("🚨 *Tus Alertas:*\n\n", user_id)
    keyboard = []

    for i, alerta in enumerate(alertas, 1):
        symbol = alerta.get('coin', 'N/A')
        price = alerta.get('target_price', 0)
        status = alerta.get('status', 'active')
        alert_id = alerta.get('id')
        condition = alerta.get('condition', 'ABOVE')

        emoji = "✅" if status == "triggered" else "🔔"
        direction_text = 'cruce arriba' if condition == 'ABOVE' else 'cruce abajo'
        mensaje += f"{i}. {emoji} *{symbol}* {direction_text} ${price:,.4f}\n"

        # Agregar botón para eliminar esta alerta
        keyboard.append([
            InlineKeyboardButton(
                f"🗑️ Eliminar #{i} ({symbol})",
                callback_data=f"delete_alert_{alert_id}"
            )
        ])

    # Agregar botón para eliminar todas
    keyboard.append([
        InlineKeyboardButton(
            "🗑️ Eliminar TODAS las alertas",
            callback_data="delete_all_alerts"
        )
    ])

    # Agregar botón para crear nueva alerta
    keyboard.append([
        InlineKeyboardButton(
            "➕ Crear nueva alerta",
            callback_data="alertas_add_help"
        )
    ])

    reply_markup = InlineKeyboardMarkup(keyboard)

    if query:
        await query.edit_message_text(
            mensaje,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await update.message.reply_text(
            mensaje,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )


async def create_alert(update: Update, context: ContextTypes.DEFAULT_TYPE, args: list) -> None:
    """Crea una nueva alerta."""
    user_id = update.effective_user.id

    if len(args) < 2:
        keyboard = [[
            InlineKeyboardButton(
                "⬅️ Volver a mis alertas",
                callback_data="alertas_back"
            )
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            _(
                "⚠️ *Uso incorrecto*\n\n"
                "Usa: `/alertas add BTC 50000`\n\n"
                "Ejemplo: `/alertas add ETH 3500`",
                user_id
            ),
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        return

    symbol = args[0].upper()

    try:
        price = float(args[1].replace(',', ''))
    except ValueError:
        keyboard = [[
            InlineKeyboardButton(
                "⬅️ Volver a mis alertas",
                callback_data="alertas_back"
            )
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            _(f"⚠️ Precio inválido: {args[1]}", user_id),
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        return

    # Crear alerta
    alert_id = add_price_alert(user_id, symbol, price)

    if alert_id:
        keyboard = [[
            InlineKeyboardButton(
                "📋 Ver mis alertas",
                callback_data="alertas_back"
            ),
            InlineKeyboardButton(
                "➕ Crear otra alerta",
                callback_data="alertas_add_help"
            )
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            _(f"✅ *Alerta creada*\n\n"
              f"🔔 {symbol} @ ${price:,.4f}\n\n"
              f"ID: `{alert_id}`\n\n"
              f"_Recibirás notificaciones cuando el precio cruce este nivel._",
              user_id),
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        keyboard = [[
            InlineKeyboardButton(
                "⬅️ Volver a mis alertas",
                callback_data="alertas_back"
            )
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            _("❌ Error al crear alerta", user_id),
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )


async def remove_alert(update: Update, context: ContextTypes.DEFAULT_TYPE, args: list) -> None:
    """Elimina una alerta específica."""
    user_id = update.effective_user.id

    if not args:
        keyboard = [[
            InlineKeyboardButton(
                "📋 Ver mis alertas",
                callback_data="alertas_back"
            )
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            _(
                "⚠️ *Uso incorrecto*\n\n"
                "Usa: `/alertas remove 1`\n\n"
                "O usa los botones inline para eliminar más fácilmente.",
                user_id
            ),
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        return

    try:
        index = int(args[0])
    except ValueError:
        keyboard = [[
            InlineKeyboardButton(
                "📋 Ver mis alertas",
                callback_data="alertas_back"
            )
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            _(f"⚠️ Índice inválido: {args[0]}", user_id),
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        return

    # Obtener alertas actuales
    alertas = get_user_alerts(user_id)

    if not alertas or index < 1 or index > len(alertas):
        keyboard = [[
            InlineKeyboardButton(
                "📋 Ver mis alertas",
                callback_data="alertas_back"
            )
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            _("⚠️ Índice fuera de rango", user_id),
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        return

    # Eliminar (índice - 1 para array)
    alerta = alertas[index - 1]
    alert_id = alerta.get('id')

    keyboard = [[
        InlineKeyboardButton(
            "📋 Ver mis alertas",
            callback_data="alertas_back"
        ),
        InlineKeyboardButton(
            "➕ Crear nueva alerta",
            callback_data="alertas_add_help"
        )
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if delete_price_alert(user_id, alert_id):
        await update.message.reply_text(
            _(f"✅ *Alerta eliminada*\n\n"
              f"🔔 {alerta.get('coin')} @ ${alerta.get('target_price'):,.4f}",
              user_id),
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await update.message.reply_text(
            _("❌ Error al eliminar alerta", user_id),
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )


async def clear_alerts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Elimina todas las alertas del usuario."""
    user_id = update.effective_user.id

    alertas = get_user_alerts(user_id)

    if not alertas:
        keyboard = [[
            InlineKeyboardButton(
                "➕ Crear mi primera alerta",
                callback_data="alertas_add_help"
            )
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            _("ℹ️ No tienes alertas para eliminar", user_id),
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        return

    keyboard = [[
        InlineKeyboardButton(
            "➕ Crear nueva alerta",
            callback_data="alertas_add_help"
        )
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if delete_all_alerts(user_id):
        await update.message.reply_text(
            _(f"✅ *{len(alertas)} alertas eliminadas*", user_id),
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await update.message.reply_text(
            _("❌ Error al eliminar alertas", user_id),
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )


# === CALLBACK HANDLERS ===

async def alertas_add_help_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra ayuda para crear una alerta."""
    query = update.callback_query
    await query.answer()

    help_text = (
        "➕ *Crear Alerta de Precio*\n\n"
        "Usa el comando:\n"
        "`/alertas add COIN PRECIO`\n\n"
        "*Ejemplos:*\n"
        "• `/alertas add BTC 50000`\n"
        "• `/alertas add ETH 3500`\n"
        "• `/alertas add SOL 150`\n\n"
        "_Recibirás una notificación cuando el precio cruce ese nivel._"
    )

    keyboard = [[
        InlineKeyboardButton(
            "⬅️ Volver",
            callback_data="alertas_back"
        )
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await query.edit_message_text(
            help_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception:
        await query.answer("Error al actualizar el mensaje", show_alert=True)


async def alertas_back_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Vuelve a la lista de alertas."""
    query = update.callback_query
    await query.answer()

    # Simplemente volvemos a mostrar las alertas
    await show_alerts(update, context, query)


# Lista de handlers para registrar en bbalert.py
alertas_handlers_list = [
    CommandHandler("alertas", alertas_command),
    CallbackQueryHandler(alertas_add_help_callback, pattern="^alertas_add_help$"),
    CallbackQueryHandler(alertas_back_callback, pattern="^alertas_back$"),
]
