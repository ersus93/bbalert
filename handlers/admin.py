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
from core.i18n import _

# Definimos los estados para nuestra conversación de mensaje masivo
AWAITING_CONTENT, AWAITING_CONFIRMATION, AWAITING_ADDITIONAL_TEXT, AWAITING_ADDITIONAL_PHOTO = range(4)
# handlers/admin.py

# --- INICIO: NUEVA LÓGICA PARA /ms INTERACTIVO ---
async def ms_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Inicia la conversación para el mensaje masivo."""
    chat_id = update.effective_chat.id
    chat_id_str = str(chat_id)
    
    if chat_id_str not in ADMIN_CHAT_IDS:
        # Mensaje 1: No autorizado
        await update.message.reply_text(
            _("🚫 Comando no autorizado.", chat_id),
            parse_mode=ParseMode.MARKDOWN
        )
        return ConversationHandler.END

    # Limpiamos datos de conversaciones anteriores
    context.user_data.pop('ms_text', None)
    context.user_data.pop('ms_photo_id', None)

    # Mensaje 2: Instrucciones
    mensaje_instrucciones = _(
        "✍️ *Creación de Mensaje Masivo*\n\n"
        "Por favor, envía el contenido principal del mensaje.\n"
        "Puedes enviar una imagen, un texto, o una imagen con texto.",
        chat_id
    )
    
    await update.message.reply_text(
        mensaje_instrucciones,
        parse_mode=ParseMode.MARKDOWN
    )
    return AWAITING_CONTENT
async def handle_initial_content(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Captura el primer contenido enviado (texto o foto)."""
    message = update.message
    chat_id = update.effective_chat.id
    
    # Textos de los botones
    btn_add_photo = _("🖼️ Añadir Imagen", chat_id)
    btn_send_only_text = _("➡️ Enviar Solo Texto", chat_id)
    btn_cancel = _("❌ Cancelar", chat_id)
    btn_add_edit_text = _("✍️ Añadir/Editar Texto", chat_id)
    btn_send_only_photo = _("➡️ Enviar Solo Imagen", chat_id)
    
    if message.text:
        context.user_data['ms_text'] = message.text
        keyboard = [
            [InlineKeyboardButton(btn_add_photo, callback_data="ms_add_photo")],
            [InlineKeyboardButton(btn_send_only_text, callback_data="ms_send_final")],
            [InlineKeyboardButton(btn_cancel, callback_data="ms_cancel")]
        ]
        # Mensaje 1: Texto recibido, ¿añadir imagen?
        mensaje_texto_recibido = _(
            "✅ Texto recibido. ¿Deseas añadir una imagen o enviar el mensaje?", 
            chat_id
        )
        await message.reply_text(
            mensaje_texto_recibido,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    elif message.photo:
        context.user_data['ms_photo_id'] = message.photo[-1].file_id
        # Si la imagen tiene un pie de foto, lo guardamos también
        if message.caption:
            context.user_data['ms_text'] = message.caption

        keyboard = [
            [InlineKeyboardButton(btn_add_edit_text, callback_data="ms_add_text")],
            [InlineKeyboardButton(btn_send_only_photo, callback_data="ms_send_final")],
            [InlineKeyboardButton(btn_cancel, callback_data="ms_cancel")]
        ]
        # Mensaje 2: Imagen recibida, ¿añadir/editar texto?
        mensaje_foto_recibida = _(
            "✅ Imagen recibida. ¿Deseas añadir o editar el texto del pie de foto?",
            chat_id
        )
        await message.reply_text(
            mensaje_foto_recibida,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        # Mensaje 3: Error de contenido
        mensaje_error_contenido = _("⚠️ Por favor, envía un texto o una imagen.", chat_id)
        await message.reply_text(mensaje_error_contenido)
        return AWAITING_CONTENT

    return AWAITING_CONFIRMATION

async def handle_confirmation_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Maneja los botones de confirmación."""
    query = update.callback_query
    await query.answer()
    choice = query.data
    user_id = query.from_user.id

    if choice == "ms_add_text":
        mensaje_add_text = _(
            "✍️ De acuerdo, por favor envía el texto que quieres usar como pie de foto.",
            user_id
        )
        await query.edit_message_text(mensaje_add_text)
        return AWAITING_ADDITIONAL_TEXT
    elif choice == "ms_add_photo":
        mensaje_add_photo = _(
            "🖼️ Entendido, por favor envía la imagen que quieres adjuntar.",
            user_id
        )
        await query.edit_message_text(mensaje_add_photo)
        return AWAITING_ADDITIONAL_PHOTO
    elif choice == "ms_send_final":
        return await send_broadcast(query, context)
    elif choice == "ms_cancel":
        mensaje_cancelar = _(
            "🚫 Operación cancelada.",
            user_id
        )
        await query.edit_message_text(mensaje_cancelar)
        return ConversationHandler.END

async def receive_additional_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recibe el texto adicional para una imagen."""
    chat_id = update.effective_chat.id
    context.user_data['ms_text'] = update.message.text
    
    # Textos de los botones
    btn_send = _("🚀 Enviar a todos los usuarios", chat_id)
    btn_cancel = _("❌ Cancelar", chat_id)
    
    keyboard = [
        [InlineKeyboardButton(btn_send, callback_data="ms_send_final")],
        [InlineKeyboardButton(btn_cancel, callback_data="ms_cancel")]
    ]
    
    # Mensaje de confirmación
    mensaje_confirmacion = _(
        "✅ Texto añadido. El mensaje está listo para ser enviado.",
        chat_id
    )
    
    await update.message.reply_text(
        mensaje_confirmacion,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return AWAITING_CONFIRMATION
    
async def receive_additional_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recibe la imagen adicional para un texto."""
    chat_id = update.effective_chat.id
    context.user_data['ms_photo_id'] = update.message.photo[-1].file_id
    
    # TextOS de los botones
    btn_send = _("🚀 Enviar a todos los usuarios", chat_id)
    btn_cancel = _("❌ Cancelar", chat_id)
    
    keyboard = [
        [InlineKeyboardButton(btn_send, callback_data="ms_send_final")],
        [InlineKeyboardButton(btn_cancel, callback_data="ms_cancel")]
    ]
    
    # Mensaje de confirmación
    mensaje_confirmacion = _(
        "✅ Imagen añadida. El mensaje está listo para ser enviado.",
        chat_id
    )
    
    await update.message.reply_text(
        mensaje_confirmacion,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return AWAITING_CONFIRMATION

async def send_broadcast(query, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Función final que envía el mensaje a todos los usuarios."""
    chat_id = query.from_user.id
    
    # Mensaje 1: Iniciando envío
    mensaje_iniciando = _(
        "⏳ *Enviando mensaje a todos los usuarios...*\nEsto puede tardar un momento.",
        chat_id
    )
    await query.edit_message_text(mensaje_iniciando, parse_mode=ParseMode.MARKDOWN)

    global _enviar_mensaje_telegram_async_ref
    if not _enviar_mensaje_telegram_async_ref:
        # Mensaje 2: Error interno
        mensaje_error_interno = _("❌ Error interno: La función de envío masivo no ha sido inicializada.", chat_id)
        await query.message.reply_text(mensaje_error_interno)
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
        # Mensaje 3a: Reporte de fallos
        fallidos_reporte = [f"  - `{chat_id}`: _{error}_" for chat_id, error in fallidos.items()]
        fallidos_str = "\n".join(fallidos_reporte)
        
        mensaje_admin_base = _(
            "✅ Envío completado.\n\n"
            "Enviado a *{total_enviados}* de {total_usuarios} usuarios.\n\n"
            "❌ Fallos ({num_fallos}):\n{fallidos_str}",
            chat_id
        )
        mensaje_admin = mensaje_admin_base.format(
            total_enviados=total_enviados,
            total_usuarios=len(chat_ids),
            num_fallos=len(fallidos),
            fallidos_str=fallidos_str
        )
    else:
        # Mensaje 3b: Éxito total
        mensaje_admin_base = _(
            "✅ ¡Éxito! Mensaje enviado a todos los *{total_usuarios}* usuarios.",
            chat_id
        )
        mensaje_admin = mensaje_admin_base.format(total_usuarios=len(chat_ids))

    await query.message.reply_text(mensaje_admin, parse_mode=ParseMode.MARKDOWN)

    # Limpiar datos al finalizar
    context.user_data.pop('ms_text', None)
    context.user_data.pop('ms_photo_id', None)
    
    return ConversationHandler.END

async def cancel_ms(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Función para cancelar la conversación."""
    chat_id = update.effective_chat.id
    
    mensaje_cancelado = _(
        "🚫 Operación cancelada.",
        chat_id
    )
    
    await update.message.reply_text(mensaje_cancelado)
    
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

    current_chat_id = update.effective_chat.id # <-- Obtener chat_id
    current_chat_id_str = str(current_chat_id)
    usuarios = cargar_usuarios()

    # Si el usuario NO es administrador, mostrar solo sus propios datos
    if current_chat_id_str not in ADMIN_CHAT_IDS:
        data = usuarios.get(current_chat_id_str)
        if not data:
            # --- MENSAJE ENVUELTO ---
            await update.message.reply_text(_("😕 No estás registrado en el sistema.", current_chat_id))
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
        
        # --- PLANTILLA ENVUELTA ---
        mensaje_template = _(
            "👤 *Tu Perfil Registrado*\n"
            "————————————————————\n"
            "  - Nombre: {nombre_completo}\n"
            "  - 🪪 ID: `{user_id}`\n"
            "  - 👤 Usuario: {username_str}\n"
            "  - 🪙 Monedas: `{monedas_str}`\n"
            "  - ⏰ Alerta cada: {intervalo_h}h\n"
            "  - 🔔 Alertas activas: {alertas_activas}\n"
            "————————————————————\n"
            "_Solo puedes ver tu propia información 🙂_",
            current_chat_id
        )
        mensaje = mensaje_template.format(
            nombre_completo=nombre_completo,
            user_id=user_id,
            username_str=username_str,
            monedas_str=monedas_str,
            intervalo_h=intervalo_h,
            alertas_activas=alertas_activas
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
    
    # --- PLANTILLA ENVUELTA ---
    mensaje_template = _(
        "👥 *Usuarios Registrados*: {num_usuarios}\n"
        "————————————————————\n"
        "```{detalles_str}```",
        current_chat_id
    )
    mensaje = mensaje_template.format(
        num_usuarios=num_usuarios,
        detalles_str=chr(10).join(detalles)
    )
    await update.message.reply_text(mensaje, parse_mode=ParseMode.MARKDOWN)


# COMANDO /logs para ver las últimas líneas del log
async def logs_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    current_chat_id = update.effective_chat.id # <-- Obtener chat_id
    
    # Comprobar si el ID está en la lista de administradores
    if str(current_chat_id) not in ADMIN_CHAT_IDS:
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

        # --- PLANTILLA ENVUELTA ---
        mensaje_template = _(
            "🤖 *Estado de BitBread Alert*\n\n"
            "————————————————————\n"
            "• Versión: {version} 🤖\n"
            "• Estado: {estado} 👌\n"
            "• Última Actualización: {ultima_actualizacion} 🕒 \n"
            "————————————————————\n\n"
            "_Ya, eso es todo lo que puedes ver 🙂👍_",
            current_chat_id
        )
        mensaje = mensaje_template.format(
            version=VERSION,
            estado=STATE,
            ultima_actualizacion=ultima_actualizacion
        )
        await update.message.reply_text(mensaje, parse_mode=ParseMode.MARKDOWN)
        return

    # Verificar que la función de logs ha sido inyectada correctamente
    if not _get_logs_data_ref:
       
        await update.message.reply_text(_("❌ Error interno: La función de logs no ha sido inicializada.", current_chat_id))
        return

    # Obtener todas las líneas del log
    log_data_full = _get_logs_data_ref()

    # 1. Obtener argumento opcional: número de líneas (por defecto 10)
    n_lineas_default = 10
    try:
        n_lineas = int(context.args[0]) if context.args and context.args[0].isdigit() else n_lineas_default
        n_lineas = max(1, min(n_lineas, 100))
    except ValueError:
        # --- MENSAJE ENVUELTO ---
        await update.message.reply_text(_("⚠️ El argumento debe ser un número entero.", current_chat_id))
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
    # --- PLANTILLA ENVUELTA ---
    mensaje_template = _(
        "🤖 *Estado de BitBread Alert*\n"
        "————————————————————\n"
        "• Versión: {version} 🤖\n"
        "• PID: {pid} 🪪\n"
        "• Python: {python_version} 🐍\n"
        "• Usuarios: {num_usuarios} 👥\n"
        "• Estado: {estado} 👌\n"
        "• Última Actualización: {ultima_actualizacion} 🕒 \n"
        "————————————————————\n"
        "•📜 *Últimas {num_lineas} líneas de {total_lineas} *\n ```{log_str}```\n",
        current_chat_id
    )
    mensaje = mensaje_template.format(
        version=VERSION,
        pid=PID,
        python_version=PYTHON_VERSION,
        num_usuarios=len(cargar_usuarios()),
        estado=STATE,
        ultima_actualizacion=ultima_actualizacion,
        num_lineas=len(log_data_n_lines),
        total_lineas=len(log_data_full),
        log_str=log_str
    )

    await update.message.reply_text(mensaje, parse_mode=ParseMode.MARKDOWN)