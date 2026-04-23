# utils/file_manager.py

import os
import json
import shutil
from datetime import datetime, timedelta
import time
from utils.logger import logger
from core.config import (
    LOG_LINES, LOG_MAX, CUSTOM_ALERT_HISTORY_PATH,
    PRICE_ALERTS_PATH, HBD_HISTORY_PATH, ELTOQUE_HISTORY_PATH,
    LAST_PRICES_PATH, HBD_THRESHOLDS_PATH, ADMIN_CHAT_IDS, USUARIOS_PATH
)

# === Importaciones de módulos extraídos (backwards compatibility) ===
from utils.user_data import (
    obtener_datos_usuario,
    obtener_datos_usuario_seguro,
    registrar_usuario,
    obtener_monedas_usuario,
    actualizar_monedas,
    set_user_language,
    get_user_language,
    actualizar_intervalo_alerta,
    update_last_alert_timestamp,
    get_user_meta,
    set_user_meta,
)

from utils.subscription_manager import (
    check_feature_access,
    registrar_uso_comando,
    add_subscription_days,
    toggle_hbd_alert_status,
    get_hbd_alert_recipients,
)

from utils.alert_manager import (
    load_price_alerts,
    save_price_alerts,
    add_price_alert,
    get_user_alerts,
    delete_price_alert,
    delete_all_alerts,
    update_alert_status,
    check_price_alerts,
    get_alert_count,
)

from core.redis_fallback import (
    get_hbd_history,
    save_hbd_history,
    get_custom_alert_history,
    save_custom_alert_history,
    get_eltoque_history,
    save_eltoque_history,
    get_last_prices,
    save_last_prices,
    get_ads,
    save_ads,
    get_hbd_thresholds,
    save_hbd_thresholds,
    get_weather_subs,
    save_weather_subs,
    get_weather_last_alerts,
    save_weather_last_alerts,
    get_year_quotes,
    save_year_quotes,
    get_year_subs,
    save_year_subs,
    get_events_log,
    save_events_log,
    save_user,  # Nueva función para guardar un solo usuario
    get_all_user_ids,  # Para obtener IDs de usuarios
)

_USUARIOS_CACHE = None
_MIGRATION_TIMESTAMPS_DONE = False


def migrate_user_timestamps():
    """
    Migrate legacy user data to include registered_at timestamps.
    For users without registered_at, attempts to estimate from available data.
    Returns counts of migrated users.
    """
    global _MIGRATION_TIMESTAMPS_DONE
    
    # Only run once per process
    if _MIGRATION_TIMESTAMPS_DONE:
        return {'migrated': 0, 'already_had': 0, 'failed': 0}
    
    # Obtener lista de IDs de usuarios
    user_ids = get_all_user_ids()
    migrated = 0
    already_had = 0
    failed = 0
    now = datetime.now()
    
    for user_id in user_ids:
        # Obtener datos completos del usuario
        usuario = obtener_datos_usuario(int(user_id))
        if not usuario:
            failed += 1
            continue
        
        # Skip if already has registered_at
        if usuario.get('registered_at'):
            already_had += 1
            continue
        
        # Try to estimate registration date from available data
        estimated_date = None
        
        # 1. Use last_alert_timestamp as oldest available activity
        if usuario.get('last_alert_timestamp'):
            try:
                estimated_date = usuario['last_alert_timestamp']
            except Exception:
                pass
        
        # 2. Use last_seen as fallback
        if not estimated_date and usuario.get('last_seen'):
            try:
                estimated_date = usuario['last_seen']
            except Exception:
                pass
        
        # 3. Use a default far-past date if no data available
        if not estimated_date:
            # Default to 90 days ago as conservative estimate
            estimated_date = (now - timedelta(days=90)).strftime('%Y-%m-%d %H:%M:%S')
        
        # Set the estimated registration date
        usuario['registered_at'] = estimated_date
        
        # Guardar el usuario modificado en Redis
        if save_user(int(user_id), usuario):
            migrated += 1
        else:
            failed += 1
    
    _MIGRATION_TIMESTAMPS_DONE = True
    return {'migrated': migrated, 'already_had': already_had, 'failed': failed}


# === Inicialización de Archivos ===

def inicializar_archivos():
    """Crea los archivos si no existen."""
    from core.config import DATA_DIR
    
    # Create data directory if it doesn't exist
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        logger.info(f"✅ Directorio de datos verificado: {DATA_DIR}")
    except Exception as e:
        logger.error(f"❌ ERROR al crear directorio de datos: {e}")
    
    try:
        if not os.path.exists(CUSTOM_ALERT_HISTORY_PATH):
            with open(CUSTOM_ALERT_HISTORY_PATH, 'w', encoding='utf-8') as f:
                json.dump({}, f, indent=4)
            add_log_line(f"✅ Archivo de historial de alertas creado en: {CUSTOM_ALERT_HISTORY_PATH}")
    except Exception as e:
        logger.error(f"❌ ERROR al inicializar el archivo de historial de alertas: {e}")

    try:
        if not os.path.exists(HBD_THRESHOLDS_PATH):
            default_thresholds = {"1.00": True, "1.10": True, "0.95": True} 
            with open(HBD_THRESHOLDS_PATH, 'w', encoding='utf-8') as f:
                json.dump(default_thresholds, f, indent=4)
            add_log_line(f"✅ Archivo de umbrales HBD creado en: {HBD_THRESHOLDS_PATH}")
    except Exception as e:
        logger.error(f"❌ ERROR al inicializar umbrales HBD: {e}")


