# utils/valerts_manager.py

import json
import os
from core.config import DATA_DIR

VALERTS_SUBS_PATH = os.path.join(DATA_DIR, "valerts_subs.json")
VALERTS_STATE_PATH = os.path.join(DATA_DIR, "valerts_state.json")

# --- CARGA Y GUARDADO BÁSICO ---

def load_json(path):
    if not os.path.exists(path): return {}
    try:
        with open(path, 'r', encoding='utf-8') as f: return json.load(f)
    except: return {}

def save_json(path, data):
    try:
        temp = f"{path}.tmp"
        with open(temp, 'w', encoding='utf-8') as f: json.dump(data, f, indent=4)
        os.replace(temp, path)
    except Exception as e: print(f"Error guardando {path}: {e}")

# --- SUSCRIPCIONES (SUBS) ---

def is_valerts_subscribed(user_id, symbol, timeframe="4h"):
    """Verifica si un usuario está suscrito a un par y timeframe específicos."""
    subs = load_json(VALERTS_SUBS_PATH)
    uid = str(user_id)
    
    # Estructura: uid -> symbol -> [lista_tfs]
    if uid in subs and symbol in subs[uid]:
        # Compatibilidad: Si es una lista antigua o nueva
        if isinstance(subs[uid][symbol], list):
            return timeframe in subs[uid][symbol]
    return False

def toggle_valerts_subscription(user_id, symbol, timeframe="4h"):
    """Activa/Desactiva suscripción y devuelve el nuevo estado (True/False)."""
    subs = load_json(VALERTS_SUBS_PATH)
    uid = str(user_id)
    
    if uid not in subs: subs[uid] = {}
    if symbol not in subs[uid]: subs[uid][symbol] = []
        
    # Asegurar que sea lista
    if not isinstance(subs[uid][symbol], list):
        subs[uid][symbol] = []

    if timeframe in subs[uid][symbol]:
        subs[uid][symbol].remove(timeframe)
        res = False
        # Limpieza: Si el usuario no sigue nada de esa moneda, borramos la key
        if not subs[uid][symbol]: 
            del subs[uid][symbol]
    else:
        subs[uid][symbol].append(timeframe)
        res = True
        
    save_json(VALERTS_SUBS_PATH, subs)
    return res

def get_valerts_subscribers(symbol, timeframe):
    """Devuelve lista de usuarios suscritos a Moneda + TF."""
    subs = load_json(VALERTS_SUBS_PATH)
    users = []
    for uid, user_symbols in subs.items():
        if symbol in user_symbols:
            # Verificamos que el TF esté en la lista del usuario
            if isinstance(user_symbols[symbol], list) and timeframe in user_symbols[symbol]:
                users.append(uid)
    return users

def get_active_symbols():
    """Lista única de monedas que tienen AL MENOS una suscripción activa."""
    subs = load_json(VALERTS_SUBS_PATH)
    active = set()
    for user_data in subs.values():
        for sym in user_data.keys():
            active.add(sym)
    return sorted(list(active))

# --- ESTADO (STATE) - CRÍTICO PARA EL LOOP ---

def get_symbol_state(symbol, timeframe="4h"):
    """
    Recupera el estado técnico de una moneda en un TF específico.
    Crea la estructura anidada si no existe para evitar KeyErrors.
    Estructura: { "BTCUSDT": { "4h": { ... }, "1d": { ... } } }
    """
    data = load_json(VALERTS_STATE_PATH)
    
    if symbol not in data: 
        data[symbol] = {}
    
    if timeframe not in data[symbol]:
        # Inicializar estructura vacía por Timeframe
        data[symbol][timeframe] = {
            "last_candle_time": 0, 
            "levels": {}, 
            "alerted_levels": []
        }
        # Guardamos la inicialización para persistencia futura
        save_json(VALERTS_STATE_PATH, data)

    return data[symbol][timeframe]

def update_symbol_state(symbol, timeframe, state_dict):
    """Guarda el estado específico sin borrar los otros timeframes."""
    data = load_json(VALERTS_STATE_PATH)
    
    if symbol not in data: data[symbol] = {}
    
    data[symbol][timeframe] = state_dict
    save_json(VALERTS_STATE_PATH, data)