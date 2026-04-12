"""core/redis_fallback.py - Sistema híbrido Redis + JSON para desarrollo."""

import os
import json
import redis
from datetime import datetime
from typing import Optional, Any, Dict, List

from utils.logger import logger
from core.config import DATA_DIR, USUARIOS_PATH

# Configuración de Redis
REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_PASSWORD = None
REDIS_DB = 0

# Variables globales
_REDIS_CLIENT = None
_USE_FALLBACK = False  # True si Redis no está disponible o se fuerza modo fallback

def _load_redis_config():
    """Carga configuración de Redis desde variables de entorno."""
    global REDIS_HOST, REDIS_PORT, REDIS_PASSWORD, REDIS_DB
    
    from core.config import load_dotenv
    load_dotenv('apit.env', override=True)
    
    REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
    REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
    REDIS_PASSWORD = os.getenv('REDIS_PASSWORD')
    REDIS_DB = int(os.getenv('REDIS_DB', 0))

def _init_redis():
    """Inicializa el cliente Redis."""
    global _REDIS_CLIENT, _USE_FALLBACK
    
    try:
        _load_redis_config()
        
        connection_kwargs = {
            'host': REDIS_HOST,
            'port': REDIS_PORT,
            'db': REDIS_DB,
            'decode_responses': True,
            'health_check_interval': 30,
            'socket_connect_timeout': 3,
            'socket_timeout': 3,
        }
        
        if REDIS_PASSWORD:
            connection_kwargs['password'] = REDIS_PASSWORD
        
        _REDIS_CLIENT = redis.Redis(**connection_kwargs)
        
        # Probar conexión
        if _REDIS_CLIENT.ping():
            logger.info("✅ Conexión a Redis establecida")
            _USE_FALLBACK = False
        else:
            logger.warning("⚠️ Redis no responde, usando modo fallback")
            _USE_FALLBACK = True
            
    except Exception as e:
        logger.warning(f"⚠️ No se pudo conectar a Redis: {e}. Usando modo fallback.")
        _USE_FALLBACK = True

def get_redis_client():
    """
    Obtiene el cliente Redis.
    Si no está inicializado, lo inicializa.
    """
    global _REDIS_CLIENT
    if _REDIS_CLIENT is None:
        _init_redis()
    return _REDIS_CLIENT if not _USE_FALLBACK else None

# === Funciones para Usuarios ===

def get_user_from_redis(user_id: int) -> Optional[Dict[str, Any]]:
    """Obtiene un usuario desde Redis."""
    client = get_redis_client()
    if client:
        try:
            datos_serializados = client.hgetall(f"usuario:{user_id}")
            if not datos_serializados:
                return None
            # Deserializar
            usuario = {}
            for key, value in datos_serializados.items():
                try:
                    usuario[key] = json.loads(value)
                except json.JSONDecodeError:
                    usuario[key] = value
            return usuario
        except Exception as e:
            logger.error(f"Error al obtener usuario {user_id} desde Redis: {e}")
            return None
    return None

def save_user_to_redis(user_id: int, usuario: Dict[str, Any]) -> bool:
    """Guarda un usuario en Redis."""
    client = get_redis_client()
    if client:
        try:
            # Serializar
            usuario_serializado = {k: json.dumps(v, ensure_ascii=False) for k, v in usuario.items()}
            client.hset(f"usuario:{user_id}", mapping=usuario_serializado)
            # Agregar al conjunto de IDs
            client.sadd('usuarios:ids', str(user_id))
            return True
        except Exception as e:
            logger.error(f"Error al guardar usuario {user_id} en Redis: {e}")
            return False
    return False

# Alias para compatibilidad
save_user = save_user_to_redis

def get_all_user_ids_from_redis() -> list:
    """Obtiene todos los IDs de usuarios desde Redis."""
    client = get_redis_client()
    if client:
        try:
            return list(client.smembers('usuarios:ids'))
        except Exception as e:
            logger.error(f"Error al obtener IDs de usuarios desde Redis: {e}")
            return []
    return []

