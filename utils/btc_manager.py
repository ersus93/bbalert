# utils/btc_manager.py

import json
import os
from datetime import datetime
from core.config import DATA_DIR

BTC_SUBS_PATH = os.path.join(DATA_DIR, "btc_subs.json")
BTC_STATE_PATH = os.path.join(DATA_DIR, "btc_alert_state.json")

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
        with open(BTC_SUBS_PATH, 'w', encoding='utf-8') as f:
            json.dump(subs, f, indent=4)
    except Exception as e:
        print(f"Error guardando subs BTC: {e}")

def toggle_btc_subscription(user_id):
    """Activa o desactiva la suscripción de un usuario."""
    subs = load_btc_subs()
    uid = str(user_id)
    
    # Toggle
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

# --- GESTIÓN DE ESTADO (Para no repetir alertas en la misma vela) ---

def load_btc_state():
    if not os.path.exists(BTC_STATE_PATH):
        return {"last_candle_time": 0, "levels": {}, "alerted_levels": []}
    try:
        with open(BTC_STATE_PATH, 'r') as f:
            return json.load(f)
    except:
        return {"last_candle_time": 0, "levels": {}, "alerted_levels": []}

def save_btc_state(data):
    with open(BTC_STATE_PATH, 'w') as f:
        json.dump(data, f, indent=4)