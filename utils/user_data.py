# utils/user_data.py
"""
Módulo de gestión de datos de usuarios.
Extraído de file_manager.py para responsabilidad única.
"""

from datetime import datetime
from typing import Dict, Any, Optional
from core.redis_fallback import get_user, save_user, get_all_user_ids, delete_user_from_redis as delete_user

# === Funciones de Carga/Guardado ===

def cargar_usuarios() -> Dict[str, Any]:
    """
    Carga usuarios desde Redis (con fallback a JSON si aplica).
    Retorna dict con todos los usuarios (claves en string).
    """
    ids = get_all_user_ids()  # Lista de IDs enteros
    result = {}
    for user_id in ids:
        data = get_user(user_id)
        if data is not None:
            result[str(user_id)] = data
    return result

def guardar_usuarios(usuarios_data: Optional[Dict] = None) -> None:
    """
    Guarda usuarios en Redis (con fallback a JSON si aplica).
    Usa escritura atómica para evitar corrupción (si aplica fallback).
    """
    if usuarios_data is None:
        return
    for chat_id_str, datos in usuarios_data.items():
        try:
            chat_id = int(chat_id_str)
            save_user(chat_id, datos)
        except (ValueError, TypeError):
            continue

# === Datos de Usuario ===

def obtener_datos_usuario(chat_id: int) -> Dict[str, Any]:
    """Obtiene todos los datos de un usuario."""
    data = get_user(chat_id)
    return data if data is not None else {}

def obtener_datos_usuario_seguro(chat_id: int) -> Optional[Dict[str, Any]]:
    """
    Obtiene datos del usuario asegurando que existan campos requeridos.
    Si no existe, retorna None.
    """
    usuario = get_user(chat_id)
    if usuario is None:
        usuario = {}
    
    guardar = False
    today_str = datetime.now().strftime('%Y-%m-%d')
    
    # Estructura de Uso Diario
    if 'daily_usage' not in usuario or usuario['daily_usage'].get('date') != today_str:
        usuario['daily_usage'] = {
            'date': today_str,
            'ver': 0, 'ta': 0,
            'temp_changes': 0, 'reminders': 0,
            'weather': 0, 'btc': 0,
        }
        guardar = True
    else:
        keys_necesarias = ['ver', 'ta', 'temp_changes', 'reminders', 'weather', 'btc']
        for key in keys_necesarias:
            if key not in usuario['daily_usage']:
                usuario['daily_usage'][key] = 0
                guardar = True
    
    # Suscripciones
    if 'subscriptions' not in usuario:
        usuario['subscriptions'] = {
            'alerts_extra': {'qty': 0, 'expires': None},
            'coins_extra': {'qty': 0, 'expires': None},
            'watchlist_bundle': {'active': False, 'expires': None},
            'ta_vip': {'active': False, 'expires': None},
            'sp_signals': {'active': False, 'expires': None},
        }
        guardar = True
    
    # Meta
    if 'meta' not in usuario:
        usuario['meta'] = {}
        guardar = True
    
    # Registered at
    if 'registered_at' not in usuario:
        usuario['registered_at'] = None
        guardar = True

    # HBD Alerts
    if 'hbd_alerts_enabled' not in usuario:
        usuario['hbd_alerts_enabled'] = False
        guardar = True

    # Legacy cleanup: migrate 'hbd_alerts' to 'hbd_alerts_enabled'
    if 'hbd_alerts' in usuario:
        usuario['hbd_alerts_enabled'] = usuario['hbd_alerts']
        del usuario['hbd_alerts']
        guardar = True

    if guardar:
        save_user(chat_id, usuario)
    
    return usuario

# === Registro de Usuario ===

def _normalizar_lang(code: str) -> str:
    """
    Normaliza el código de idioma del usuario.
    Maneja None, códigos regionales (es-419 → es), y valores no soportados.
    """
    if not code:
        return 'es'
    base = code.split('-')[0].lower()
    return base if base in ('es', 'en') else 'es'

def registrar_usuario(chat_id: int, user_lang_code: str = 'es') -> None:
    """Registra un nuevo usuario o actualiza existente."""
    usuario = get_user(chat_id)
    lang_normalizado = _normalizar_lang(user_lang_code)

    if usuario is None:
        usuario = {
            'language': lang_normalizado,
            'registered_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'monedas': [],
            'intervalo_alerta_h': 2.5,
            'last_seen': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }
    else:
        usuario['last_seen'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        if usuario.get('language') != lang_normalizado:
            usuario['language'] = lang_normalizado

    save_user(chat_id, usuario)

# === Monedas/Lista ===

def obtener_monedas_usuario(chat_id: int) -> list:
    """Obtiene la lista de monedas del usuario."""
    usuario = get_user(chat_id)
    return usuario.get("monedas", []) if usuario else []

def actualizar_monedas(chat_id: int, lista_monedas: list) -> None:
    """Actualiza la lista de monedas del usuario."""
    usuario = get_user(chat_id)
    if usuario is None:
        usuario = {}
    usuario["monedas"] = lista_monedas
    save_user(chat_id, usuario)

# === Idioma ===

def set_user_language(chat_id: int, lang_code: str) -> None:
    """Establece el idioma del usuario."""
    usuario = get_user(chat_id)
    if usuario is not None:
        usuario['language'] = lang_code
        save_user(chat_id, usuario)

def get_user_language(chat_id: int) -> str:
    """Obtiene el idioma del usuario."""
    usuario = get_user(chat_id)
    return usuario.get('language', 'es') if usuario else 'es'

# === Intervalo de Alertas ===

def actualizar_intervalo_alerta(chat_id: int, new_interval_h: float) -> bool:
    """Actualiza el intervalo de alertas del usuario."""
    usuario = get_user(chat_id)
    if usuario is not None:
        try:
            usuario['intervalo_alerta_h'] = float(new_interval_h)
            save_user(chat_id, usuario)
            return True
        except ValueError:
            return False
    return False

def update_last_alert_timestamp(chat_id: int) -> None:
    """Actualiza el timestamp de última alerta."""
    usuario = get_user(chat_id)
    if usuario is not None:
        usuario['last_alert_timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        save_user(chat_id, usuario)

# === Meta datos ===

def get_user_meta(user_id: int, key: str, default=None):
    """Obtiene un metadata del usuario."""
    usuario = get_user(user_id)
    if usuario is not None:
        meta = usuario.get('meta', {})
        return meta.get(key, default)
    return default

def set_user_meta(user_id: int, key: str, value) -> None:
    """Establece un metadata del usuario."""
    usuario = get_user(user_id)
    if usuario is None:
        usuario = {'meta': {}}
    elif 'meta' not in usuario:
        usuario['meta'] = {}
    usuario['meta'][key] = value
    save_user(user_id, usuario)