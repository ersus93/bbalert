# handlers/admin.py


import asyncio
import os
import openpyxl 
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import BadRequest  # <--- NUEVO
from io import BytesIO
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
from collections import Counter
from utils.file_manager import cargar_usuarios, load_price_alerts, get_user_alerts, load_hbd_history
from utils.ads_manager import load_ads, add_ad, delete_ad
from core.config import VERSION, PID, PYTHON_VERSION, STATE, ADMIN_CHAT_IDS
from core.i18n import _

# Definimos los estados para nuestra conversación de mensaje masivo
AWAITING_CONTENT, AWAITING_CONFIRMATION, AWAITING_ADDITIONAL_TEXT, AWAITING_ADDITIONAL_PHOTO = range(4)


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

# COMANDO /users 
async def users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Comando /users mejorado. 
    - Usuarios normales: Ven su propio perfil.
    - Admins: Ven estadísticas globales, desglose VIP y últimos registros.
    """
    current_chat_id = update.effective_chat.id
    current_chat_id_str = str(current_chat_id)
    usuarios = cargar_usuarios() # Carga users.json
    all_alerts = load_price_alerts() # Carga price_alerts.json

    # --- VISTA DE USUARIO NORMAL (Sin cambios) ---
    if current_chat_id_str not in ADMIN_CHAT_IDS:
        data = usuarios.get(current_chat_id_str)
        if not data:
            await update.message.reply_text(_("😕 No estás registrado en el sistema.", current_chat_id))
            return

        monedas_str = ', '.join(data.get('monedas', []))
        intervalo_h = data.get('intervalo_alerta_h', 1.0)
        user_id = int(current_chat_id_str)
        # Contamos alertas activas específicas de este usuario
        user_alerts = [a for a in all_alerts.get(current_chat_id_str, []) if a['status'] == 'ACTIVE']
        alertas_activas = len(user_alerts)

        try:
            chat_info = await context.bot.get_chat(user_id)
            nombre_completo = chat_info.full_name or "N/A"
            username_str = f"@{chat_info.username}" if chat_info.username else "N/A"
        except Exception as e:
            nombre_completo = data.get('first_name', 'N/A')
            username_str = f"@{data.get('username', 'N/A')}"
            if 'Bot blocked' in str(e):
                nombre_completo += " (Bloqueado)"
        
        mensaje_template = _(
            "👤 *Tu Perfil Registrado*\n"
            "—————————————————\n"
            "  - Nombre: {nombre_completo}\n"
            "  - 🪪 ID: `{user_id}`\n"
            "  - 👤 Usuario: {username_str}\n"
            "  - 🪙 Monedas: `{monedas_str}`\n"
            "  - ⏰ Alerta cada: {intervalo_h}h\n"
            "  - 🔔 Alertas cruce activas: {alertas_activas}\n"
            "—————————————————\n"
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

    # --- VISTA DE ADMINISTRADOR (NUEVA LÓGICA VIP) ---
    msg_procesando = await update.message.reply_text("⏳ Calculando estadísticas...")
    
    # 1. Cálculos Estadísticos Generales
    total_usuarios = len(usuarios)
    
    # Alertas de cruce activas
    total_alertas_cruce = sum(
        len([a for a in alerts if a['status'] == 'ACTIVE']) 
        for alerts in all_alerts.values()
    )
    
    # Alertas HBD
    total_hbd_users = sum(1 for u in usuarios.values() if u.get('hbd_alerts', False))
    porcentaje_hbd = (total_hbd_users / total_usuarios * 100) if total_usuarios > 0 else 0

    # --- 2. CÁLCULO DE SUSCRIPCIONES PREMIUM (VIP) ---
    # Contadores inicializados
    vip_stats = {
        'watchlist_bundle': 0, # Pack Control Total
        'tasa_vip': 0,         # Tasa VIP
        'ta_vip': 0,           # TA Pro
        'coins_extra': 0,      # Espacios Moneda Extra (Usuarios que tienen > 0)
        'alerts_extra': 0      # Alertas Cruce Extra (Usuarios que tienen > 0)
    }

    now = datetime.now()

    for u in usuarios.values():
        subs = u.get('subscriptions', {})
        
        # Verificar Pack Control Total
        wb = subs.get('watchlist_bundle', {})
        if wb.get('active') and wb.get('expires'):
            try:
                if datetime.strptime(wb['expires'], '%Y-%m-%d %H:%M:%S') > now:
                    vip_stats['watchlist_bundle'] += 1
            except ValueError: pass

        # Verificar Tasa VIP
        tv = subs.get('tasa_vip', {})
        if tv.get('active') and tv.get('expires'):
            try:
                if datetime.strptime(tv['expires'], '%Y-%m-%d %H:%M:%S') > now:
                    vip_stats['tasa_vip'] += 1
            except ValueError: pass

        # Verificar TA Pro
        tav = subs.get('ta_vip', {})
        if tav.get('active') and tav.get('expires'):
            try:
                if datetime.strptime(tav['expires'], '%Y-%m-%d %H:%M:%S') > now:
                    vip_stats['ta_vip'] += 1
            except ValueError: pass

        # Verificar Extras (Monedas)
        ce = subs.get('coins_extra', {})
        if ce.get('qty', 0) > 0:
            # Aquí podríamos contar usuarios O contar total de slots vendidos. 
            # Contaremos usuarios que han comprado al menos 1 slot.
            vip_stats['coins_extra'] += 1

        # Verificar Extras (Alertas)
        ae = subs.get('alerts_extra', {})
        if ae.get('qty', 0) > 0:
            vip_stats['alerts_extra'] += 1

    # Total de usuarios únicos con ALGO pagado (aprox)
    # Nota: Es una aproximación simple, un usuario puede tener varios packs.
    # Para ser exacto habría que usar un set de IDs.
    
    # --- 3. Top Monedas y Usuarios Pesados ---
    todas_monedas = []
    for u in usuarios.values():
        todas_monedas.extend(u.get('monedas', []))
    conteo_monedas = Counter(todas_monedas)
    top_5_monedas = conteo_monedas.most_common(5)
    top_5_monedas_str = ", ".join([f"{m} ({c})" for m, c in top_5_monedas])

    # Usuarios más pesados
    users_by_alerts = []
    for uid, alerts in all_alerts.items():
        active_count = len([a for a in alerts if a['status'] == 'ACTIVE'])
        if active_count > 0:
            users_by_alerts.append((uid, active_count))
    
    users_by_alerts.sort(key=lambda x: x[1], reverse=True)
    top_3_users_data = users_by_alerts[:3]
    
    top_3_str = ""
    for idx, (uid, count) in enumerate(top_3_users_data):
        u_data = usuarios.get(uid, {})
        name_display = u_data.get('username', uid) 
        top_3_str += f"{idx+1}. {name_display}: {count} alertas\n"
    if not top_3_str: top_3_str = "N/A"

    # --- 4. Últimos Registros ---
    lista_ids_usuarios = list(usuarios.keys())
    ultimos_5_ids = lista_ids_usuarios[-5:]
    ultimos_5_ids.reverse()

    detalles_ultimos = []
    for chat_id_str in ultimos_5_ids:
        data = usuarios[chat_id_str]
        chat_id = int(chat_id_str)
        monedas_user = ', '.join(data.get('monedas', []))
        try:
            chat_info = await context.bot.get_chat(chat_id)
            nombre_completo = chat_info.full_name or "N/A"
            username_str = f"@{chat_info.username}" if chat_info.username else "N/A"
        except Exception:
            nombre_completo = "Desconocido"
            username_str = "N/A"

        detalles_ultimos.append(
            f"🔹 {nombre_completo} ({username_str}) | ID: {chat_id}\n"
            f"   Monedas: {monedas_user}"
        )

    # --- 5. Construcción del Mensaje ---
    mensaje_admin = (
        f"📊 *ESTADÍSTICAS GENERALES\n🤖 BitBread Alert* (v{VERSION})\n"
        f"—————————————————\n" 
        f"👥 *Usuarios Totales:* `{total_usuarios}`\n"
        f"🔔 *Alertas Cruce:* `{total_alertas_cruce}` activas\n"
        f"📢 *Subs HBD:* `{total_hbd_users}` ({porcentaje_hbd:.1f}%)\n•\n"
        
        f"💎 *ESTADÍSTICAS PREMIUM (Activos)*\n"
        f"📦 Pack Control Total: `{vip_stats['watchlist_bundle']}`\n"
        f"💱 Tasa VIP: `{vip_stats['tasa_vip']}`\n"
        f"📈 TA Pro: `{vip_stats['ta_vip']}`\n"
        f"🪙 Extra Monedas: `{vip_stats['coins_extra']}` usuarios\n"
        f"🔔 Extra Alertas: `{vip_stats['alerts_extra']}` usuarios\n•\n"
        
        f"🏆 *Top 5 Monedas:*\n"
        f"`{top_5_monedas_str}`\n•\n"
        
        f"⚡ *Top 3 Heavy Users (Alertas):*\n"
        f"{top_3_str}\n"
        
        f"🆕 *Últimos 5 Registrados:*\n"
        f"—————————————————\n"
        f"```{chr(10).join(detalles_ultimos)}```"
    )

    await msg_procesando.delete() 
    await update.message.reply_text(mensaje_admin, parse_mode=ParseMode.MARKDOWN)



# COMANDO /logs para ver las últimas líneas del log
async def logs_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    current_chat_id = update.effective_chat.id # <-- Obtener chat_id
    global _get_logs_data_ref # <--- ¡ARREGLO 1: Mover esta línea aquí!
    
    # Comprobar si el ID está en la lista de administradores
    if str(current_chat_id) not in ADMIN_CHAT_IDS:
        # Obtener la última actualización desde el log si es posible
        # global _get_logs_data_ref <--- Quitarla de aquí
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
            "—————————————————\n"
            "• Versión: {version} 🤖\n"
            "• Estado: {estado} 👌\n"
            "• Última Actualización: {ultima_actualizacion} 🕒 \n"
            "—————————————————\n\n"
            "_Ya, eso es todo lo que puedes ver 🙂👍_",
            current_chat_id
        )
        
        # --- ¡NUEVA SECCIÓN DE ESCAPE! ---
        # Escapamos las variables para evitar errores de Markdown
        safe_version = str(VERSION).replace("_", " ").replace("*", " ").replace("`", " ")
        safe_estado = str(STATE).replace("_", " ").replace("*", " ").replace("`", " ")
        safe_ultima_actualizacion = str(ultima_actualizacion).replace("_", " ").replace("*", " ").replace("`", " ")

        mensaje = mensaje_template.format(
            version=safe_version,
            estado=safe_estado,
            ultima_actualizacion=safe_ultima_actualizacion
        )
        await update.message.reply_text(mensaje, parse_mode=ParseMode.MARKDOWN)
        return

    # --- Lógica de Administrador ---
    
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
    
    # (Esta es tu limpieza de logs, que ya estaba bien)
    log_lines_cleaned = [
        line.replace("_", " ").replace("*", "#").replace("`", "'")
            .replace("[", "(").replace("]", ")")
        for line in log_data_n_lines
    ]

    log_str = "\n".join(log_lines_cleaned)

    # Extraer la marca de tiempo de la última línea del log
    ultima_actualizacion = "N/A"
    if log_data_full: 
        try:
            timestamp_ms_part = log_data_full[-1].split(" | ")[0] 
            timestamp_part = timestamp_ms_part.split("[")[1].split("]")[0].strip()
            ultima_actualizacion = f"{timestamp_part} UTC"
        except Exception:
            pass

    # 3. Mensaje de respuesta completo para administradores
    # --- PLANTILLA ENVUELTA ---
    mensaje_template = _(
        "🤖 *Estado de BitBread Alert*\n"
        "—————————————————\n"
        "• Versión: {version} 🤖\n"
        "• PID: {pid} 🪪\n"
        "• Python: {python_version} 🐍\n"
        "• Usuarios: {num_usuarios} 👥\n"
        "• Estado: {estado} 👌\n"
        "• Última Actualización: {ultima_actualizacion} 🕒 \n"
        "—————————————————\n"
        "•📜 *Últimas {num_lineas} líneas de {total_lineas} *\n ```{log_str}```\n",
        current_chat_id
    )

    # --- ¡NUEVA SECCIÓN DE ESCAPE (PARA ADMIN)! ---
    # Escapamos todas las variables que podrían contener _ * `
    safe_version = str(VERSION).replace("_", " ").replace("*", " ").replace("`", " ")
    safe_pid = str(PID).replace("_", " ").replace("*", " ").replace("`", " ")
    safe_python_version = str(PYTHON_VERSION).replace("_", " ").replace("*", " ").replace("`", " ")
    safe_estado = str(STATE).replace("_", " ").replace("*", " ").replace("`", " ")
    safe_ultima_actualizacion = str(ultima_actualizacion).replace("_", " ").replace("*", " ").replace("`", " ")

    mensaje = mensaje_template.format(
        version=safe_version,
        pid=safe_pid,
        python_version=safe_python_version,
        num_usuarios=len(cargar_usuarios()),
        estado=safe_estado,
        ultima_actualizacion=safe_ultima_actualizacion,
        num_lineas=len(log_data_n_lines),
        total_lineas=len(log_data_full),
        log_str=log_str
    )

    await update.message.reply_text(mensaje, parse_mode=ParseMode.MARKDOWN)


# --- COMANDO /ad SUPER ROBUSTO ---
async def ad_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Gestión de anuncios robusta.
    Si el Markdown del usuario falla, se envía en texto plano.
    """
    chat_id = update.effective_chat.id
    user_id_str = str(update.effective_user.id)

    if user_id_str not in ADMIN_CHAT_IDS:
        return 

    args = context.args

    # --- LISTAR ANUNCIOS ---
    if not args:
        ads = load_ads()
        if not ads:
            await update.message.reply_text("📭 No hay anuncios activos.\nUsa `/ad add Mi Anuncio` para crear uno.", parse_mode=ParseMode.MARKDOWN)
            return
        
        mensaje = "📢 *Lista de Anuncios Activos:*\n\n"
        for i, ad in enumerate(ads):
            # Intentamos preservar el formato que haya puesto el usuario
            mensaje += f"*{i+1}.* {ad}\n"
        
        mensaje += "\nPara borrar: `/ad del N` (ej: `/ad del 1`)"

        try:
            await update.message.reply_text(mensaje, parse_mode=ParseMode.MARKDOWN)
        except BadRequest:
            # FALLBACK: Si falla el Markdown (ej: un '_' sin cerrar), enviamos texto plano
            fallback_msg = "⚠️ *Error de visualización Markdown*\n" \
                           "Alguno de tus anuncios tiene caracteres especiales sin cerrar, pero aquí está la lista en texto plano:\n\n"
            for i, ad in enumerate(ads):
                fallback_msg += f"{i+1}. {ad}\n"
            
            fallback_msg += "\nUsa /ad del N para eliminar."
            await update.message.reply_text(fallback_msg) # Sin parse_mode
        return

    accion = args[0].lower()

    # --- AÑADIR ANUNCIO ---
    if accion == "add":
        if len(args) < 2:
            await update.message.reply_text("⚠️ Escribe el texto del anuncio.\nEj: `/ad add Visita mi canal @canal`", parse_mode=ParseMode.MARKDOWN)
            return
        
        texto_nuevo = ' '.join(args[1:]) 
        add_ad(texto_nuevo) # Guardamos EXACTAMENTE lo que escribió el usuario
        
        # Intentamos confirmar con Markdown bonito
        try:
            await update.message.reply_text(f"✅ Anuncio añadido:\n\n_{texto_nuevo}_", parse_mode=ParseMode.MARKDOWN)
        except BadRequest:
            # Si falla (ej: usuario puso 'pepe_bot' sin escapar), confirmamos en texto plano
            await update.message.reply_text(f"✅ Anuncio añadido (Sintaxis MD inválida, mostrado plano):\n\n{texto_nuevo}")

    # --- BORRAR ANUNCIO ---
    elif accion == "del":
        try:
            indice = int(args[1]) - 1 
            eliminado = delete_ad(indice)
            if eliminado:
                # Intentamos mostrar confirmación bonita
                try:
                    await update.message.reply_text(f"🗑️ Anuncio eliminado:\n\n_{eliminado}_", parse_mode=ParseMode.MARKDOWN)
                except BadRequest:
                     # Si falla, confirmamos en texto plano
                    await update.message.reply_text(f"🗑️ Anuncio eliminado:\n\n{eliminado}")
            else:
                await update.message.reply_text("⚠️ Número de anuncio no válido.", parse_mode=ParseMode.MARKDOWN)
        except (IndexError, ValueError):
            await update.message.reply_text("⚠️ Uso: `/ad del N` (N es el número del anuncio).", parse_mode=ParseMode.MARKDOWN)
    
    else:
        await update.message.reply_text("⚠️ Comandos: `/ad`, `/ad add <txt>`, `/ad del <num>`", parse_mode=ParseMode.MARKDOWN)