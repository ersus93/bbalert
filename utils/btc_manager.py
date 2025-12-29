# utils/btc_manager.py

import json
import os
from datetime import datetime
from core.config import DATA_DIR

BTC_SUBS_PATH = os.path.join(DATA_DIR, "btc_subs.json")
BTC_STATE_PATH = os.path.join(DATA_DIR, "btc_alert_state.json")

# Constantes de intervalos válidos
VALID_TIMEFRAMES = ["1h", "2h", "4h", "8h", "12h", "1d", "1w"]

def load_btc_subs():
    if not os.path.exists(BTC_SUBS_PATH):
        return {}
    try:
        with open(BTC_SUBS_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        # --- MIGRACIÓN AUTOMÁTICA DE FORMATO ANTIGUO ---
        # Si detectamos formato antiguo ('active': True), lo convertimos a lista ['4h']
        migrated = False
        for uid, user_data in data.items():
            if 'active' in user_data:
                is_active = user_data.pop('active')
                # Si estaba activo, le damos suscripción a 4h por defecto
                user_data['subscriptions'] = ["1d"] if is_active else []
                migrated = True
            # Aseguramos que exista la clave subscriptions
            if 'subscriptions' not in user_data:
                user_data['subscriptions'] = []
        
        if migrated:
            save_btc_subs(data)
            
        return data
    except Exception as e:
        print(f"Error cargando subs BTC: {e}")
        return {}

def save_btc_subs(subs):
    try:
        with open(BTC_SUBS_PATH, 'w', encoding='utf-8') as f:
            json.dump(subs, f, indent=4)
    except Exception as e:
        print(f"Error guardando subs BTC: {e}")

def toggle_btc_subscription(user_id, timeframe="1d"):
    """Activa o desactiva una temporalidad específica para el usuario."""
    subs = load_btc_subs()
    uid = str(user_id)
    
    if uid not in subs:
        subs[uid] = {"subscriptions": []}
    
    # Asegurar compatibilidad con formato viejo
    if "subscriptions" not in subs[uid]:
        subs[uid]["subscriptions"] = []

    user_subs = subs[uid]["subscriptions"]

    if timeframe in user_subs:
        user_subs.remove(timeframe) # Si existe, la quita
        is_active = False
    else:
        user_subs.append(timeframe) # Si no existe, la pone
        is_active = True
        
    save_btc_subs(subs)
    return is_active

def is_btc_subscribed(user_id, interval="1d"):
    """Verifica si el usuario está suscrito a un intervalo específico."""
    subs = load_btc_subs()
    user_list = subs.get(str(user_id), {}).get('subscriptions', [])
    return interval in user_list

def get_btc_subscribers(timeframe):
    """Devuelve lista de IDs suscritos a un timeframe específico."""
    subs = load_btc_subs()
    active_users = []
    
    for uid, data in subs.items():
        # Verificamos si la lista 'subscriptions' existe y contiene el timeframe
        if "subscriptions" in data and timeframe in data["subscriptions"]:
            active_users.append(uid)
            
    return active_users

# --- GESTIÓN DE ESTADO MULTI-TEMPORAL ---

def load_btc_state():
    """
    Carga el estado. Ahora retorna un diccionario con claves por intervalo.
    Ej: {'4h': {...}, '1d': {...}}
    """
    default_structure = {
        "1h": {"last_candle_time": 0, "levels": {}, "alerted_levels": []},
        "2h": {"last_candle_time": 0, "levels": {}, "alerted_levels": []},
        "4h": {"last_candle_time": 0, "levels": {}, "alerted_levels": []},
        "8h": {"last_candle_time": 0, "levels": {}, "alerted_levels": []},
        "12h": {"last_candle_time": 0, "levels": {}, "alerted_levels": []},
        "1d": {"last_candle_time": 0, "levels": {}, "alerted_levels": []},
        "1w": {"last_candle_time": 0, "levels": {}, "alerted_levels": []}
    }

    if not os.path.exists(BTC_STATE_PATH):
        return default_structure
        
    try:
        with open(BTC_STATE_PATH, 'r') as f:
            data = json.load(f)
            
        # Si el JSON es del formato viejo (sin claves de intervalo), lo reseteamos o adaptamos
        if "levels" in data and "1d" not in data:
            # Migración simple: movemos lo viejo a "4h"
            return {
                "1h": default_structure["1h"],
                "2h": default_structure["2h"],
                "4h": default_structure["4h"],
                "8h": default_structure["8h"],
                "12h": default_structure["12h"],
                "1d": data,
                "1w": default_structure["1w"]
            }
            
        # Asegurar que todas las claves existan
        for tf in VALID_TIMEFRAMES:
            if tf not in data:
                data[tf] = default_structure[tf]
                
        return data
    except:
        return default_structure

def save_btc_state(data):
    with open(BTC_STATE_PATH, 'w') as f:
        json.dump(data, f, indent=4)