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
ADMIN_CHAT_IDS = [id.strip() for id in ADMIN_CHAT_IDS_STR.split(',')] if ADMIN_CHAT_IDS_STR else []
# --- Claves de API ---
CMC_API_KEY_ALERTA = os.environ.get("CMC_API_KEY_ALERTA")
CMC_API_KEY_CONTROL = os.environ.get("CMC_API_KEY_CONTROL")
SCREENSHOT_API_KEY = os.environ.get("SCREENSHOT_API_KEY")
ELTOQUE_API_KEY = os.environ.get("ELTOQUE_API_KEY")
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Construye las rutas a los archivos dentro de la carpeta /data
DATA_DIR = os.path.join(BASE_DIR, "data")
USUARIOS_PATH = os.path.join(DATA_DIR, "users.json")
PRICE_ALERTS_PATH = os.path.join(DATA_DIR, "price_alerts.json")
HBD_HISTORY_PATH = os.path.join(DATA_DIR, "hbd_price_history.json")
CUSTOM_ALERT_HISTORY_PATH = os.path.join(DATA_DIR, "custom_alert_history.json")
ELTOQUE_HISTORY_PATH = os.path.join(DATA_DIR, "eltoque_history.json")
LAST_PRICES_PATH = os.path.join(DATA_DIR, "last_prices.json")
TEMPLATE_PATH = os.path.join(DATA_DIR, "img.png")
# --- Configuración de la Aplicación ---
PID = os.getpid()
VERSION = "0.1.010-beta"
STATE = "RUNNING"
PYTHON_VERSION = platform.python_version()
# --- Configuración de Logs y Loops ---
LOG_MAX = 45
LOG_LINES = []
INTERVALO_ALERTA = 300
INTERVALO_CONTROL = 600
