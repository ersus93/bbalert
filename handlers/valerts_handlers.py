from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler, CommandHandler
from telegram.constants import ParseMode
from core.i18n import _
from utils.valerts_manager import (
    is_valerts_subscribed, 
    toggle_valerts_subscription, 
    get_symbol_state,
    get_active_symbols
)

def get_zone_indicator(current_price, levels):
    """Retorna emoji e indicador de zona para tabla de niveles."""
    if current_price > levels.get('R2', 0):
        return "🚀 EXTENSIÓN ALCISTA"
    elif current_price > levels.get('R1', 0):
        return "🐂 ZONA ALCISTA"
    elif current_price > levels.get('S1', 0):
        return "⚖️ NEUTRAL"
    elif current_price > levels.get('S2', 0):
        return "🐻 ZONA BAJISTA"
    else:
        return "🩸 EXTENSIÓN BAJISTA"

async def valerts_list_view(bot, chat_id):
    """Muestra la lista de símbolos activos."""
    active_symbols = get_active_symbols()
    
    msg = (
        "🦁 *Monitor de Volatilidad Multi-Moneda*\n"
        "—————————————————\n"
        "Recibe alertas técnicas inteligentes cuando el precio toca niveles clave.\n\n"
        "Usa: `/valerts ETH` o `/valerts BNB`\n\n"
    )
    
    kb_rows = []
    
    if active_symbols:
        msg += "*📍 Símbolos Activos:*\n\n"
        
        # Crear botones: 3 por fila
        temp_row = []
        for i, sym in enumerate(active_symbols):
            temp_row.append(InlineKeyboardButton(sym, callback_data=f"valerts_view|{sym}"))
            if (i + 1) % 3 == 0:
                kb_rows.append(temp_row)
                temp_row = []
        if temp_row:
            kb_rows.append(temp_row)
            
        reply_markup = InlineKeyboardMarkup(kb_rows)
        
    else:
        msg += "_No hay símbolos activos. ¡Únete a uno!_"
        reply_markup = None

    await bot.send_message(chat_id=chat_id, text=msg, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)

async def valerts_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Muestra niveles y botón de suscripción para una moneda específica,
    o muestra una lista de monedas activas si no se especifican argumentos.
    """
    
    # --- Lógica de Manejo de Callback o Comando ---
    is_callback = False
    if update.callback_query:
        query = update.callback_query
        user_id = query.from_user.id
        chat_id = query.message.chat_id
        
        try:
            symbol = query.data.split("|")[1]
            # Manejo especial para "list"
            if symbol == "list":
                await query.answer()
                await valerts_list_view(context.bot, chat_id)
                return
        except IndexError:
            await query.answer("Error en datos de moneda.", show_alert=True)
            return
        is_callback = True
        
    elif context.args:
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        
        symbol_raw = context.args[0].upper()
        symbol = symbol_raw if symbol_raw.endswith("USDT") else f"{symbol_raw}USDT"
        
    else:
        # === CASO: /valerts sin argumentos ===
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        
        await valerts_list_view(context.bot, chat_id)
        return
        
    # Cargar datos
    subscribed = is_valerts_subscribed(user_id, symbol)
    state = get_symbol_state(symbol)
    levels = state.get('levels', {})

    status_icon = "✅ ACTIVADAS" if subscribed else "☑️ DESACTIVADAS"
    
    # Construcción de la tabla mejorada
    if levels:
        price_now = levels.get('current_price', 0)
        p = levels.get('P', 0)
        zone = get_zone_indicator(price_now, levels)
        
        # Determinar número de decimales según el precio
        decimals = 2 if price_now > 100 else 4
        fmt = f",.{decimals}f"
        
        levels_msg = (
            f"*📊 Estructura {symbol} (4H)*\n"
            f"⚡Estado: {zone}\n\n"
            f"🧗 R3: `${levels.get('R3',0):{fmt}}` _(Máximo)_\n"
            f"🟥 R2: `${levels.get('R2',0):{fmt}}` _(Extensión)_\n"
            f"🟧 R1: `${levels.get('R1',0):{fmt}}` _(Resistencia)_\n"
            f"⚖️ PIVOT: `${p:{fmt}}` _(Equilibrio)_\n"
            f"🟦 S1: `${levels.get('S1',0):{fmt}}` _(Soporte)_\n"
            f"🟩 S2: `${levels.get('S2',0):{fmt}}` _(Extensión)_\n"
            f"🕳️ S3: `${levels.get('S3',0):{fmt}}` _(Mínimo)_\n\n"
            f"💰 Precio: `${price_now:{fmt}}`"
        )
    else:
        levels_msg = f"_Calculando niveles para {symbol}..._\n_Espera al próximo cierre de vela._"

    msg = (
        f"🦁 *Monitor Volatilidad: {symbol}*\n"
        f"—————————————————\n"
        f"{levels_msg}\n"
        f"—————————————————\n"
        f"Alertas {symbol}: {status_icon}\n\n"
        f"Recibe notificaciones técnicas de cruces de niveles."
    )

    # Botones mejorados - CORRECCIÓN DEL CALLBACK BACK
    btn_text = f"🔕 Desactivar {symbol}" if subscribed else f"🔔 Activar {symbol}"
    
    kb = [
        [InlineKeyboardButton(btn_text, callback_data=f"toggle_valerts|{symbol}")],
        [InlineKeyboardButton("🔙 Volver a la lista", callback_data="valerts_list_back")]
    ]
    
    if is_callback:
        await update.callback_query.answer()
        await context.bot.send_message(chat_id=chat_id, text=msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)

async def valerts_toggle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Alterna suscripción con botón dinámico."""
    query = update.callback_query
    await query.answer()
    
    # Extraer símbolo
    data_parts = query.data.split("|")
    if len(data_parts) < 2:
        return
    symbol = data_parts[1]
    
    # Cambiar estado
    new_status = toggle_valerts_subscription(query.from_user.id, symbol)
    
    # Actualizar botón
    btn_text = f"🔕 Desactivar {symbol}" if new_status else f"🔔 Activar {symbol}"
    kb = [
        [InlineKeyboardButton(btn_text, callback_data=f"toggle_valerts|{symbol}")],
        [InlineKeyboardButton("🔙 Volver a la lista", callback_data="valerts_list_back")]
    ]
    
    try:
        await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(kb))
        status_text = f"✅ {symbol} activadas" if new_status else f"🔕 {symbol} desactivadas"
        await query.answer(status_text, show_alert=False)
    except:
        pass

async def valerts_list_back_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback para volver a la lista principal."""
    query = update.callback_query
    await query.answer()
    
    chat_id = query.message.chat_id
    await valerts_list_view(context.bot, chat_id)

# Lista de handlers para exportar
valerts_handlers_list = [
    CommandHandler("valerts", valerts_command),
    CallbackQueryHandler(valerts_toggle_callback, pattern="^toggle_valerts\\|"),
    CallbackQueryHandler(valerts_list_back_callback, pattern="^valerts_list_back$"),
    CallbackQueryHandler(valerts_command, pattern="^valerts_view\\|")
]
