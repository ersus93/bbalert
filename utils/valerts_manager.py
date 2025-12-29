# utils/valerts_manager.py

import json
import os
from datetime import datetime
from core.config import DATA_DIR

# Archivos independientes para no mezclar con BTC
VALERTS_SUBS_PATH = os.path.join(DATA_DIR, "valerts_subs.json")
VALERTS_STATE_PATH = os.path.join(DATA_DIR, "valerts_state.json")

# --- SUBSCRIPCIONES ---
def load_valerts_subs():
    if not os.path.exists(VALERTS_SUBS_PATH):
        return {}
    try:
        with open(VALERTS_SUBS_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

def save_valerts_subs(subs):
    try:
        temp_path = f"{VALERTS_SUBS_PATH}.tmp"
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(subs, f, indent=4)
        os.replace(temp_path, VALERTS_SUBS_PATH)
    except Exception as e:
        print(f"Error guardando subs Valerts: {e}")

def toggle_valerts_subscription(user_id, symbol):
    """
    Activa/Desactiva suscripción.
    Estructura: { "ETHUSDT": { "12345": { "active": true } } }
    """
    subs = load_valerts_subs()
    symbol = symbol.upper()
    uid = str(user_id)
    
    if symbol not in subs:
        subs[symbol] = {}
        
    if uid in subs[symbol]:
        current = subs[symbol][uid].get('active', False)
        subs[symbol][uid]['active'] = not current
    else:
        subs[symbol][uid] = {'active': True, 'joined_at': datetime.now().isoformat()}
    
    # Limpieza: si no hay nadie activo en una moneda, podríamos borrar la key, 
    # pero por ahora lo dejamos simple.
    
    save_valerts_subs(subs)
    return subs[symbol][uid]['active']

def is_valerts_subscribed(user_id, symbol):
    subs = load_valerts_subs()
    symbol = symbol.upper()
    return subs.get(symbol, {}).get(str(user_id), {}).get('active', False)

def get_valerts_subscribers(symbol):
    """Devuelve lista de UIDs suscritos a una moneda específica."""
    subs = load_valerts_subs()
    symbol = symbol.upper()
    if symbol not in subs:
        return []
    return [uid for uid, data in subs[symbol].items() if data.get('active')]

def get_active_symbols():
    """Devuelve una lista de símbolos que tienen al menos un suscriptor activo."""
    subs = load_valerts_subs()
    active_symbols = []
    for symbol, users in subs.items():
        if any(u.get('active') for u in users.values()):
            active_symbols.append(symbol)
    return active_symbols

# --- GESTIÓN DE ESTADO (Niveles y Alertas enviadas) ---

def load_valerts_state():
    if not os.path.exists(VALERTS_STATE_PATH):
        return {}
    try:
        with open(VALERTS_STATE_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

def save_valerts_state(all_states):
    try:
        temp_path = f"{VALERTS_STATE_PATH}.tmp"
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(all_states, f, indent=4)
        os.replace(temp_path, VALERTS_STATE_PATH)
    except Exception as e:
        print(f"Error guardando estado Valerts: {e}")

def get_symbol_state(symbol):
    all_states = load_valerts_state()
    return all_states.get(symbol.upper(), {"last_candle_time": 0, "levels": {}, "alerted_levels": []})

def update_symbol_state(symbol, new_data):
    all_states = load_valerts_state()
    all_states[symbol.upper()] = new_data
    save_valerts_state(all_states)