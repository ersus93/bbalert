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
                                add_price_alert, get_user_alerts, delete_price_alert,delete_all_alerts, toggle_hbd_alert_status
                                ) 
from core.api_client import obtener_precios_control
from core.loops import set_custom_alert_history_util # Nueva importación
from core.config import ADMIN_CHAT_IDS

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
    
    # Intenta parsear la lista de monedas
    monedas_limpias = [m.strip() for m in texto.split(',') if m.strip()]
    
    if monedas_limpias:
        actualizar_monedas(update.effective_chat.id, monedas_limpias)
        mensaje = (
            f"✅ ¡Lista de monedas actualizada!\n"
            f"Ahora recibirás alertas de para: `{', '.join(monedas_limpias)}`\n\n"
            f"Puedes cambiar esta lista en cualquier momento enviando una nueva lista de símbolos separados por comas."
        )
    else:
        mensaje = "⚠️ Por favor, envía una lista de símbolos de monedas separados por comas. Ejemplo: `BTC, ETH, HIVE`"
        
    await update.message.reply_text(mensaje, parse_mode=ParseMode.MARKDOWN)


async def mismonedas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /mismonedas. Muestra las monedas que sigue el usuario."""
    monedas = obtener_monedas_usuario(update.effective_chat.id)
    if monedas:
        mensaje = f"✅ Listo! recibirás alertas para las siguientes monedas:\n`{', '.join(monedas)}`."
    else:
        mensaje = "⚠️ No tienes monedas configuradas para la alerta de tempralidad."
        
    await update.message.reply_text(mensaje, parse_mode=ParseMode.MARKDOWN)


async def parar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /parar. Elimina las monedas del usuario para detener alertas de control."""
    actualizar_monedas(update.effective_chat.id, [])
    await update.message.reply_text("🛑 Alertas  detenidas. Ya no recibirás mensajes cada hora (a menos que vuelvas a configurar tu lista o ajustes la temporalidad).", parse_mode=ParseMode.MARKDOWN)


