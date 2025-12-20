# utils/weather_manager.py

import json
import os
from datetime import datetime, timedelta
from core.config import DATA_DIR

# Rutas
WEATHER_SUBS_PATH = os.path.join(DATA_DIR, "weather_subs.json")
WEATHER_LAST_ALERTS_PATH = os.path.join(DATA_DIR, "weather_last_alerts.json")
GLOBAL_EVENTS_BUFFER_PATH = os.path.join(DATA_DIR, "global_events_buffer.json")

# --- GESTIÓN DE SUSCRIPCIONES (Estándar) ---

def load_weather_subscriptions():
    if not os.path.exists(WEATHER_SUBS_PATH):
        return {}
    try:
        with open(WEATHER_SUBS_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

def save_weather_subscriptions(subs):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(WEATHER_SUBS_PATH, 'w', encoding='utf-8') as f:
        json.dump(subs, f, indent=4, ensure_ascii=False)

def subscribe_user(user_id, city, country, timezone_str, lat, lon, alert_time="07:00"):
    subs = load_weather_subscriptions()
    subs[str(user_id)] = {
        "city": city,
        "country": country,
        "timezone": timezone_str,
        "lat": lat,
        "lon": lon,
        "alert_time": alert_time,
        "subscribed_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "alerts_enabled": True,
        "alert_types": {
            "rain": True, "uv_high": True, "storm": True, 
            "snow": True, "fog": True, "temp_high": True, 
            "temp_low": True, "global_disasters": True
        }
    }
    save_weather_subscriptions(subs)
    return True

def unsubscribe_user(user_id):
    subs = load_weather_subscriptions()
    if str(user_id) in subs:
        del subs[str(user_id)]
        save_weather_subscriptions(subs)
        return True
    return False

def get_user_subscription(user_id):
    subs = load_weather_subscriptions()
    return subs.get(str(user_id))

def get_all_subscribed_users():
    subs = load_weather_subscriptions()
    return [int(uid) for uid, data in subs.items() if data.get('alerts_enabled', False)]

def toggle_alert_type(user_id, alert_type):
    subs = load_weather_subscriptions()
    if str(user_id) in subs:
        current = subs[str(user_id)]['alert_types'].get(alert_type, True)
        subs[str(user_id)]['alert_types'][alert_type] = not current
        save_weather_subscriptions(subs)
        return True
    return False

# --- LOGICA DE ALERTAS (La Vieja Confiable) ---

def load_last_alerts():
    if not os.path.exists(WEATHER_LAST_ALERTS_PATH):
        return {}
    try:
        with open(WEATHER_LAST_ALERTS_PATH, 'r') as f:
            return json.load(f)
    except:
        return {}

def update_last_alert_time(user_id, alert_type):
    """Registra que acabamos de enviar una alerta."""
    data = load_last_alerts()
    user_key = str(user_id)
    if user_key not in data:
        data[user_key] = {}
    
    data[user_key][alert_type] = datetime.now().isoformat()
    
    with open(WEATHER_LAST_ALERTS_PATH, 'w') as f:
        json.dump(data, f, indent=4)

def should_send_alert(user_id, alert_type, cooldown_hours=4):
    """
    Lógica simple: ¿Ha pasado X tiempo desde la última alerta de este tipo?
    """
    data = load_last_alerts()
    user_key = str(user_id)
    
    # Si nunca se ha enviado, enviar
    if user_key not in data or alert_type not in data[user_key]:
        return True
    
    last_time_str = data[user_key][alert_type]
    try:
        last_time = datetime.fromisoformat(last_time_str)
        diff = datetime.now() - last_time
        hours_passed = diff.total_seconds() / 3600
        return hours_passed >= cooldown_hours
    except:
        return True

# --- GESTIÓN DE DESASTRES GLOBALES (BUFFER) ---

def buffer_global_event(title, description, source_url=None):
    """Guarda un desastre global en una lista para ser enviada en el resumen."""
    events = []
    if os.path.exists(GLOBAL_EVENTS_BUFFER_PATH):
        try:
            with open(GLOBAL_EVENTS_BUFFER_PATH, 'r', encoding='utf-8') as f:
                events = json.load(f)
        except:
            pass
    
    # Evitar duplicados simples por título
    for ev in events:
        if ev['title'] == title:
            return

    new_event = {
        "title": title,
        "description": description,
        "url": source_url,
        "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M')
    }
    events.append(new_event)
    
    # Guardar (Mantener solo los últimos 5 para no saturar)
    with open(GLOBAL_EVENTS_BUFFER_PATH, 'w', encoding='utf-8') as f:
        json.dump(events[-5:], f, indent=4, ensure_ascii=False)

def get_and_clear_global_events():
    """Obtiene los eventos acumulados y limpia el archivo."""
    if not os.path.exists(GLOBAL_EVENTS_BUFFER_PATH):
        return []
    
    try:
        with open(GLOBAL_EVENTS_BUFFER_PATH, 'r', encoding='utf-8') as f:
            events = json.load(f)
        
        # Limpiar el archivo después de leer (o dejarlo vacío)
        with open(GLOBAL_EVENTS_BUFFER_PATH, 'w', encoding='utf-8') as f:
            json.dump([], f)
            
        return events
    except:
        return []