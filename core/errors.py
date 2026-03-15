# core/errors.py
"""
Módulo de manejo de errores categorizados para BBAlert.
Proporciona categorización, logging estructurado y feedback friendly al usuario.
"""

import asyncio
import functools
import time
from enum import Enum
from typing import Callable, Any, Optional, TypeVar, Coroutine, T
from telegram import Update
from telegram.ext import ContextTypes
from utils.logger import logger
from telegram.error import (
    NetworkError, 
    TimedOut, 
    RetryAfter, 
    BadRequest, 
    TelegramError,
    ChatMigrated,
    Forbidden,
    InvalidToken
)

# ============================================================
# ENUMS Y CONSTANTES
# ============================================================

class ErrorCategory(Enum):
    """Categorías de errores para mejor debugging y respuesta."""
    API_TIMEOUT = "API_TIMEOUT"        
    API_FAILURE = "API_FAILURE"        
    NETWORK = "NETWORK"                
    USER_INPUT = "USER_INPUT"          
    TELEGRAM_API = "TELEGRAM_API"      
    PERMISSION = "PERMISSION"          
    INTERNAL = "INTERNAL"              
    UNKNOWN = "UNKNOWN"                


ERROR_MESSAGES = {
    ErrorCategory.API_TIMEOUT: (
        "⏳ *Tiempo de espera agotado*\n\n"
        "El servicio está tardando más de lo normal. "
        "Por favor, intenta de nuevo en un momento.",
        "⏳ *Timeout*\n\nThe service is taking longer than usual. "
        "Please try again in a moment."
    ),
    ErrorCategory.API_FAILURE: (
        "😕 *Servicio no disponible*\n\n"
        "No pude conectar con el servicio externo. "
        "Intenta de nuevo más tarde.",
        "😕 *Service unavailable*\n\nI couldn't connect to the external service. "
        "Please try again later."
    ),
    ErrorCategory.NETWORK: (
        "🌐 *Problema de conexión*\n\n"
        "Hay problemas de conexión. Verifica tu internet e intenta de nuevo.",
        "🌐 *Connection issue*\n\nThere are connection issues. "
        "Check your internet and try again."
    ),
    ErrorCategory.USER_INPUT: (
        "⚠️ *Datos incorrectos*\n\n"
        "Los datos proporcionados no son válidos. "
        "Usa /help para ver cómo usar este comando.",
        "⚠️ *Invalid data*\n\nThe provided data is not valid. "
        "Use /help to see how to use this command."
    ),
    ErrorCategory.TELEGRAM_API: (
        "🤖 *Error de Telegram*\n\n"
        "Hubo un problema con Telegram. El mensaje no pudo ser enviado.",
        "🤖 *Telegram error*\n\nThere was a problem with Telegram. "
        "The message could not be sent."
    ),
    ErrorCategory.PERMISSION: (
        "🔒 *Sin permisos*\n\n"
        "No tienes permiso para realizar esta acción. "
        "Contacta al administrador si crees que es un error.",
        "🔒 *No permissions*\n\nYou don't have permission to perform this action. "
        "Contact the administrator if you think this is an error."
    ),
    ErrorCategory.INTERNAL: (
        "🐛 *Error interno*\n\n"
        "Ocurrió un error inesperado. Los desarrolladores han sido notificados. "
        "Intenta de nuevo más tarde.",
        "🐛 *Internal error*\n\nAn unexpected error occurred. "
        "Developers have been notified. Please try again later."
    ),
    ErrorCategory.UNKNOWN: (
        "❓ *Algo salió mal*\n\n"
        "No pude procesar tu solicitud. Intenta de nuevo.",
        "❓ *Something went wrong*\n\nI couldn't process your request. Try again."
    )
}

