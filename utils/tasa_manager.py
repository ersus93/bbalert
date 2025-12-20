# Utils/tasa_manager.py

import os
import requests
import json
from utils.logger import save_log_to_disk
from utils.file_manager import add_log_line
from core.config import ELTOQUE_HISTORY_PATH, ELTOQUE_API_KEY, DATA_DIR

# Definimos la ruta para el historial de BCC
BCC_HISTORY_PATH = os.path.join(DATA_DIR, "bcc_history.json")
CADECA_HISTORY_PATH = os.path.join(DATA_DIR, "cadeca_history.json")

def load_eltoque_history():
    if not os.path.exists(ELTOQUE_HISTORY_PATH):
        return {}
    try:
        with open(ELTOQUE_HISTORY_PATH, "r", encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return {}

def save_eltoque_history(tasas_dict: dict):
    try:
        with open(ELTOQUE_HISTORY_PATH, "w", encoding='utf-8') as f:
            json.dump(tasas_dict, f, indent=4)
    except Exception as e:
        add_log_line(f"❌ Error al guardar el historial de ElToque: {e}")

# --- FUNCIONES BCC (NUEVAS) ---
def load_bcc_history():
    """Carga el historial de tasas del BCC."""
    if not os.path.exists(BCC_HISTORY_PATH):
        return {}
    try:
        with open(BCC_HISTORY_PATH, "r", encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return {}

def save_bcc_history(tasas_dict: dict):
    """Guarda las tasas actuales del BCC para comparar en el futuro."""
    try:
        with open(BCC_HISTORY_PATH, "w", encoding='utf-8') as f:
            json.dump(tasas_dict, f, indent=4)
    except Exception as e:
        add_log_line(f"❌ Error al guardar historial BCC: {e}")

# --- FUNCIONES CADECA (NUEVAS) ---
def load_cadeca_history():
    """Carga el historial de tasas de CADECA."""
    if not os.path.exists(CADECA_HISTORY_PATH):
        return {}
    try:
        with open(CADECA_HISTORY_PATH, "r", encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return {}

def save_cadeca_history(tasas_dict: dict):
    """Guarda las tasas actuales de CADECA."""
    try:
        with open(CADECA_HISTORY_PATH, "w", encoding='utf-8') as f:
            json.dump(tasas_dict, f, indent=4)
    except Exception as e:
        add_log_line(f"❌ Error al guardar historial CADECA: {e}")

# Funciones para obtener datos de CoinMarketCap y ElToque
def obtener_tasas_eltoque():
    """
    Obtiene las tasas de cambio más recientes de la API de eltoque.com.
    """

    URL_API_ELTOQUE = "https://tasas.eltoque.com/v1/trmi" 
    
    if not ELTOQUE_API_KEY:
        print("❌ Error: La variable ELTOQUE_API_KEY no está configurada en config.py.")
        return None


    headers = {
        "Authorization": f"Bearer {ELTOQUE_API_KEY}",
        "Accept": "application/json"
    }

    try:
        response = requests.get(URL_API_ELTOQUE, headers=headers, timeout=10)
        response.raise_for_status() 
        
        data = response.json()
        
        # --- AGREGAR ESTO TEMPORALMENTE PARA VERIFICAR ---
        print("🔍 RESPUESTA JSON DE ELTOQUE:", json.dumps(data, indent=2))
        # -------------------------------------------------

        return data
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Error al contactar la API de ElToque: {e}")
        return None
    except (KeyError, json.JSONDecodeError):
        print("❌ Error al procesar la respuesta JSON de ElToque.")
        return None
    