# 💡 COMANDO /temp ajustes de temporalidad de notificacion de lista
async def cmd_temp(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Permite al usuario configurar la temporalidad de sus alertas."""
    chat_id = update.effective_chat.id
    user_input = context.args[0] if context.args else None
    
    if not user_input:
        # Mostrar configuración actual
        usuarios = cargar_usuarios()
        intervalo_actual = usuarios.get(str(chat_id), {}).get('intervalo_alerta_h', 1.0)
        
        mensaje = (
            "⚙️ *Configuración de Temporalidad*\n"
            f"Tu intervalo de alerta actual es de *{intervalo_actual} horas*.\n\n"
            "Para cambiarlo, envía el comando con las horas deseadas (desde 1h hasta 12h).\n"
            "Ejemplo: `/temp 2.5` (para 2 horas y 30 minutos)." # 💡 Comando actualizado a /temp
        )
        await update.message.reply_text(mensaje, parse_mode=ParseMode.MARKDOWN)
        return

    try:
        interval_h = float(user_input)
        
        # Validar el rango de horas (0.5h a 24.0h)
        if not (0.02 <= interval_h <= 24.0):
            await update.message.reply_text("⚠️ El valor debe ser un número entre *0.5* (30min) y *24.0* horas. Ejemplo: `2.5`", parse_mode=ParseMode.MARKDOWN)
            return

        # 1. Guardar el nuevo intervalo
        if not actualizar_intervalo_alerta(chat_id, interval_h):
             await update.message.reply_text("❌ No se pudo guardar tu configuración. ¿Estás registrado con /start?", parse_mode=ParseMode.MARKDOWN)
             return
             
        # 2. Reprogramar la alerta (usando la función inyectada)
        if _reprogramar_alerta_ref:
            # Llama a la función programar_alerta_usuario de bbalert.py
            _reprogramar_alerta_ref(chat_id, interval_h)
            mensaje_final = (
                f"✅ ¡Temporalidad de alerta actualizada a *{interval_h} horas*!\n"
                f"La alerta con tus monedas ha sido *reprogramada* para ejecutarse cada {interval_h} horas."
            )
        else:
            # Fallback en caso de que la inyección falle
            mensaje_final = (
                f"✅ ¡Temporalidad de alerta actualizada a *{interval_h} horas*!\n"
                "⚠️ Pero hubo un error al reprogramar la alerta. Intenta enviar /temp nuevamente."
            )

        await update.message.reply_text(mensaje_final, parse_mode=ParseMode.MARKDOWN)

    except ValueError:
        await update.message.reply_text("⚠️ Formato de hora inválido. Usa un número como `2` o `2.5` (minimo 0.5)(máximo 24.0).", parse_mode=ParseMode.MARKDOWN)
    except IndexError:
        await update.message.reply_text("⚠️ Debes especificar el número de horas. Ejemplo: `/temp 2.5`", parse_mode=ParseMode.MARKDOWN) # 💡 Comando actualizado a /temp

# === LÓGICA DE JOBQUEUE PARA ALERTAS DE TEMPORALIDAD ===
async def set_monedas_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Comando /monedas. Permite al usuario establecer su lista de monedas.
    Ejemplo: /monedas BTC, ETH, HIVE
    """
    chat_id = update.effective_chat.id
    
    if not context.args:
        # Si el usuario solo envía /monedas, le mostramos cómo usarlo
        monedas_actuales = obtener_monedas_usuario(chat_id)
        lista_str = '`' + ', '.join(monedas_actuales) + '`' if monedas_actuales else "ninguna"
        mensaje = (
            "⚠️ *Formato incorrecto*.\n\n"
            "Para establecer tu lista de monedas, envía el comando seguido de los símbolos. Ejemplo:\n\n"
            "`/monedas BTC, ETH, HIVE, SOL`\n\n"
            f"Tu lista actual es: {lista_str}"
        )
        await update.message.reply_text(mensaje, parse_mode=ParseMode.MARKDOWN)
        return

    # 1. Unir todos los argumentos en un solo string
    # (Permite formatos como: /monedas BTC,ETH,HIVE o /monedas BTC, ETH, HIVE)
    texto_recibido = ' '.join(context.args)
    
    # 2. Limpiar y procesar la entrada del usuario
    monedas = [m.strip().upper() for m in texto_recibido.split(',') if m.strip()]

    if not monedas:
        await update.message.reply_text("⚠️ No pude encontrar ninguna moneda en tu mensaje. Intenta de nuevo.", parse_mode=ParseMode.MARKDOWN)
        return

    # 3. Guardar la nueva lista de monedas
    actualizar_monedas(chat_id, monedas)
    
    # 4. Obtener los precios de la nueva lista para dar una respuesta inmediata
    precios = obtener_precios_control(monedas)

    # 5. Construir y enviar el mensaje de confirmación
    if precios:
        mensaje_respuesta = "✅ *Tu lista de monedas ha sido guardada.*\n\nPrecios actuales:\n"
        for moneda in monedas:
            precio_actual = precios.get(moneda)
            if precio_actual:
                mensaje_respuesta += f"*{moneda}/USD*: ${precio_actual:,.4f}\n"
            else:
                mensaje_respuesta += f"*{moneda}/USD*: No encontrado\n"
    else:
        mensaje_respuesta = "✅ *Tu lista de monedas ha sido guardada*, pero no pude obtener los precios en este momento."

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
        text = "✅ Tus alertas predefinidas de HBD están *ACTIVADAS*."
        button_text = "🔕 Desactivar alertas"
    else:
        text = "☑️ Tus alertas predefinidas de HBD están *DESACTIVADAS*."
        button_text = "🔔 Activar alertas"

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
    await query.answer()  # Responde al callback para que el cliente de Telegram no se quede esperando

    user_id = query.from_user.id
    new_status = toggle_hbd_alert_status(user_id) # Cambia el estado y obtiene el nuevo

    if new_status:
        # Si el nuevo estado es TRUE (activado)
        text = "✅ ¡Alertas de HBD *activadas*! Volverás a recibir notificaciones."
        button_text = "🔕 Desactivar estas alertas"
    else:
        # Si el nuevo estado es FALSE (desactivado)
        text = "☑️ Alertas de HBD *desactivadas*. Ya no recibirás estos mensajes."
        button_text = "🔔 Activar alertas de HBD"

    # Actualiza el mensaje original con el nuevo texto y el nuevo botón
    keyboard = [[
        InlineKeyboardButton(button_text, callback_data="toggle_hbd_alerts")
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(text=text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)