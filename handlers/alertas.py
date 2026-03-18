# handlers/alertas.py
"""
Handler unificado para comandos de alertas.
Unifica: /alerta, /alertas, /misalertas

Funcionalidad:
- /alertas - Ver mis alertas (con dos botones principales)
- /alerta MONEDA PRECIO - Crear alerta
- Botón "➕ Crear nueva alerta" - Muestra formato para crear
- Botón "❌ Eliminar alerta" - Muestra alertas con botón para eliminar cada una
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


# === COMANDO PRINCIPAL /alertas ===

async def alertas_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Comando unificado /alertas.
    Muestra las alertas del usuario con dos botones principales:
    - ➕ Crear nueva alerta
    - ❌ Eliminar alerta
    """
    user_id = update.effective_user.id
    
    # Registrar usuario
    registrar_usuario(user_id, update.effective_user.language_code)
    
    # Mostrar alertas con botones principales
    await show_alerts_with_main_buttons(update, context)


async def show_alerts_with_main_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE, query=None) -> None:
    """
    Muestra las alertas del usuario con dos botones principales:
    - ➕ Crear nueva alerta
    - ❌ Eliminar alerta
    """
    user_id = update.effective_user.id

    alertas = get_user_alerts(user_id)

    if not alertas:
        # No hay alertas - mostrar mensaje de ayuda
        keyboard = [[
            InlineKeyboardButton(
                "➕ Crear mi primera alerta",
                callback_data="alertas_create"
            )
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        text = (
            "🔔 *Sin alertas de precio*\n\n"
            "Crea una alerta fácilmente:\n"
            "`/alerta BTC 72000`\n\n"
            "O usa el botón de abajo."
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

    # Construir mensaje con formato específico
    mensaje = "🔔 *Tus Alertas de Precio Activas:*\n\n"
    
    # Agrupar alertas por precio (cada precio tiene above y below)
    alerts_by_price = {}
    for alerta in alertas:
        key = (alerta.get('coin'), alerta.get('target_price'))
        if key not in alerts_by_price:
            alerts_by_price[key] = []
        alerts_by_price[key].append(alerta)
    
    # Mostrar cada par de alertas (arriba y abajo)
    for (coin, price), alert_list in sorted(alerts_by_price.items()):
        above = next((a for a in alert_list if a.get('condition') == 'ABOVE'), None)
        below = next((a for a in alert_list if a.get('condition') == 'BELOW'), None)
        
        if above:
            mensaje += f"- {coin} 📈 > ${price:.4f}\n"
        if below:
            mensaje += f"- {coin} 📉 < ${price:.4f}\n"

    # Botones principales
    keyboard = [
        [
            InlineKeyboardButton(
                "➕ Crear nueva alerta",
                callback_data="alertas_create"
            )
        ],
        [
            InlineKeyboardButton(
                "❌ Eliminar alerta",
                callback_data="alertas_delete_menu"
            )
        ]
    ]
    
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


# === FLUJO DE CREAR NUEVA ALERTA ===

async def alertas_create_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra ayuda para crear una nueva alerta."""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id

    help_text = (
        "➕ *Crear Alerta de Precio*\n\n"
        "*Opción 1 - Comando completo:*\n"
        "`/alerta BTC 72000`\n\n"
        "*Opción 2 - Solo envía:*\n"
        "`BTC 72000`\n\n"
        "_Recibirás notificaciones cuando el precio suba o baje del nivel indicado._"
    )

    keyboard = [
        [
            InlineKeyboardButton(
                "⬅️ Volver a mis alertas",
                callback_data="alertas_back"
            )
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await query.edit_message_text(
            help_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        logger.error(f"Error en alertas_create_callback: {e}")
        await query.answer("Error al actualizar el mensaje", show_alert=True)


# === FLUJO DE ELIMINAR ALERTA ===

async def alertas_delete_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Muestra el menú de eliminación con un botón para cada alerta.
    """
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    alertas = get_user_alerts(user_id)

    if not alertas:
        keyboard = [[
            InlineKeyboardButton(
                "⬅️ Volver",
                callback_data="alertas_back"
            )
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            "ℹ️ No tienes alertas para eliminar.",
            reply_markup=reply_markup
        )
        return

    # Construir mensaje
    mensaje = "❌ *Selecciona la alerta a eliminar:*\n\n"
    
    # Agrupar alertas por precio
    alerts_by_price = {}
    for alerta in alertas:
        key = (alerta.get('coin'), alerta.get('target_price'))
        if key not in alerts_by_price:
            alerts_by_price[key] = []
        alerts_by_price[key].append(alerta)
    
    # Crear botón para cada par de alertas (arriba y abajo del mismo precio)
    keyboard = []
    idx = 0
    for (coin, price), alert_list in sorted(alerts_by_price.items()):
        idx += 1
        # Obtener el alert_id de la alerta above (o la primera)
        alert_id = alert_list[0].get('alert_id')
        
        emoji = "📈" if alert_list[0].get('condition') == 'ABOVE' else "📉"
        condition_str = ">" if alert_list[0].get('condition') == 'ABOVE' else "<"
        
        mensaje += f"{idx}. {coin} {emoji} {condition_str} ${price:.4f}\n"
        
        keyboard.append([
            InlineKeyboardButton(
                f"🗑️ Eliminar {coin} @ ${price:.4f}",
                callback_data=f"alertas_delete_{alert_id}"
            )
        ])

    # Botón para eliminar todas
    keyboard.append([
        InlineKeyboardButton(
            "🗑️ Eliminar TODAS las alertas",
            callback_data="alertas_delete_all"
        )
    ])

    # Botón volver
    keyboard.append([
        InlineKeyboardButton(
            "⬅️ Volver",
            callback_data="alertas_back"
        )
    ])

    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await query.edit_message_text(
            mensaje,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        logger.error(f"Error en alertas_delete_menu_callback: {e}")
        await query.answer("Error al actualizar el mensaje", show_alert=True)


async def alertas_delete_single_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Elimina una alerta específica (ambas direcciones: above y below)."""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    alert_id = query.data.split("_")[-1]  # Obtener el último parte del callback_data

    # Obtener la alerta para mostrar info
    alertas = get_user_alerts(user_id)
    alerta_encontrada = None
    for a in alertas:
        if a.get('alert_id') == alert_id:
            alerta_encontrada = a
            break

    if alerta_encontrada:
        coin = alerta_encontrada.get('coin')
        price = alerta_encontrada.get('target_price')
        
        # Eliminar TODAS las alertas de ese precio (both above and below)
        delete_price_alert(user_id, alert_id)
        
        # Buscar y eliminar la otra dirección también
        for a in alertas:
            if a.get('coin') == coin and a.get('target_price') == price:
                if a.get('alert_id') != alert_id:
                    delete_price_alert(user_id, a.get('alert_id'))

    # Volver al menú de alertas
    await show_alerts_with_main_buttons(update, context, query)


async def alertas_delete_all_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Elimina todas las alertas del usuario."""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    
    delete_all_alerts(user_id)

    # Volver al menú principal de alertas
    await show_alerts_with_main_buttons(update, context, query)


async def alertas_back_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Vuelve a la lista de alertas con botones principales."""
    query = update.callback_query
    await query.answer()

    await show_alerts_with_main_buttons(update, context, query)


# === COMANDO /alerta (para compatibilidad) ===

async def alerta_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Comando /alerta para crear alertas.
    Uso: /alerta MONEDA PRECIO
    Ejemplo: /alerta BTC 72000
    """
    user_id = update.effective_user.id
    
    if not context.args or len(context.args) != 2:
        await update.message.reply_text(
            "⚠️ *Uso incorrecto*\n\n"
            "Usa: `/alerta MONEDA PRECIO`\n\n"
            "Ejemplo: `/alerta BTC 72000`",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    symbol = context.args[0].upper()
    
    try:
        price = float(context.args[1].replace(',', ''))
    except ValueError:
        await update.message.reply_text(
            f"⚠️ Precio inválido: {context.args[1]}",
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
            )
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            f"✅ *Alerta creada*\n\n"
            f"🔔 {symbol} @ ${price:,.4f}\n\n"
            f"Recibirás notificaciones cuando el precio suba o baje de este nivel.",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await update.message.reply_text(
            "❌ Error al crear alerta",
            parse_mode=ParseMode.MARKDOWN
        )


# === COMANDO /misalertas (para compatibilidad) ===

async def misalertas_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Comando /misalertas - alias para /alertas."""
    await show_alerts_with_main_buttons(update, context)


# === HANDLERS PARA REGISTRAR EN bbalert.py ===

alertas_handlers_list = [
    CommandHandler("alertas", alertas_command),
    CommandHandler("alerta", alerta_command),
    CommandHandler("misalertas", misalertas_command),
    
    # Callbacks
    CallbackQueryHandler(alertas_create_callback, pattern="^alertas_create$"),
    CallbackQueryHandler(alertas_delete_menu_callback, pattern="^alertas_delete_menu$"),
    CallbackQueryHandler(alertas_delete_single_callback, pattern="^alertas_delete_"),
    CallbackQueryHandler(alertas_delete_all_callback, pattern="^alertas_delete_all$"),
    CallbackQueryHandler(alertas_back_callback, pattern="^alertas_back$"),
]
