# handlers/valerts_handlers.py

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

async def valerts_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Muestra niveles y botón de suscripción para una moneda específica,
    o muestra una lista de monedas activas si no se especifican argumentos.
    """
    
    # --- Lógica de Manejo de Callback o Comando ---
    is_callback = False
    if update.callback_query:
        # Si viene de un callback, procesamos el símbolo (lógica existente)
        # Esto es necesario si el callback es 'valerts_view|ETHUSDT'
        # ... (cuerpo de la lógica de callback, sin cambios) ...
        
        query = update.callback_query
        user_id = query.from_user.id
        chat_id = query.message.chat_id
        try:
            symbol = query.data.split("|")[1]
        except IndexError:
            # Esto maneja callbacks mal formados, aunque ya debería estar cubierto
            await query.answer("Error en datos de moneda.")
            return
        is_callback = True
        
    elif context.args:
        # Si el usuario escribe /valerts ETH
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        
        symbol_raw = context.args[0].upper()
        # Normalizar a USDT si no lo tiene (simple helper)
        symbol = symbol_raw if symbol_raw.endswith("USDT") else f"{symbol_raw}USDT"
        
    else:
        # === CASO NUEVO: /valerts sin argumentos ===
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        
        # 1. Obtener la lista de símbolos que tienen suscriptores activos
        active_symbols = get_active_symbols()
        
        msg = (
            "🦁 *Monitor Volatilidad Multi-Moneda*\n"
            "—————————————————\n"
            "Para ver/añadir niveles, usa el comando así:\n"
            "👉 Ej: `/valerts ETH`\n\n"
        )
        
        kb_rows = []
        
        if active_symbols:
            msg += "*👇 Símbolos con Alertas Activas:*\n"
            
            # Crear botones: 3 por fila para ahorrar espacio
            temp_row = []
            for i, sym in enumerate(active_symbols):
                # El callback_data ahora usa 'valerts_view|SIMBOLO'
                temp_row.append(InlineKeyboardButton(sym, callback_data=f"valerts_view|{sym}"))
                if (i + 1) % 3 == 0:
                    kb_rows.append(temp_row)
                    temp_row = []
            if temp_row:
                kb_rows.append(temp_row)
                
            reply_markup = InlineKeyboardMarkup(kb_rows)
            
        else:
            msg += "_Actualmente no hay símbolos con alertas activadas. Únete a uno con el comando de ejemplo._"
            reply_markup = None

        await update.message.reply_text(msg, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
        return # Terminamos la ejecución si no hay argumentos
    
    
    # --- Lógica de Mostrar Niveles para un Símbolo Específico (Sigue Igual) ---

    # Cargar datos
    subscribed = is_valerts_subscribed(user_id, symbol)
    state = get_symbol_state(symbol)
    levels = state.get('levels', {})

    status_icon = "✅ ACTIVADAS" if subscribed else "☑️ DESACTIVADAS"
    
    # Construcción de la tabla (Idéntica a BTC pero con symbol)
    if levels:
        price_now = levels.get('current_price', 0)
        p = levels.get('P', 0)
        
        # Zona textual
        zone = "Neutral (Pivot)"
        if price_now > levels.get('R2', 0): zone = "🚀 Zona de Extensión (Sobre R2)"
        elif price_now > levels.get('R1', 0): zone = "🐂 Zona Alcista (Sobre R1)"
        elif price_now < levels.get('S2', 0): zone = "🩸 Zona de Extensión (Bajo S2)"
        elif price_now < levels.get('S1', 0): zone = "🐻 Zona Bajista (Bajo S1)"
        
        levels_msg = (
            f"📊 *Estructura {symbol} (4H)*\n"
            f"⚡ *Estado:* {zone}\n\n"
            f"🧗 *R3:* `${levels.get('R3',0):,.4f}`\n"  # 4 decimales para alts
            f"🟥 *R2:* `${levels.get('R2',0):,.4f}`\n"
            f"🟧 *R1:* `${levels.get('R1',0):,.4f}`\n"
            f"⚖️ *PIVOT:* `${p:,.4f}`\n"
            f"🟦 *S1:* `${levels.get('S1',0):,.4f}`\n"
            f"🟩 *S2:* `${levels.get('S2',0):,.4f}`\n"
            f"🕳️ *S3:* `${levels.get('S3',0):,.4f}`"
        )
    else:
        levels_msg = f"⏳ _Calculando niveles para {symbol}...\nEspera al próximo cierre de vela o asegúrate que el par existe en Binance._"

    msg = (
        f"🦁 *Monitor Volatilidad: {symbol}*\n"
        "—————————————————\n"
        f"{levels_msg}\n"
        "—————————————————\n"
        f"🔔 *Alertas {symbol}:* {status_icon}\n\n"
        "Alertas de cruces de niveles R1/R2/R3 y S1/S2/S3."
    )

    # Botón Toggle CON EL SÍMBOLO INCRUSTADO
    # Formato callback: accion|simbolo
    btn_text = f"🔕 Desactivar {symbol}" if subscribed else f"🔔 Activar {symbol}"
    
    # === AÑADIR BOTÓN DE REGRESO A LA LISTA ===
    kb = [[InlineKeyboardButton(btn_text, callback_data=f"toggle_valerts|{symbol}")]]
    kb.append([InlineKeyboardButton("🔙 Ver todas las monedas", callback_data="valerts_view|list")])
    
    if is_callback:
        await update.callback_query.answer()
        # Enviar mensaje NUEVO (como pediste en BTC)
        await context.bot.send_message(chat_id=chat_id, text=msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)

async def valerts_toggle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # Extraer símbolo del callback data: "toggle_valerts|ETHUSDT"
    data_parts = query.data.split("|")
    if len(data_parts) < 2:
        return
    symbol = data_parts[1]
    
    # Cambiar estado
    new_status = toggle_valerts_subscription(query.from_user.id, symbol)
    
    # Actualizar botón
    btn_text = f"🔕 Desactivar {symbol}" if new_status else f"🔔 Activar {symbol}"
    kb = [[InlineKeyboardButton(btn_text, callback_data=f"toggle_valerts|{symbol}")]]
    
    try:
        await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(kb))
        status_text = f"✅ Alertas {symbol} ON" if new_status else f"🔕 Alertas {symbol} OFF"
        await query.answer(status_text, show_alert=False)
    except:
        pass

# Lista de handlers para exportar
valerts_handlers_list = [
    CommandHandler("valerts", valerts_command),
    CallbackQueryHandler(valerts_toggle_callback, pattern="^toggle_valerts\|"), # Regex captura el pipe
    CallbackQueryHandler(valerts_command, pattern="^valerts_view\|") # Reutilizamos el comando como view
]