MAX_HISTORY_ENTRIES = 2 # Limita el archivo para que no crezca indefinidamente

# === Funciones para HBD History (ahora usan Redis) ===

def load_hbd_history():
    return get_hbd_history()

def save_hbd_history(history):
    from core.redis_fallback import save_hbd_history as redis_save_hbd_history
    return redis_save_hbd_history(history)

def leer_precio_anterior_alerta():
    history = load_hbd_history()
    if not history:
        return None
    return history[-1].get("hbd")

def guardar_precios_alerta(precios):
    history = load_hbd_history()
    nuevo_registro = {
        "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "btc": precios.get('BTC'),
        "hive": precios.get('HIVE'),
        "hbd": precios.get('HBD'),
        "ton": precios.get('TON')
    }
    history.append(nuevo_registro)
    if len(history) > MAX_HISTORY_ENTRIES:
        history = history[-MAX_HISTORY_ENTRIES:]
    save_hbd_history(history)
    logger.info("✅ Precios de alerta guardados en Redis")

# === FUNCIONES DE UMBRALES HBD ===

def load_hbd_thresholds():
    return get_hbd_thresholds()

def save_hbd_thresholds(thresholds):
    return save_hbd_thresholds(thresholds)

def modify_hbd_threshold(price: float, action: str):
    thresholds = load_hbd_thresholds()
    target_key = f"{price:.4f}"
    existing_key = None
    
    if target_key in thresholds:
        existing_key = target_key
    else:
        for key in thresholds.keys():
            try:
                if abs(float(key) - price) < 0.00001:
                    existing_key = key
                    break
            except ValueError:
                continue

    if action == 'add':
        key_to_use = existing_key if existing_key else target_key
        thresholds[key_to_use] = True
        msg = f"✅ Alerta HBD para ${key_to_use} añadida y activada."
    elif action == 'del':
        if existing_key:
            del thresholds[existing_key]
            msg = f"🗑️ Alerta HBD para ${existing_key} eliminada."
        else:
            msg = f"⚠️ No existe alerta para ${target_key}."
    elif action == 'run':
        if existing_key:
            thresholds[existing_key] = True
            msg = f"▶️ Alerta HBD para ${existing_key} activada (Running)."
        else:
            thresholds[target_key] = True
            msg = f"▶️ Alerta HBD para ${target_key} creada y activada."
    elif action == 'stop':
        if existing_key:
            thresholds[existing_key] = False
            msg = f"⏸️ Alerta HBD para ${existing_key} detenida (Stopped)."
        else:
            msg = f"⚠️ No existe alerta para ${target_key} para detener."
    else:
        return False, "Acción desconocida"

    save_hbd_thresholds(thresholds)
    logger.info(msg)
    return True, msg

# === FUNCIONES DE LAST PRICES ===

def load_last_prices_status():
    return get_last_prices()

def save_last_prices_status(data: dict):
    return save_last_prices(data)

# === FUNCIONES DE CUSTOM ALERT HISTORY ===

def cargar_custom_alert_history():
    return get_custom_alert_history()

def guardar_custom_alert_history(history_data: dict):
    return save_custom_alert_history(history_data)

# === FUNCIONES DE ELTOQUE HISTORY ===

def load_eltoque_history():
    return get_eltoque_history()

def save_eltoque_history(history):
    return save_eltoque_history(history)

# === FUNCIONES DE ADS ===

def load_ads():
    return get_ads()

def save_ads(ads):
    return save_ads(ads)

# === FUNCIONES DE WEATHER SUBS ===

def load_weather_subs():
    return get_weather_subs()

def save_weather_subs(subs):
    return save_weather_subs(subs)

# === FUNCIONES DE WEATHER LAST ALERTS ===

def load_weather_last_alerts():
    return get_weather_last_alerts()

def save_weather_last_alerts(data):
    return save_weather_last_alerts(data)

# === FUNCIONES DE YEAR QUOTES ===

def load_year_quotes():
    return get_year_quotes()

def save_year_quotes(quotes):
    return save_year_quotes(quotes)

# === FUNCIONES DE YEAR SUBS ===

def load_year_subs():
    return get_year_subs()

def save_year_subs(subs):
    return save_year_subs(subs)

# === FUNCIONES DE EVENTS LOG ===

def load_events_log():
    return get_events_log()

def save_events_log(log):
    return save_events_log(log)

# === FUNCIONES VARIAS ===

def add_log_line(linea):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    LOG_LINES.append(f"[{timestamp}] | {linea}") 
    if len(LOG_LINES) > LOG_MAX:
        del LOG_LINES[0]
    print(LOG_LINES[-1])
    logger.info(linea)

def delete_all_alerts(user_id: int) -> bool:
    user_alerts = get_user_alerts(user_id)
    if not user_alerts:
        return False
    for alert in user_alerts:
        delete_price_alert(user_id, alert['alert_id'])
    return True