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

def get_year_limit(year=None):
    """
    Devuelve 366 si el año es bisiesto, 365 si no.
    Si no se pasa año, usa el año actual.
    
    Un año es bisiesto si: divisible por 4 y (no divisible por 100 o divisible por 400)
    """
    if year is None:
        year = datetime.now().year
    
    if (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0):
        return 366
    return 365


def get_quote_stats():
    """
    Devuelve un diccionario con estadísticas de las frases.
    
    Returns:
        dict: {
            'total': número total de frases en el JSON,
            'limit': límite de días del año actual (365/366),
            'current_index': índice de la frase de hoy (basado en día del año),
            'has_reached_limit': True si total >= limit,
            'next_year_count': cuántas frases hay "adelantadas" para el año siguiente
        }
    """
    quotes = load_quotes()
    total = len(quotes)
    limit = get_year_limit()
    day_of_year = datetime.now().timetuple().tm_yday
    current_index = (day_of_year - 1) % max(total, 1) if total > 0 else 0
    has_reached_limit = total >= limit
    next_year_count = max(0, total - limit)
    
    return {
        "total": total,
        "limit": limit,
        "current_index": current_index,
        "has_reached_limit": has_reached_limit,
        "next_year_count": next_year_count
    }


def is_new_year():
    """
    Detecta si es 1 de enero y no hay frases aún (o solo la frase de año nuevo).
    
    Returns:
        bool: True si es 1 de enero Y (no hay frases O la última frase no es del año nuevo)
    """
    now = datetime.now()
    if now.month != 1 or now.day != 1:
        return False
    
    quotes = load_quotes()
    if not quotes:
        return True
    
    year = now.year
    new_year_greeting = f"🎉 ¡Feliz año {year}! 🎆✨ Que este año esté lleno de éxitos y bendiciones. 🥂"
    
    # Verificar si la última frase ya es el saludo de año nuevo
    if quotes[-1] == new_year_greeting:
        return False
    
    return True


def add_new_year_greeting():
    """
    Añade automáticamente la frase de año nuevo.
    Solo se añade si is_new_year() es True.
    
    Returns:
        bool: True si se añadió la frase, False si no se añadió
    """
    if not is_new_year():
        return False
    
    year = datetime.now().year
    greeting = f"🎉 ¡Feliz año {year}! 🎆✨ Que este año esté lleno de éxitos y bendiciones. 🥂"
    
    return add_quote(greeting)


def get_quote_context(quote_index):
    """
    Devuelve el contexto de una frase según su índice.
    
    Args:
        quote_index: Índice de la frase en el array (0-based)
    
    Returns:
        dict: {
            'current': número de frase (1-based) dentro del año que corresponde,
            'limit': límite de días (365/366),
            'year': año al que pertenece (actual o siguiente),
            'is_extra': True si es frase para año siguiente
        }
    """
    current_year = datetime.now().year
    limit = get_year_limit(current_year)
    
    if quote_index < limit:
        return {
            "current": quote_index + 1,
            "limit": limit,
            "year": current_year,
            "is_extra": False
        }
    else:
        next_year = current_year + 1
        next_year_limit = get_year_limit(next_year)
        position_in_next_year = quote_index - limit + 1
        return {
            "current": position_in_next_year,
            "limit": next_year_limit,
            "year": next_year,
            "is_extra": True
        }


def get_extended_daily_quote():
    """
    Similar a get_daily_quote() pero retorna información extendida.
    
    Returns:
        dict: {
            'quote': la frase del día,
            'index': índice de la frase,
            'context': resultado de get_quote_context()
        }
    """
    quotes = load_quotes()
    
    if not quotes:
        quote = "⏳ El tiempo vuela, pero tú eres el piloto."
        index = -1
        context = {
            "current": 0,
            "limit": get_year_limit(),
            "year": datetime.now().year,
            "is_extra": False
        }
    else:
        day_of_year = datetime.now().timetuple().tm_yday
        index = (day_of_year - 1) % len(quotes)
        quote = quotes[index]
        context = get_quote_context(index)
    
    return {
        "quote": quote,
        "index": index,
        "context": context
    }


def add_quote(text, target_year=None):
    """
    Añade una nueva frase al JSON de frases.
    
    Args:
        text: Texto de la frase a añadir
        target_year: Año objetivo (int o None). Si es None, se añade al final.
                    Si es un año, calcula la posición correcta en el array.
    
    Returns:
        dict: {
            'success': bool,
            'index': int,
            'context': dict,
            'is_duplicate': bool
        }
    """
    quotes = load_quotes()
    
    # Verificar si es duplicado
    if text in quotes:
        existing_index = quotes.index(text)
        return {
            "success": False,
            "index": existing_index,
            "context": get_quote_context(existing_index),
            "is_duplicate": True
        }
    
    if target_year is None:
        # Comportamiento normal: añadir al final
        quotes.append(text)
        index = len(quotes) - 1
    else:
        # Calcular posición según el año objetivo
        current_year = datetime.now().year
        
        if target_year == current_year:
            # Añadir en la posición actual del año
            limit = get_year_limit(current_year)
            day_of_year = datetime.now().timetuple().tm_yday
            # Insertar en la posición actual del día
            index = min(day_of_year - 1, len(quotes))
            quotes.insert(index, text)
        elif target_year == current_year + 1:
            # Añadir al inicio del siguiente año
            limit_current = get_year_limit(current_year)
            index = min(limit_current, len(quotes))
            quotes.insert(index, text)
        else:
            # Para años futuros más lejanos, añadir al final
            quotes.append(text)
            index = len(quotes) - 1
    
    success = save_quotes(quotes)
    
    return {
        "success": success,
        "index": index,
        "context": get_quote_context(index),
        "is_duplicate": False
    }

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