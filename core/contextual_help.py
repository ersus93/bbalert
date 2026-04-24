# core/contextual_help.py
"""
Sistema de ayuda contextual para BBAlert.
Proporciona sugerencias relevantes basadas en la última acción del usuario.
"""

from typing import Dict, List, Optional
from telegram import Update
from telegram.ext import ContextTypes

# === SUGERENCIAS POR COMANDO ===

SUGGESTIONS = {
    # After /prices
    "prices": [
        ("🚨 Crear alerta", "/alertas add {symbol} 50000"),
        ("📊 Análisis técnico", "/ta {symbol}"),
        ("⚙️ Ajustes", "/ajustes"),
    ],
    
    # After /alertas
    "alertas": [
        ("📊 Ver precios", "/prices"),
        ("📈 Trading", "/trading ta BTC"),
        ("❓ Ayuda", "/help"),
    ],
    
    # After /trading
    "trading": [
        ("📊 Ver precios", "/prices"),
        ("🚨 Crear alerta", "/alertas add BTC 50000"),
        ("❓ Ayuda", "/help"),
    ],
    
    # After /ajustes
    "ajustes": [
        ("📊 Ver precios", "/prices"),
        ("🚨 Crear alerta", "/alertas"),
        ("❓ Ayuda", "/help"),
    ],
    
    # After /sp (SmartSignals)
    "sp": [
        ("📊 Ver precios", "/prices"),
        ("📈 Análisis técnico", "/ta BTC"),
        ("🛒 Tienda", "/shop"),
    ],
    
    # After /ta (technical analysis)
    "ta": [
        ("📊 Ver precios", "/prices"),
        ("🚨 Alertas", "/alertas"),
        ("❓ Ayuda", "/help"),
    ],
    
    # After /shop
    "shop": [
        ("📊 Ver precios", "/prices"),
        ("📈 Trading", "/trading"),
        ("❓ Ayuda", "/help"),
    ],
    
    # After /help
    "help": [
        ("📊 Ver precios", "/prices"),
        ("🚨 Crear alerta", "/alertas"),
    ],
}

# === ERROR SUGGESTIONS ===

ERROR_SUGGESTIONS = {
    "no_coin": [
        ("📊 Ver lista", "/prices lista"),
        ("➕ Añadir", "/prices add BTC"),
    ],
    "no_alerts": [
        ("➕ Crear alerta", "/alertas add BTC 50000"),
        ("📊 Ver precios", "/prices"),
    ],
    "invalid_price": [
        ("📊 Ver precios", "/prices"),
        ("❓ Ayuda", "/help"),
    ],
    "api_error": [
        ("⏳ Reintentar", "/prices"),
        ("❓ Ayuda", "/help"),
    ],
}


def get_command_suggestions(command: str, symbol: str = None) -> List[tuple]:
    """
    Obtiene sugerencias para un comando específico.
    
    Args:
        command: El comando ejecutado (sin /)
        symbol: Símbolo de la moneda (opcional)
        
    Returns:
        Lista de tuplas (label, comando)
    """
    suggestions = SUGGESTIONS.get(command.lower(), [])
    
    # Reemplazar {symbol} si se proporcionó
    if symbol and suggestions:
        return [
            (label, cmd.replace("{symbol}", symbol.upper()) if "{symbol}" in cmd else cmd)
            for label, cmd in suggestions
        ]
    
    return suggestions


def get_error_suggestions(error_type: str) -> List[tuple]:
    """
    Obtiene sugerencias para un tipo de error.
    
    Args:
        error_type: Tipo de error
        
    Returns:
        Lista de tuplas (label, comando)
    """
    return ERROR_SUGGESTIONS.get(error_type, [])


