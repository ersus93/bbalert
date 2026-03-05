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
TTLs diferenciados por endpoint (Paso 7):
- weather (clima actual): 10 min — cambia con frecuencia
- forecast (pronóstico): 30 min — OWM lo actualiza cada 3 h
- uvi (UV index): 60 min — índice horario, cambia lento
- air_pollution (AQI): 30 min
Límite: 200 entradas en memoria con auto-limpieza.
Invalidación automática al cruzar medianoche para evitar datos del día anterior.
"""
DEFAULT_TTLS = {
"weather": 10 * 60, # 10 min
"forecast": 30 * 60, # 30 min
"uvi": 60 * 60, # 60 min
"air_pollution": 30 * 60, # 30 min
}
DEFAULT_TTL = 15 * 60 # fallback para endpoints no listados
MAX_ENTRIES = 200
def __init__(self):
self.cache: Dict[str, Dict] = {}
self._last_midnight: Optional[datetime] = None
# ── Helpers ──────────────────────────────────────────────────────────
def _ttl(self, endpoint: str) -> int:
return self.DEFAULT_TTLS.get(endpoint, self.DEFAULT_TTL)
def _key(self, lat: float, lon: float, endpoint: str) -> str:
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
Al cruzar medianoche, elimina entradas de UV y forecast para que el
primer ciclo del día siempre traiga datos frescos (Paso 7).
"""
if self._midnight_passed():
stale = [
k for k in self.cache
if k.startswith("uvi:") or k.startswith("forecast:")
]
for k in stale:
del self.cache[k]
if stale:
add_log_line(
f"
Cache: {len(stale)} entradas UV/forecast invalidadas al cruzar media
)
# ── API pública ───────────────────────────────────────────────────────
def get(self, lat: float, lon: float, endpoint: str) -> Optional[Dict]:
self._invalidate_on_midnight()
key = self._key(lat, lon, endpoint)
if key in self.cache:
entry = self.cache[key]
age = time.time() - entry["timestamp"]
if age < self._ttl(endpoint):
return entry["data"]
# Entrada expirada
del self.cache[key]
return None
def set(self, lat: float, lon: float, endpoint: str, data: Dict):
if len(self.cache) >= self.MAX_ENTRIES:
self._cleanup()
self.cache[self._key(lat, lon, endpoint)] = {

 "data": data,
"timestamp": time.time(),
}
def _cleanup(self):
"""Elimina expiradas; si sigue lleno, elimina el 25 % más antiguo."""
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
max_retries: int = 3,
base_url: Optional[str] = None,
) -> Optional[Dict]:
url = f"{base_url or self.base_url}/{endpoint}"
for attempt in range(max_retries):
try:
resp = requests.get(url, params=params, timeout=10)
if resp.status_code == 200:
return resp.json()
elif resp.status_code == 429:
wait = 2 ** attempt

 add_log_line(f"
Rate limit en {endpoint}, esperando {wait}s…")
time.sleep(wait)
else:
add_log_line(f"
HTTP {resp.status_code} en {endpoint}")
except requests.Timeout:
add_log_line(f"
Timeout en {endpoint} (intento {attempt + 1})")
except Exception as e:
add_log_line(f"
Error en {endpoint}: {str(e)[:100]}")
if attempt < max_retries - 1:
time.sleep(1)
return None
# ── Endpoints ─────────────────────────────────────────────────────────
def get_current_weather(self, lat: float, lon: float) -> Optional[Dict]:
cached = self.cache.get(lat, lon, "weather")
if cached:
return cached
data = self._make_request(
"weather",
{"lat": lat, "lon": lon, "appid": self.api_key,
"units": "metric", "lang": "es"},
)
if data:
self.cache.set(lat, lon, "weather", data)
return data
def get_forecast(self, lat: float, lon: float) -> Optional[Dict]:
cached = self.cache.get(lat, lon, "forecast")
if cached:
return cached
data = self._make_request(
"forecast",
{"lat": lat, "lon": lon, "appid": self.api_key,
"units": "metric", "lang": "es"},
)
if data:
self.cache.set(lat, lon, "forecast", data)
return data
def get_uv_index(self, lat: float, lon: float) -> float:
"""

 Obtiene el UV index.
Primero intenta leer el UV desde el forecast (One Call / forecast),
que es más fiable que el endpoint /uvi (deprecado en plan gratuito).
Si no lo encuentra, cae al endpoint legacy /uvi.
"""
# ── Intento 1: desde forecast (campo 'uvi' en cada entry) ──────────
forecast = self.get_forecast(lat, lon)
if forecast and isinstance(forecast, dict):
entries = forecast.get("list", [])
if entries:
uvi = entries[0].get("uvi") or entries[0].get("uv")
if uvi is not None:
return float(uvi)
# ── Intento 2: endpoint /uvi (legacy, cache 60 min) ────────────────
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
cached = self.cache.get(lat, lon, "air_pollution")
if cached:
try:
return cached["list"][0]["main"]["aqi"]
except (KeyError, IndexError):
pass
try:
resp = requests.get(
"http://api.openweathermap.org/data/2.5/air_pollution",
params={"lat": lat, "lon": lon, "appid": self.api_key},
timeout=5,
)
data = resp.json()
if data and "list" in data:
self.cache.set(lat, lon, "air_pollution", data)
return data["list"][0]["main"]["aqi"]

 except Exception:
pass
return 0
def reverse_geocode(self, lat: float, lon: float) -> Optional[Tuple[str, str]]:
try:
resp = requests.get(
"http://api.openweathermap.org/geo/1.0/reverse",
params={"lat": lat, "lon": lon, "limit": 1, "appid": self.api_key},
timeout=10,
)
data = resp.json()
if data:
return data[0].get("name", "Ubicación"), data[0].get("country", "")
except Exception as e:
add_log_line(f"
Error en reverse_geocode: {e}")
return None
# ---------------------------------------------------------------------------
# Instancia global
# ---------------------------------------------------------------------------
weather_api = WeatherAPI()
# Funciones alias para compatibilidad con el resto del proyecto
def get_current_weather(lat, lon):
return weather_api.get_current_weather(lat, lon)
def get_forecast(lat, lon):
return weather_api.get_forecast(lat, lon)
def get_uv_index(lat, lon):
return weather_api.get_uv_index(lat, lon)
def get_air_quality(lat, lon):
return weather_api.get_air_quality(lat, lon)
def reverse_geocode(lat, lon):
return weather_api.reverse_geocode(lat, lon)
def geocode_location(query_text: str) -> Optional[Dict]:
"""Geocoding directo por texto."""
try:
resp = requests.get(
"http://api.openweathermap.org/geo/1.0/direct",

 params={"q": query_text, "limit": 1, "appid": OPENWEATHER_API_KEY},
timeout=10,
)
data = resp.json()
if data:
return {
"lat": data[0]["lat"],
"lon": data[0]["lon"],
"name": data[0]["name"],
"country": data[0].get("country", ""),
}
except Exception:
pass
return None
