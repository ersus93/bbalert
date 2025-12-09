# handlers/user_settings.py


import asyncio
import os
import uuid
import openpyxl 
from datetime import datetime
from telegram import Update
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.ext import ConversationHandler, ContextTypes
from telegram.ext import ConversationHandler, CallbackQueryHandler
from telegram.constants import ParseMode
# importaciones de utilidades y configuración
from core.config import TOKEN_TELEGRAM, ADMIN_CHAT_IDS, PID, VERSION, STATE, PYTHON_VERSION, LOG_LINES, USUARIOS_PATH
from utils.file_manager import(cargar_usuarios, guardar_usuarios, registrar_usuario,\
                               actualizar_monedas, obtener_monedas_usuario, actualizar_intervalo_alerta, add_log_line,\
                                add_price_alert, get_user_alerts, delete_price_alert,delete_all_alerts,\
                                      toggle_hbd_alert_status, set_user_language, get_user_language,\
                                      toggle_hbd_alert_status, modify_hbd_threshold, load_hbd_thresholds,\
                                        check_feature_access, registrar_uso_comando
                                ) 
from core.api_client import obtener_precios_control
from core.loops import set_custom_alert_history_util # Nueva importación
from core.config import ADMIN_CHAT_IDS

from core.i18n import _ # <-- AGREGAR LA FUNCIÓN DE TRADUCCIÓN

# Soporte de idiomas
SUPPORTED_LANGUAGES = {
    'es': '🇪🇸 Español',
    'en': '🇬🇧 English'
}
    # Agrega más aquí cuando tengas los archivos .po/.mo


# ... (set_admin_util y set_logs_util) ...
_reprogramar_alerta_ref = None

def set_reprogramar_alerta_util(func):
    """Permite a bbalert inyectar la función de reprogramación de alerta."""
    global _reprogramar_alerta_ref
    _reprogramar_alerta_ref = func

# manejar texto para actualizar la lista de monedas
async def manejar_texto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja el texto plano (lista de monedas) para actualizar la configuración."""
    texto = update.message.text.upper().strip()
    chat_id = update.effective_chat.id # Obtener el ID para la traducción
    user_id = update.effective_user.id

    # Intenta parsear la lista de monedas
    monedas_limpias = [m.strip() for m in texto.split(',') if m.strip()]
    
    if monedas_limpias:
        # === GUARDIA DE CAPACIDAD ===
        # Verificamos si la longitud de la nueva lista está permitida
        acceso, mensaje = check_feature_access(update.effective_chat.id, 'coins_capacity', current_count=len(monedas_limpias))
        
        if not acceso:
            await update.message.reply_text(mensaje, parse_mode=ParseMode.MARKDOWN)
            return
        # ============================
        actualizar_monedas(chat_id, monedas_limpias)
        
        # Mensaje 1 (Éxito) - Requiere formateo
        mensaje_base = _(
            "✅ ¡Lista de monedas actualizada!\n"
            "Ahora recibirás alertas de para: `{monedas_limpias_str}`\n\n"
            "Puedes cambiar esta lista en cualquier momento enviando una nueva lista de símbolos separados por comas.",
             user_id
        )
        mensaje = mensaje_base.format(monedas_limpias_str=', '.join(monedas_limpias))
    else:
        # Mensaje 2 (Advertencia/Error)
        mensaje = _(
            "⚠️ Por favor, envía una lista de símbolos de monedas separados por comas. Ejemplo: `BTC, ETH, HIVE`",
            user_id
        )
        
    await update.message.reply_text(mensaje, parse_mode=ParseMode.MARKDOWN)


async def mismonedas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /mismonedas. Muestra las monedas que sigue el usuario."""
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    monedas = obtener_monedas_usuario(chat_id)
    
    if monedas:
        # Mensaje 1: Éxito (requiere formateo)
        mensaje_base = _(
            "✅ Listo! recibirás alertas para las siguientes monedas:\n`{monedas_str}`.",
            user_id
        )
        mensaje = mensaje_base.format(monedas_str=', '.join(monedas))
    else:
        # Mensaje 2: Advertencia
        mensaje = _(
            "⚠️ No tienes monedas configuradas para la alerta de tempralidad.",
            user_id
        )
        
    await update.message.reply_text(mensaje, parse_mode=ParseMode.MARKDOWN)


