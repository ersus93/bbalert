# utils/logger.py

import sys
import os
import logging
import traceback
from pathlib import Path
from typing import Optional, Union

# --- 1. CONFIGURACIÓN DE RUTAS (Original de logger.py) ---
# Mantenemos esto idéntico para no romper la estructura de carpetas
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(CURRENT_DIR)
LOGS_DIR = os.path.join(BASE_DIR, "logs")
LOG_FILE_NAME = "bbalert.log"  # Mantenemos tu nombre de archivo original
LOG_FILE_PATH = os.path.join(LOGS_DIR, LOG_FILE_NAME)
ERROR_LOG_PATH = os.path.join(LOGS_DIR, "bbalert_errors.log")

# Asegurar que la carpeta logs exista (Lógica original mejorada)
if not os.path.exists(LOGS_DIR):
    os.makedirs(LOGS_DIR, exist_ok=True)
    print(f"📁 Carpeta logs creada en: {LOGS_DIR}")

# --- 2. MOTOR DE LOGGING (Loguru con Fallback) ---
try:
    from loguru import logger as _loguru_logger
    HAS_LOGURU = True
except ImportError:
    HAS_LOGURU = False
    # Fallback a logging estándar si loguru no está instalado
    # Esto asegura que el bot no crashee si faltan dependencias
    _std_logger = logging.getLogger("bbalert_fallback")
    _std_logger.setLevel(logging.INFO)
    if not _std_logger.handlers:
        _handler = logging.StreamHandler(sys.stdout)
        _handler.setFormatter(logging.Formatter("[%(asctime)s] | %(levelname)s | %(message)s"))
        _std_logger.addHandler(_handler)

    # Proxy simple para imitar loguru si no está presente
    class _StdLoggerProxy:
        def debug(self, msg, *args, **kwargs): _std_logger.debug(msg)
        def info(self, msg, *args, **kwargs): _std_logger.info(msg)
        def warning(self, msg, *args, **kwargs): _std_logger.warning(msg)
        def error(self, msg, *args, **kwargs): _std_logger.error(msg)
        def critical(self, msg, *args, **kwargs): _std_logger.critical(msg)
        def remove(self): pass
        def add(self, *args, **kwargs): pass

    _loguru_logger = _StdLoggerProxy()
    print("⚠️ ADVERTENCIA: 'loguru' no está instalado. Usando logging estándar básico.")


class Logger:
    """
    Sistema de logging unificado. Integra la gestión de rutas de tu logger original
    con la potencia de estructuración del nuevo sistema.
    """

    def __init__(self):
        self.monitoring_handler = None
        self.log_file_path = LOG_FILE_PATH
        
        # Configuración inicial
        self._setup_logger()

    def _setup_logger(self):
        """Configura los handlers (Consola y Archivo)."""
        if not HAS_LOGURU:
            return # Ya está configurado el fallback arriba

        _loguru_logger.remove() # Limpiar handlers por defecto

        # 1. Handler de Consola (Colorizado y limpio)
        _loguru_logger.add(
            sys.stdout,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{function}</cyan> - <level>{message}</level>",
            level="INFO",
            colorize=True
        )

        # 2. Handler de Archivo Principal (Rotativo como en tu original)
        # Rotación a 5MB y retención de 5 archivos (similar a tu backupCount=5)
        _loguru_logger.add(
            self.log_file_path,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
            level="INFO",
            rotation="5 MB",
            retention="10 days",
            compression="zip", # Comprime logs viejos para ahorrar espacio
            encoding="utf-8"
        )

        # 3. Handler de Errores (Separado para facilitar depuración)
        _loguru_logger.add(
            ERROR_LOG_PATH,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
            level="ERROR",
            rotation="5 MB",
            retention="30 days",
            encoding="utf-8"
        )

    def _format_clean_traceback(self, error: Exception) -> str:
        """Limpia el traceback para mostrar solo lo relevante de TU código."""
        tb_lines = traceback.format_exception(type(error), error, error.__traceback__)
        # Aquí podrías filtrar líneas de librerías externas si quisieras
        tb_str = "".join(tb_lines).strip()
        if len(tb_str) > 2000:
            tb_str = tb_str[:2000] + "\n... (traceback truncado)"
        return tb_str

    def set_monitoring_handler(self, monitoring_handler):
        """Para integrar con sistemas de monitoreo en tiempo real si los tienes."""
        self.monitoring_handler = monitoring_handler

    # --- MÉTODOS GENÉRICOS ---

    def info(self, message: str, *args, **kwargs):
        _loguru_logger.info(message, *args, **kwargs)

    def warning(self, message: str, *args, **kwargs):
        _loguru_logger.warning(message, *args, **kwargs)

    def error(self, message: Union[str, Exception], error: Optional[Exception] = None, *args, **kwargs):
        """Log de error inteligente. Acepta (mensaje) o (mensaje, excepcion) o (excepcion)."""
        if isinstance(message, Exception) and error is None:
            error = message
            message = str(message)

        if error:
            tb_str = self._format_clean_traceback(error)
            message = f"{message}\n  ╚══ 💥 Detalles:\n{tb_str}"

        _loguru_logger.error(message, *args, **kwargs)

    # --- MÉTODOS ESPECÍFICOS DEL BOT (Integrados del código nuevo) ---

    def log_bot_event(self, level: str, message: str, user_id: Optional[int] = None, **kwargs):
        """Registra un evento específico del bot."""
        log_method = getattr(_loguru_logger, level.lower(), _loguru_logger.info)
        extra_info = f"[User:{user_id}]" if user_id else ""
        full_msg = f"{extra_info} {message}".strip()
        
        log_method(full_msg, **kwargs)
        
        if self.monitoring_handler:
            self.monitoring_handler.add_log(level.upper(), full_msg, user_id)

    def log_user_action(self, action: str, user_id: int, details: Optional[str] = None):
        """Ej: logger.log_user_action('start_bot', 123456)"""
        msg = f"User Action: {action}"
        if details: msg += f" - {details}"
        self.log_bot_event("INFO", msg, user_id)

    def log_payment_event(self, event_type: str, amount: int, user_id: int, success: bool):
        """Ej: logger.log_payment_event('stars_deposit', 500, 12345, True)"""
        status = "✅" if success else "❌"
        level = "INFO" if success else "ERROR"
        msg = f"Payment {event_type} {status} - {amount} stars"
        self.log_bot_event(level, msg, user_id)

    # --- UTILIDADES DE LECTURA ---
    def get_last_logs(self, lines: int = 15) -> str:
        """Devuelve las últimas líneas del archivo de log."""
        if not os.path.exists(self.log_file_path):
            return "📂 El archivo de log aún no existe."
        try:
            with open(self.log_file_path, "r", encoding="utf-8", errors='ignore') as f:
                all_lines = f.readlines()
                return "".join(all_lines[-lines:])
        except Exception as e:
            return f"❌ Error leyendo logs: {str(e)}"


# --- INSTANCIA GLOBAL ---
logger = Logger()

# --- COMPATIBILIDAD RETROACTIVA (CRUCIAL PARA TU PROYECTO ACTUAL) ---
def save_log_to_disk(mensaje: str):
    """
    Función wrapper para mantener compatibilidad con archivos antiguos 
    que importan 'save_log_to_disk' directamente.
    """
    # Redirigimos la llamada a la nueva instancia de logger
    logger.info(mensaje)