# === Funciones de Respaldo (JSON) ===

def _get_usuarios_cache() -> Optional[Dict]:
    """Obtiene el cache de usuarios desde JSON."""
    cache_path = os.path.join(DATA_DIR, "usuarios_cache.json")
    if os.path.exists(cache_path):
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return None
    return None

def _set_usuarios_cache(data: Dict):
    """Guarda el cache de usuarios en JSON."""
    cache_path = os.path.join(DATA_DIR, "usuarios_cache.json")
    try:
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        logger.error(f"Error al guardar cache de usuarios: {e}")

def get_user_from_fallback(user_id: int) -> Optional[Dict[str, Any]]:
    """Obtiene un usuario desde el fallback (JSON)."""
    cache = _get_usuarios_cache()
    if cache and str(user_id) in cache:
        return cache[str(user_id)]
    return None

def save_user_to_fallback(user_id: int, usuario: Dict[str, Any]) -> bool:
    """Guarda un usuario en el fallback (JSON)."""
    cache = _get_usuarios_cache() or {}
    cache[str(user_id)] = usuario
    try:
        _set_usuarios_cache(cache)
        return True
    except Exception as e:
        logger.error(f"Error al guardar usuario en fallback: {e}")
        return False

def get_all_user_ids_from_fallback() -> list:
    """Obtiene todos los IDs de usuarios desde el fallback."""
    cache = _get_usuarios_cache()
    if cache:
        return [int(uid) for uid in cache.keys()]
    return []

# === Funciones Unificadas para Usuarios ===

def get_user(user_id: int) -> Optional[Dict[str, Any]]:
    """Obtiene un usuario, primero intenta desde Redis, luego desde fallback."""
    # Intentar con Redis primero
    usuario = get_user_from_redis(user_id)
    if usuario is not None:
        return usuario
    # Si no está en Redis, intentar con fallback
    return get_user_from_fallback(user_id)

def save_user(user_id: int, usuario: Dict[str, Any]) -> bool:
    """Guarda un usuario en Redis, si falla usa fallback."""
    if save_user_to_redis(user_id, usuario):
        return True
    return save_user_to_fallback(user_id, usuario)

def get_all_user_ids() -> list:
    """Obtiene todos los IDs de usuarios."""
    ids = get_all_user_ids_from_redis()
    if ids:
        return [int(uid) for uid in ids]
    # Si no hay IDs en Redis, intentar con fallback
    return get_all_user_ids_from_fallback()

# === Funciones para Price Alerts ===

def get_price_alerts(user_id: int) -> List[Dict]:
    """Obtiene las alertas de precio para un usuario."""
    client = get_redis_client()
    if client:
        try:
            key = f"price_alerts:{user_id}"
            data_json = client.get(key)
            if data_json:
                return json.loads(data_json)
            else:
                return []
        except Exception as e:
            logger.error(f"Error al obtener price_alerts de Redis: {e}")
            return []
    # Fallback a archivo
    from core.config import PRICE_ALERTS_PATH
    if os.path.exists(PRICE_ALERTS_PATH):
        try:
            with open(PRICE_ALERTS_PATH, 'r', encoding='utf-8') as f:
                all_alerts = json.load(f)
                return all_alerts.get(str(user_id), [])
        except (json.JSONDecodeError, FileNotFoundError):
            return []
    return []

def save_price_alerts(user_id: int, alerts: List[Dict]) -> bool:
    """Guarda las alertas de precio para un usuario."""
    client = get_redis_client()
    if client:
        try:
            key = f"price_alerts:{user_id}"
            data_json = json.dumps(alerts, ensure_ascii=False)
            client.set(key, data_json)
            return True
        except Exception as e:
            logger.error(f"Error al guardar price_alerts en Redis: {e}")
            return False
    # Fallback a archivo
    from core.config import PRICE_ALERTS_PATH
    # Cargar todo, actualizar y guardar
    all_alerts = {}
    if os.path.exists(PRICE_ALERTS_PATH):
        try:
            with open(PRICE_ALERTS_PATH, 'r', encoding='utf-8') as f:
                all_alerts = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            pass
    all_alerts[str(user_id)] = alerts
    try:
        with open(PRICE_ALERTS_PATH, 'w', encoding='utf-8') as f:
            json.dump(all_alerts, f, indent=4)
        return True
    except Exception as e:
        logger.error(f"Error al guardar price_alerts en archivo: {e}")
        return False

