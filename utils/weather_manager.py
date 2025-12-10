# utils/weather_manager.py

import json
import os
from datetime import datetime, timedelta
from core.config import WEATHER_SUBS_PATH, WEATHER_LAST_ALERTS_PATH

def load_weather_subscriptions():
    """Carga las suscripciones de clima."""
    if not os.path.exists(WEATHER_SUBS_PATH):
        return {}
    try:
        with open(WEATHER_SUBS_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return {}

def save_weather_subscriptions(subs):
    """Guarda las suscripciones de clima."""
    try:
        with open(WEATHER_SUBS_PATH, 'w', encoding='utf-8') as f:
            json.dump(subs, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Error guardando suscripciones de clima: {e}")

def subscribe_user(user_id, city, country, timezone, alert_time="07:00"):
    """Suscribe un usuario a alertas de clima."""
    subs = load_weather_subscriptions()
    
    subs[str(user_id)] = {
        "city": city,
        "country": country,
        "timezone": timezone,
        "alert_time": alert_time,
        "subscribed_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "alerts_enabled": True,
        "alert_types": {
            "rain": True,
            "uv_high": True,
            "storm": True,
            "snow": True, 
            "fog": True,
            "temp_high": True,
            "temp_low": True 
        }
    }
    save_weather_subscriptions(subs)
    return True

def unsubscribe_user(user_id):
    """Elimina la suscripción de un usuario."""
    subs = load_weather_subscriptions()
    if str(user_id) in subs:
        del subs[str(user_id)]
        save_weather_subscriptions(subs)
        return True
    return False

def update_alert_time(user_id, alert_time):
    """Actualiza la hora del resumen diario."""
    subs = load_weather_subscriptions()
    if str(user_id) in subs:
        subs[str(user_id)]['alert_time'] = alert_time
        save_weather_subscriptions(subs)
        return True
    return False

def toggle_alert_type(user_id, alert_type):
    """Activa/desactiva un tipo de alerta específico."""
    subs = load_weather_subscriptions()
    if str(user_id) in subs:
        current = subs[str(user_id)]['alert_types'].get(alert_type, True)
        subs[str(user_id)]['alert_types'][alert_type] = not current
        save_weather_subscriptions(subs)
        return True
    return False

def get_user_subscription(user_id):
    """Obtiene la suscripción de un usuario."""
    subs = load_weather_subscriptions()
    return subs.get(str(user_id))

def get_all_subscribed_users():
    """Obtiene todos los usuarios suscritos."""
    subs = load_weather_subscriptions()
    return [uid for uid, data in subs.items() if data.get('alerts_enabled', False)]

def update_last_alert_time(user_id, alert_type):
    """Registra la última vez que se envió una alerta."""
    if not os.path.exists(WEATHER_LAST_ALERTS_PATH):
        data = {}
    else:
        try:
            with open(WEATHER_LAST_ALERTS_PATH, 'r') as f:
                data = json.load(f)
        except:
            data = {}
    
    user_key = str(user_id)
    if user_key not in data:
        data[user_key] = {}
    
    data[user_key][alert_type] = datetime.now().isoformat()
    
    with open(WEATHER_LAST_ALERTS_PATH, 'w') as f:
        json.dump(data, f, indent=4)

def should_send_alert(user_id, alert_type, cooldown_hours=3):
    """Verifica si se debe enviar una alerta (evita spam)."""
    if not os.path.exists(WEATHER_LAST_ALERTS_PATH):
        return True
    
    try:
        with open(WEATHER_LAST_ALERTS_PATH, 'r') as f:
            data = json.load(f)
    except:
        return True
    
    user_key = str(user_id)
    if user_key not in data or alert_type not in data[user_key]:
        return True
    
    last_time = datetime.fromisoformat(data[user_key][alert_type])
    time_diff = datetime.now() - last_time
    return time_diff.total_seconds() >= cooldown_hours * 3600