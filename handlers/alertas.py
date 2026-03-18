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
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters
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
    Muestra el menú de eliminación con un botón para CADA alerta (above y below separadas).
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

    # Construir mensaje - mostrar CADA alerta individualmente
    mensaje = "❌ *Selecciona la alerta a eliminar:*\n\n"
    
    # NO agrupar - mostrar cada alerta por separado
    keyboard = []
    idx = 0
    
    # Ordenar por coin y price para consistencia
    alertas_ordenadas = sorted(alertas, key=lambda x: (x.get('coin', ''), x.get('target_price', 0)))
    
    for alerta in alertas_ordenadas:
        idx += 1
        coin = alerta.get('coin')
        price = alerta.get('target_price')
        condition = alerta.get('condition')
        alert_id = alerta.get('alert_id')
        
        emoji = "📈" if condition == 'ABOVE' else "📉"
        condition_str = ">" if condition == 'ABOVE' else "<"
        
        mensaje += f"{idx}. {coin} {emoji} {condition_str} ${price:.4f}\n"
        
        keyboard.append([
            InlineKeyboardButton(
                f"🗑️ Eliminar {coin} {idx}",
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
    """Elimina una sola alerta (solo la seleccionada, no ambas direcciones)."""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    alert_id = query.data.split("_")[-1]  # Obtener el alert_id del callback_data

    # Eliminar SOLO esta alerta específica
    delete_price_alert(user_id, alert_id)

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


# === MENSAJE DE TEXTO (Opción 2: "BTC 72000" sin comando) ===

async def alertas_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Maneja mensajes de texto que no son comandos.
    Si el formato es "MONEDA PRECIO", crea una alerta.
    Ejemplo: "BTC 72000" o "HIVE 0.15"
    """
    # Ignorar si es un comando (empieza con /)
    if update.message.text.startswith('/'):
        return
    
    # Ignorar si es una respuesta a un callback (tiene mensaje anterior)
    if update.message.reply_to_message:
        return
    
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    # Parsear el texto: debe tener exactamente 2 partes
    parts = text.split()
    
    if len(parts) != 2:
        return  # No es formato de alerta, ignorar
    
    symbol = parts[0].upper()
    price_str = parts[1]
    
    # Validar que el símbolo sea una moneda conocida o válido
    # Símbolos válidos comunes (mínimo 2 letras)
    if len(symbol) < 2:
        return
    
    # Validar el precio
    try:
        price = float(price_str.replace(',', ''))
        if price <= 0:
            return
    except ValueError:
        return
    
    # Registrar usuario
    registrar_usuario(user_id, update.effective_user.language_code)
    
    # Crear alerta
    alert_id = add_price_alert(user_id, symbol, price)
    
    if alert_id:
        keyboard = [
            [
                InlineKeyboardButton(
                    "📋 Ver mis alertas",
                    callback_data="alertas_back"
                )
            ],
            [
                InlineKeyboardButton(
                    "➕ Crear otra",
                    callback_data="alertas_create"
                )
            ]
        ]
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


# === HANDLERS PARA REGISTRAR EN bbalert.py ===

alertas_handlers_list = [
    CommandHandler("alertas", alertas_command),
    CommandHandler("alerta", alerta_command),
    CommandHandler("misalertas", misalertas_command),
    
    # MessageHandler para capturar "BTC 72000" sin comando
    MessageHandler(filters.TEXT & ~filters.COMMAND, alertas_text_handler),
    
    # Callbacks
    CallbackQueryHandler(alertas_create_callback, pattern="^alertas_create$"),
    CallbackQueryHandler(alertas_delete_menu_callback, pattern="^alertas_delete_menu$"),
    CallbackQueryHandler(alertas_delete_single_callback, pattern="^alertas_delete_"),
    CallbackQueryHandler(alertas_delete_all_callback, pattern="^alertas_delete_all$"),
    CallbackQueryHandler(alertas_back_callback, pattern="^alertas_back$"),
]
