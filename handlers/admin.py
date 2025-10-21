# handlers/admin.py


import asyncio
import os
import openpyxl 
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, 
    ConversationHandler, 
    CommandHandler, 
    MessageHandler, 
    CallbackQueryHandler,
    filters
)
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from utils.file_manager import cargar_usuarios
from utils.file_manager import get_user_alerts
from utils.file_manager import load_hbd_history
from core.config import VERSION, PID, PYTHON_VERSION, STATE, ADMIN_CHAT_IDS

# Definimos los estados para nuestra conversación de mensaje masivo
AWAITING_CONTENT, AWAITING_CONFIRMATION, AWAITING_ADDITIONAL_TEXT, AWAITING_ADDITIONAL_PHOTO = range(4)
# handlers/admin.py

# --- INICIO: NUEVA LÓGICA PARA /ms INTERACTIVO ---
async def ms_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Inicia la conversación para el mensaje masivo."""
    chat_id_str = str(update.effective_chat.id)
    if chat_id_str not in ADMIN_CHAT_IDS:
        await update.message.reply_text("🚫 Comando no autorizado.")
        return ConversationHandler.END

    # Limpiamos datos de conversaciones anteriores
    context.user_data.pop('ms_text', None)
    context.user_data.pop('ms_photo_id', None)

    await update.message.reply_text(
        "✍️ *Creación de Mensaje Masivo*\n\n"
        "Por favor, envía el contenido principal del mensaje.\n"
        "Puedes enviar una imagen, un texto, o una imagen con texto.",
        parse_mode=ParseMode.MARKDOWN
    )
    return AWAITING_CONTENT

async def handle_initial_content(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Captura el primer contenido enviado (texto o foto)."""
    message = update.message
    
    if message.text:
        context.user_data['ms_text'] = message.text
        keyboard = [
            [InlineKeyboardButton("🖼️ Añadir Imagen", callback_data="ms_add_photo")],
            [InlineKeyboardButton("➡️ Enviar Solo Texto", callback_data="ms_send_final")],
            [InlineKeyboardButton("❌ Cancelar", callback_data="ms_cancel")]
        ]
        await message.reply_text(
            "✅ Texto recibido. ¿Deseas añadir una imagen o enviar el mensaje?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    elif message.photo:
        context.user_data['ms_photo_id'] = message.photo[-1].file_id
        # Si la imagen tiene un pie de foto, lo guardamos también
        if message.caption:
            context.user_data['ms_text'] = message.caption

        keyboard = [
            [InlineKeyboardButton("✍️ Añadir/Editar Texto", callback_data="ms_add_text")],
            [InlineKeyboardButton("➡️ Enviar Solo Imagen", callback_data="ms_send_final")],
            [InlineKeyboardButton("❌ Cancelar", callback_data="ms_cancel")]
        ]
        await message.reply_text(
            "✅ Imagen recibida. ¿Deseas añadir o editar el texto del pie de foto?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await message.reply_text("⚠️ Por favor, envía un texto o una imagen.")
        return AWAITING_CONTENT

    return AWAITING_CONFIRMATION

async def handle_confirmation_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Maneja los botones de confirmación."""
    query = update.callback_query
    await query.answer()
    choice = query.data

    if choice == "ms_add_text":
        await query.edit_message_text("✍️ De acuerdo, por favor envía el texto que quieres usar como pie de foto.")
        return AWAITING_ADDITIONAL_TEXT
    elif choice == "ms_add_photo":
        await query.edit_message_text("🖼️ Entendido, por favor envía la imagen que quieres adjuntar.")
        return AWAITING_ADDITIONAL_PHOTO
    elif choice == "ms_send_final":
        return await send_broadcast(query, context)
    elif choice == "ms_cancel":
        await query.edit_message_text("🚫 Operación cancelada.")
        return ConversationHandler.END

async def receive_additional_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recibe el texto adicional para una imagen."""
    context.user_data['ms_text'] = update.message.text
    keyboard = [
        [InlineKeyboardButton("🚀 Enviar a todos los usuarios", callback_data="ms_send_final")],
        [InlineKeyboardButton("❌ Cancelar", callback_data="ms_cancel")]
    ]
    await update.message.reply_text(
        "✅ Texto añadido. El mensaje está listo para ser enviado.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return AWAITING_CONFIRMATION
    
async def receive_additional_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recibe la imagen adicional para un texto."""
    context.user_data['ms_photo_id'] = update.message.photo[-1].file_id
    keyboard = [
        [InlineKeyboardButton("🚀 Enviar a todos los usuarios", callback_data="ms_send_final")],
        [InlineKeyboardButton("❌ Cancelar", callback_data="ms_cancel")]
    ]
    await update.message.reply_text(
        "✅ Imagen añadida. El mensaje está listo para ser enviado.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return AWAITING_CONFIRMATION

async def send_broadcast(query, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Función final que envía el mensaje a todos los usuarios."""
    await query.edit_message_text("⏳ *Enviando mensaje a todos los usuarios...*\nEsto puede tardar un momento.", parse_mode=ParseMode.MARKDOWN)

    global _enviar_mensaje_telegram_async_ref
    if not _enviar_mensaje_telegram_async_ref:
        await query.message.reply_text("❌ Error interno: La función de envío masivo no ha sido inicializada.")
        return ConversationHandler.END

    text_to_send = context.user_data.get('ms_text', "")
    photo_id_to_send = context.user_data.get('ms_photo_id')
    
    usuarios = cargar_usuarios()
    chat_ids = list(usuarios.keys())
        
    fallidos = await _enviar_mensaje_telegram_async_ref(
        text_to_send, 
        chat_ids, 
        photo=photo_id_to_send
    )

    total_enviados = len(chat_ids) - len(fallidos)
    if fallidos:
        fallidos_reporte = [f"  - `{chat_id}`: _{error}_" for chat_id, error in fallidos.items()]
        fallidos_str = "\n".join(fallidos_reporte)
        mensaje_admin = (
            f"✅ Envío completado.\n\n"
            f"Enviado a *{total_enviados}* de {len(chat_ids)} usuarios.\n\n"
            f"❌ Fallos ({len(fallidos)}):\n{fallidos_str}"
        )
    else:
        mensaje_admin = f"✅ ¡Éxito! Mensaje enviado a todos los *{len(chat_ids)}* usuarios."

    await query.message.reply_text(mensaje_admin, parse_mode=ParseMode.MARKDOWN)

    # Limpiar datos al finalizar
    context.user_data.pop('ms_text', None)
    context.user_data.pop('ms_photo_id', None)
    
    return ConversationHandler.END

async def cancel_ms(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Función para cancelar la conversación."""
    await update.message.reply_text("🚫 Operación cancelada.")
    # Limpiar datos al cancelar
    context.user_data.pop('ms_text', None)
    context.user_data.pop('ms_photo_id', None)
    return ConversationHandler.END

# Definición del ConversationHandler para el comando /ms
ms_conversation_handler = ConversationHandler(
    entry_points=[CommandHandler("ms", ms_start)],
    states={
        AWAITING_CONTENT: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_initial_content),
            MessageHandler(filters.PHOTO, handle_initial_content)
        ],
        AWAITING_CONFIRMATION: [
            CallbackQueryHandler(handle_confirmation_choice)
        ],
        AWAITING_ADDITIONAL_TEXT: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, receive_additional_text)
        ],
        AWAITING_ADDITIONAL_PHOTO: [
            MessageHandler(filters.PHOTO, receive_additional_photo)
        ],
    },
    fallbacks=[CommandHandler("cancelar", cancel_ms)],
    conversation_timeout=600, # Se cancela automáticamente después de 10 minutos de inactividad
    per_message=True  # <--- ¡AÑADE ESTA LÍNEA!
)

# Referencias para inyección de funciones
# Estas referencias se inyectan desde bbalert para enviar mensajes masivos y obtener logs
_enviar_mensaje_telegram_async_ref = None
_get_logs_data_ref = None

def set_admin_util(func):
    """Permite a bbalert inyectar la función de envío masivo."""
    global _enviar_mensaje_telegram_async_ref
    _enviar_mensaje_telegram_async_ref = func

def set_logs_util(func):
    """Permite a bbalert inyectar la función para obtener los logs."""
    global _get_logs_data_ref
    _get_logs_data_ref = func

# Comando /users para ver el número de usuarios registrados
async def users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /users. Muestra el número de usuarios registrados con detalles.
    Si el usuario no es admin, solo ve sus propios datos.
    """

    current_chat_id_str = str(update.effective_chat.id)
    usuarios = cargar_usuarios()

    # Si el usuario NO es administrador, mostrar solo sus propios datos
    if current_chat_id_str not in ADMIN_CHAT_IDS:
        data = usuarios.get(current_chat_id_str)
        if not data:
            await update.message.reply_text("😕 No estás registrado en el sistema.")
            return

        monedas_str = ', '.join(data.get('monedas', []))
        intervalo_h = data.get('intervalo_alerta_h', 1.0)
        user_id = int(current_chat_id_str)
        alertas_activas = len(get_user_alerts(user_id))

        try:
            chat_info = await context.bot.get_chat(user_id)
            nombre_completo = chat_info.full_name or "N/A"
            username_str = f"@{chat_info.username}" if chat_info.username else "N/A"
        except Exception as e:
            nombre_completo = data.get('first_name', 'N/A')
            username_str = f"@{data.get('username', 'N/A')}"
            if 'Bot blocked' in str(e):
                nombre_completo += " (Bloqueado)"

        mensaje = (
            f"👤 *Tu Perfil Registrado*\n"
            f"————————————————————\n"
            f"  - Nombre: {nombre_completo}\n"
            f"  - 🪪 ID: `{user_id}`\n"
            f"  - 👤 Usuario: {username_str}\n"
            f"  - 🪙 Monedas: `{monedas_str}`\n"
            f"  - ⏰ Alerta cada: {intervalo_h}h\n"
            f"  - 🔔 Alertas activas: {alertas_activas}\n"
            f"————————————————————\n"
            f"_Solo puedes ver tu propia información 🙂_"
        )
        await update.message.reply_text(mensaje, parse_mode=ParseMode.MARKDOWN)
        return

    # Si es administrador, mostrar todos los usuarios
    num_usuarios = len(usuarios)
    detalles = []

    for chat_id_str, data in usuarios.items():
        chat_id = int(chat_id_str)
        monedas_str = ', '.join(data.get('monedas', []))
        intervalo_h = data.get('intervalo_alerta_h', 1.0)
        alertas_activas = len(get_user_alerts(chat_id))

        try:
            chat_info = await context.bot.get_chat(chat_id)
            nombre_completo = chat_info.full_name or "N/A"
            username_str = f"@{chat_info.username}" if chat_info.username else "N/A"
        except Exception as e:
            nombre_completo = data.get('first_name', 'N/A')
            username_str = f"@{data.get('username', 'N/A')}"
            if 'Bot blocked' in str(e):
                nombre_completo += " (Bloqueado)"

        detalles.append(
            f"  - Nombre: {nombre_completo}\n"
            f"  - 🪪 ID: `{chat_id}`\n"
            f"  - 👤 Usuario: {username_str}\n"
            f"  - 🪙 Monedas: `{monedas_str}`\n"
            f"  - ⏰ Alerta cada: {intervalo_h}h\n"
            f"  - 🔔 Alertas activas: {alertas_activas}\n"
        )

    mensaje = (
        f"👥 *Usuarios Registrados*: {num_usuarios}\n"
        f"————————————————————\n"
        f"```{chr(10).join(detalles)}```"
    )
    await update.message.reply_text(mensaje, parse_mode=ParseMode.MARKDOWN)


# COMANDO /logs para ver las últimas líneas del log
async def logs_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Comprobar si el ID está en la lista de administradores
    if str(update.effective_chat.id) not in ADMIN_CHAT_IDS:
        # Obtener la última actualización desde el log si es posible
        global _get_logs_data_ref
        ultima_actualizacion = "N/A"
        if _get_logs_data_ref:
            log_data_full = _get_logs_data_ref()
            if log_data_full:
                try:
                    timestamp_ms_part = log_data_full[-1].split(" | ")[0]
                    timestamp_part = timestamp_ms_part.split("[")[1].split("]")[0].strip()
                    ultima_actualizacion = f"{timestamp_part} UTC"
                except Exception:
                    pass

        # Mensaje limitado para usuarios no administradores
        mensaje = f"""🤖 *Estado de BitBread Alert*

————————————————————
• Versión: {VERSION} 🤖
• Estado: {STATE} 👌
• Última Actualización: {ultima_actualizacion} 🕒 
————————————————————

_Ya, eso es todo lo que puedes ver 🙂👍_"""
        await update.message.reply_text(mensaje, parse_mode=ParseMode.MARKDOWN)
        return

    # Verificar que la función de logs ha sido inyectada correctamente
    if not _get_logs_data_ref:
        await update.message.reply_text("❌ Error interno: La función de logs no ha sido inicializada.")
        return

    # Obtener todas las líneas del log
    log_data_full = _get_logs_data_ref()

    # 1. Obtener argumento opcional: número de líneas (por defecto 10)
    n_lineas_default = 10
    try:
        n_lineas = int(context.args[0]) if context.args and context.args[0].isdigit() else n_lineas_default
        n_lineas = max(1, min(n_lineas, 100))
    except ValueError:
        await update.message.reply_text("⚠️ El argumento debe ser un número entero.")
        return

    # 2. Extraer las últimas N líneas
    log_data_n_lines = log_data_full[-n_lineas:] if log_data_full else []
    log_str = "\n".join(log_data_n_lines)

    # Extraer la marca de tiempo de la última línea del log
    ultima_actualizacion = "N/A"
    if log_data_n_lines:
        try:
            timestamp_ms_part = log_data_n_lines[-1].split(" | ")[0]
            timestamp_part = timestamp_ms_part.split("[")[1].split("]")[0].strip()
            ultima_actualizacion = f"{timestamp_part} UTC"
        except Exception:
            pass

    # 3. Mensaje de respuesta completo para administradores
    mensaje = f"""🤖 *Estado de BitBread Alert*
————————————————————
• Versión: {VERSION} 🤖
• PID: {PID} 🪪
• Python: {PYTHON_VERSION} 🐍
• Usuarios: {len(cargar_usuarios())} 👥
• Estado: {STATE} 👌
• Última Actualización: {ultima_actualizacion} 🕒 
————————————————————
•📜 *Últimas {len(log_data_n_lines)} líneas de {len(log_data_full)} *\n ```{log_str}```\n"""

    await update.message.reply_text(mensaje, parse_mode=ParseMode.MARKDOWN)

