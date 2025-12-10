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
    """Muestra el estado de alertas BTC y niveles actuales."""
    
    # Manejo si viene de botón o comando
    if update.callback_query:
        user_id = update.callback_query.from_user.id
        msg_func = update.callback_query.edit_message_text
    else:
        user_id = update.effective_user.id
        msg_func = update.message.reply_text

    subscribed = is_btc_subscribed(user_id)
    state = load_btc_state()
    levels = state.get('levels', {})

    # Icono de estado
    status_icon = "✅ ACTIVADAS" if subscribed else "☑️ DESACTIVADAS"
    
    # Construir Tabla de Niveles "Pro"
    if levels:
        price_now = levels.get('current_price', 0)
        p = levels.get('P', 0)
        
        # Determinar zona
        zone = "Neutral"
        if price_now > levels.get('R1', 0): zone = "🐂 Bullish (Sobre R1)"
        elif price_now < levels.get('S1', 0): zone = "🐻 Bearish (Bajo S1)"
        
        levels_msg = (
            f"📊 *Niveles Clave (4H)*\n"
            f"⚡ *Zona:* {zone}\n\n"
            f"🟥 *R2:* `${levels.get('R2',0):,.0f}` (Target Extendido)\n"
            f"🟧 *R1:* `${levels.get('R1',0):,.0f}` (Resistencia Clave)\n"
            f"🎯 *PIVOT:* `${p:,.0f}` (Punto de Equilibrio)\n"
            f"🟦 *S1:* `${levels.get('S1',0):,.0f}` (Soporte Clave)\n"
            f"🟩 *S2:* `${levels.get('S2',0):,.0f}` (Soporte Crítico)\n"
        )
    else:
        levels_msg = "⏳ _Calculando niveles de mercado... intenta en unos minutos._"

    msg = _(
        "🦁 *Monitor de Volatilidad BTC Pro*\n"
        "—————————————————\n"
        "{levels_msg}\n"
        "—————————————————\n"
        "🔔 *Estado:* {status_icon}\n\n"
        "Recibe alertas en tiempo real cuando BTC rompa soportes o resistencias clave.",
        user_id
    ).format(levels_msg=levels_msg, status_icon=status_icon)

    # Botón Toggle
    btn_text = _("🔕 Desactivar", user_id) if subscribed else _("🔔 Activar Alertas BTC", user_id)
    kb = [[InlineKeyboardButton(btn_text, callback_data="toggle_btc_alerts")]]
    
    # Si estamos en callback (botón "Ver Niveles"), añadir botón de "Actualizar" para refrescar precios
    if update.callback_query:
        kb.append([InlineKeyboardButton("🔄 Actualizar", callback_data="btcalerts_view")])

    if update.callback_query:
        # Usamos edit_message_text pero aseguramos que el contenido sea distinto o atrapamos el error si es igual
        try:
            await msg_func(msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)
        except Exception:
            pass # Si el mensaje es idéntico (spam click), telegram da error, lo ignoramos.
    else:
        await msg_func(msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)

async def btc_toggle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    toggle_btc_subscription(query.from_user.id)
    # Recargamos el menú
    await btc_alerts_command(update, context)

async def btc_view_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manejador específico para el botón 'Ver Niveles'."""
    query = update.callback_query
    await query.answer() # Importante: Detiene la animación de carga del botón
    await btc_alerts_command(update, context)

# Exportar handler para registrarlo en bbalert.py
btc_handlers_list = [
    CommandHandler("btcalerts", btc_alerts_command),
    CallbackQueryHandler(btc_toggle_callback, pattern="^toggle_btc_alerts$"),
    CallbackQueryHandler(btc_view_callback, pattern="^btcalerts_view$") # <--- AÑADIDO
]