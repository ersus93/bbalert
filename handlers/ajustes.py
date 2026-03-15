# handlers/ajustes.py
"""
Handler unificado para comandos de ajustes.
Unifica: /lang, /temp, /monedas

Sintaxis:
  /ajustes              - Ver ajustes actuales
  /ajustes lang es     - Cambiar idioma
  /ajustes temp 2.5     - Intervalo de alertas
  /ajustes help        - Ayuda
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from utils.user_data import (
    set_user_language,
    actualizar_intervalo_alerta,
    actualizar_monedAS,
    obtener_monedAS_usuario,
    obtener_datos_usuario,
    registrar_usuario
)
from utils.logger import logger
from core.i18n import _


async def ajustes_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Comando unificado /ajustes.
    """
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    args = context.args
    
    # Registrar usuario
    registrar_usuario(user_id, update.effective_user.language_code)
    
    if not args:
        await show_ajustes(update, context)
        return
    
    action = args[0].lower()
    
    if action == "lang":
        # /ajustes lang es
        await set_language(update, context, args[1:] if len(args) > 1 else [])
        return
    
    if action == "temp" or action == "intervalo":
        # /ajustes temp 2.5
        await set_interval(update, context, args[1:] if len(args) > 1 else [])
        return
    
    if action == "monedas" or action == "lista":
        # /ajustes monedas BTC,ETH
        await set_money_list(update, context, args[1:] if len(args) > 1 else [])
        return
    
    if action == "help" or action == "ayuda":
        await show_ajustes_help(update, context)
        return
    
    # Comando desconocido
    await show_ajustes(update, context)


async def show_ajustes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Muestra los ajustes actuales del usuario."""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    datos = obtener_datos_usuario(chat_id)
    
    lang = datos.get('language', 'es')
    interval = datos.get('intervalo_alerta_h', 2.5)
    monedas = obtener_monedas_usuario(chat_id)
    
    lang_name = "Español" if lang == "es" else "English"
    
    mensaje = _(
        f"⚙️ *Tus Ajustes*\n\n"
        f"🌐 *Idioma:* {lang_name}\n"
        f"⏰ *Intervalo:* {interval}h\n"
        f"💰 *Monedas:* {', '.join(monedas) if monedas else '(vacía)'}\n\n"
        f"Usa `/ajustes help` para ver más opciones",
        user_id
    )
    
    keyboard = [
        [InlineKeyboardButton("🌐 Idioma", callback_data="ajustes_lang")],
        [InlineKeyboardButton("⏰ Intervalo", callback_data="ajustes_temp")]
    ]
    
    await update.message.reply_text(
        mensaje,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )


async def show_ajustes_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Muestra ayuda del comando /ajustes."""
    user_id = update.effective_user.id
    
    mensaje = _(
        "⚙️ *Ajustes Disponibles*\n\n"
        "• `/ajustes` - Ver ajustes actuales\n"
        "• `/ajustes lang es` - Cambiar idioma (es/en)\n"
        "• `/ajustes temp 2.5` - Intervalo de alertas\n"
        "• `/ajustes monedas BTC,ETH` - Tu lista de monedas\n\n"
        "También puedes usar:\n"
        "• `/lang` - Cambiar idioma\n"
        "• `/temp 2.5` - Intervalo\n"
        "• `/monedas BTC,ETH` - Lista",
        user_id
    )
    
    await update.message.reply_text(
        mensaje,
        parse_mode=ParseMode.MARKDOWN
    )


async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE, args: list) -> None:
    """Cambia el idioma del usuario."""
    user_id = update.effective_user.id
    
    if not args:
        await update.message.reply_text(
            _(
                "⚠️ *Uso incorrecto*\n\n"
                "Usa: `/ajustes lang es` o `/ajustes lang en`",
                user_id
            ),
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    lang = args[0].lower()
    if lang not in ['es', 'en']:
        await update.message.reply_text(
            _("⚠️ Idioma no válido. Usa: es o en", user_id),
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    set_user_language(update.effective_user.id, lang)
    
    lang_name = "Español" if lang == "es" else "English"
    
    await update.message.reply_text(
        _(f"✅ *Idioma actualizado*\n\nAhora usas: {lang_name}", user_id),
        parse_mode=ParseMode.MARKDOWN
    )


async def set_interval(update: Update, context: ContextTypes.DEFAULT_TYPE, args: list) -> None:
    """Cambia el intervalo de alertas."""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    if not args:
        await update.message.reply_text(
            _(
                "⚠️ *Uso incorrecto*\n\n"
                "Usa: `/ajustes temp 2.5`",
                user_id
            ),
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    try:
        interval = float(args[0])
        if interval < 0.5 or interval > 24:
            raise ValueError("Out of range")
    except ValueError:
        await update.message.reply_text(
            _("⚠️ Intervalo inválido. Usa un valor entre 0.5 y 24 horas.", user_id),
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    actualizar_intervalo_alerta(chat_id, interval)
    
    await update.message.reply_text(
        _(f"✅ *Intervalo actualizado*\n\nAhora: cada {interval} horas", user_id),
        parse_mode=ParseMode.MARKDOWN
    )


async def set_money_list(update: Update, context: ContextTypes.DEFAULT_TYPE, args: list) -> None:
    """Cambia la lista de monedas."""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    if not args:
        await update.message.reply_text(
            _(
                "⚠️ *Uso incorrecto*\n\n"
                "Usa: `/ajustes monedas BTC,ETH,HIVE`",
                user_id
            ),
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # Parsear monedas
    nuevas = []
    for coin_arg in args:
        nuevas.extend([c.strip().upper() for c in coin_arg.split(",") if c.strip()])
    
    actualizar_monedas(chat_id, nuevas)
    
    await update.message.reply_text(
        _(f"✅ *Lista actualizada*\n\nMonedas: {', '.join(nuevas)}", user_id),
        parse_mode=ParseMode.MARKDOWN
    )
