# handlers/alerts.py

import asyncio
import os
import uuid
import openpyxl 
from datetime import datetime
from telegram import Update, Bot
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.ext import ConversationHandler, ContextTypes
from telegram.ext import ConversationHandler, CallbackQueryHandler
from telegram.constants import ParseMode
from core.config import TOKEN_TELEGRAM, ADMIN_CHAT_IDS, PID, VERSION, STATE, PYTHON_VERSION, LOG_LINES, USUARIOS_PATH
from core.api_client import obtener_precios_control
from core.loops import set_custom_alert_history_util # Nueva importación
from core.config import ADMIN_CHAT_IDS
from utils.file_manager import(\
     delete_all_alerts, add_price_alert, get_user_alerts,\
        delete_price_alert, cargar_usuarios, guardar_usuarios, registrar_usuario,\
            actualizar_monedas, obtener_monedas_usuario, actualizar_intervalo_alerta, add_log_line, load_price_alerts, update_alert_status\
)

# ------------------------------------------------------------------
#  HISTORIAL EN MEMORIA DE PRECIOS (para comparar cruces)
# ------------------------------------------------------------------
CUSTOM_ALERT_HISTORY: dict[str, float] = {}
COIN, TARGET_PRICE = range(2) # Estados de la conversación
    
# Variable para almacenar la función de envío asíncrono (inyectada)
_enviar_mensaje_telegram_async_ref = None

def set_admin_util(func):
    """Permite a bbalert inyectar la función de envío masivo para romper la dependencia circular."""
    global _enviar_mensaje_telegram_async_ref
    _enviar_mensaje_telegram_async_ref = func


# COMANDO /alerta
async def alerta_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Crea una alerta de precio.
    Uso exclusivo: /alerta <MONEDA> <PRECIO>
    """
    user_id = update.effective_user.id

    # 1. Validar que se hayan proporcionado exactamente dos argumentos
    if not context.args or len(context.args) != 2:
        await update.message.reply_text(
            "⚠️ *Formato incorrecto*.\n\n El uso correcto es:\n"
            "/alerta *MONEDA PRECIO*\n\n"
            "Ejemplo: `/alerta HIVE 0.35`",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    # 2. Procesar los argumentos
    coin = context.args[0].upper().strip()
    precio_str = context.args[1]

    try:
        target_price = float(precio_str.replace(',', '.'))
        if target_price <= 0:
            raise ValueError("El precio debe ser positivo.")
    except ValueError:
        await update.message.reply_text(
            "⚠️ El precio que ingresaste no es válido. Debe ser un número positivo.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    # 3. Obtener el precio actual para establecer un punto de referencia inicial
    precios_actuales = obtener_precios_control([coin])
    initial_price = precios_actuales.get(coin)

    if initial_price is not None:
        set_custom_alert_history_util(coin, initial_price)
        add_log_line(f"Precio inicial de {coin} (${initial_price:.4f}) guardado al crear alerta.")
    else:
        # Aunque no se pudo obtener el precio, la alerta se crea de todas formas
        add_log_line(f"❌ Falló consulta de precio inicial de {coin} al crear alerta.")

    # 4. Crear la alerta y enviar mensaje de confirmación
    confirmation_message = add_price_alert(user_id, coin, target_price)

    # Añadir el precio actual al mensaje si se obtuvo
    if initial_price:
        confirmation_message += f"\n📊 Precio actual: `${initial_price:,.4f}`"

    await update.message.reply_text(
        confirmation_message,
        parse_mode=ParseMode.MARKDOWN,
    )

# Mostrar alertas activas
async def misalertas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_alerts = get_user_alerts(user_id)

    if not user_alerts:
        await update.message.reply_text("No tienes ninguna alerta de precio activa. Crea una con el comando /alerta.")
        return

    message = "🔔 *Tus Alertas de Precio Activas:*\n\n"
    keyboard = []

    for alert in user_alerts:
        condicion = "📈 >" if alert['condition'] == 'ABOVE' else "📉 <"
        precio = f"{alert['target_price']:,.4f}"
        message += f"- *{alert['coin']}* {condicion} `${precio}`\n"
        keyboard.append([InlineKeyboardButton(
            f"🗑️ {alert['coin']} {condicion} {precio}",
            callback_data=f"delete_alert_{alert['alert_id']}"
    )])

    keyboard.append([InlineKeyboardButton("🧹 Borrar Todas", callback_data="delete_all_alerts")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(message, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)

# Borrar una alerta y actualizar el mensaje
async def borrar_alerta_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    alert_id = query.data.split("delete_alert_")[1]

    delete_price_alert(user_id, alert_id)
    user_alerts = get_user_alerts(user_id)

    if not user_alerts:
        await query.edit_message_text("✅ Alerta borrada. Ya no tienes alertas activas.")
        return

    message = "🔔 *Tus Alertas de Precio Activas:*\n\n"
    keyboard = []

    for alert in user_alerts:
        condicion = "📈 >" if alert['condition'] == 'ABOVE' else "📉 <"
        precio = f"{alert['target_price']:,.4f}"
        message += f"- *{alert['coin']}* {condicion} `${precio}`\n"
        keyboard.append([InlineKeyboardButton(
            f"🗑️ {alert['coin']} {condicion} {precio}",
            callback_data=f"delete_alert_{alert['alert_id']}"
    )])



    keyboard.append([InlineKeyboardButton("🧹 Borrar Todas", callback_data="delete_all_alerts")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)

# Borrar todas las alertas
async def borrar_todas_alertas_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    delete_all_alerts(user_id)

    await query.edit_message_text("✅ Todas tus alertas han sido eliminadas.")
# ============================================================