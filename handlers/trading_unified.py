# handlers/trading_unified.py
"""
Handler unificado para comandos de trading.
Unifica: /ta, /graf, /mk

Sintaxis:
  /trading ta BTC        - Análisis técnico
  /trading graf BTC 1h   - Gráfico
  /trading mk           - Mercados globales
  /trading help         - Ayuda
"""

from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

# Importar funciones existentes de los handlers originales
from handlers.ta import ta_command
from handlers.trading import graf_command, mk_command
from utils.logger import logger
from core.i18n import _


async def trading_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Comando unificado /trading.
    """
    user_id = update.effective_user.id
    args = context.args
    
    if not args:
        await show_trading_help(update, context)
        return
    
    action = args[0].lower()
    
    if action == "ta":
        # /trading ta BTC
        # Reutilizar lógica de ta_command pero con args correctos
        if len(args) > 1:
            context.args = args[1:]  # Pasar el símbolo como argumento
        else:
            context.args = []
        await ta_command(update, context)
        return
    
    if action == "graf" or action == "chart":
        # /trading graf BTC 1h
        if len(args) > 1:
            context.args = args[1:]
        else:
            context.args = []
        await graf_command(update, context)
        return
    
    if action == "mk" or action == "mercados":
        # /trading mk
        await mk_command(update, context)
        return
    
    if action == "help" or action == "ayuda":
        await show_trading_help(update, context)
        return
    
    # Comando desconocido - mostrar ayuda
    await show_trading_help(update, context)


async def show_trading_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Muestra ayuda del comando /trading."""
    user_id = update.effective_user.id
    
    mensaje = _(
        "📊 *Comandos de Trading*\n\n"
        "• `/trading ta BTC` - Análisis técnico\n"
        "• `/trading graf BTC 1h` - Gráfico\n"
        "• `/trading mk` - Mercados globales\n\n"
        "También puedes usar directamente:\n"
        "• `/ta BTC` - Análisis rápido\n"
        "• `/graf BTC 1h` - Gráfico\n"
        "• `/mk` - Mercados",
        user_id
    )
    
    await update.message.reply_text(
        mensaje,
        parse_mode=ParseMode.MARKDOWN
    )
