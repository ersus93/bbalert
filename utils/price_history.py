# utils/price_history.py
"""
Gestión de historial de precios para indicadores de movimiento.
Almacena precios anteriores en Redis para comparación.
"""

import json
from datetime import datetime
from core.redis_fallback import get_user, save_user


def get_previous_prices(chat_id: int) -> dict:
    """
    Obtiene los precios anteriores guardados del usuario.
    Retorna un diccionario con formato {moneda: precio}
    """
    usuario = get_user(chat_id)
    if usuario and "price_history" in usuario:
        return usuario["price_history"]
    return {}


def save_current_prices(chat_id: int, prices: dict) -> None:
    """
    Guarda los precios actuales como historial para la próxima comparación.
    """
    usuario = get_user(chat_id)
    if usuario is None:
        usuario = {}
    
    usuario["price_history"] = prices
    usuario["last_price_update"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    save_user(chat_id, usuario)


def calculate_price_change(current_prices: dict, previous_prices: dict) -> dict:
    """
    Calcula el cambio porcentual entre precios actuales y anteriores.
    Retorna dict con formato {moneda: {'current': precio, 'change': porcentaje}}
    """
    result = {}
    
    for moneda, current_price in current_prices.items():
        if moneda in previous_prices and previous_prices[moneda] > 0:
            previous_price = previous_prices[moneda]
            change_percent = ((current_price - previous_price) / previous_price) * 100
            result[moneda] = {
                'current': current_price,
                'previous': previous_price,
                'change': change_percent
            }
        else:
            # Primera vez o sin datos anteriores
            result[moneda] = {
                'current': current_price,
                'previous': None,
                'change': None
            }
    
    return result


def get_change_emoji(change_percent: float | None) -> str:
    """
    Retorna el emoji correspondiente al cambio de precio.
    """
    if change_percent is None:
        return "➖"  # Sin datos
    elif change_percent > 0:
        return "📈"  # Subida
    elif change_percent < 0:
        return "📉"  # Bajada
    else:
        return "➖"  # Sin cambio