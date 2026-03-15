# core/config.py

import os
import platform
from dotenv import load_dotenv

# --- Cargar Variables de Entorno ---
# Lee el archivo apit.env y lo carga en el entorno del sistema
load_dotenv('apit.env')

# --- Credenciales y IDs ---
TOKEN_TELEGRAM = os.environ.get("TOKEN_TELEGRAM")
ADMIN_CHAT_IDS_STR = os.environ.get("ADMIN_CHAT_IDS")
# Convertir a lista de integers para comparaciones correctas
ADMIN_CHAT_IDS = [int(id.strip()) for id in ADMIN_CHAT_IDS_STR.split(',')] if ADMIN_CHAT_IDS_STR else []
# --- Claves de API ---
CMC_API_KEY_ALERTA = os.environ.get("CMC_API_KEY_ALERTA")
CMC_API_KEY_CONTROL = os.environ.get("CMC_API_KEY_CONTROL")
SCREENSHOT_API_KEY = os.environ.get("SCREENSHOT_API_KEY")
ELTOQUE_API_KEY = os.environ.get("ELTOQUE_API_KEY")
OPENWEATHER_API_KEY = os.environ.get("OPENWEATHER_API_KEY")
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
# Construye las rutas a los archivos dentro de la carpeta /data
DATA_DIR = os.path.join(BASE_DIR, "data")
USUARIOS_PATH = os.path.join(DATA_DIR, "users.json")
PRICE_ALERTS_PATH = os.path.join(DATA_DIR, "price_alerts.json")
HBD_HISTORY_PATH = os.path.join(DATA_DIR, "hbd_price_history.json")
CUSTOM_ALERT_HISTORY_PATH = os.path.join(DATA_DIR, "custom_alert_history.json")
ELTOQUE_HISTORY_PATH = os.path.join(DATA_DIR, "eltoque_history.json")
LAST_PRICES_PATH = os.path.join(DATA_DIR, "last_prices.json")
TEMPLATE_PATH = os.path.join(DATA_DIR, "img.jpg")
ADS_PATH = os.path.join(DATA_DIR, "ads.json")
HBD_THRESHOLDS_PATH = os.path.join(DATA_DIR, "hbd_thresholds.json")
WEATHER_SUBS_PATH = os.path.join(DATA_DIR, "weather_subs.json")
WEATHER_LAST_ALERTS_PATH = os.path.join(DATA_DIR, "weather_last_alerts.json")
YEAR_QUOTES_PATH = os.path.join(DATA_DIR, "year_quotes.json")
YEAR_SUBS_PATH = os.path.join(DATA_DIR, "year_subs.json")
EVENTS_LOG_PATH = os.path.join(DATA_DIR, "events_log.json")
# --- Configuración de la Aplicación ---
PID = os.getpid()
STATE = "RUNNING"
PYTHON_VERSION = platform.python_version()
# --- Configuración de Logs y Loops ---
LOG_MAX = 45
LOG_LINES = []
INTERVALO_ALERTA = 300
INTERVALO_CONTROL = 480

try:
    with open(os.path.join(BASE_DIR, "version.txt"), "r") as f:
        VERSION = f.read().strip()
except Exception as e:
    print(f"⚠️ No se pudo leer version.txt: {e}")
    VERSION = "0.0.0"
    
# --- Configuración de Timeouts (segundos) ---
# Timeouts globales para llamadas a APIs externas
TIMEOUTS = {
    "default": 10,           # Timeout por defecto
    "price_api": 5,          # APIs de precios (CoinMarketCap, etc)
    "chart_generation": 30, # Generación de gráficos
    "weather": 8,            # OpenWeatherMap API
    "tradingview": 15,      # TradingView
    "telegram": 10,          # Llamadas a Telegram API
    "scraper": 15,          # Web scraping
}

# --- Configuración de Reintentos ---
# Configuración para retry logic automático
RETRY_CONFIG = {
    "max_retries": 3,           # Máximo de reintentos
    "initial_delay": 1.0,        # Delay inicial en segundos
    "backoff_factor": 2.0,      # Factor de backoff exponencial
    "retry_on_timeout": True,   # Reintentar en timeouts
    "retry_on_connection": True, # Reintentar en errores de conexión
}
    
