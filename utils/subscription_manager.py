# utils/subscription_manager.py
"""
Módulo de gestión de suscripciones y límites.
Extraído de file_manager.py para responsabilidad única.
"""

from datetime import datetime, timedelta
from typing import Tuple, Any
from utils.logger import logger
from core.config import ADMIN_CHAT_IDS

# Importar desde user_data
from utils.user_data import obtener_datos_usuario_seguro, cargar_usuarios, guardar_usuarios


def check_feature_access(chat_id: int, feature_type: str, current_count: int = None) -> Tuple[bool, str]:
    """
    Verifica si el usuario tiene permiso o si alcanzó su límite.
    Retorna: (Bool, Mensaje) -> (True, "OK") o (False, "Razón")
    """
    # 1. Los Admins siempre tienen pase VIP
    if chat_id in ADMIN_CHAT_IDS:
        if feature_type == 'temp_min_val':
            return 0.25, "Admin Mode"
        return True, "Admin Mode"

    user_data = obtener_datos_usuario_seguro(chat_id)
    if not user_data:
        return False, "Usuario no registrado. Usa /start."

    subs = user_data['subscriptions']
    daily = user_data['daily_usage']
    now = datetime.now()

    def is_active(sub_key: str) -> bool:
        if not subs.get(sub_key):
            return False
        if not subs[sub_key]['active']:
            return False
        if not subs[sub_key]['expires']:
            return False
        try:
            exp_date = datetime.strptime(subs[sub_key]['expires'], '%Y-%m-%d %H:%M:%S')
            return exp_date > now
        except ValueError:
            return False

    # REGLA 1: Comando /ver
    if feature_type == 'ver_limit':
        limit = 8
        if is_active('watchlist_bundle'):
            limit = 48
        
        if daily['ver'] >= limit:
            return False, (
                f"🔒 *Límite Diario Alcanzado ({limit}/{limit})*\n"
                "—————————————————\n\n"
                f"Has usado tus {limit} consultas gratuitas de /ver por hoy.\n\n"
                "—————————————————\n"
                "Adquiere el 'Pack Control Total' en /shop para aumentar a 48 consultas diarias"
            )
        return True, "OK"

    # REGLA 2: Comando /tasa
    if feature_type == 'tasa_limit':
        limit = 8
        if is_active('tasa_vip'):
            limit = 24
        
        if daily['tasa'] >= limit:
            return False, (
                f"🔒 *Límite Diario Alcanzado ({limit}/{limit})*\n"
                "—————————————————\n\n"
                f"Has usado tus {limit} consultas de /tasa por hoy.\n\n"
                "—————————————————\n"
                "Adquiere 'Tasa VIP' en /shop para aumentar a 24 consultas diarias"
            )
        return True, "OK"

    # REGLA 3: Comando /ta
    if feature_type == 'ta_limit':
        limit = 21
        if is_active('ta_vip'):
            limit = 999999
            
        if daily['ta'] >= limit:
            return False, (
                f"🔒 *Límite Diario Alcanzado ({limit}/{limit})*\n"
                "—————————————————\n\n"
                f"Has realizado {limit} análisis técnicos hoy.\n\n"
                "—————————————————\n"
                "Adquiere 'TA Pro' en /shop para uso ILIMITADO por 30 días."
            )
        return True, "OK"
    
    # REGLA 4: Cambios de Temporalidad (valor mínimo)
    if feature_type == 'temp_min_val':
        min_val = 8.0
        if is_active('watchlist_bundle'):
            min_val = 0.25
        return min_val, "Valor Mínimo"
    
    # REGLA 5: Cambios de Temporalidad (límite)
    if feature_type == 'temp_change_limit':
        if is_active('watchlist_bundle'):
            return True, "OK"

        if daily.get('temp_changes', 0) >= 1:
            return False, (
                f"🔒 *Límite Diario Alcanzado*\n"
                "—————————————————\n\n"
                "Solo puedes cambiar la temporalidad 1 vez al día en el plan gratuito.\n"
                "Adquiere el 'Pack Control Total' para cambios ilimitados."
            )
        return True, "OK"

    # REGLA 6: Capacidad de alertas de precio
    if feature_type == 'alerts_capacity':
        base_limit = 2  # 2 pares (4 alertas: arriba + abajo cada una)
        
        extra_qty = subs.get('alerts_extra', {}).get('qty', 0)
        total_limit = base_limit + extra_qty
        
        # current_count is the number of currently active alerts
        if current_count is not None and current_count >= total_limit * 2:
            return False, (
                f"🔒 *Límite de Alertas Alcanzado ({current_count}/{total_limit * 2})*\n"
                "—————————————————\n\n"
                f"Tienes el máximo de {total_limit} pares de alerta activos.\n\n"
                "—————————————————\n"
                "Adquiere '+1 Alerta' en /shop para ampliar tu capacidad."
            )
        return True, "OK"

    return True, "OK"