async def parar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /parar. Elimina las monedas del usuario para detener alertas de control."""
    chat_id = update.effective_chat.id
    actualizar_monedas(chat_id, [])
    
    mensaje = _(
        "🛑 Alertas detenidas. Ya no recibirás mensajes cada hora (a menos que vuelvas a configurar tu lista o ajustes la temporalidad).",
        chat_id
    )
    
    await update.message.reply_text(mensaje, parse_mode=ParseMode.MARKDOWN)


# 💡 COMANDO /temp ajustes de temporalidad de notificacion de lista
async def cmd_temp(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Permite al usuario configurar la temporalidad de sus alertas."""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    user_input = context.args[0] if context.args else None
    
    # 1. Obtener el límite permitido para este usuario
    # NOTA: Usamos 'msg_status' en lugar de '_' para no romper la función de traducción
    min_val, msg_status = check_feature_access(chat_id, 'temp_min_val')

    if not user_input:
        # Mostrar configuración actual
        usuarios = cargar_usuarios()
        intervalo_actual = usuarios.get(str(chat_id), {}).get('intervalo_alerta_h', 1.0)
        
        mensaje_base = _(
            "⚙️ *Configuración de Temporalidad*\n"
            "Tu intervalo de alerta actual es de *{intervalo_actual} horas*.\n\n"
            "Tu plan actual permite un mínimo de: *{min_val} horas*.\n"
            "Para cambiarlo, envía: `/temp <horas>` (ej: `/temp 8`).",
            user_id
        )
        mensaje = mensaje_base.format(intervalo_actual=intervalo_actual, min_val=min_val)
        await update.message.reply_text(mensaje, parse_mode=ParseMode.MARKDOWN)
        return

    try:
        # Reemplazar coma por punto para decimales (ej: 2,5 -> 2.5)
        interval_h = float(user_input.replace(',', '.'))

        # === GUARDIA 1: VALOR MÍNIMO PERMITIDO ===
        # Si intenta poner un valor menor al permitido (ej: pone 1.0 pero su mínimo es 4.0)
        if interval_h < min_val:
            mensaje_rango = _(
                f"🔒 *Función Premium*\n—————————————————\n\n"
                f"Has intentado configurar *{interval_h} horas*, pero tu plan actual solo permite un mínimo de *{min_val} horas*.\n\n"
                f"—————————————————\n"
                f"🚀 Adquiere el 'Pack Control Total' en /shop para desbloquear alertas rápidas (hasta 0.25h), estre otras funciones.",
                user_id
            )
            await update.message.reply_text(mensaje_rango, parse_mode=ParseMode.MARKDOWN)
            return
        
        # Validar el rango máximo lógico (24 horas)
        if interval_h > 24.0:
             await update.message.reply_text(_("⚠️ El máximo permitido es 24 horas.", user_id), parse_mode=ParseMode.MARKDOWN)
             return
        # ========================================

        # === GUARDIA 2: LÍMITE DE CAMBIOS DIARIOS ===
        acceso_cambio, msg_cambio = check_feature_access(chat_id, 'temp_change_limit')
        if not acceso_cambio:
            await update.message.reply_text(msg_cambio, parse_mode=ParseMode.MARKDOWN)
            return
        # ============================================
        
        # 1. Guardar el nuevo intervalo
        if not actualizar_intervalo_alerta(chat_id, interval_h):
            mensaje_error_guardar = _("❌ No se pudo guardar tu configuración. ¿Estás registrado con /start?", chat_id)
            await update.message.reply_text(mensaje_error_guardar, parse_mode=ParseMode.MARKDOWN)
            return
            
        # === REGISTRAR EL USO ===
        registrar_uso_comando(chat_id, 'temp_changes')
        # ========================
            
        # 2. Reprogramar la alerta
        msg_extra = ""
        if _reprogramar_alerta_ref:
            try:
                _reprogramar_alerta_ref(chat_id, interval_h)
            except Exception as e:
                msg_extra = "\n⚠️ (Alerta guardada, se aplicará en el próximo ciclo)"
        
        mensaje_base_final = _(
            "✅ ¡Temporalidad actualizada a *{interval_h} horas*!\n"
            "Tus alertas llegarán con esta frecuencia.{extra}",
            user_id
        )
        mensaje_final = mensaje_base_final.format(interval_h=interval_h, extra=msg_extra)

        await update.message.reply_text(mensaje_final, parse_mode=ParseMode.MARKDOWN)

    except ValueError:
        mensaje_error_valor = _("⚠️ Formato inválido. Usa un número. Ejemplo: `/temp 4` o `/temp 2.5`", user_id)
        await update.message.reply_text(mensaje_error_valor, parse_mode=ParseMode.MARKDOWN)
    except IndexError:
        mensaje_error_indice = _("⚠️ Debes especificar las horas. Ejemplo: `/temp 4`", user_id)
        await update.message.reply_text(mensaje_error_indice, parse_mode=ParseMode.MARKDOWN)


