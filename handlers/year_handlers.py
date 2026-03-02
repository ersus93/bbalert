# handlers/year_handlers.py

import os
import json
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from utils.year_manager import (
    get_detailed_year_message,
    add_quote,
    update_user_sub,
    load_subs,
    get_quote_stats,
    get_extended_daily_quote,
    get_quote_context,
    is_new_year,
    add_new_year_greeting,
    get_year_limit
)
from core.config import YEAR_QUOTES_PATH
from core.i18n import _ # Si usas traducción, si no, quítalo


def _get_first_extra_flag():
    """Retorna True si es la primera vez que se supera el límite este año."""
    flag_file = os.path.join(os.path.dirname(YEAR_QUOTES_PATH), ".year_extra_flag")
    current_year = datetime.now().year
    try:
        if os.path.exists(flag_file):
            with open(flag_file, 'r') as f:
                data = json.load(f)
                if data.get('year') == current_year:
                    return data.get('asked', False)
    except:
        pass
    return False


def _set_first_extra_flag(asked=True):
    """Marca que ya se mostró la pregunta de pasar al siguiente año."""
    flag_file = os.path.join(os.path.dirname(YEAR_QUOTES_PATH), ".year_extra_flag")
    current_year = datetime.now().year
    try:
        with open(flag_file, 'w') as f:
            json.dump({'year': current_year, 'asked': asked}, f)
    except:
        pass

# como usar en otros mensajes: 
# from utils.year_manager import get_simple_year_string
# # ... dentro de tu código ...
# ytext = get_simple_year_string() 
# # Resultado: "📅 2025 Progress: ▓▓▓▓▓░░░░░ 50.1%"
# mensaje_final = f"{mensaje_btc}\n\n{texto_simple}"

async def year_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja el comando /y"""
    user_id = update.effective_user.id
    args = context.args
    
    # 1. Modo Agregar Frase: /y add La frase...
    if args and args[0].lower() == "add":
        # Detectar y manejar cambio de año automáticamente
        if is_new_year():
            add_new_year_greeting()

        text_to_add = " ".join(args[1:])
        if len(text_to_add) < 5:
            await update.message.reply_text(
                _("❌ Escribe una frase más larga. Uso: `/y add Tu frase aquí`"),
                parse_mode="Markdown"
            )
            return

        stats = get_quote_stats()

        # Verificar si se alcanzó el límite
        if stats['has_reached_limit']:
            # Primera vez que se supera el límite
            if not _get_first_extra_flag():
                _set_first_extra_flag(True)
                next_year = datetime.now().year + 1
                await update.message.reply_text(
                    _("⚠️ Has alcanzado el límite de frases para {year} ({limit} frases).\n\n"
                      "¿Deseas añadir esta frase para el año {next_year}?\n"
                      "Usa `/y add {text}`").format(
                        year=datetime.now().year,
                        limit=stats['limit'],
                        next_year=next_year,
                        text=text_to_add
                    ),
                    parse_mode="Markdown"
                )
                return
            else:
                # Modo año siguiente - añadir normalmente
                result = add_quote(text_to_add)
                if result['is_duplicate']:
                    await update.message.reply_text(_("⚠️ Esa frase ya existe."))
                elif result['success']:
                    ctx = result['context']
                    daily = get_extended_daily_quote()
                    await update.message.reply_text(
                        _("✅ Frase {current} de {limit} añadida para el año {year}.\n"
                          "La frase de hoy es: \"{quote}\"").format(
                            current=ctx['current'],
                            limit=ctx['limit'],
                            year=ctx['year'],
                            quote=daily['quote']
                        )
                    )
                else:
                    await update.message.reply_text(_("❌ Error al guardar la frase."))
                return
        else:
            # Dentro del límite normal
            result = add_quote(text_to_add)
            if result['is_duplicate']:
                await update.message.reply_text(_("⚠️ Esa frase ya existe."))
            elif result['success']:
                ctx = result['context']
                daily = get_extended_daily_quote()
                await update.message.reply_text(
                    _("✅ Frase {current} de {limit} añadida a la colección del año.\n"
                      "La frase de hoy es: \"{quote}\"").format(
                        current=ctx['current'],
                        limit=ctx['limit'],
                        quote=daily['quote']
                    )
                )
            else:
                await update.message.reply_text(_("❌ Error al guardar la frase."))
        return

    # 2. Modo Mostrar Info (por defecto)
    msg_text = get_detailed_year_message()
    
    # Verificar si el usuario ya está suscrito para marcar el botón
    subs = load_subs()
    current_hour = subs.get(str(user_id), {}).get("hour", None)

    # Botones de configuración
    keyboard = [
        [
            InlineKeyboardButton(f"{'✅' if current_hour == 6 else ''} {_('🕕 6 AM')}", callback_data="year_sub_6"),
            InlineKeyboardButton(f"{'✅' if current_hour == 9 else ''} {_('🕘 9 AM')}", callback_data="year_sub_9"),
        ],
        [
            InlineKeyboardButton(f"{'✅' if current_hour == 12 else ''} {_('🕛 12 PM')}", callback_data="year_sub_12"),
            InlineKeyboardButton(f"{'✅' if current_hour == 20 else ''} {_('🕗 8 PM')}", callback_data="year_sub_20"),
        ],
        [InlineKeyboardButton(_("🔕 Desactivar Alerta Diaria"), callback_data="year_sub_off")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(msg_text, parse_mode="Markdown", reply_markup=reply_markup)

async def year_sub_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja los clics en los botones de hora."""
    user_id = update.effective_user.id
    query = update.callback_query
    await query.answer()
    
    data = query.data # ej: year_sub_6
    
    action = data.split("_")[-1] # "6", "9", "off", etc.
    
    if action == "off":
        update_user_sub(user_id, None)
        text_resp = _("🔕 Has desactivado las alertas de progreso anual.")
    else:
        hour = int(action)
        update_user_sub(user_id, hour)
        text_resp = _("🔔 Alerta programada diariamente a las {hour}:00 h (Hora servidor).").format(hour=hour)

    # Regeneramos el teclado para mostrar el check actualizado
    subs = load_subs()
    current_hour = subs.get(str(user_id), {}).get("hour", None)
    
    keyboard = [
        [
            InlineKeyboardButton(f"{'✅' if current_hour == 6 else ''} {_('🕕 6 AM')}", callback_data="year_sub_6"),
            InlineKeyboardButton(f"{'✅' if current_hour == 9 else ''} {_('🕘 9 AM')}", callback_data="year_sub_9"),
        ],
        [
            InlineKeyboardButton(f"{'✅' if current_hour == 12 else ''} {_('🕛 12 PM')}", callback_data="year_sub_12"),
            InlineKeyboardButton(f"{'✅' if current_hour == 20 else ''} {_('🕗 8 PM')}", callback_data="year_sub_20"),
        ],
        [InlineKeyboardButton(_("🔕 Desactivar Alerta Diaria"), callback_data="year_sub_off")]
    ]
    
    # Editamos el mensaje original para refrescar botones
    try:
        await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))
        # Opcional: Mandar un mensajito temporal o solo editar
        await context.bot.send_message(chat_id=user_id, text=text_resp)
    except Exception:
        pass