def format_suggestions(suggestions: List[tuple], title: str = "📌 *Otras opciones:*") -> str:
    """
    Formatea las sugerencias como texto para Telegram.
    
    Args:
        suggestions: Lista de tuplas (label, comando)
        title: Título de la sección
        
    Returns:
        String formateado
    """
    if not suggestions:
        return ""
    
    lines = [title, ""]
    for label, cmd in suggestions:
        lines.append(f"• {label}: `{cmd}`")
    
    return "\n".join(lines)


def add_suggestions_to_message(
    message: str, 
    command: str, 
    symbol: str = None,
    include_tip: bool = True
) -> str:
    """
    Añade sugerencias contextuales a un mensaje.
    
    Args:
        message: Mensaje original
        command: Comando que se ejecutó
        symbol: Símbolo de la moneda (opcional)
        include_tip: Si True, añade un tip aleatorio
        
    Returns:
        Mensaje con sugerencias añadidas
    """
    suggestions = get_command_suggestions(command, symbol)
    
    if not suggestions:
        return message
    
    # Añadir separador
    message += "\n\n" + format_suggestions(suggestions)
    
    # Añadir tip aleatorio si se solicita
    if include_tip:
        tips = [
            "💡 *Tip:* Usa /help para ver todos los comandos.",
            "💡 *Tip:* Con /prices add BTC,ETH monitorizas varias monedas.",
            "💡 *Tip:* Las alertas te notifican cuando el precio llega a tu objetivo.",
        ]
        import random
        tip = random.choice(tips)
        message += f"\n\n{tip}"
    
    return message


# === ONBOARDING WIZARD ===

ONBOARDING_STEPS = {
    "step1": {
        "message": (
            "👋 *¡Bienvenido a BBAlert!*\n\n"
            "Soy tu asistente para crypto y trading.\n\n"
            "¿Qué te interesa?"
        ),
        "buttons": [
            ("📊 Precios", "onboarding_prices"),
            ("🚨 Alertas", "onboarding_alerts"),
            ("📈 Trading", "onboarding_trading"),
            ("🌤️ Clima", "onboarding_weather"),
        ]
    },
    "step2_prices": {
        "message": (
            "📊 *Precios de Criptomonedas*\n\n"
            "Puedes:\n"
            "• Ver precios de tu lista personal\n"
            "• Consultar una moneda específica\n"
            "• Crear alertas de precio\n\n"
            "¿Qué quieres hacer?"
        ),
        "buttons": [
            ("👀 Ver precios", "onboarding_see_prices"),
            ("➕ Añadir a mi lista", "onboarding_add_coin"),
        ]
    },
    "step2_alerts": {
        "message": (
            "🚨 *Alertas de Precio*\n\n"
            "Te notifico cuando una cryptomoneda\n"
            "alcanza el precio que tú elijas.\n\n"
            "¿Qué moneda te interesa?"
        ),
        "buttons": [
            ("₿ Bitcoin", "onboarding_alert_btc"),
            ("Ξ Ethereum", "onboarding_alert_eth"),
            ("Otra...", "onboarding_alert_other"),
        ]
    },
    "step2_trading": {
        "message": (
            "📈 *Análisis de Trading*\n\n"
            "Puedes ver:\n"
            "• Análisis técnico (RSI, MACD)\n"
            "• Gráficos interactivos\n"
            "• Señales de SmartSignals\n\n"
            "¿Qué prefieres?"
        ),
        "buttons": [
            ("📊 Análisis técnico", "onboarding_ta"),
            ("📈 Gráfico", "onboarding_graf"),
        ]
    },
}


def get_onboarding_step(step: str) -> Optional[Dict]:
    """Obtiene la configuración de un paso del onboarding."""
    return ONBOARDING_STEPS.get(step)


def format_onboarding_message(step: str, user_name: str = None) -> tuple:
    """
    Formatea el mensaje y botones para un paso del onboarding.
    
    Returns:
        (message, keyboard_buttons)
    """
    step_config = get_onboarding_step(step)
    if not step_config:
        return None, None
    
    message = step_config["message"]
    if user_name:
        message = message.replace("{name}", user_name)
    
    return message, step_config["buttons"]
