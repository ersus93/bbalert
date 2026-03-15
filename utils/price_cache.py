# utils/price_cache.py
"""
Sistema de cache con fallback para precios y datos externos.
Proporciona resiliencia cuando las APIs externas fallan.
"""

import json
import time
import os
from pathlib import Path
from typing import Any, Dict, Optional
from datetime import datetime, timedelta
from utils.logger import logger
from core.config import DATA_DIR

# ============================================================
# CONSTANTES
# ============================================================

CACHE_DIR = Path(DATA_DIR) / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# TTL por defecto (en segundos)
DEFAULT_TTL = 300  # 5 minutos


# ============================================================
# CLASE PRINCIPAL
# ============================================================

class PriceCache:
    """
    Cache con TTL y fallback para precios de criptomonedas.
    """
    
    def __init__(self, default_ttl: int = DEFAULT_TTL):
        """
        Inicializa el cache.
        
        Args:
            default_ttl: Tiempo de vida por defecto en segundos
        """
        self.default_ttl = default_ttl
        self._memory_cache: Dict[str, Dict[str, Any]] = {}
    
    def _get_cache_path(self, key: str) -> Path:
        """Obtiene la ruta del archivo de cache."""
        # Sanitize key para evitar path traversal
        safe_key = "".join(c if c.isalnum() or c in "-_" else "_" for c in key)
        return CACHE_DIR / f"{safe_key}.json"
    
    def get(self, key: str) -> Optional[Any]:
        """
        Obtiene un valor del cache.
        
        Args:
            key: Clave del cache
            
        Returns:
            El valor cacheado o None si no existe/expiró
        """
        # Primero buscar en memoria
        if key in self._memory_cache:
            entry = self._memory_cache[key]
            if time.time() - entry["timestamp"] < entry["ttl"]:
                logger.debug(f"Cache HIT (memory): {key}")
                return entry["value"]
            else:
                # Expirado en memoria
                del self._memory_cache[key]
        
        # Luego buscar en disco
        cache_path = self._get_cache_path(key)
        if cache_path.exists():
            try:
                with open(cache_path, "r") as f:
                    entry = json.load(f)
                
                if time.time() - entry["timestamp"] < entry["ttl"]:
                    # Cargar en memoria para acceso rápido
                    self._memory_cache[key] = entry
                    logger.debug(f"Cache HIT (disk): {key}")
                    return entry["value"]
                else:
                    # Expirado - borrar
                    cache_path.unlink()
                    
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Cache read error for {key}: {e}")
        
        logger.debug(f"Cache MISS: {key}")
        return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """
        Guarda un valor en el cache.
        
        Args:
            key: Clave del cache
            value: Valor a guardar
            ttl: Tiempo de vida en segundos (None = usar default)
        """
        ttl = ttl or self.default_ttl
        
        entry = {
            "value": value,
            "timestamp": time.time(),
            "ttl": ttl
        }
        
        # Guardar en memoria
        self._memory_cache[key] = entry
        
        # Guardar en disco
        try:
            cache_path = self._get_cache_path(key)
            with open(cache_path, "w") as f:
                json.dump(entry, f)
            logger.debug(f"Cache SET: {key} (ttl={ttl}s)")
        except IOError as e:
            logger.warning(f"Cache write error for {key}: {e}")
    
    def invalidate(self, key: str) -> None:
        """
        Invalida una entrada del cache.
        
        Args:
            key: Clave a invalidar
        """
        # Borrar de memoria
        if key in self._memory_cache:
            del self._memory_cache[key]
        
        # Borrar de disco
        cache_path = self._get_cache_path(key)
        if cache_path.exists():
            cache_path.unlink()
        
        logger.debug(f"Cache INVALIDATE: {key}")
    
    def clear(self) -> None:
        """Limpia todo el cache."""
        self._memory_cache.clear()
        
        for cache_file in CACHE_DIR.glob("*.json"):
            try:
                cache_file.unlink()
            except IOError:
                pass
        
        logger.info("Cache cleared")
    
    def get_with_fallback(
        self, 
        key: str, 
        fetch_func, 
        ttl: Optional[int] = None,
        *args,
        **kwargs
    ) -> Any:
        """
        Obtiene del cache o ejecuta fetch_func si no existe.
        
        Args:
            key: Clave del cache
            fetch_func: Función async para obtener datos frescos
            ttl: Tiempo de vida
            *args, **kwargs: Argumentos para fetch_func
            
        Returns:
            Datos cacheados o frescos
        """
        # Intentar obtener del cache
        cached = self.get(key)
        if cached is not None:
            return cached
        
        # Si no hay cache, intentar obtener datos frescos
        try:
            # Ejecutar función de fetch
            result = fetch_func(*args, **kwargs)
            
            # Si es un awaitable (coroutine), manejarlo
            import asyncio
            if asyncio.iscoroutine(result):
                # Promise - el caller debe await
                return result
            
            # Guardar en cache y retornar
            if result is not None:
                self.set(key, result, ttl)
            return result
            
        except Exception as e:
            logger.warning(f"Fetch failed for {key}, no fallback: {e}")
            return None


# ============================================================
# INSTANCIA GLOBAL
# ============================================================

# Instancia global del cache de precios
price_cache = PriceCache()


# ============================================================
# HELPERS RÁPIDOS
# ============================================================

def get_cached_price(symbol: str) -> Optional[Dict[str, Any]]:
    """
    Obtiene el precio cacheado de una cryptomoneda.
    
    Args:
        symbol: Símbolo de la cryptomoneda (ej: 'BTC')
        
    Returns:
        Dict con precio o None
    """
    return price_cache.get(f"price_{symbol.upper()}")


def set_cached_price(symbol: str, price_data: Dict[str, Any], ttl: int = 60) -> None:
    """
    Guarda el precio en cache.
    
    Args:
        symbol: Símbolo de la cryptomoneda
        price_data: Dict con datos del precio
        ttl: Tiempo de vida en segundos
    """
    price_cache.set(f"price_{symbol.upper()}", price_data, ttl)


def invalidate_price(symbol: str) -> None:
    """
    Invalida el cache de precio de una cryptomoneda.
    
    Args:
        symbol: Símbolo de la cryptomoneda
    """
    price_cache.invalidate(f"price_{symbol.upper()}")
