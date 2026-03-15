# utils/user_data.py
"""
Módulo de gestión de datos de usuarios.
Extraído de file_manager.py para responsabilidad única.
"""

import os
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from utils.logger import logger
from core.config import USUARIOS_PATH

# Cache global
_USUARIOS_CACHE = None

# === Funciones de Carga/Guardado ===

def _get_usuarios_cache():
    """Obtiene el cache de usuarios (interno)."""
    global _USUARIOS_CACHE
    return _USUARIOS_CACHE

def _set_usuarios_cache(data):
    """Establece el cache de usuarios (interno)."""
    global _USUARIOS_CACHE
    _USUARIOS_CACHE = data

def cargar_usuarios() -> Dict[str, Any]:
    """
    Carga usuarios desde archivo.
    Retorna dict con todos los usuarios.
    """
    global _USUARIOS_CACHE
    
    if _USUARIOS_CACHE is not None:
        return _USUARIOS_CACHE
    
    if not os.path.exists(USUARIOS_PATH):
        _USUARIOS_CACHE = {}
        return _USUARIOS_CACHE
    
    try:
        with open(USUARIOS_PATH, 'r', encoding='utf-8') as f:
            _USUARIOS_CACHE = json.load(f)
            return _USUARIOS_CACHE
    except json.JSONDecodeError:
        if os.path.exists(USUARIOS_PATH):
            import shutil
            shutil.copy(USUARIOS_PATH, f"{USUARIOS_PATH}.corrupto")
        _USUARIOS_CACHE = {}
        return _USUARIOS_CACHE
    except Exception:
        return {}

def guardar_usuarios(usuarios_data: Optional[Dict] = None) -> None:
    """
    Guarda usuarios en archivo.
    Usa escritura atómica para evitar corrupción.
    """
    global _USUARIOS_CACHE
    
    if usuarios_data is not None:
        _USUARIOS_CACHE = usuarios_data
    
    if _USUARIOS_CACHE is None:
        return
    
    try:
        temp_path = f"{USUARIOS_PATH}.tmp"
        with open(temp_path, "w", encoding='utf-8') as f:
            json.dump(_USUARIOS_CACHE, f, indent=4)
        os.replace(temp_path, USUARIOS_PATH)
    except Exception as e:
        logger.error(f"Error al guardar usuarios: {e}")

# === Datos de Usuario ===

def obtener_datos_usuario(chat_id: int) -> Dict[str, Any]:
    """Obtiene todos los datos de un usuario."""
    usuarios = cargar_usuarios()
    return usuarios.get(str(chat_id), {})

def obtener_datos_usuario_seguro(chat_id: int) -> Dict[str, Any]:
    """
    Obtiene datos del usuario asegurando que existan campos requeridos.
    Si no existe, retorna None.
    """
    usuarios = cargar_usuarios()
    chat_id_str = str(chat_id)
    
    if chat_id_str not in usuarios:
        return None
    
    usuario = usuarios[chat_id_str]
    guardar = False
    today_str = datetime.now().strftime('%Y-%m-%d')
    
    # Estructura de Uso Diario
    if 'daily_usage' not in usuario or usuario['daily_usage'].get('date') != today_str:
        usuario['daily_usage'] = {
            'date': today_str,
            'ver': 0, 'tasa': 0, 'ta': 0,
            'temp_changes': 0, 'reminders': 0,
            'weather': 0, 'btc': 0,
        }
        guardar = True
    else:
        keys_necesarias = ['ver', 'tasa', 'ta', 'temp_changes', 'reminders', 'weather', 'btc']
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
            'tasa_vip': {'active': False, 'expires': None},
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
    
    if guardar:
        guardar_usuarios(usuarios)
    
    return usuario

# === Registro de Usuario ===

def registrar_usuario(chat_id: int, user_lang_code: str = 'es') -> None:
    """Registra un nuevo usuario o actualiza existente."""
    usuarios = cargar_usuarios()
    chat_id_str = str(chat_id)
    
    if chat_id_str not in usuarios:
        usuarios[chat_id_str] = {
            'language': user_lang_code,
            'registered_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'monedas': [],
            'intervalo_alerta_h': 2.5,
            'last_seen': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }
    else:
        usuarios[chat_id_str]['last_seen'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    guardar_usuarios(usuarios)

# === Monedas/Lista ===

def obtener_monedAS_usuario(chat_id: int) -> list:
    """Obtiene la lista de monedas del usuario."""
    usuarios = cargar_usuarios()
    return usuarios.get(str(chat_id), {}).get("monedas", [])

def actualizar_monedAS(chat_id: int, lista_monedAS: list) -> None:
    """Actualiza la lista de monedas del usuario."""
    usuarios = cargar_usuarios()
    chat_id_str = str(chat_id)
    
    if chat_id_str not in usuarios:
        usuarios[chat_id_str] = {}
    
    usuarios[chat_id_str]["monedas"] = lista_monedAS
    guardar_usuarios(usuarios)

# === Idioma ===

def set_user_language(chat_id: int, lang_code: str) -> None:
    """Establece el idioma del usuario."""
    usuarios = cargar_usuarios()
    chat_id_str = str(chat_id)
    
    if chat_id_str in usuarios:
        usuarios[chat_id_str]['language'] = lang_code
        guardar_usuarios(usuarios)

def get_user_language(chat_id: int) -> str:
    """Obtiene el idioma del usuario."""
    usuarios = cargar_usuarios()
    return usuarios.get(str(chat_id), {}).get('language', 'es')

# === Intervalo de Alertas ===

def actualizar_intervalo_alerta(chat_id: int, new_interval_h: float) -> bool:
    """Actualiza el intervalo de alertas del usuario."""
    usuarios = cargar_usuarios()
    chat_id_str = str(chat_id)
    
    if chat_id_str in usuarios:
        try:
            usuarios[chat_id_str]['intervalo_alerta_h'] = float(new_interval_h)
            guardar_usuarios(usuarios)
            return True
        except ValueError:
            return False
    return False

def update_last_alert_timestamp(chat_id: int) -> None:
    """Actualiza el timestamp de última alerta."""
    usuarios = cargar_usuarios()
    chat_id_str = str(chat_id)
    
    if chat_id_str in usuarios:
        usuarios[chat_id_str]['last_alert_timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        guardar_usuarios(usuarios)

# === Meta datos ===

def get_user_meta(user_id: int, key: str, default=None):
    """Obtiene un metadata del usuario."""
    usuarios = cargar_usuarios()
    user_id_str = str(user_id)
    
    if user_id_str in usuarios:
        meta = usuarios[user_id_str].get('meta', {})
        return meta.get(key, default)
    return default

def set_user_meta(user_id: int, key: str, value) -> None:
    """Establece un metadata del usuario."""
    usuarios = cargar_usuarios()
    user_id_str = str(user_id)
    
    if user_id_str not in usuarios:
        usuarios[user_id_str] = {'meta': {}}
    
    if 'meta' not in usuarios[user_id_str]:
        usuarios[user_id_str]['meta'] = {}
    
    usuarios[user_id_str]['meta'][key] = value
    guardar_usuarios(usuarios)