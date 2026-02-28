import json
import os
import time
import uuid
from datetime import datetime, timedelta
from utils.logger import logger

# Importar relativedelta si está disponible, sino usar implementación manual
try:
    from dateutil.relativedelta import relativedelta
    HAS_RELATIVEDELTA = True
except ImportError:
    HAS_RELATIVEDELTA = False

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


def add_reminder(user_id, text, trigger_time_dt, recurrence_config=None):
    """Añade un nuevo recordatorio."""
    data = load_reminders()
    str_uid = str(user_id)
    if str_uid not in data:
        data[str_uid] = []

    reminder_id = str(uuid.uuid4())[:8]  # ID corto

    new_reminder = {
        "id": reminder_id,
        "text": text,
        "time": trigger_time_dt.isoformat(),
        "created_at": datetime.now().isoformat()
    }

    if recurrence_config:
        new_reminder["recurrence"] = recurrence_config

    data[str_uid].append(new_reminder)
    save_reminders(data)
    return reminder_id


def get_user_reminders(user_id):
    """Obtiene los recordatorios de un usuario ordenados por fecha/hora."""
    data = load_reminders()
    reminders = data.get(str(user_id), [])
    # Ordenar por fecha/hora (más próximo primero)
    reminders.sort(key=lambda r: datetime.fromisoformat(r['time']))
    return reminders


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


def is_recurring(reminder):
    """Verifica si un recordatorio tiene recurrencia activa."""
    recurrence = reminder.get("recurrence")
    if not recurrence:
        return False
    return recurrence.get("enabled", False)


def calculate_next_occurrence(reminder):
    """Calcula la siguiente fecha de ocurrencia para un recordatorio recurrente.

    Args:
        reminder: Diccionario del recordatorio con campo 'recurrence'

    Returns:
        datetime: Próxima fecha de ocurrencia o None si hay fecha fin alcanzada
    """
    if not is_recurring(reminder):
        return None

    recurrence = reminder.get("recurrence", {})
    current_time = datetime.fromisoformat(reminder["time"])
    recurrence_type = recurrence.get("type", "daily")
    interval = recurrence.get("interval", 1)
    end_date_str = recurrence.get("end_date")

    # Calcular siguiente fecha según el tipo
    if recurrence_type == "daily":
        next_time = current_time + timedelta(days=interval)
    elif recurrence_type == "weekly":
        next_time = current_time + timedelta(weeks=interval)
    elif recurrence_type == "monthly":
        next_time = _add_months(current_time, interval)
    elif recurrence_type == "yearly":
        next_time = _add_years(current_time, interval)
    else:
        logger.warning(f"Tipo de recurrencia desconocido: {recurrence_type}")
        return None

    # Verificar fecha fin
    if end_date_str:
        end_date = datetime.fromisoformat(end_date_str)
        if next_time > end_date:
            return None

    return next_time


def _add_months(source_date, months):
    """Añade meses a una fecha, manejando días fin de mes."""
    if HAS_RELATIVEDELTA:
        return source_date + relativedelta(months=months)

    # Implementación manual si dateutil no está disponible
    month = source_date.month - 1 + months
    year = source_date.year + month // 12
    month = month % 12 + 1
    day = min(source_date.day, _days_in_month(year, month))
    return source_date.replace(year=year, month=month, day=day)


def _add_years(source_date, years):
    """Añade años a una fecha, manejando años bisiestos (29 de febrero)."""
    if HAS_RELATIVEDELTA:
        return source_date + relativedelta(years=years)

    # Implementación manual
    year = source_date.year + years
    # Si es 29 de febrero y el año destino no es bisiesto, usar 28 de febrero
    if source_date.month == 2 and source_date.day == 29:
        if not _is_leap_year(year):
            return source_date.replace(year=year, day=28)
    return source_date.replace(year=year)


def _days_in_month(year, month):
    """Retorna el número de días en un mes específico."""
    if month in (1, 3, 5, 7, 8, 10, 12):
        return 31
    elif month in (4, 6, 9, 11):
        return 30
    elif month == 2:
        return 29 if _is_leap_year(year) else 28


def _is_leap_year(year):
    """Determina si un año es bisiesto."""
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def update_reminder_time(user_id, reminder_id, new_time):
    """Actualiza el campo 'time' de un recordatorio existente.

    Args:
        user_id: ID del usuario
        reminder_id: ID del recordatorio
        new_time: Nuevo datetime para el recordatorio

    Returns:
        bool: True si se actualizó correctamente, False si no se encontró
    """
    data = load_reminders()
    str_uid = str(user_id)

    if str_uid not in data:
        return False

    for r in data[str_uid]:
        if r["id"] == reminder_id:
            r["time"] = new_time.isoformat()
            # Incrementar contador de ocurrencias si es recurrente
            if is_recurring(r):
                recurrence = r.get("recurrence", {})
                recurrence["occurrence_count"] = recurrence.get("occurrence_count", 0) + 1
                r["recurrence"] = recurrence
            save_reminders(data)
            return True

    return False