# === Funciones para HBD History ===

def get_hbd_history() -> List[Dict]:
    """Obtiene el historial de precios de HBD."""
    client = get_redis_client()
    if client:
        try:
            key = "hbd_history"
            data_json = client.get(key)
            if data_json:
                return json.loads(data_json)
            else:
                return []
        except Exception as e:
            logger.error(f"Error al obtener hbd_history de Redis: {e}")
            return []
    # Fallback a archivo
    from core.config import HBD_HISTORY_PATH
    if os.path.exists(HBD_HISTORY_PATH):
        try:
            with open(HBD_HISTORY_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return []
    return []

def save_hbd_history(history: List[Dict]) -> bool:
    """Guarda el historial de precios de HBD."""
    client = get_redis_client()
    if client:
        try:
            key = "hbd_history"
            data_json = json.dumps(history, ensure_ascii=False)
            client.set(key, data_json)
            return True
        except Exception as e:
            logger.error(f"Error al guardar hbd_history en Redis: {e}")
            return False
    # Fallback a archivo
    from core.config import HBD_HISTORY_PATH
    try:
        with open(HBD_HISTORY_PATH, 'w', encoding='utf-8') as f:
            json.dump(history, f, indent=4)
        return True
    except Exception as e:
        logger.error(f"Error al guardar hbd_history en archivo: {e}")
        return False

# === Funciones para Custom Alert History ===

def get_custom_alert_history() -> Dict:
    """Obtiene el historial de alertas personalizadas."""
    client = get_redis_client()
    if client:
        try:
            key = "custom_alert_history"
            data_json = client.get(key)
            if data_json:
                return json.loads(data_json)
            else:
                return {}
        except Exception as e:
            logger.error(f"Error al obtener custom_alert_history de Redis: {e}")
            return {}
    # Fallback a archivo
    from core.config import CUSTOM_ALERT_HISTORY_PATH
    if os.path.exists(CUSTOM_ALERT_HISTORY_PATH):
        try:
            with open(CUSTOM_ALERT_HISTORY_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {}
    return {}

def save_custom_alert_history(history: Dict) -> bool:
    """Guarda el historial de alertas personalizadas."""
    client = get_redis_client()
    if client:
        try:
            key = "custom_alert_history"
            data_json = json.dumps(history, ensure_ascii=False)
            client.set(key, data_json)
            return True
        except Exception as e:
            logger.error(f"Error al guardar custom_alert_history en Redis: {e}")
            return False
    # Fallback a archivo
    from core.config import CUSTOM_ALERT_HISTORY_PATH
    try:
        with open(CUSTOM_ALERT_HISTORY_PATH, 'w', encoding='utf-8') as f:
            json.dump(history, f, indent=4)
        return True
    except Exception as e:
        logger.error(f"Error al guardar custom_alert_history en archivo: {e}")
        return False

# === Funciones para ElToque History ===

def get_eltoque_history() -> List[Dict]:
    """Obtiene el historial de ElToque."""
    client = get_redis_client()
    if client:
        try:
            key = "eltoque_history"
            data_json = client.get(key)
            if data_json:
                return json.loads(data_json)
            else:
                return []
        except Exception as e:
            logger.error(f"Error al obtener eltoque_history de Redis: {e}")
            return []
    # Fallback a archivo
    from core.config import ELTOQUE_HISTORY_PATH
    if os.path.exists(ELTOQUE_HISTORY_PATH):
        try:
            with open(ELTOQUE_HISTORY_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return []
    return []

def save_eltoque_history(history: List[Dict]) -> bool:
    """Guarda el historial de ElToque."""
    client = get_redis_client()
    if client:
        try:
            key = "eltoque_history"
            data_json = json.dumps(history, ensure_ascii=False)
            client.set(key, data_json)
            return True
        except Exception as e:
            logger.error(f"Error al guardar eltoque_history en Redis: {e}")
            return False
    # Fallback a archivo
    from core.config import ELTOQUE_HISTORY_PATH
    try:
        with open(ELTOQUE_HISTORY_PATH, 'w', encoding='utf-8') as f:
            json.dump(history, f, indent=4)
        return True
    except Exception as e:
        logger.error(f"Error al guardar eltoque_history en archivo: {e}")
        return False

# === Funciones para Last Prices ===

def get_last_prices() -> Dict:
    """Obtiene los últimos precios."""
    client = get_redis_client()
    if client:
        try:
            key = "last_prices"
            data_json = client.get(key)
            if data_json:
                return json.loads(data_json)
            else:
                return {}
        except Exception as e:
            logger.error(f"Error al obtener last_prices de Redis: {e}")
            return {}
    # Fallback a archivo
    from core.config import LAST_PRICES_PATH
    if os.path.exists(LAST_PRICES_PATH):
        try:
            with open(LAST_PRICES_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {}
    return {}

def save_last_prices(prices: Dict) -> bool:
    """Guarda los últimos precios."""
    client = get_redis_client()
    if client:
        try:
            key = "last_prices"
            data_json = json.dumps(prices, ensure_ascii=False)
            client.set(key, data_json)
            return True
        except Exception as e:
            logger.error(f"Error al guardar last_prices en Redis: {e}")
            return False
    # Fallback a archivo
    from core.config import LAST_PRICES_PATH
    try:
        with open(LAST_PRICES_PATH, 'w', encoding='utf-8') as f:
            json.dump(prices, f, indent=4)
        return True
    except Exception as e:
        logger.error(f"Error al guardar last_prices en archivo: {e}")
        return False

# === Funciones para Ads ===

def get_ads() -> Dict:
    """Obtiene los anuncios."""
    client = get_redis_client()
    if client:
        try:
            key = "ads"
            data_json = client.get(key)
            if data_json:
                return json.loads(data_json)
            else:
                return {}
        except Exception as e:
            logger.error(f"Error al obtener ads de Redis: {e}")
            return {}
    # Fallback a archivo
    from core.config import ADS_PATH
    if os.path.exists(ADS_PATH):
        try:
            with open(ADS_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {}
    return {}

def save_ads(ads: Dict) -> bool:
    """Guarda los anuncios."""
    client = get_redis_client()
    if client:
        try:
            key = "ads"
            data_json = json.dumps(ads, ensure_ascii=False)
            client.set(key, data_json)
            return True
        except Exception as e:
            logger.error(f"Error al guardar ads en Redis: {e}")
            return False
    # Fallback a archivo
    from core.config import ADS_PATH
    try:
        with open(ADS_PATH, 'w', encoding='utf-8') as f:
            json.dump(ads, f, indent=4)
        return True
    except Exception as e:
        logger.error(f"Error al guardar ads en archivo: {e}")
        return False

# === Funciones para HBD Thresholds ===

def get_hbd_thresholds() -> Dict:
    """Obtiene los umbrales de HBD."""
    client = get_redis_client()
    if client:
        try:
            key = "hbd_thresholds"
            data_json = client.get(key)
            if data_json:
                return json.loads(data_json)
            else:
                return {}
        except Exception as e:
            logger.error(f"Error al obtener hbd_thresholds de Redis: {e}")
            return {}
    # Fallback a archivo
    from core.config import HBD_THRESHOLDS_PATH
    if os.path.exists(HBD_THRESHOLDS_PATH):
        try:
            with open(HBD_THRESHOLDS_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {}
    return {}

def save_hbd_thresholds(thresholds: Dict) -> bool:
    """Guarda los umbrales de HBD."""
    client = get_redis_client()
    if client:
        try:
            key = "hbd_thresholds"
            data_json = json.dumps(thresholds, ensure_ascii=False)
            client.set(key, data_json)
            return True
        except Exception as e:
            logger.error(f"Error al guardar hbd_thresholds en Redis: {e}")
            return False
    # Fallback a archivo
    from core.config import HBD_THRESHOLDS_PATH
    try:
        with open(HBD_THRESHOLDS_PATH, 'w', encoding='utf-8') as f:
            json.dump(thresholds, f, indent=4, sort_keys=True)
        return True
    except Exception as e:
        logger.error(f"Error al guardar hbd_thresholds en archivo: {e}")
        return False

# === Funciones para Weather Subs ===

def get_weather_subs() -> Dict:
    """Obtiene las suscripciones de clima."""
    client = get_redis_client()
    if client:
        try:
            key = "weather_subs"
            data_json = client.get(key)
            if data_json:
                return json.loads(data_json)
            else:
                return {}
        except Exception as e:
            logger.error(f"Error al obtener weather_subs de Redis: {e}")
            return {}
    # Fallback a archivo
    from core.config import WEATHER_SUBS_PATH
    if os.path.exists(WEATHER_SUBS_PATH):
        try:
            with open(WEATHER_SUBS_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {}
    return {}

def save_weather_subs(subs: Dict) -> bool:
    """Guarda las suscripciones de clima."""
    client = get_redis_client()
    if client:
        try:
            key = "weather_subs"
            data_json = json.dumps(subs, ensure_ascii=False)
            client.set(key, data_json)
            return True
        except Exception as e:
            logger.error(f"Error al guardar weather_subs en Redis: {e}")
            return False
    # Fallback a archivo
    from core.config import WEATHER_SUBS_PATH
    try:
        with open(WEATHER_SUBS_PATH, 'w', encoding='utf-8') as f:
            json.dump(subs, f, indent=4)
        return True
    except Exception as e:
        logger.error(f"Error al guardar weather_subs en archivo: {e}")
        return False

# === Funciones para Weather Last Alerts ===

def get_weather_last_alerts() -> Dict:
    """Obtiene los últimos alertas de clima."""
    client = get_redis_client()
    if client:
        try:
            key = "weather_last_alerts"
            data_json = client.get(key)
            if data_json:
                return json.loads(data_json)
            else:
                return {}
        except Exception as e:
            logger.error(f"Error al obtener weather_last_alerts de Redis: {e}")
            return {}
    # Fallback a archivo
    from core.config import WEATHER_LAST_ALERTS_PATH
    if os.path.exists(WEATHER_LAST_ALERTS_PATH):
        try:
            with open(WEATHER_LAST_ALERTS_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {}
    return {}

def save_weather_last_alerts(data: Dict) -> bool:
    """Guarda los últimos alertas de clima."""
    client = get_redis_client()
    if client:
        try:
            key = "weather_last_alerts"
            data_json = json.dumps(data, ensure_ascii=False)
            client.set(key, data_json)
            return True
        except Exception as e:
            logger.error(f"Error al guardar weather_last_alerts en Redis: {e}")
            return False
    # Fallback a archivo
    from core.config import WEATHER_LAST_ALERTS_PATH
    try:
        with open(WEATHER_LAST_ALERTS_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
        return True
    except Exception as e:
        logger.error(f"Error al guardar weather_last_alerts en archivo: {e}")
        return False

# === Funciones para Year Quotes ===

def get_year_quotes() -> List[str]:
    """Obtiene las frases anuales."""
    client = get_redis_client()
    if client:
        try:
            key = "year_quotes"
            data_json = client.get(key)
            if data_json:
                return json.loads(data_json)
            else:
                return []
        except Exception as e:
            logger.error(f"Error al obtener year_quotes de Redis: {e}")
            return []
    # Fallback a archivo
    from core.config import YEAR_QUOTES_PATH
    if os.path.exists(YEAR_QUOTES_PATH):
        try:
            with open(YEAR_QUOTES_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return []
    return []

def save_year_quotes(quotes: List[str]) -> bool:
    """Guarda las frases anuales."""
    client = get_redis_client()
    if client:
        try:
            key = "year_quotes"
            data_json = json.dumps(quotes, ensure_ascii=False)
            client.set(key, data_json)
            return True
        except Exception as e:
            logger.error(f"Error al guardar year_quotes en Redis: {e}")
            return False
    # Fallback a archivo
    from core.config import YEAR_QUOTES_PATH
    try:
        with open(YEAR_QUOTES_PATH, 'w', encoding='utf-8') as f:
            json.dump(quotes, f, indent=4)
        return True
    except Exception as e:
        logger.error(f"Error al guardar year_quotes en archivo: {e}")
        return False

# === Funciones para Year Subs ===

def get_year_subs() -> Dict:
    """Obtiene las suscripciones anuales."""
    client = get_redis_client()
    if client:
        try:
            key = "year_subs"
            data_json = client.get(key)
            if data_json:
                return json.loads(data_json)
            else:
                return {}
        except Exception as e:
            logger.error(f"Error al obtener year_subs de Redis: {e}")
            return {}
    # Fallback a archivo
    from core.config import YEAR_SUBS_PATH
    if os.path.exists(YEAR_SUBS_PATH):
        try:
            with open(YEAR_SUBS_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {}
    return {}

def save_year_subs(subs: Dict) -> bool:
    """Guarda las suscripciones anuales."""
    client = get_redis_client()
    if client:
        try:
            key = "year_subs"
            data_json = json.dumps(subs, ensure_ascii=False)
            client.set(key, data_json)
            return True
        except Exception as e:
            logger.error(f"Error al guardar year_subs en Redis: {e}")
            return False
    # Fallback a archivo
    from core.config import YEAR_SUBS_PATH
    try:
        with open(YEAR_SUBS_PATH, 'w', encoding='utf-8') as f:
            json.dump(subs, f, indent=4)
        return True
    except Exception as e:
        logger.error(f"Error al guardar year_subs en archivo: {e}")
        return False

# === Funciones para Events Log ===

def get_events_log() -> List[Dict]:
    """Obtiene el log de eventos."""
    client = get_redis_client()
    if client:
        try:
            key = "events_log"
            data_json = client.get(key)
            if data_json:
                return json.loads(data_json)
            else:
                return []
        except Exception as e:
            logger.error(f"Error al obtener events_log de Redis: {e}")
            return []
    # Fallback a archivo
    from core.config import EVENTS_LOG_PATH
    if os.path.exists(EVENTS_LOG_PATH):
        try:
            with open(EVENTS_LOG_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return []
    return []

def save_events_log(log: List[Dict]) -> bool:
    """Guarda el log de eventos."""
    client = get_redis_client()
    if client:
        try:
            key = "events_log"
            data_json = json.dumps(log, ensure_ascii=False)
            client.set(key, data_json)
            return True
        except Exception as e:
            logger.error(f"Error al guardar events_log en Redis: {e}")
            return False
    # Fallback a archivo
    from core.config import EVENTS_LOG_PATH
    try:
        with open(EVENTS_LOG_PATH, 'w', encoding='utf-8') as f:
            json.dump(log, f, indent=4)
        return True
    except Exception as e:
        logger.error(f"Error al guardar events_log en archivo: {e}")
        return False

def get_all_user_ids() -> List[int]:
    """Obtiene todos los IDs de usuarios desde Redis."""
    client = get_redis_client()
    if client:
        try:
            return [int(uid) for uid in client.smembers('usuarios:ids')]
        except Exception as e:
            logger.error(f"Error al obtener IDs de usuarios desde Redis: {e}")
            return []
    return []

# Alias para compatibilidad
get_all_user_ids = get_all_user_ids