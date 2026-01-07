import json
import os
import time
import uuid
from datetime import datetime, timedelta
from utils.logger import logger

# Ruta al archivo JSON
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
REMINDERS_FILE = os.path.join(DATA_DIR, "reminders.json")

def load_reminders():
    """Carga los recordatorios desde el JSON."""
    if not os.path.exists(REMINDERS_FILE):
        return {}
    try:
        with open(REMINDERS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error cargando reminders.json: {e}")
        return {}

def save_reminders(data):
    """Guarda los recordatorios en el JSON."""
    try:
        with open(REMINDERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error guardando reminders.json: {e}")

def add_reminder(user_id, text, trigger_time_dt):
    """Añade un nuevo recordatorio."""
    data = load_reminders()
    str_uid = str(user_id)
    if str_uid not in data:
        data[str_uid] = []
    
    reminder_id = str(uuid.uuid4())[:8] # ID corto
    
    new_reminder = {
        "id": reminder_id,
        "text": text,
        "time": trigger_time_dt.isoformat(),
        "created_at": datetime.now().isoformat()
    }
    
    data[str_uid].append(new_reminder)
    save_reminders(data)
    return reminder_id

def get_user_reminders(user_id):
    """Obtiene los recordatorios de un usuario."""
    data = load_reminders()
    return data.get(str(user_id), [])

def delete_reminder(user_id, reminder_id):
    """Elimina un recordatorio específico."""
    data = load_reminders()
    str_uid = str(user_id)
    if str_uid in data:
        initial_len = len(data[str_uid])
        data[str_uid] = [r for r in data[str_uid] if r["id"] != reminder_id]
        if len(data[str_uid]) < initial_len:
            save_reminders(data)
            return True
    return False

def postpone_reminder_by_id(user_id, reminder_id, minutes):
    """Pospone un recordatorio sumando minutos."""
    data = load_reminders()
    str_uid = str(user_id)
    if str_uid in data:
        for r in data[str_uid]:
            if r["id"] == reminder_id:
                current_time = datetime.fromisoformat(r["time"])
                new_time = current_time + timedelta(minutes=minutes)
                r["time"] = new_time.isoformat()
                save_reminders(data)
                return new_time
    return None