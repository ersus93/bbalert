# handlers/health.py
"""
Handler para el comando /health - Muestra estado del sistema.
"""

import asyncio
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from core.health_check import run_health_check, format_health_message
from core.config import ADMIN_CHAT_IDS
from utils.logger import logger


async def health_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Comando /health - Muestra el estado de salud del sistema.
    Solo accesible para administradores.
    """
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    # Verificar que es admin
    if user_id not in ADMIN_CHAT_IDS:
        await update.message.reply_text(
            "🔒 Este comando solo está disponible para administradores.",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # Enviar mensaje de "consultando"
    status_msg = await update.message.reply_text(
        "🔍 *Verificando estado del sistema...*",
        parse_mode=ParseMode.MARKDOWN
    )
    
    try:
        # Intentar obtener el bot desde el contexto
        # Nota: En algunos contextos podemos obtener el bot así
        bot = context.bot
        
        # Ejecutar health check
        health_result = await run_health_check(bot)
        
        # Formatear y enviar mensaje
        message = format_health_message(health_result)
        
        await status_msg.edit_text(
            message,
            parse_mode=ParseMode.MARKDOWN
        )
        
        logger.info(f"Health check executed by user {user_id}")
        
    except Exception as e:
        logger.error(f"Error executing health check: {e}")
        await status_msg.edit_text(
            f"❌ Error al ejecutar health check: {e}",
            parse_mode=ParseMode.MARKDOWN
        )
