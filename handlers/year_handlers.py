# handlers/year_handlers.py

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from utils.year_manager import (
    get_detailed_year_message, 
    add_quote, 
    update_user_sub, 
    load_subs
)
from core.i18n import _ # Si usas traducción, si no, quítalo

# como usar en otros mensajes: 
# from utils.year_manager import get_simple_year_string
# # ... dentro de tu código ...
# ytext = get_simple_year_string() 
# # Resultado: "📅 2025 Progress: ▓▓▓▓▓░░░░░ 50.1%"
# mensaje_final = f"{mensaje_btc}\n\n{texto_simple}"

async def year_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja el comando /y"""
    args = context.args
    user_id = update.effective_user.id
    
    # 1. Modo Agregar Frase: /y add La frase...
    if args and args[0].lower() == "add":
        # Verificar admin si quieres, o dejarlo libre
        text_to_add = " ".join(args[1:])
        if len(text_to_add) < 5:
            await update.message.reply_text("❌ Escribe una frase más larga. Uso: `/y add Tu frase aquí`", parse_mode="Markdown")
            return
        
        if add_quote(text_to_add):
            await update.message.reply_text("✅ Frase añadida a la colección del año.")
        else:
            await update.message.reply_text("⚠️ Esa frase ya existe.")
        return

    # 2. Modo Mostrar Info (por defecto)
    msg_text = get_detailed_year_message()
    
    # Verificar si el usuario ya está suscrito para marcar el botón
    subs = load_subs()
    current_hour = subs.get(str(user_id), {}).get("hour", None)

    # Botones de configuración
    keyboard = [
        [
            InlineKeyboardButton(f"{'✅' if current_hour == 6 else ''} 🕕 6 AM", callback_data="year_sub_6"),
            InlineKeyboardButton(f"{'✅' if current_hour == 9 else ''} 🕘 9 AM", callback_data="year_sub_9"),
        ],
        [
            InlineKeyboardButton(f"{'✅' if current_hour == 12 else ''} 🕛 12 PM", callback_data="year_sub_12"),
            InlineKeyboardButton(f"{'✅' if current_hour == 20 else ''} 🕗 8 PM", callback_data="year_sub_20"),
        ],
        [InlineKeyboardButton("🔕 Desactivar Alerta Diaria", callback_data="year_sub_off")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(msg_text, parse_mode="Markdown", reply_markup=reply_markup)

async def year_sub_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja los clics en los botones de hora."""
    query = update.callback_query
    await query.answer()
    
    data = query.data # ej: year_sub_6
    user_id = query.from_user.id
    
    action = data.split("_")[-1] # "6", "9", "off", etc.
    
    if action == "off":
        update_user_sub(user_id, None)
        text_resp = "🔕 Has desactivado las alertas de progreso anual."
    else:
        hour = int(action)
        update_user_sub(user_id, hour)
        text_resp = f"🔔 Alerta programada diariamente a las {hour}:00 h (Hora servidor)."

    # Regeneramos el teclado para mostrar el check actualizado
    subs = load_subs()
    current_hour = subs.get(str(user_id), {}).get("hour", None)
    
    keyboard = [
        [
            InlineKeyboardButton(f"{'✅' if current_hour == 6 else ''} 🕕 6 AM", callback_data="year_sub_6"),
            InlineKeyboardButton(f"{'✅' if current_hour == 9 else ''} 🕘 9 AM", callback_data="year_sub_9"),
        ],
        [
            InlineKeyboardButton(f"{'✅' if current_hour == 12 else ''} 🕛 12 PM", callback_data="year_sub_12"),
            InlineKeyboardButton(f"{'✅' if current_hour == 20 else ''} 🕗 8 PM", callback_data="year_sub_20"),
        ],
        [InlineKeyboardButton("🔕 Desactivar Alerta Diaria", callback_data="year_sub_off")]
    ]
    
    # Editamos el mensaje original para refrescar botones
    try:
        await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))
        # Opcional: Mandar un mensajito temporal o solo editar
        await context.bot.send_message(chat_id=user_id, text=text_resp)
    except Exception:
        pass