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
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from utils.file_manager import (
    add_price_alert,
    get_user_alerts,
    delete_price_alert,
    delete_all_alerts,
    registrar_usuario
)
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


async def show_alerts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Muestra las alertas del usuario."""
    user_id = update.effective_user.id
    
    alertas = get_user_alerts(user_id)
    
    if not alertas:
        await update.message.reply_text(
            _(
                "🔔 *Sin alertas*\n\n"
                "Crea una alerta:\n"
                "`/alertas add BTC 50000`",
                user_id
            ),
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    mensaje = _("🚨 *Tus Alertas:*\n\n", user_id)
    
    for i, alerta in enumerate(alertas, 1):
        symbol = alerta.get('coin', 'N/A')
        price = alerta.get('target_price', 0)
        status = alerta.get('status', 'active')
        
        emoji = "✅" if status == "triggered" else "🔔"
        mensaje += f"{i}. {emoji} *{symbol}* @ ${price:,.4f}\n"
    
    mensaje += f"\n_Usa /alertas remove [número]_"
    
    await update.message.reply_text(
        mensaje,
        parse_mode=ParseMode.MARKDOWN
    )


async def create_alert(update: Update, context: ContextTypes.DEFAULT_TYPE, args: list) -> None:
    """Crea una nueva alerta."""
    user_id = update.effective_user.id
    
    if len(args) < 2:
        await update.message.reply_text(
            _(
                "⚠️ *Uso incorrecto*\n\n"
                "Usa: `/alertas add BTC 50000`\n\n"
                "Ejemplo: `/alertas add ETH 3500`",
                user_id
            ),
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    symbol = args[0].upper()
    
    try:
        price = float(args[1].replace(',', ''))
    except ValueError:
        await update.message.reply_text(
            _(f"⚠️ Precio inválido: {args[1]}", user_id),
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # Crear alerta
    alert_id = add_price_alert(user_id, symbol, price)
    
    if alert_id:
        await update.message.reply_text(
            _(f"✅ *Alerta creada*\n\n"
              f"🔔 {symbol} @ ${price:,.4f}\n\n"
              f"ID: `{alert_id}`",
              user_id),
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await update.message.reply_text(
            _("❌ Error al crear alerta", user_id),
            parse_mode=ParseMode.MARKDOWN
        )


async def remove_alert(update: Update, context: ContextTypes.DEFAULT_TYPE, args: list) -> None:
    """Elimina una alerta específica."""
    user_id = update.effective_user.id
    
    if not args:
        await update.message.reply_text(
            _(
                "⚠️ *Uso incorrecto*\n\n"
                "Usa: `/alertas remove 1`",
                user_id
            ),
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    try:
        index = int(args[0])
    except ValueError:
        await update.message.reply_text(
            _(f"⚠️ Índice inválido: {args[0]}", user_id),
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # Obtener alertas actuales
    alertas = get_user_alerts(user_id)
    
    if not alertas or index < 1 or index > len(alertas):
        await update.message.reply_text(
            _("⚠️ Índice fuera de rango", user_id),
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # Eliminar (índice - 1 para array)
    alerta = alertas[index - 1]
    alert_id = alerta.get('id')
    
    if delete_price_alert(user_id, alert_id):
        await update.message.reply_text(
            _(f"✅ *Alerta eliminada*\n\n"
              f"🔔 {alerta.get('coin')} @ ${alerta.get('target_price')}",
              user_id),
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await update.message.reply_text(
            _("❌ Error al eliminar alerta", user_id),
            parse_mode=ParseMode.MARKDOWN
        )


async def clear_alerts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Elimina todas las alertas del usuario."""
    user_id = update.effective_user.id
    
    alertas = get_user_alerts(user_id)
    
    if not alertas:
        await update.message.reply_text(
            _("ℹ️ No tienes alertas para eliminar", user_id),
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    if delete_all_alerts(user_id):
        await update.message.reply_text(
            _(f"✅ *{len(alertas)} alertas eliminadas*", user_id),
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await update.message.reply_text(
            _("❌ Error al eliminar alertas", user_id),
            parse_mode=ParseMode.MARKDOWN
        )
