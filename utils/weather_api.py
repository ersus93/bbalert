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
    - TTL de 15 minutos por defecto
    - Límite de 100 entradas en memoria
    - Auto-limpieza de entradas expiradas
    """
    
    def __init__(self, ttl_minutes: int = 15, max_entries: int = 100):
        self.cache: Dict[str, Dict] = {}
        self.ttl_seconds = ttl_minutes * 60
        self.max_entries = max_entries
    
    def _generate_key(self, lat: float, lon: float, endpoint: str) -> str:
        """Genera clave única para caché."""
        return f"{endpoint}:{lat:.4f}:{lon:.4f}"
    
    def get(self, lat: float, lon: float, endpoint: str) -> Optional[Dict]:
        """Obtiene datos del caché si no expiraron."""
        key = self._generate_key(lat, lon, endpoint)
        
        if key in self.cache:
            entry = self.cache[key]
            age = time.time() - entry['timestamp']
            
            if age < self.ttl_seconds:
                add_log_line(f"💾 Caché HIT: {endpoint} ({lat:.4f}, {lon:.4f})")
                return entry['data']
            else:
                del self.cache[key]
        
        return None
    
    def set(self, lat: float, lon: float, endpoint: str, data: Dict):
        """Guarda en caché."""
        # Limpiar caché si está lleno
        if len(self.cache) >= self.max_entries:
            self._cleanup_old_entries()
        
        key = self._generate_key(lat, lon, endpoint)
        self.cache[key] = {
            'data': data,
            'timestamp': time.time()
        }
    
    def _cleanup_old_entries(self):
        """Elimina entradas expiradas."""
        now = time.time()
        expired = [
            k for k, v in self.cache.items()
            if (now - v['timestamp']) >= self.ttl_seconds
        ]
        
        for key in expired:
            del self.cache[key]
        
        # Si aún está lleno, eliminar las más antiguas
        if len(self.cache) >= self.max_entries:
            sorted_keys = sorted(
                self.cache.keys(),
                key=lambda k: self.cache[k]['timestamp']
            )
            
            to_remove = sorted_keys[:self.max_entries // 4]
            for key in to_remove:
                del self.cache[key]

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
        """Obtiene índice UV con caché."""
        cached = self.cache.get(lat, lon, 'uvi')
        if cached:
            return cached.get('value', 0)
        
        params = {
            "lat": lat,
            "lon": lon,
            "appid": self.api_key
        }
        
        data = self._make_request('uvi', params)
        
        if data:
            self.cache.set(lat, lon, 'uvi', data)
            return data.get('value', 0)
        
        return 0
    
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
        except:
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
    except:
        pass
    
    return None

def reverse_geocode(lat, lon):
    return weather_api.reverse_geocode(lat, lon)
