# core/rate_limiter.py
"""
Sistema global de rate limiting para BBAlert.
Protege contra abuso y flooding de comandos.
"""

import time
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from utils.logger import logger
from core.config import ADMIN_CHAT_IDS

# === CONFIGURACIÓN ===

# Límites por tier (comandos por minuto)
RATE_LIMITS = {
    "premium": 100,    # Usuarios premium
    "free": 10,        # Usuarios gratuitos
    "admin": 1000,     # Admins
}

# Ventana de tiempo para rate limiting (segundos)
RATE_WINDOW = 60

# Comandos que no cuentan para rate limit
EXCLUDED_COMMANDS = [
    "start",     # Siempre permitido
    "myid",     # Solo muestra ID
    "help",     # Ayuda
]

# === ALMACENAMIENTO ===

class RateLimitStore:
    """Almacén en memoria para tracking de rate limits."""
    
    def __init__(self):
        # {user_id: [(timestamp, command), ...]}
        self._user_commands: Dict[int, list] = defaultdict(list)
        # Cache de tier por usuario
        self._user_tier: Dict[int, str] = {}
    
    def get_user_commands(self, user_id: int) -> list:
        """Obtiene comandos del usuario en la ventana actual."""
        cutoff = time.time() - RATE_WINDOW
        commands = self._user_commands[user_id]
        # Filtrar solo comandos recientes
        recent = [(ts, cmd) for ts, cmd in commands if ts > cutoff]
        self._user_commands[user_id] = recent
        return recent
    
    def add_command(self, user_id: int, command: str) -> None:
        """Registra un comando del usuario."""
        self._user_commands[user_id].append((time.time(), command))
    
    def get_tier(self, user_id: int, is_admin: bool = False) -> str:
        """Obtiene el tier del usuario."""
        if is_admin:
            return "admin"
        
        if user_id in self._user_tier:
            return self._user_tier[user_id]
        
        return "free"
    
    def set_tier(self, user_id: int, tier: str) -> None:
        """Establece el tier del usuario."""
        self._user_tier[user_id] = tier
    
    def clear_old_entries(self) -> None:
        """Limpia entradas antiguas para evitar memory leak."""
        cutoff = time.time() - (RATE_WINDOW * 2)
        for user_id in list(self._user_commands.keys()):
            self._user_commands[user_id] = [
                (ts, cmd) for ts, cmd in self._user_commands[user_id]
                if ts > cutoff
            ]
            # Limpiar usuarios sin comandos recientes
            if not self._user_commands[user_id]:
                del self._user_commands[user_id]
                if user_id in self._user_tier:
                    del self._user_tier[user_id]


# Instancia global
_rate_store = RateLimitStore()


# === FUNCIONES PRINCIPALES ===

def get_rate_limit(user_id: int, is_admin: bool = False) -> int:
    """
    Obtiene el límite de rate para un usuario.
    
    Args:
        user_id: ID del usuario
        is_admin: Si el usuario es admin
        
    Returns:
        Número máximo de comandos por minuto
    """
    tier = _rate_store.get_tier(user_id, is_admin)
    return RATE_LIMITS.get(tier, RATE_LIMITS["free"])


def check_rate_limit(user_id: int, command: str, is_admin: bool = False) -> Tuple[bool, str]:
    """
    Verifica si el usuario puede ejecutar un comando.
    
    Args:
        user_id: ID del usuario
        command: Nombre del comando (sin /)
        is_admin: Si el usuario es admin
        
    Returns:
        (allowed, message) - Tupla con resultado y mensaje
    """
    # Comandos excluidos siempre permitidos
    if command.lower() in EXCLUDED_COMMANDS:
        return True, "OK"
    
    # Admins siempre permitidos
    if is_admin:
        return True, "OK"
    
    # Obtener comandos recientes del usuario
    recent_commands = _rate_store.get_user_commands(user_id)
    command_count = len(recent_commands)
    
    # Obtener límite
    limit = get_rate_limit(user_id, is_admin)
    
    if command_count >= limit:
        # Calcular tiempo restante
        if recent_commands:
            oldest = recent_commands[0][0]
            wait_time = RATE_WINDOW - (time.time() - oldest)
            if wait_time < 0:
                wait_time = 0
            
            minutes = int(wait_time // 60) + 1
            
            return False, (
                f"⏳ *Límite alcanzado*\n\n"
                f"Has usado {command_count} comandos en el último minuto.\n"
                f"Espera {minutes} minuto(s) antes de continuar."
            )
        
        return False, "⏳ Has alcanzado el límite de comandos. Espera un momento."
    
    # Registrar comando
    _rate_store.add_command(user_id, command)
    
    return True, "OK"


def set_user_tier(user_id: int, tier: str) -> None:
    """
    Establece el tier de un usuario.
    
    Args:
        user_id: ID del usuario
        tier: Tier ('free' o 'premium')
    """
    if tier not in ["free", "premium"]:
        logger.warning(f"Invalid tier: {tier}")
        return
    
    _rate_store.set_tier(user_id, tier)
    logger.info(f"User {user_id} tier set to {tier}")


def reset_user_rate_limit(user_id: int) -> None:
    """
    Resetea el rate limit de un usuario.
    
    Args:
        user_id: ID del usuario
    """
    if user_id in _rate_store._user_commands:
        del _rate_store._user_commands[user_id]
    logger.info(f"Rate limit reset for user {user_id}")


def get_user_stats(user_id: int) -> Dict:
    """
    Obtiene estadísticas de uso del usuario.
    
    Args:
        user_id: ID del usuario
        
    Returns:
        Dict con estadísticas
    """
    recent_commands = _rate_store.get_user_commands(user_id)
    tier = _rate_store.get_tier(user_id)
    limit = get_rate_limit(user_id)
    
    return {
        "commands_last_minute": len(recent_commands),
        "limit": limit,
        "tier": tier,
        "usage_percent": (len(recent_commands) / limit * 100) if limit > 0 else 0
    }


def cleanup_rate_limits() -> None:
    """Limpia entradas antiguas (para llamar periódicamente)."""
    _rate_store.clear_old_entries()
    logger.debug("Rate limit store cleaned up")


# === DECORADOR ===

def rate_limit_command(command_name: str = None):
    """
    Decorador para aplicar rate limiting a un comando.
    
    Usage:
        @rate_limit_command("my_command")
        async def my_command(update, context):
            ...
    """
    def decorator(func):
        async def wrapper(update, context):
            if not update or not update.effective_user:
                return await func(update, context)
            
            user_id = update.effective_user.id
            is_admin = user_id in ADMIN_CHAT_IDS
            
            # Determinar nombre del comando
            cmd = command_name or func.__name__
            
            # Verificar rate limit
            allowed, message = check_rate_limit(user_id, cmd, is_admin)
            
            if not allowed:
                await update.message.reply_text(
                    message,
                    parse_mode="Markdown"
                )
                return
            
            return await func(update, context)
        
        return wrapper
    return decorator