def categorize_error(error: Exception) -> ErrorCategory:
    """Categoriza un error según su tipo."""
    if isinstance(error, (NetworkError, TimedOut)):
        return ErrorCategory.NETWORK
    
    if isinstance(error, RetryAfter):
        return ErrorCategory.API_TIMEOUT
    
    if isinstance(error, TelegramError):
        error_str = str(error).lower()
        if "chat not found" in error_str or "user not found" in error_str:
            return ErrorCategory.TELEGRAM_API
        if "bot was blocked" in error_str or "user is blocked" in error_str:
            return ErrorCategory.TELEGRAM_API
        if "not enough rights" in error_str or "forbidden" in error_str:
            return ErrorCategory.PERMISSION
        if "invalid token" in error_str:
            return ErrorCategory.INTERNAL
        return ErrorCategory.TELEGRAM_API
    
    if isinstance(error, BadRequest):
        return ErrorCategory.USER_INPUT
    
    if isinstance(error, asyncio.TimeoutError):
        return ErrorCategory.API_TIMEOUT
    
    if isinstance(error, (ValueError, KeyError, TypeError)):
        return ErrorCategory.USER_INPUT
    
    if "timeout" in str(error).lower() or "timed out" in str(error).lower():
        return ErrorCategory.API_TIMEOUT
    
    if "connection" in str(error).lower() or "network" in str(error).lower():
        return ErrorCategory.NETWORK
    
    if "http" in str(error).lower() or "api" in str(error).lower():
        return ErrorCategory.API_FAILURE
    
    return ErrorCategory.UNKNOWN


def get_user_message(category: ErrorCategory, lang: str = "es") -> str:
    """Obtiene el mensaje user-friendly según la categoría e idioma."""
    messages = ERROR_MESSAGES.get(category, ERROR_MESSAGES[ErrorCategory.UNKNOWN])
    return messages[0] if lang == "es" else messages[1]


async def send_error_message(
    update: Optional[Update],
    category: ErrorCategory,
    lang: str = "es"
) -> None:
    """Envía un mensaje de error friendly al usuario."""
    if not update or not update.effective_chat:
        return
    
    message = get_user_message(category, lang)
    
    try:
        await update.effective_chat.send_message(
            text=message,
            parse_mode="Markdown"
        )
    except Exception:
        try:
            await update.effective_chat.send_message(text=message)
        except Exception:
            pass


def log_error_with_context(
    category: ErrorCategory,
    error: Exception,
    update: Optional[object] = None,
    context: Optional[str] = None
) -> None:
    """Loguea el error con contexto estructurado."""
    error_id = f"{int(time.time())}"
    
    log_msg = [
        f"[{category.value}]",
        f"Error ID: {error_id}",
        f"Error: {type(error).__name__}: {error}"
    ]
    
    if context:
        log_msg.append(f"Context: {context}")
    
    if update:
        try:
            if hasattr(update, 'effective_user') and update.effective_user:
                user_info = f"user_id={update.effective_user.id}"
                if update.effective_user.username:
                    user_info += f" @{update.effective_user.username}"
                log_msg.append(f"User: {user_info}")
            
            if hasattr(update, 'effective_chat') and update.effective_chat:
                log_msg.append(f"Chat: {update.effective_chat.id}")
                
            if hasattr(update, 'message') and update.message:
                msg = update.message
                log_msg.append(f"Message: {msg.text[:100] if msg.text else 'N/A'}")
        except Exception:
            pass
    
    logger.error(" | ".join(log_msg), exc_info=True)


async def retry_async(
    func: Callable[..., Coroutine[Any, Any, T]],
    max_retries: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    *args,
    **kwargs
) -> T:
    """Ejecuta una función async con retry automático."""
    delay = initial_delay
    last_error = None
    
    for attempt in range(max_retries):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            last_error = e
            
            if isinstance(e, (BadRequest, InvalidToken, UserIsBot)):
                raise
            
            if attempt < max_retries - 1:
                logger.warning(
                    f"Retry {attempt + 1}/{max_retries} for {func.__name__}: {e}. "
                    f"Waiting {delay}s..."
                )
                await asyncio.sleep(delay)
                delay *= backoff_factor
            else:
                logger.error(f"All retries exhausted for {func.__name__}: {e}")
    
    raise last_error


def with_retry(max_retries: int = 3, initial_delay: float = 1.0):
    """Decorador para añadir retry automático a funciones async."""
    def decorator(func: Callable[..., Coroutine[Any, Any, T]]) -> Callable[..., Coroutine[Any, Any, T]]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            return await retry_async(
                func, 
                max_retries=max_retries,
                initial_delay=initial_delay,
                *args,
                **kwargs
            )
        return wrapper
    return decorator
