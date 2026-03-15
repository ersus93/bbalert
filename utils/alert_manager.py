# utils/alert_manager.py
"""
Módulo de gestión de alertas de precio.
Extraído de file_manager.py para responsabilidad única.
"""

import os
import json
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime
from utils.logger import logger
from core.config import PRICE_ALERTS_PATH


# === Funciones de Carga/Guardado ===

def load_price_alerts() -> Dict[str, Any]:
    """Carga alertas desde archivo."""
    if not os.path.exists(PRICE_ALERTS_PATH):
        return {}
    try:
        with open(PRICE_ALERTS_PATH, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return {}

def save_price_alerts(alerts: Dict[str, Any]) -> None:
    """Guarda alertas en archivo."""
    try:
        with open(PRICE_ALERTS_PATH, "w") as f:
            json.dump(alerts, f, indent=4)
    except Exception as e:
        logger.error(f"Error al guardar alertas de precio: {e}")

# === CRUD de Alertas ===

def add_price_alert(user_id: int, coin: str, target_price: float) -> Optional[str]:
    """
    Crea una alerta de precio para el usuario.
    Crea dos alertas: una para precio above y otra para below.
    
    Args:
        user_id: ID del usuario
        coin: Símbolo de la moneda
        target_price: Precio objetivo
        
    Returns:
        ID de la alerta o mensaje de error
    """
    alerts = load_price_alerts()
    user_id_str = str(user_id)
    
    if user_id_str not in alerts:
        alerts[user_id_str] = []
    
    alert_id = str(uuid.uuid4())[:8]
    
    alert_above = {
        "alert_id": alert_id,
        "coin": coin.upper(),
        "target_price": target_price,
        "condition": "ABOVE",
        "status": "ACTIVE",
        "created_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    # Segunda alerta para precio below
    alert_below = {
        "alert_id": str(uuid.uuid4())[:8],
        "coin": coin.upper(),
        "target_price": target_price,
        "condition": "BELOW",
        "status": "ACTIVE",
        "created_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    alerts[user_id_str].append(alert_above)
    alerts[user_id_str].append(alert_below)
    save_price_alerts(alerts)
    
    return alert_id


def get_user_alerts(user_id: int) -> List[Dict[str, Any]]:
    """
    Obtiene las alertas activas del usuario.
    
    Args:
        user_id: ID del usuario
        
    Returns:
        Lista de alertas activas
    """
    alerts = load_price_alerts()
    return [a for a in alerts.get(str(user_id), []) if a.get('status') == 'ACTIVE']


def delete_price_alert(user_id: int, alert_id: str) -> bool:
    """
    Elimina una alerta específica.
    
    Args:
        user_id: ID del usuario
        alert_id: ID de la alerta
        
    Returns:
        True si se eliminó, False si no existía
    """
    alerts = load_price_alerts()
    user_id_str = str(user_id)
    
    if user_id_str in alerts:
        original_count = len(alerts[user_id_str])
        alerts[user_id_str] = [a for a in alerts[user_id_str] if a.get('alert_id') != alert_id]
        
        if len(alerts[user_id_str]) < original_count:
            save_price_alerts(alerts)
            return True
    return False


def delete_all_alerts(user_id: int) -> bool:
    """
    Elimina todas las alertas del usuario.
    
    Args:
        user_id: ID del usuario
        
    Returns:
        True si éxito
    """
    alerts = load_price_alerts()
    user_id_str = str(user_id)
    
    if user_id_str in alerts:
        alerts[user_id_str] = []
        save_price_alerts(alerts)
    
    return True


def update_alert_status(user_id: int, alert_id: str, new_status: str) -> bool:
    """
    Actualiza el estado de una alerta.
    
    Args:
        user_id: ID del usuario
        alert_id: ID de la alerta
        new_status: Nuevo estado (ACTIVE, TRIGGERED, etc)
        
    Returns:
        True si se actualizó, False si no existía
    """
    alerts = load_price_alerts()
    user_id_str = str(user_id)
    
    if user_id_str in alerts:
        for alert in alerts[user_id_str]:
            if alert.get('alert_id') == alert_id:
                alert['status'] = new_status
                alert['updated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                save_price_alerts(alerts)
                return True
    return False


def check_price_alerts(prices: Dict[str, float]) -> List[Dict[str, Any]]:
    """
    Verifica si alguna alerta debe activarse según los precios dados.
    
    Args:
        prices: Dict con símbolo -> precio
        
    Returns:
        Lista de alertas a activar
    """
    alerts = load_price_alerts()
    triggered = []
    
    for user_id_str, user_alerts in alerts.items():
        for alert in user_alerts:
            if alert.get('status') != 'ACTIVE':
                continue
            
            coin = alert.get('coin', '').upper()
            target = alert.get('target_price', 0)
            condition = alert.get('condition', 'ABOVE')
            
            current_price = prices.get(coin)
            if current_price is None:
                continue
            
            # Verificar condición
            should_trigger = False
            if condition == 'ABOVE' and current_price >= target:
                should_trigger = True
            elif condition == 'BELOW' and current_price <= target:
                should_trigger = True
            
            if should_trigger:
                triggered.append({
                    'user_id': int(user_id_str),
                    'alert': alert,
                    'current_price': current_price,
                    'target_price': target,
                    'condition': condition
                })
    
    return triggered


def get_alert_count(user_id: int) -> int:
    """Obtiene el número de alertas activas del usuario."""
    alerts = load_price_alerts()
    return len([a for a in alerts.get(str(user_id), []) if a.get('status') == 'ACTIVE'])
