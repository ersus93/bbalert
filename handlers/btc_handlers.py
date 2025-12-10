# handlers/btc_handlers.py

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler, CommandHandler
from telegram.constants import ParseMode
import json
import os
from core.i18n import _
from utils.btc_manager import is_btc_subscribed, toggle_btc_subscription, load_btc_state
from utils.ads_manager import get_random_ad_text
from datetime import datetime
from core.config import DATA_DIR

BTC_SUBS_PATH = os.path.join(DATA_DIR, "btc_subs.json")
BTC_STATE_PATH = os.path.join(DATA_DIR, "btc_alert_state.json")

# --- SUBSCRIPCIONES ---
def load_btc_subs():
    if not os.path.exists(BTC_SUBS_PATH):
        return {}
    try:
        with open(BTC_SUBS_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

def save_btc_subs(subs):
    try:
        # Guardado atómico para evitar corrupción
        temp_path = f"{BTC_SUBS_PATH}.tmp"
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(subs, f, indent=4)
        os.replace(temp_path, BTC_SUBS_PATH)
    except Exception as e:
        print(f"Error guardando subs BTC: {e}")

def toggle_btc_subscription(user_id):
    """Activa o desactiva la suscripción de un usuario."""
    subs = load_btc_subs()
    uid = str(user_id)
    
    if uid in subs:
        current = subs[uid].get('active', False)
        subs[uid]['active'] = not current
    else:
        subs[uid] = {'active': True, 'joined_at': datetime.now().isoformat()}
    
    save_btc_subs(subs)
    return subs[uid]['active']

def is_btc_subscribed(user_id):
    subs = load_btc_subs()
    return subs.get(str(user_id), {}).get('active', False)

def get_btc_subscribers():
    subs = load_btc_subs()
    return [uid for uid, data in subs.items() if data.get('active')]

# --- GESTIÓN DE ESTADO (PERSISTENCIA DE NIVELES Y ALERTAS) ---

def load_btc_state():
    """Carga el estado de niveles y alertas enviadas."""
    if not os.path.exists(BTC_STATE_PATH):
        # Estado inicial por defecto si no existe archivo
        return {"last_candle_time": 0, "levels": {}, "alerted_levels": []}
    try:
        with open(BTC_STATE_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠️ Error cargando estado BTC ({e}). Iniciando limpio.")
        return {"last_candle_time": 0, "levels": {}, "alerted_levels": []}

def save_btc_state(data):
    """Guarda el estado actual en JSON de forma segura."""
    try:
        temp_path = f"{BTC_STATE_PATH}.tmp"
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
        os.replace(temp_path, BTC_STATE_PATH)
    except Exception as e:
        print(f"❌ Error crítico guardando estado BTC: {e}")

async def btc_alerts_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra el estado de alertas BTC y niveles actuales con R3/S3."""
    
    # Detectar origen
    if update.callback_query:
        # Si viene de botón, queremos ENVIAR UN MENSAJE NUEVO, no editar.
        # Necesitamos chat_id del mensaje original
        user_id = update.callback_query.from_user.id
        chat_id = update.callback_query.message.chat_id
        is_callback = True
    else:
        # Si viene de comando /btcalerts
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        is_callback = False

    subscribed = is_btc_subscribed(user_id)
    state = load_btc_state()
    levels = state.get('levels', {})

    status_icon = "✅ ACTIVADAS" if subscribed else "☑️ DESACTIVADAS"
    
    # Construcción de la tabla PRO con R3 y S3
    if levels:
        price_now = levels.get('current_price', 0)
        p = levels.get('P', 0)
        
        # Determinar zona textual
        zone = "Neutral (Pivot)"
        if price_now > levels.get('R2', 0): zone = "🚀 Zona de Extensión (Sobre R2)"
        elif price_now > levels.get('R1', 0): zone = "🐂 Zona Alcista (Sobre R1)"
        elif price_now < levels.get('S2', 0): zone = "🩸 Zona de Extensión (Bajo S2)"
        elif price_now < levels.get('S1', 0): zone = "🐻 Zona Bajista (Bajo S1)"
        
        levels_msg = (
            f"📊 *Estructura de Mercado (4H)*\n"
            f"⚡ *Estado:* {zone}\n\n"
            f"🧗 *R3:* `${levels.get('R3',0):,.0f}` _(Máximo)_\n"
            f"🟥 *R2:* `${levels.get('R2',0):,.0f}` _(Extensión)_\n"
            f"🟧 *R1:* `${levels.get('R1',0):,.0f}` _(Resistencia)_\n"
            f"⚖️ *PIVOT:* `${p:,.0f}` _(Equilibrio)_\n"
            f"🟦 *S1:* `${levels.get('S1',0):,.0f}` _(Soporte)_\n"
            f"🟩 *S2:* `${levels.get('S2',0):,.0f}` _(Extensión)_\n"
            f"🕳️ *S3:* `${levels.get('S3',0):,.0f}` _(Mínimo)_"
        )
    else:
        levels_msg = "⏳ _Calculando niveles de mercado... espera al próximo cierre de vela._"

    msg = _(
        "🦁 *Monitor BTC Pro*\n"
        "—————————————————\n"
        "{levels_msg}\n"
        "—————————————————\n"
        "🔔 *Suscripción:* {status_icon}\n\n"
        "Alertas automáticas de cruces de niveles clave.",
        user_id
    ).format(levels_msg=levels_msg, status_icon=status_icon)

    # Botón Toggle
    btn_text = _("🔕 Desactivar", user_id) if subscribed else _("🔔 Activar Alertas", user_id)
    kb = [[InlineKeyboardButton(btn_text, callback_data="toggle_btc_alerts")]]
    
    # Enviar mensaje
    if is_callback:
        # Respondemos al callback para quitar el "relojito" de carga
        await update.callback_query.answer()
        # Enviamos MENSAJE NUEVO
        await context.bot.send_message(chat_id=chat_id, text=msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)
    else:
        # Respondemos al comando
        await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)

async def btc_toggle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # Cambiar estado
    new_status = toggle_btc_subscription(query.from_user.id)
    
    # Actualizar solo el teclado y mostrar notificación flotante
    user_id = query.from_user.id
    btn_text = _("🔕 Desactivar", user_id) if new_status else _("🔔 Activar Alertas", user_id)
    kb = [[InlineKeyboardButton(btn_text, callback_data="toggle_btc_alerts")]]
    
    try:
        # Editamos solo el botón, no generamos un mensaje nuevo ni recargamos todo el texto para no ser intrusivos
        await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(kb))
        
        status_text = "✅ Alertas ACTIVADAS" if new_status else "🔕 Alertas DESACTIVADAS"
        await query.answer(status_text, show_alert=False)
    except:
        pass

async def btc_view_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback para el botón 'Ver Niveles'."""
    # Simplemente llamamos al comando principal, que detectará que es un callback
    # y enviará un mensaje nuevo.
    await btc_alerts_command(update, context)

# Lista de handlers para importar en bbalert.py
btc_handlers_list = [
    CommandHandler("btcalerts", btc_alerts_command),
    CallbackQueryHandler(btc_toggle_callback, pattern="^toggle_btc_alerts$"),
    CallbackQueryHandler(btc_view_callback, pattern="^btcalerts_view$") 
]