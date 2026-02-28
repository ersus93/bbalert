# utils/year_manager.py

import json
import os
import random
import math
from datetime import datetime, date
from typing import Optional
from core.config import YEAR_QUOTES_PATH, YEAR_SUBS_PATH
from core.i18n import _

# --- GESTIÓN DE FRASES (QUOTES) ---

def load_quotes():
    if not os.path.exists(YEAR_QUOTES_PATH):
        return []
    try:
        with open(YEAR_QUOTES_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return []

def save_quotes(quotes_list):
    try:
        with open(YEAR_QUOTES_PATH, 'w', encoding='utf-8') as f:
            json.dump(quotes_list, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error guardando frases: {e}")
        return False

def add_quote(text):
    quotes = load_quotes()
    if text not in quotes:
        quotes.append(text)
        save_quotes(quotes)
        return True
    return False

def get_daily_quote():
    quotes = load_quotes()
    if not quotes:
        return "⏳ El tiempo vuela, pero tú eres el piloto."
    
    # Obtenemos el número de día del año (ej: 1 de Enero es 1, 5 de Febrero es 36, etc.)
    day_of_year = datetime.now().timetuple().tm_yday
    
    # Calculamos el índice matemático.
    # (day_of_year - 1) ajusta para que el día 1 sea el índice 0 (primera frase).
    # % len(quotes) asegura que si se acaban las frases, vuelva a empezar desde la primera.
    quote_index = (day_of_year - 1) % len(quotes)
    
    return quotes[quote_index]

# --- GESTIÓN DE SUSCRIPCIONES ---

def load_subs():
    if not os.path.exists(YEAR_SUBS_PATH):
        return {}
    try:
        with open(YEAR_SUBS_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}

def save_subs(subs_data):
    try:
        with open(YEAR_SUBS_PATH, 'w', encoding='utf-8') as f:
            json.dump(subs_data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Error guardando subs de año: {e}")

def update_user_sub(user_id, hour):
    """
    Suscribe o actualiza a un usuario.
    hour: int (0-23) o None para borrar.
    """
    subs = load_subs()
    str_id = str(user_id)
    
    if hour is None:
        if str_id in subs:
            del subs[str_id]
            save_subs(subs)
        return False # Inda que se borró
    else:
        # Guardamos la hora y 'last_sent' para evitar spam el mismo día
        subs[str_id] = {
            "hour": hour,
            "last_sent": "" # Fecha ISO YYYY-MM-DD
        }
        save_subs(subs)
        return True

# --- LÓGICA DE TIEMPO Y FORMATO ---

def get_year_progress_data():
    """Calcula todos los datos matemáticos del año."""
    now = datetime.now()
    start_of_year = datetime(now.year, 1, 1)
    end_of_year = datetime(now.year + 1, 1, 1)
    
    total_seconds = (end_of_year - start_of_year).total_seconds()
    elapsed_seconds = (now - start_of_year).total_seconds()
    
    percent = (elapsed_seconds / total_seconds) * 100
    days_left = (end_of_year - now).days
    
    return {
        "year": now.year,
        "percent": percent,
        "days_left": days_left,
        "date_str": now.strftime("%d/%m/%Y")
    }

def generate_progress_bar(percent, length=15):
    """Genera una barrita visual tipo ▓▓▓▓░░░"""
    filled_length = int(length * percent // 100)
    bar = "▓" * filled_length + "░" * (length - filled_length)
    return bar

def get_simple_year_string():
    """Para inyectar en otros mensajes (versión compacta)."""
    data = get_year_progress_data()
    bar = generate_progress_bar(data['percent'], length=12)
    return f"📅 {data['year']} Progress: \n{bar} {data['percent']:.2f}%"

def get_detailed_year_message(user_id: Optional[int] = None):
    """Mensaje completo y divertido para el comando /y o el loop."""
    data = get_year_progress_data()
    quote = get_daily_quote()
    bar = generate_progress_bar(data['percent'], length=20)

    # Textos dinámicos según el porcentaje
    status_mood = ""
    if data['percent'] < 2: status_mood = _("🍀 Recién estamos empezando...", user_id)
    elif data['percent'] < 10: status_mood = _("🌱 Arrancando motores...", user_id)
    elif data['percent'] < 50: status_mood = _("🏃‍♂️ Aún hay tiempo de cumplir propósitos.", user_id)
    elif data['percent'] < 80: status_mood = _("🔥 ¡Se nos va el año!", user_id)
    else: status_mood = _("🏁 Recta final, ¡agárrate!", user_id)

    msg = (
        f"🗓 *{ _('ESTADO DEL AÑO', user_id) } {data['year']}*\n"
        f"•••\n"
        f"📆 *{ _('Fecha', user_id) }:* {data['date_str']}\n"
        f"⏳ *{ _('Progreso', user_id) }:* `{data['percent']:.2f}%`\n"
        f"📊 `{bar}`\n\n"
        f"🔚 { _('Faltan', user_id) } *{data['days_left']} { _('días', user_id) }* { _('para', user_id) } {data['year']+1}.\n"
        f"💭 _{status_mood}_\n"
        f"•••\n"
        f"💡 *{ _('Frase Del Día', user_id) }:*\n"
        f"\"{quote}\""
    )
    return msg