# utils/logger.py

import logging
import os
from logging.handlers import RotatingFileHandler
from core.config import BASE_DIR

# Configuración
LOGS_DIR = os.path.join(BASE_DIR, "logs")
LOG_FILE_NAME = "bbalert.log"
LOG_FILE_PATH = os.path.join(LOGS_DIR, LOG_FILE_NAME)

# 1. Asegurar que la carpeta de logs exista
if not os.path.exists(LOGS_DIR):
    os.makedirs(LOGS_DIR, exist_ok=True)

# 2. Configurar el Logger
# Usamos un nombre específico para no chocar con otros loggers de librerías (telegram, requests, etc)
_file_logger = logging.getLogger("bbalert_disk_logger")
_file_logger.setLevel(logging.INFO)

# Evitamos duplicar handlers si el módulo se recarga
if not _file_logger.handlers:
    # RotatingFileHandler:
    # maxBytes=5*1024*1024 -> 5 MB por archivo
    # backupCount=5 -> Mantiene los últimos 5 archivos (bbalert.log.1, .2, etc)
    handler = RotatingFileHandler(
        LOG_FILE_PATH, 
        maxBytes=5 * 1024 * 1024, 
        backupCount=5, 
        encoding='utf-8'
    )
    
    # Formato: [FECHA HORA] | MENSAJE
    formatter = logging.Formatter('[%(asctime)s] | %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    handler.setFormatter(formatter)
    
    _file_logger.addHandler(handler)

def save_log_to_disk(mensaje: str):
    """
    Guarda un mensaje en el archivo de log rotativo.
    No es necesario pasarle la fecha, el logger la pone automáticamente.
    """
    try:
        # Eliminamos posibles caracteres de nueva línea al final para mantener el formato
        clean_msg = mensaje.strip()
        _file_logger.info(clean_msg)
    except Exception as e:
        # Si falla el log en disco, lo imprimimos en consola como último recurso
        print(f"⚠️ Error escribiendo log en disco: {e}")