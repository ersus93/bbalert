"""core/redis_client.py - Módulo de conexión a Redis con pool y caché local."""

import os
import redis
import time
import logging
from typing import Optional, Any, Dict
from core.config import DATA_DIR, USUARIOS_PATH

# Configuración de Redis (se cargará desde apit.env o variables de entorno)
REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_PASSWORD = None
REDIS_DB = 0
REDIS_SSL = False

# Variables para caché local
_REDIS_CLIENT = None
_REDIS_CONNECTED = False
CACHE_TTL = 300  # 5 minutos por defecto
CACHE_MAX_SIZE = 1000  # Limite máximo de entradas en caché local
_LOCAL_CACHE: Dict[str, Any] = {}
_CACHE_TIMESTAMPS: Dict[str, float] = {}

logger = logging.getLogger(__name__)

def _load_redis_config():
    """Carga la configuración de Redis desde variables de entorno."""
    global REDIS_HOST, REDIS_PORT, REDIS_PASSWORD, REDIS_DB, REDIS_SSL
    
    from core.config import load_dotenv
    load_dotenv('apit.env', override=True)
    
    REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
    REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
    REDIS_PASSWORD = os.getenv('REDIS_PASSWORD')
    REDIS_DB = int(os.getenv('REDIS_DB', 0))
    REDIS_SSL = os.getenv('REDIS_SSL', 'false').lower() == 'true'

def get_redis_client():
    """
    Obtiene el cliente Redis con conexión persistente.
    Utiliza un singleton para reutilizar la conexión.
    """
    global _REDIS_CLIENT, _REDIS_CONNECTED
    
    if _REDIS_CLIENT is None:
        try:
            _load_redis_config()
            
            # Crear pool de conexiones para mejor rendimiento
            connection_kwargs = {
                'host': REDIS_HOST,
                'port': REDIS_PORT,
                'db': REDIS_DB,
                'decode_responses': True,  # Para manejar strings como respuestas
                'health_check_interval': 30,
                'socket_connect_timeout': 5,
                'socket_timeout': 5,
            }
            
            if REDIS_PASSWORD:
                connection_kwargs['password'] = REDIS_PASSWORD
                
            if REDIS_SSL:
                connection_kwargs['ssl'] = True
                connection_kwargs['ssl_cert_reqs'] = None  # No verificar certificado (para desarrollo)
            
            # Crear cliente Redis con pool
            _REDIS_CLIENT = redis.Redis(**connection_kwargs)
            
            # Probar conexión
            pong = _REDIS_CLIENT.ping()
            if pong:
                _REDIS_CONNECTED = True
                logger.info("✅ Conexión a Redis establecida exitosamente")
            else:
                logger.warning("⚠️ No se pudo establecer conexión a Redis")
                
        except Exception as e:
            logger.error(f"❌ Error al conectar a Redis: {e}")
            _REDIS_CLIENT = None
    
    return _REDIS_CLIENT

def is_redis_connected() -> bool:
    """Verifica si hay conexión activa a Redis."""
    if _REDIS_CLIENT is None:
        return False
    try:
        return _REDIS_CLIENT.ping()
    except:
        return False

def clear_redis_cache():
    """Limpia la caché local."""
    _LOCAL_CACHE.clear()
    _CACHE_TIMESTAMPS.clear()
    logger.debug("🗑️ Caché local de Redis limpiada")

def get_with_cache(key: str, ttl: int = CACHE_TTL) -> Optional[Any]:
    """
    Obtiene un valor de Redis con caché local.
    Devuelve None si no existe o expiró.
    """
    current_time = time.time()
    
    # Verificar caché local primero
    if key in _LOCAL_CACHE:
        cache_time = _CACHE_TIMESTAMPS.get(key, 0)
        if current_time - cache_time < ttl:
            # Caché válida
            return _LOCAL_CACHE[key]
        else:
            # Caché expirada, la eliminamos
            del _LOCAL_CACHE[key]
            if key in _CACHE_TIMESTAMPS:
                del _CACHE_TIMESTAMPS[key]
    
    # No en caché o expirada, obtener de Redis
    client = get_redis_client()
    if client:
        try:
            value = client.get(key)
            if value is not None:
                # Guardar en caché local
                _LOCAL_CACHE[key] = value
                _CACHE_TIMESTAMPS[key] = current_time
                return value
            else:
                return None
        except Exception as e:
            logger.error(f"❌ Error al obtener clave '{key}' de Redis: {e}")
            return None
    else:
        logger.warning(f"⚠️ Redis no disponible, no se pudo obtener '{key}'")
        return None

def set_with_cache(key: str, value: Any, expire: Optional[int] = None) -> bool:
    """
    Guarda un valor en Redis y actualiza la caché local.
    Devuelve True si fue exitoso, False en caso de error.
    """
    from core.config import logger
    
    client = get_redis_client()
    if client:
        try:
            success = client.set(key, value, ex=expire)
            if success:
                # Actualizar caché local
                _LOCAL_CACHE[key] = value
                _CACHE_TIMESTAMPS[key] = time.time()
                
                # Limitar tamaño de caché - eliminar entradas más antiguas si excede límite
                if len(_LOCAL_CACHE) > CACHE_MAX_SIZE:
                    # Ordenar por timestamp (más viejo primero)
                    sorted_keys = sorted(_CACHE_TIMESTAMPS.keys(), key=lambda k: _CACHE_TIMESTAMPS[k])
                    # Eliminar 20% de las entradas más antiguas
                    remove_count = int(CACHE_MAX_SIZE * 0.2)
                    for old_key in sorted_keys[:remove_count]:
                        if old_key in _LOCAL_CACHE:
                            del _LOCAL_CACHE[old_key]
                        if old_key in _CACHE_TIMESTAMPS:
                            del _CACHE_TIMESTAMPS[old_key]
                    logger.debug(f"🗑️ Caché local limpiada: eliminadas {remove_count} entradas antiguas")
                
                return True
            else:
                logger.warning(f"⚠️ No se pudo guardar '{key}' en Redis (respuesta: {success})")
                return False
        except Exception as e:
            logger.error(f"❌ Error al guardar clave '{key}' en Redis: {e}")
            return False
    else:
        logger.warning(f"⚠️ Redis no disponible, no se pudo guardar '{key}'")
        # Guardar en archivo JSON como fallback
        return False

def hget_with_cache(name: str, key: str) -> Optional[Any]:
    """Obtiene un campo de un hash de Redis con caché local."""
    cache_key = f"{name}:{key}"
    return get_with_cache(cache_key)

def hset_with_cache(name: str, mapping: Dict) -> bool:
    """Guarda un hash en Redis y actualiza la caché local."""
    # Para cada campo, actualizamos la caché
    success = True
    for key, value in mapping.items():
        cache_key = f"{name}:{key}"
        _LOCAL_CACHE[cache_key] = value
        _CACHE_TIMESTAMPS[cache_key] = time.time()
    
    client = get_redis_client()
    if client:
        try:
            return client.hset(name, mapping=mapping)
        except Exception as e:
            logger.error(f"❌ Error al guardar hash '{name}' en Redis: {e}")
            return False
    else:
        return False

# Inicializar logger para este módulo
import logging
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    # Prueba rápida
    client = get_redis_client()
    if client:
        print("✅ Redis conectado")
        print(f"Ping: {client.ping()}")
    else:
        print("❌ No se pudo conectar a Redis")