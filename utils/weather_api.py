# utils/weather_api.py - API CLIENT CON CACHÉ INTELIGENTE

import requests
import time
from typing import Optional, Dict, Tuple
from datetime import datetime, timedelta
from core.config import OPENWEATHER_API_KEY
from utils.file_manager import add_log_line


class WeatherAPICache:
    """
    Caché inteligente para llamadas a OpenWeather API.

    Características:
    - Caché por coordenadas (lat/lon)
    - TTLs diferenciados por endpoint
    - Límite de 200 entradas en memoria
    - Auto-limpieza de entradas expiradas
    - Invalidación al cruzar medianoche
    - Estadísticas de uso (hit/miss ratio)
    - Compartido entre todos los loops de clima
    """

    DEFAULT_TTLS = {
        "weather": 10 * 60,       # 10 min — clima actual cambia frecuentemente
        "forecast": 30 * 60,      # 30 min — OWM actualiza cada 3h
        "uvi": 60 * 60,           # 60 min — índice UV cambia lentamente
        "air_pollution": 30 * 60,  # 30 min
    }
    DEFAULT_TTL = 15 * 60  # fallback
    MAX_ENTRIES = 200  # Aumentado de 100 a 200

    def __init__(self):
        self.cache: Dict[str, Dict] = {}
        self._last_midnight: Optional[datetime] = None
        # Estadísticas para debug
        self._stats = {
            "hits": 0,
            "misses": 0,
            "total_requests": 0
        }

    def _ttl(self, endpoint: str) -> int:
        """Obtiene el TTL específico para el endpoint."""
        return self.DEFAULT_TTLS.get(endpoint, self.DEFAULT_TTL)

    def _key(self, lat: float, lon: float, endpoint: str) -> str:
        """Genera clave única para caché."""
        return f"{endpoint}:{lat:.4f}:{lon:.4f}"

    def _midnight_passed(self) -> bool:
        """True si hemos cruzado medianoche desde el último reset."""
        today = datetime.now().date()
        if self._last_midnight is None or self._last_midnight.date() < today:
            self._last_midnight = datetime.now()
            return True
        return False

    def _invalidate_on_midnight(self):
        """
        Al cruzar medianoche, elimina entradas de UV y forecast
        para que el primer ciclo del día siempre traiga datos frescos.
        """
        if self._midnight_passed():
            stale = [
                k for k in self.cache
                if k.startswith("uvi:") or k.startswith("forecast:")
            ]
            for k in stale:
                del self.cache[k]
            if stale:
                add_log_line(f"🌙 Cache: {len(stale)} entradas UV/forecast invalidadas al cruzar medianoche")

    def get(self, lat: float, lon: float, endpoint: str) -> Optional[Dict]:
        """Obtiene datos del caché si no expiraron."""
        self._invalidate_on_midnight()
        key = self._key(lat, lon, endpoint)
        self._stats["total_requests"] += 1

        if key in self.cache:
            entry = self.cache[key]
            age = time.time() - entry["timestamp"]
            if age < self._ttl(endpoint):
                self._stats["hits"] += 1
                add_log_line(f"💾 Caché HIT: {endpoint} ({lat:.4f}, {lon:.4f}) | Edad: {int(age)}s | TTL: {self._ttl(endpoint)}s")
                return entry["data"]
            del self.cache[key]
        
        self._stats["misses"] += 1
        add_log_line(f"🔌 Caché MISS: {endpoint} ({lat:.4f}, {lon:.4f})")
        return None

    def set(self, lat: float, lon: float, endpoint: str, data: Dict):
        """Guarda en caché."""
        if len(self.cache) >= self.MAX_ENTRIES:
            self._cleanup()

        self.cache[self._key(lat, lon, endpoint)] = {
            "data": data,
            "timestamp": time.time(),
        }

    def _cleanup(self):
        """Elimina expiradas; si sigue lleno, elimina el 25% más antiguo."""
        now = time.time()
        # Primero: expiradas por su TTL específico
        expired = [
            k for k, v in self.cache.items()
            if (now - v["timestamp"]) >= self._ttl(k.split(":")[0])
        ]
        for k in expired:
            del self.cache[k]
        # Segundo: si aún está lleno, eliminar los más antiguos
        if len(self.cache) >= self.MAX_ENTRIES:
            oldest = sorted(self.cache, key=lambda k: self.cache[k]["timestamp"])
            for k in oldest[: self.MAX_ENTRIES // 4]:
                del self.cache[k]

    def get_stats(self) -> Dict:
        """Obtiene estadísticas del caché para monitoreo."""
        hit_ratio = (self._stats["hits"] / self._stats["total_requests"]) * 100 if self._stats["total_requests"] > 0 else 0
        return {
            **self._stats,
            "hit_ratio": round(hit_ratio, 2),
            "entries": len(self.cache),
            "max_entries": self.MAX_ENTRIES
        }
    
    def log_stats(self):
        """Registra estadísticas del caché en los logs."""
        stats = self.get_stats()
        add_log_line(f"📊 Caché stats: HIT: {stats['hits']} | MISS: {stats['misses']} | Ratio: {stats['hit_ratio']}% | Entradas: {stats['entries']}/{stats['max_entries']}")


class WeatherAPI:
    """Cliente robusto para OpenWeather API con reintentos y caché."""

    def __init__(self):
        self.cache = WeatherAPICache()
        self.api_key = OPENWEATHER_API_KEY
        self.base_url = "https://api.openweathermap.org/data/2.5"

    def _make_request(
        self,
        endpoint: str,
        params: Dict,
        max_retries: int = 3
    ) -> Optional[Dict]:
        """Hace request con reintentos."""
        url = f"{self.base_url}/{endpoint}"

        for attempt in range(max_retries):
            try:
                response = requests.get(
                    url,
                    params=params,
                    timeout=10
                )

                if response.status_code == 200:
                    return response.json()

                elif response.status_code == 429:
                    # Rate limit
                    wait_time = 2 ** attempt
                    add_log_line(f"⏱️ Rate limit en {endpoint}, esperando {wait_time}s...")
                    time.sleep(wait_time)

                else:
                    add_log_line(f"⚠️ HTTP {response.status_code} en {endpoint}")

            except requests.Timeout:
                add_log_line(f"⏱️ Timeout en {endpoint} (intento {attempt + 1})")

            except Exception as e:
                add_log_line(f"❌ Error en {endpoint}: {str(e)[:100]}")

            # Espera entre reintentos
            if attempt < max_retries - 1:
                time.sleep(1)

        return None

    def get_current_weather(self, lat: float, lon: float) -> Optional[Dict]:
        """Obtiene clima actual con caché."""
        # Verificar caché
        cached = self.cache.get(lat, lon, 'weather')
        if cached:
            return cached

        # Hacer request
        params = {
            "lat": lat,
            "lon": lon,
            "appid": self.api_key,
            "units": "metric",
            "lang": "es"
        }

        data = self._make_request('weather', params)

        if data:
            self.cache.set(lat, lon, 'weather', data)

        return data

    def get_forecast(self, lat: float, lon: float) -> Optional[Dict]:
        """Obtiene pronóstico con caché."""
        cached = self.cache.get(lat, lon, 'forecast')
        if cached:
            return cached

        params = {
            "lat": lat,
            "lon": lon,
            "appid": self.api_key,
            "units": "metric",
            "lang": "es"
        }

        data = self._make_request('forecast', params)

        if data:
            self.cache.set(lat, lon, 'forecast', data)

        return data

    def get_uv_index(self, lat: float, lon: float) -> float:
        """
        Obtiene el UV index.
        Primero intenta leer el UV desde el forecast (campo 'uvi'),
        que es más fiable que el endpoint /uvi (deprecado en plan gratuito).
        Si no lo encuentra, cae al endpoint legacy /uvi.
        """
        # Intento 1: desde forecast
        forecast = self.get_forecast(lat, lon)
        if forecast and isinstance(forecast, dict):
            entries = forecast.get("list", [])
            if entries:
                uvi = entries[0].get("uvi") or entries[0].get("uv")
                if uvi is not None:
                    return float(uvi)

        # Intento 2: endpoint /uvi (legacy, cache 60 min)
        cached = self.cache.get(lat, lon, "uvi")
        if cached:
            return float(cached.get("value", 0))

        data = self._make_request(
            "uvi",
            {"lat": lat, "lon": lon, "appid": self.api_key},
        )
        if data:
            self.cache.set(lat, lon, "uvi", data)
            return float(data.get("value", 0))
        return 0.0

    def get_air_quality(self, lat: float, lon: float) -> int:
        """Obtiene calidad del aire con caché."""
        cached = self.cache.get(lat, lon, 'air_pollution')
        if cached:
            return cached['list'][0]['main']['aqi']

        url = "http://api.openweathermap.org/data/2.5/air_pollution"
        params = {
            "lat": lat,
            "lon": lon,
            "appid": self.api_key
        }

        try:
            response = requests.get(url, params=params, timeout=5)
            data = response.json()

            if data and 'list' in data:
                self.cache.set(lat, lon, 'air_pollution', data)
                return data['list'][0]['main']['aqi']
        except Exception:
            pass

        return 0

    def reverse_geocode(self, lat: float, lon: float) -> Optional[Tuple[str, str]]:
        """
        Geocoding reverso: obtiene ciudad/país desde coordenadas.

        Returns:
            Tuple (city, country) o None si falla
        """
        url = "http://api.openweathermap.org/geo/1.0/reverse"
        params = {
            "lat": lat,
            "lon": lon,
            "limit": 1,
            "appid": self.api_key
        }

        try:
            response = requests.get(url, params=params, timeout=10)
            data = response.json()

            if data and len(data) > 0:
                city = data[0].get('name', 'Ubicación')
                country = data[0].get('country', '')
                return (city, country)

        except Exception as e:
            add_log_line(f"❌ Error en reverse_geocode: {e}")

        return None


# Instancia global
weather_api = WeatherAPI()


# Funciones alias para compatibilidad
def get_current_weather(lat, lon):
    return weather_api.get_current_weather(lat, lon)


def get_forecast(lat, lon):
    return weather_api.get_forecast(lat, lon)


def get_uv_index(lat, lon):
    return weather_api.get_uv_index(lat, lon)


def get_air_quality(lat, lon):
    return weather_api.get_air_quality(lat, lon)


def geocode_location(query_text):
    """Geocoding directo por texto."""
    url = "http://api.openweathermap.org/geo/1.0/direct"
    params = {
        "q": query_text,
        "limit": 1,
        "appid": OPENWEATHER_API_KEY
    }

    try:
        r = requests.get(url, params=params, timeout=10)
        data = r.json()

        if data:
            return {
                "lat": data[0]["lat"],
                "lon": data[0]["lon"],
                "name": data[0]["name"],
                "country": data[0].get("country", "")
            }
    except Exception:
        pass

    return None


def reverse_geocode(lat, lon):
    return weather_api.reverse_geocode(lat, lon)

def get_cache_stats():
    return weather_api.cache.get_stats()

def log_cache_stats():
    weather_api.cache.log_stats()

def invalidate_cache():
    """Limpia completamente el caché (para debugging)."""
    weather_api.cache.cache.clear()
    add_log_line("🧹 Cache: Todas las entradas eliminadas manualmente")
