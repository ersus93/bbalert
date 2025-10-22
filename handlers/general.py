# handlers/general.py 

import asyncio
import os
import uuid
import openpyxl 
from datetime import datetime
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ConversationHandler, ContextTypes
from utils.file_manager import load_hbd_history, registrar_usuario
from core.config import ADMIN_CHAT_IDS
from core.i18n import _

#  Telegram comando /satart 

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /start. Registra al usuario."""

    user = update.effective_user # Obtén el objeto de usuario completo
    user_id = user.id # Obtener el chat_id
    user_lang = user.language_code # Obtener el idioma del cliente (ej. 'en', 'es')
    
    # Pasa el idioma del usuario al registrarlo
    registrar_usuario(user_id, user_lang) # <--- ÚNICA LLAMADA (Correcta)
    
    nombre_usuario = update.effective_user.first_name
    
    # ENVUELVE TODO EL MENSAJE CON _() y usa el chat_id
    mensaje = _(
    "*Hola👋 {nombre_usuario}!* Bienvenido a BitBreadAlert.\n\n"
    "Para recibir alertas periódicas con los precios de tu lista de monedas, "
    "usa el comando `/monedas` seguido de los símbolos separados por comas. "
    "Puedes usar *cualquier* símbolo de criptomoneda listado en CoinMarketCap. Ejemplo:\n\n"
    "`/monedas BTC, ETH, TRX, HIVE, ADA`\n\n"
    "Puedes modificar la temporalidad de esta alerta en cualquier momento con el comando /temp seguido de las horas (entre 0.5 y 24.0).\n"
    "Ejemplo: /temp 2.5 (para 2 horas y 30 minutos)\n\n",
    user_id # <-- PASA EL chat_id
).format(nombre_usuario=nombre_usuario) 

    await update.message.reply_text(mensaje, parse_mode=ParseMode.MARKDOWN)

# COMANDO /ver para ver la última lectura de precios
from utils.file_manager import load_hbd_history # Nueva importación

async def ver(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra la última lectura de precios desde el historial JSON."""
    history = load_hbd_history()
    user_id = update.effective_user.id # <-- Obtener chat_id

    if not history:
        # --- MENSAJE ENVUELTO ---
        await update.message.reply_text(_("⚠️ No hay registros de precios aún.", user_id))
        return

    # El último registro es el más reciente
    ultimo_registro = history[-1]
    
    fecha_str = ultimo_registro.get('timestamp', 'N/A')
    btc = ultimo_registro.get('btc', 0)
    hive = ultimo_registro.get('hive', 0)
    hbd = ultimo_registro.get('hbd', 0)
    ton = ultimo_registro.get('ton', 0)

    mensaje_template = _(
        """📊 *Última lectura (máx. 5 min atrás):*

🟠 *BTC/USD*: ${btc_val:,.2f}
🔷 *TON/USD*: ${ton_val:,.4f}
🐝 *HIVE/USD*: ${hive_val:,.4f}
💰 *HBD/USD*: ${hbd_val:,.4f}

_Actualizado: {fecha}_""",
        user_id # Pasar el chat_id para obtener la traducción
    )
    
    # Rellenar la plantilla con los valores reales
    mensaje = mensaje_template.format(
        btc_val=btc,
        ton_val=ton,
        hive_val=hive,
        hbd_val=hbd,
        fecha=fecha_str
    )

    await update.message.reply_text(mensaje, parse_mode=ParseMode.MARKDOWN)
# ============================================================

# COMANDO /myid para ver datos del usuario
async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /myid. Muestra el ID de chat del usuario."""
    user_id = update.effective_user.id
    user = update.effective_user
    
    # 1. Preparacion de las variables
    nombre_completo = user.first_name or 'N/A'
    username_str = f"@{user.username}" if user.username else 'N/A'

    # 2. Traduce la plantilla de mensaje, usando marcadores de posición.
    #    NOTA: La plantilla debe ser una sola cadena literal (sin f-string dentro de _()).
    mensaje_template = _(
        "Estos son tus datos de Telegram:\n\n"
        "Nombre: {nombre}\n"
        "Usuario: {usuario}\n"
        "ID: `{id_chat}`",
        user_id # <-- PASAR EL CHAT_ID
    )

    # 3. Formatea el resultado de la traducción con los valores de las variables
    mensaje = mensaje_template.format(
        nombre=nombre_completo,
        usuario=username_str,
        id_chat=user_id
    )

    await update.message.reply_text(mensaje, parse_mode=ParseMode.MARKDOWN)
# ============================================================