def registrar_uso_comando(chat_id: int, comando: str) -> None:
    """
    Registra el uso de un comando para el límite diario.
    """
    usuarios = cargar_usuarios()
    chat_id_str = str(chat_id)
    
    if chat_id_str not in usuarios:
        return
    
    if 'daily_usage' not in usuarios[chat_id_str]:
        usuarios[chat_id_str]['daily_usage'] = {
            'date': datetime.now().strftime('%Y-%m-%d'),
            'ver': 0, 'tasa': 0, 'ta': 0,
            'temp_changes': 0, 'reminders': 0,
            'weather': 0, 'btc': 0,
        }
    
    # Map comando to daily_usage key
    command_map = {
        'ver': 'ver',
        'tasa': 'tasa', 
        'ta': 'ta',
        'temp': 'temp_changes',
        'rec': 'reminders',
        'w': 'weather',
        'weather': 'weather',
        'btc': 'btc',
    }
    
    key = command_map.get(comando)
    if key:
        usuarios[chat_id_str]['daily_usage'][key] = usuarios[chat_id_str]['daily_usage'].get(key, 0) + 1
        guardar_usuarios(usuarios)


def add_subscription_days(chat_id: int, sub_type: str, days: int = 30, quantity: int = 0) -> bool:
    """
    Añade días de suscripción a un usuario.
    
    Args:
        chat_id: ID del usuario
        sub_type: Tipo de suscripción
        days: Días a añadir
        quantity: Cantidad (para alertas extra, etc)
        
    Returns:
        True si éxito, False si error
    """
    usuarios = cargar_usuarios()
    chat_id_str = str(chat_id)
    
    if chat_id_str not in usuarios:
        return False
    
    if 'subscriptions' not in usuarios[chat_id_str]:
        usuarios[chat_id_str]['subscriptions'] = {
            'alerts_extra': {'qty': 0, 'expires': None},
            'coins_extra': {'qty': 0, 'expires': None},
            'watchlist_bundle': {'active': False, 'expires': None},
            'tasa_vip': {'active': False, 'expires': None},
            'ta_vip': {'active': False, 'expires': None},
            'sp_signals': {'active': False, 'expires': None},
        }
    
    now = datetime.now()
    exp_date = (now + timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
    
    subs = usuarios[chat_id_str]['subscriptions']
    
    if sub_type in subs:
        # Si es subscription (boolean active)
        if isinstance(subs[sub_type], dict) and 'active' in subs[sub_type]:
            subs[sub_type]['active'] = True
            subs[sub_type]['expires'] = exp_date
        # Si es qty (cantidad)
        elif isinstance(subs[sub_type], dict) and 'qty' in subs[sub_type]:
            subs[sub_type]['qty'] = subs[sub_type].get('qty', 0) + (quantity or days)
    
    guardar_usuarios(usuarios)
    logger.info(f"Subscription added: user={chat_id}, type={sub_type}, days={days}")
    return True


def toggle_hbd_alert_status(user_id: int) -> bool:
    """Activa/desactiva alertas HBD para el usuario."""
    usuarios = cargar_usuarios()
    user_id_str = str(user_id)
    
    if user_id_str not in usuarios:
        return False
    
    current = usuarios[user_id_str].get('hbd_alerts_enabled', True)
    usuarios[user_id_str]['hbd_alerts_enabled'] = not current
    guardar_usuarios(usuarios)
    return not current


def get_hbd_alert_recipients() -> list:
    """Obtiene lista de usuarios con alertas HBD activas."""
    usuarios = cargar_usuarios()
    recipients = []
    
    for uid, data in usuarios.items():
        if data.get('hbd_alerts_enabled', True):
            recipients.append(int(uid))
    
    return recipients
