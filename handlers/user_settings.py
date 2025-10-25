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
                                      toggle_hbd_alert_status, set_user_language, get_user_language
                                ) 
from core.api_client import obtener_precios_control
from core.loops import set_custom_alert_history_util # Nueva importación
from core.config import ADMIN_CHAT_IDS

from core.i18n import _ # <-- AGREGAR LA FUNCIÓN DE TRADUCCIÓN

# Soporte de idiomas
SUPPORTED_LANGUAGES = {
    'es': '🇪🇸 Español',
    'en': '🇬🇧 English',
    'pt': '🇧🇷 Português',
    # Agrega más aquí cuando tengas los archivos .po/.mo
}

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
    
    if not user_input:
        # Mostrar configuración actual
        usuarios = cargar_usuarios()
        intervalo_actual = usuarios.get(str(chat_id), {}).get('intervalo_alerta_h', 1.0)
        
        # Mensaje 1: Configuración actual (requiere formateo)
        mensaje_base = _(
            "⚙️ *Configuración de Temporalidad*\n"
            "Tu intervalo de alerta actual es de *{intervalo_actual} horas*.\n\n"
            "Para cambiarlo, envía el comando con las horas deseadas (desde 1h hasta 12h).\n"
            "Ejemplo: `/temp 2.5` (para 2 horas y 30 minutos).",
            user_id
        )
        mensaje = mensaje_base.format(intervalo_actual=intervalo_actual)
        await update.message.reply_text(mensaje, parse_mode=ParseMode.MARKDOWN)
        return

    try:
        interval_h = float(user_input)
        
        # Validar el rango de horas (0.5h a 24.0h)
        if not (0.02 <= interval_h <= 24.0):
            # Mensaje 2: Rango inválido
            mensaje_rango_invalido = _("⚠️ El valor debe ser un número entre *0.5* (30min) y *24.0* horas. Ejemplo: `2.5`", chat_id)
            await update.message.reply_text(mensaje_rango_invalido, parse_mode=ParseMode.MARKDOWN)
            return

        # 1. Guardar el nuevo intervalo
        if not actualizar_intervalo_alerta(chat_id, interval_h):
            # Mensaje 3: Error al guardar
            mensaje_error_guardar = _("❌ No se pudo guardar tu configuración. ¿Estás registrado con /start?", chat_id)
            await update.message.reply_text(mensaje_error_guardar, parse_mode=ParseMode.MARKDOWN)
            return
            
        # 2. Reprogramar la alerta (usando la función inyectada)
        if _reprogramar_alerta_ref:
            # Mensaje 4: Éxito con reprogramación (requiere formateo)
            _reprogramar_alerta_ref(chat_id, interval_h)
            mensaje_base_final = _(
                "✅ ¡Temporalidad de alerta actualizada a *{interval_h} horas*!\n"
                "La alerta con tus monedas ha sido *reprogramada* para ejecutarse cada {interval_h} horas.",
                user_id
            )
            mensaje_final = mensaje_base_final.format(interval_h=interval_h)
        else:
            # Mensaje 5: Éxito sin reprogramación (requiere formateo)
            mensaje_base_final = _(
                "✅ ¡Temporalidad de alerta actualizada a *{interval_h} horas*!\n"
                "⚠️ Pero hubo un error al reprogramar la alerta. Intenta enviar /temp nuevamente.",
                user_id
            )
            mensaje_final = mensaje_base_final.format(interval_h=interval_h)

        await update.message.reply_text(mensaje_final, parse_mode=ParseMode.MARKDOWN)

    except ValueError:
        # Mensaje 6: Formato de hora inválido
        mensaje_error_valor = _("⚠️ Formato de hora inválido. Usa un número como `2` o `2.5` (minimo 0.5)(máximo 24.0).", user_id)
        await update.message.reply_text(mensaje_error_valor, parse_mode=ParseMode.MARKDOWN)
    except IndexError:
        # Mensaje 7: Falta el argumento
        mensaje_error_indice = _("⚠️ Debes especificar el número de horas. Ejemplo: `/temp 2.5`", user_id)
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

    # 3. Guardar la nueva lista de monedas
    actualizar_monedas(chat_id, monedas)
    
    # 4. Obtener los precios de la nueva lista para dar una respuesta inmediata
    precios = obtener_precios_control(monedas)

    # 5. Construir y enviar el mensaje de confirmación
    if precios:
        # Mensaje 3a: Éxito con precios disponibles
        encabezado_base = _("✅ *Tu lista de monedas ha sido guardada.*\n\nPrecios actuales:\n", user_id)
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

# COMANDO /hbdalerts para activar/desactivar alertas de HBD
async def hbd_alerts_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra el estado de las alertas HBD y permite al usuario activarlas/desactivarlas."""
    user_id = update.effective_user.id
    usuarios = cargar_usuarios()
    user_data = usuarios.get(str(user_id), {})

    # Se asume True si la clave no existe (para usuarios antiguos)
    is_enabled = user_data.get('hbd_alerts', True)

    if is_enabled:
        # Mensaje 1: Alertas activadas
        text = _(
            "✅ Tus alertas predefinidas de HBD están *ACTIVADAS*.",
            user_id
        )
        # Botón 1: Desactivar
        button_text = _(
            "🔕 Desactivar alertas",
            user_id
        )
    else:
        # Mensaje 2: Alertas desactivadas
        text = _(
            "☑️ Tus alertas predefinidas de HBD están *DESACTIVADAS*.",
            user_id
        )
        # Botón 2: Activar
        button_text = _(
            "🔔 Activar alertas",
            user_id
        )

    # Reutilizamos el mismo callback_data para no tener que crear un nuevo handler
    keyboard = [[
        InlineKeyboardButton(button_text, callback_data="toggle_hbd_alerts")
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)

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
            "✅ ¡Idioma cambiado a **{new_lang_name}**!\n"
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