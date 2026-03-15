# handlers/alerts.py

import asyncio
import os
from datetime import datetime
from telegram import Update, Bot
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from core.config import TOKEN_TELEGRAM, ADMIN_CHAT_IDS, PID, VERSION, STATE, PYTHON_VERSION, LOG_LINES, USUARIOS_PATH
from core.api_client import obtener_precios_control
from core.loops import set_custom_alert_history_util
from utils.file_manager import delete_all_alerts, add_log_line
from utils.user_data import (
    cargar_usuarios, guardar_usuarios, registrar_usuario,
    actualizar_monedas, obtener_monedas_usuario, actualizar_intervalo_alerta
)
from utils.alert_manager import (
    add_price_alert, get_user_alerts, delete_price_alert,
    load_price_alerts, update_alert_status
)
from utils.subscription_manager import check_feature_access, registrar_uso_comando
from core.i18n import _
# ------------------------------------------------------------------
#  HISTORIAL EN MEMORIA DE PRECIOS (para comparar cruces)
# ------------------------------------------------------------------
CUSTOM_ALERT_HISTORY: dict[str, float] = {}


# COMANDO /alerta
async def alerta_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Crea una alerta de precio.
    Uso exclusivo: /alerta <MONEDA> <PRECIO>
    """
    user_id = update.effective_user.id # user_id es igual a chat_id

    # 1. Validar que se hayan proporcionado exactamente dos argumentos
    if not context.args or len(context.args) != 2:
        mensaje_error = _(
            "⚠️ *Formato incorrecto*.\n\nEl uso correcto es:\n"
            "/alerta *MONEDA PRECIO*\n\n"
            "Ejemplo: `/alerta HIVE 0.35`",
            user_id # Pasa el user_id para obtener la traducción
        )
        await update.message.reply_text(
            mensaje_error,
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
        mensaje_error_precio = _(
            "⚠️ El precio que ingresaste no es válido. Debe ser un número positivo.",
            user_id # Pasa el user_id para obtener la traducción
        )
        await update.message.reply_text(
            mensaje_error_precio,
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

    # === GUARDIA DE CAPACIDAD ===
    # Contamos cuántas alertas tiene activas actualmente
    alertas_actuales = get_user_alerts(user_id) # Devuelve lista de diccionarios
    num_alertas_db = len(alertas_actuales)
    # Verificamos si caben 2 más (una arriba, una abajo)
    acceso, mensaje = check_feature_access(user_id, 'alerts_capacity', current_count=num_alertas_db)
    registrar_uso_comando(user_id, 'alerta')
    
    if not acceso:
        await update.message.reply_text(mensaje, parse_mode=ParseMode.MARKDOWN)
        return
    # ============================

    # 4. Crear la alerta
    add_price_alert(user_id, coin, target_price)

    # Creamos el mensaje de confirmación aquí para poder traducirlo.
    confirmation_message_template = _(
        "✅ ¡Alertas creadas! Te avisaré cuando *{coin}* cruce por encima o por debajo de *${target_price:,.4f}*.",
        user_id
    )
    confirmation_message = confirmation_message_template.format(
        coin=coin.upper(),
        target_price=target_price
    )
    # --- FIN DE LA MODIFICACIÓN ---

    # Traducir la plantilla del precio actual
    if initial_price:
        plantilla_precio_actual = _(
            "\n📊 Precio actual: `{initial_price:,.4f}`",
            user_id
        )
        
        # Usamos .format() para inyectar el valor numérico *después* de la traducción
        confirmation_message += plantilla_precio_actual.format(initial_price=initial_price)

    await update.message.reply_text(
        confirmation_message,
        parse_mode=ParseMode.MARKDOWN,
    )

# Mostrar alertas activas
async def misalertas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_alerts = get_user_alerts(user_id)

    if not user_alerts:
        # Mensaje 1: No hay alertas
        await update.message.reply_text(
            _(
                "No tienes ninguna alerta de precio activa. Crea una con el comando /alerta.",
                user_id
            )
        )
        return

    # Mensaje 2: Encabezado de la lista de alertas
    message = _(
        "🔔 *Tus Alertas de Precio Activas:*\n\n",
        user_id
    )
    
    keyboard = []

    for alert in user_alerts:
        # Los símbolos y números son universales, no necesitan traducción.
        condicion = "📈 >" if alert['condition'] == 'ABOVE' else "📉 <"
        precio = f"{alert['target_price']:,.4f}"
        
        # El formato del mensaje principal usa variables
        message += f"- *{alert['coin']}* {condicion} `${precio}`\n"
        
        # El texto del botón usa variables
        keyboard.append([InlineKeyboardButton(
            f"🗑️ {alert['coin']} {condicion} {precio}",
            callback_data=f"delete_alert_{alert['alert_id']}"
        )])

    # Mensaje 3: Texto del botón "Borrar Todas"
    texto_borrar_todas = _(
        "🧹 Borrar Todas",
        user_id
    )
    keyboard.append([InlineKeyboardButton(texto_borrar_todas, callback_data="delete_all_alerts")])
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
        await query.edit_message_text(
            _(
                "✅ Alerta borrada. Ya no tienes alertas activas.",
                user_id
            )
        )
        return

    message = _(
        "🔔 *Tus Alertas de Precio Activas:*\n\n",
        user_id
    )
    keyboard = []

    for alert in user_alerts:
        condicion = "📈 >" if alert['condition'] == 'ABOVE' else "📉 <"
        precio = f"{alert['target_price']:,.4f}"
        message += f"- *{alert['coin']}* {condicion} `${precio}`\n"
        keyboard.append([InlineKeyboardButton(
            f"🗑️ {alert['coin']} {condicion} {precio}",
            callback_data=f"delete_alert_{alert['alert_id']}"
        )])


    texto_borrar_todas = _(
        "🧹 Borrar Todas",
        user_id
    )
    keyboard.append([InlineKeyboardButton(texto_borrar_todas, callback_data="delete_all_alerts")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)

# Borrar todas las alertas
async def borrar_todas_alertas_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    delete_all_alerts(user_id)

    await query.edit_message_text(
        _(
            "✅ Todas tus alertas han sido eliminadas.",
            user_id
        )
    )
# ============================================================