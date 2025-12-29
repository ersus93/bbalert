# utils/logger.py

import logging
import os
from logging.handlers import RotatingFileHandler

# --- CORRECCIÓN DE RUTAS ---
# Obtenemos la ruta real de ESTE archivo (logger.py)
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
# Subimos un nivel para llegar a la raíz del proyecto
BASE_DIR = os.path.dirname(CURRENT_DIR)

LOGS_DIR = os.path.join(BASE_DIR, "logs")
LOG_FILE_NAME = "bbalert.log"
LOG_FILE_PATH = os.path.join(LOGS_DIR, LOG_FILE_NAME)

# 1. Asegurar que la carpeta de logs exista
if not os.path.exists(LOGS_DIR):
    os.makedirs(LOGS_DIR, exist_ok=True)
    print(f"📁 Carpeta logs creada en: {LOGS_DIR}")

# 2. Configurar el Logger
_file_logger = logging.getLogger("bbalert_disk_logger")
_file_logger.setLevel(logging.INFO)
_file_logger.propagate = False # Evita que salga doble en consola

if not _file_logger.handlers:
    try:
        # RotatingFileHandler: 5MB por archivo, guarda 5 backups
        handler = RotatingFileHandler(
            LOG_FILE_PATH, 
            maxBytes=5 * 1024 * 1024, 
            backupCount=2, 
            encoding='utf-8'
        )
        
        formatter = logging.Formatter('[%(asctime)s] | %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
        handler.setFormatter(formatter)
        
        _file_logger.addHandler(handler)
        print(f"✅ LOGS ACTIVADOS: Escribiendo en {LOG_FILE_PATH}")
    except Exception as e:
        print(f"❌ ERROR CRÍTICO LOGGER: No se puede escribir en {LOG_FILE_PATH}. Error: {e}")

def save_log_to_disk(mensaje: str):
    """
    Guarda un mensaje en el archivo de log rotativo.
    """
    try:
        clean_msg = mensaje.strip()
        # Logueamos
        _file_logger.info(clean_msg)
    except Exception as e:
        print(f"⚠️ Error escribiendo log en disco: {e}")