# === LÓGICA DE JOBQUEUE PARA ALERTAS DE TEMPORALIDAD ===
async def set_monedas_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Comando /monedas. Permite al usuario establecer su lista de monedas.
    Ejemplo: /monedas BTC, ETH, HIVE
    """
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    if not context.args:
        # Si el usuario solo envía /monedas, le mostramos cómo usarlo
        monedas_actuales = obtener_monedas_usuario(user_id)
        lista_str = '`' + ', '.join(monedas_actuales) + '`' if monedas_actuales else _("ninguna", user_id)
        
        # Mensaje 1: Formato incorrecto (requiere formateo para la lista actual)
        mensaje_base = _(
            "⚠️ *Formato incorrecto*.\n\n"
            "Para establecer tu lista de monedas, envía el comando seguido de los símbolos. Ejemplo:\n\n"
            "`/monedas BTC, ETH, HIVE, SOL`\n\n"
            "Tu lista actual es: {lista_str}",
            user_id
        )
        mensaje = mensaje_base.format(lista_str=lista_str)
        await update.message.reply_text(mensaje, parse_mode=ParseMode.MARKDOWN)
        return

    # 1. Unir todos los argumentos en un solo string
    texto_recibido = ' '.join(context.args)
    
    # 2. Limpiar y procesar la entrada del usuario
    monedas = [m.strip().upper() for m in texto_recibido.split(',') if m.strip()]

    if not monedas:
        # Mensaje 2: No se encontraron monedas
        mensaje_error_vacio = _("⚠️ No pude encontrar ninguna moneda en tu mensaje. Intenta de nuevo.", user_id)
        await update.message.reply_text(mensaje_error_vacio, parse_mode=ParseMode.MARKDOWN)
        return
    
    # === GUARDIA DE CAPACIDAD ===
    acceso, mensaje = check_feature_access(chat_id, 'coins_capacity', current_count=len(monedas))
    if not acceso:
        await update.message.reply_text(mensaje, parse_mode=ParseMode.MARKDOWN)
        return
    # ============================

    # 3. Guardar la nueva lista de monedas
    actualizar_monedas(chat_id, monedas)
    
    # 4. Obtener los precios de la nueva lista para dar una respuesta inmediata
    precios = obtener_precios_control(monedas)

    # 5. Construir y enviar el mensaje de confirmación
    if precios:
        # Mensaje 3a: Éxito con precios disponibles
        encabezado_base = _("✅ *Tu lista de monedas ha sido guardada.*\n—————————————————\n\n*Precios actuales:*\n•\n", user_id)
        mensaje_respuesta = encabezado_base
        
        # Etiqueta 4: 'No encontrado'
        etiqueta_no_encontrado = _("No encontrado", user_id)
        
        for moneda in monedas:
            precio_actual = precios.get(moneda)
            if precio_actual:
                mensaje_respuesta += f"*{moneda}/USD*: ${precio_actual:,.4f}\n"
            else:
                mensaje_respuesta += f"*{moneda}/USD*: {etiqueta_no_encontrado}\n"
    else:
        # Mensaje 3b: Éxito sin precios disponibles
        mensaje_respuesta = _("✅ *Tu lista de monedas ha sido guardada*, pero no pude obtener los precios en este momento.", user_id)

    await update.message.reply_text(mensaje_respuesta, parse_mode=ParseMode.MARKDOWN)

# COMANDO /hbdalerts (Actualizado con lógica Admin)
async def hbd_alerts_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Gestión de alertas HBD.
    Admins: /hbdalerts add/del/edit <precio> [run/stop]
    Usuarios: Ver lista y botón Activar/Desactivar suscripción personal.
    """
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    user_id_str = str(user_id)
    args = context.args

    # --- LÓGICA DE ADMINISTRADOR (Edición) ---
    if user_id_str in ADMIN_CHAT_IDS and args:
        if len(args) < 2:
            await update.message.reply_text(
                "👮‍♂️ *Admin*: Uso: `/hbdalerts <add|del|edit> <precio> [run|stop]`",
                parse_mode=ParseMode.MARKDOWN
            )
            return

        action = args[0].lower()
        try:
            precio = float(args[1].replace(',', '.'))
        except ValueError:
            await update.message.reply_text("⚠️ El precio debe ser un número válido.")
            return

        sub_action = args[2].lower() if len(args) > 2 else None

        # Mapeo de lógica para 'edit' con 'run/stop'
        final_action = action
        if action == 'edit':
            if sub_action in ['run', 'stop']:
                final_action = sub_action
            else:
                await update.message.reply_text("⚠️ Para editar usa: `/hbdalerts edit <precio> run` o `stop`.")
                return

        success, msg = modify_hbd_threshold(precio, final_action)
        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
        return

    # --- VISTA GENERAL (Usuarios y Admins sin argumentos) ---
    
    # 1. Obtener estado de suscripción del usuario
    usuarios = cargar_usuarios()
    user_data = usuarios.get(str(user_id), {})
    is_subscribed = user_data.get('hbd_alerts', False)

    # 2. Cargar lista de umbrales configurados
    thresholds = load_hbd_thresholds()
    
    # Ordenar precios de mayor a menor para visualizar (convertimos a float para ordenar numéricamente)
    sorted_prices = sorted(thresholds.keys(), key=lambda x: float(x), reverse=True)

    lista_msg = ""
    if not thresholds:
        lista_msg = _("_(No hay alertas configuradas por el administrador)_", user_id)
    else:
        for p in sorted_prices:
            status = thresholds[p]
            icon = "🟢 Running" if status else "🔴 Stopped"
            
            # --- CAMBIO: Convertir a float y formatear a 4 decimales para visualización ---
            try:
                precio_display = f"{float(p):.4f}"
            except ValueError:
                precio_display = p # Fallback por si hay error de datos
            # -----------------------------------------------------------------------------

            lista_msg += f"• *${precio_display}* USD ({icon})\n"

    # 3. Construir mensaje
    encabezado = _("🚨 *Configuración de Alertas HBD*\n—————————————————\n\n", user_id)
    
    estado_usuario = _("✅ Tus notificaciones están *ACTIVADAS*", user_id) if is_subscribed else _("☑️ Tus notificaciones están *DESACTIVADAS*", user_id)
    
    mensaje_final = (
        f"{encabezado}"
        f"{lista_msg}\n"
        f"—————————————————\n"
        f"{estado_usuario}\n\n"
        f"_{_('Usa el botón abajo para cambiar tu preferencia.', user_id)}_"
    )

    # 4. Botón Toggle
    if is_subscribed:
        button_text = _("🔕 Desactivar mis alertas", user_id)
    else:
        button_text = _("🔔 Activar mis alertas", user_id)

    keyboard = [[
        InlineKeyboardButton(button_text, callback_data="toggle_hbd_alerts")
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(mensaje_final, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)


# Callback para el botón de activar/desactivar alertas de HBD
async def toggle_hbd_alerts_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja el callback del botón para activar/desactivar las alertas de HBD."""
    query = update.callback_query
    await query.answer() 

    user_id = query.from_user.id
    new_status = toggle_hbd_alert_status(user_id) # Cambia el estado y obtiene el nuevo

    if new_status:
        # Mensaje 1: Activado
        text = _(
            "✅ ¡Alertas de HBD *activadas*! Volverás a recibir notificaciones.",
            user_id
        )
        # Botón 1: Desactivar
        button_text = _(
            "🔕 Desactivar estas alertas",
            user_id
        )
    else:
        # Mensaje 2: Desactivado
        text = _(
            "☑️ Alertas de HBD *desactivadas*. Ya no recibirás estos mensajes.",
            user_id
        )
        # Botón 2: Activar
        button_text = _(
            "🔔 Activar alertas de HBD",
            user_id
        )

    # Actualiza el mensaje original con el nuevo texto y el nuevo botón
    keyboard = [[
        InlineKeyboardButton(button_text, callback_data="toggle_hbd_alerts")
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(text=text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)

# COMANDO /lang para cambiar el idioma
async def lang_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra el menú para cambiar el idioma."""
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    current_lang = get_user_language(user_id)

    # Usamos la traducción para el texto de introducción
    # Mensaje 1: Introducción al menú de idiomas
    text = _(
        "🌐 *Selecciona tu idioma:*\n\n"
        "El idioma actual es: {current_lang_name}",
        user_id
    ).format(current_lang_name=SUPPORTED_LANGUAGES.get(current_lang, 'N/A'))

    keyboard = []
    for code, name in SUPPORTED_LANGUAGES.items():
        keyboard.append([InlineKeyboardButton(
            name + (' ✅' if code == current_lang else ''), 
            callback_data=f"set_lang_{code}"
        )])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)

# CALLBACK para cambiar el idioma
async def set_language_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    lang_code = query.data.split("set_lang_")[1]

    if lang_code in SUPPORTED_LANGUAGES:
        set_user_language(user_id, lang_code)

        # Recarga el traductor para el nuevo idioma ANTES de generar el mensaje

        # Mensaje 1: Éxito (requiere formateo)
        new_text = _(
            "✅ ¡Idioma cambiado a *{new_lang_name}*!\n"
            "Usa el comando /lang si deseas cambiarlo de nuevo.",
            user_id
        ).format(new_lang_name=SUPPORTED_LANGUAGES[lang_code])

        await query.edit_message_text(new_text, parse_mode=ParseMode.MARKDOWN)
    else:
        # Mensaje 2: Error
        await query.edit_message_text(
            _(
                "⚠️ Idioma no soportado.", 
                user_id
            ), 
            parse_mode=ParseMode.MARKDOWN
        )