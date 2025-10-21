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


#  Telegram comando /satart 

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /start. Registra al usuario."""
    registrar_usuario(update.effective_chat.id)
    
    nombre_usuario = update.effective_user.first_name
    
    mensaje = (
        f"*Hola👋 {nombre_usuario}!* Bienvenido a BitBreadAlert.\n\n"
        "Para recibir alertas cada hora con los precios de tu lista de monedas solo, "
        "envíame un mensaje con los sombolos separados por comas. "
        "Puedes usar *cualquier* símbolo de criptomoneda listado en CoinMarketCap. Ejemplo:\n\n"
        "`BTC, ETH, TRX, HIVE, ADA, DOGE, SHIB`\n\n"
        "Pudes modificar la temporalidad en cualquier momento con el comando /temp seguido de las horas (entre 0.5 y 24.0).\n"
        "Ejemplo: /temp 2.5 (para 2 horas y 30 minutos)\n\n"
    )

    await update.message.reply_text(mensaje, parse_mode=ParseMode.MARKDOWN)
# ============================================================

# COMANDO /ver para ver la última lectura de precios
from utils.file_manager import load_hbd_history # Nueva importación

async def ver(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra la última lectura de precios desde el historial JSON."""
    history = load_hbd_history()

    if not history:
        await update.message.reply_text("⚠️ No hay registros de precios aún.")
        return

    # El último registro es el más reciente
    ultimo_registro = history[-1]
    
    fecha_str = ultimo_registro.get('timestamp', 'N/A')
    btc = ultimo_registro.get('btc', 0)
    hive = ultimo_registro.get('hive', 0)
    hbd = ultimo_registro.get('hbd', 0)
    ton = ultimo_registro.get('ton', 0)

    mensaje = f"""📊 *Última lectura (máx. 5 min atrás):*

🟠 *BTC/USD*: ${btc:,.2f}
🔷 *TON/USD*: ${ton:,.4f}
🐝 *HIVE/USD*: ${hive:,.4f}
💰 *HBD/USD*: ${hbd:,.4f}

_Actualizado: {fecha_str}_"""

    await update.message.reply_text(mensaje, parse_mode=ParseMode.MARKDOWN)
# ============================================================

# COMANDO /myid para ver datos del usuario
async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /myid. Muestra el ID de chat del usuario."""
    chat_id = update.effective_chat.id
    user = update.effective_user
    nombre_completo = user.first_name or 'N/A'
    username_str = f"@{user.username}" if user.username else 'N/A'

    mensaje = (
        "Estos son tus datos de Telegram\n\n"
        f"Nombre: {nombre_completo}\n"
        f"Usuario: {username_str}\n"
        f"ID: `{chat_id}`"
    )

    await update.message.reply_text(mensaje, parse_mode=ParseMode.MARKDOWN)
# ============================================================