# utils/file_manager.py

import os
import json
import shutil
from datetime import datetime, timedelta
import time 
import uuid # Para generar IDs únicos si es necesario
import openpyxl
from utils.logger import logger
from core.config import (
    LOG_LINES, LOG_MAX, CUSTOM_ALERT_HISTORY_PATH, 
    PRICE_ALERTS_PATH, HBD_HISTORY_PATH, ELTOQUE_HISTORY_PATH, 
    LAST_PRICES_PATH, HBD_THRESHOLDS_PATH, ADMIN_CHAT_IDS, USUARIOS_PATH
)

# === Importaciones de módulos extraídos (backwards compatibility) ===
from utils.user_data import (
    cargar_usuarios,
    guardar_usuarios,
    obtener_datos_usuario,
    obtener_datos_usuario_seguro,
    registrar_usuario,
    obtener_monedAS_usuario,
    actualizar_monedAS,
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
    
    usuarios = cargar_usuarios()
    migrated = 0
    already_had = 0
    failed = 0
    now = datetime.now()
    
    for uid, u in usuarios.items():
        # Skip if already has registered_at
        if u.get('registered_at'):
            already_had += 1
            continue
        
        # Try to estimate registration date from available data
        estimated_date = None
        
        # 1. Use last_alert_timestamp as oldest available activity
        if u.get('last_alert_timestamp'):
            try:
                estimated_date = u['last_alert_timestamp']
            except Exception:
                pass
        
        # 2. Use last_seen as fallback
        if not estimated_date and u.get('last_seen'):
            try:
                estimated_date = u['last_seen']
            except Exception:
                pass
        
        # 3. Use a default far-past date if no data available
        if not estimated_date:
            # Default to 90 days ago as conservative estimate
            estimated_date = (now - timedelta(days=90)).strftime('%Y-%m-%d %H:%M:%S')
            failed += 1  # Mark as failed (estimated) since we had no real data
        else:
            migrated += 1
        
        # Set the estimated registration date
        u['registered_at'] = estimated_date
    
    # Save if any changes were made
    if migrated > 0 or failed > 0:
        guardar_usuarios(usuarios)
        logger.info(f"Migration complete: {migrated} migrated, {failed} estimated, {already_had} already had timestamps")
    
    _MIGRATION_TIMESTAMPS_DONE = True
    return {'migrated': migrated, 'already_had': already_had, 'failed': failed}


# === Inicialización de Archivos ===
def inicializar_archivos():
    """Crea los archivos si no existen."""
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

def load_hbd_history():
    if not os.path.exists(HBD_HISTORY_PATH):
        return []
    try:
        with open(HBD_HISTORY_PATH, "r", encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return []

def save_hbd_history(history):
    try:
        with open(HBD_HISTORY_PATH, "w", encoding='utf-8') as f:
            json.dump(history, f, indent=4)
    except Exception as e:
        logger.error(f"Error al guardar el historial de HBD: {e}")

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
    logger.info("✅ Precios de alerta guardados en hbd_price_history.json")

def add_log_line(linea):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    LOG_LINES.append(f"[{timestamp}] | {linea}") 
    if len(LOG_LINES) > LOG_MAX:
        del LOG_LINES[0]
    print(LOG_LINES[-1])
    logger.info(linea)

# === FUNCIONES DE UMBRALES HBD ===
def load_hbd_thresholds():
    if not os.path.exists(HBD_THRESHOLDS_PATH):
        return {}
    try:
        with open(HBD_THRESHOLDS_PATH, "r", encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return {}

def save_hbd_thresholds(thresholds):
    try:
        with open(HBD_THRESHOLDS_PATH, "w", encoding='utf-8') as f:
            json.dump(thresholds, f, indent=4, sort_keys=True)
    except Exception as e:
        logger.error(f"Error al guardar umbrales HBD: {e}")

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

def load_last_prices_status():
    if not os.path.exists(LAST_PRICES_PATH):
        return {}
    try:
        with open(LAST_PRICES_PATH, "r", encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return {}

def save_last_prices_status(data: dict):
    try:
        with open(LAST_PRICES_PATH, "w", encoding='utf-8') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        logger.error(f"❌ Error guardando last_prices.json: {e}")

def cargar_custom_alert_history():
    try:
        if os.path.exists(CUSTOM_ALERT_HISTORY_PATH):
            with open(CUSTOM_ALERT_HISTORY_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            return {}
    except Exception as e:
        return {}

def guardar_custom_alert_history(history_data: dict):
    try:
        with open(CUSTOM_ALERT_HISTORY_PATH, 'w', encoding='utf-8') as f:
            json.dump(history_data, f, indent=4)
    except Exception as e:
        logger.error(f"❌ ERROR al guardar el historial de alertas: {e}")

def delete_all_alerts(user_id: int) -> bool:
    user_alerts = get_user_alerts(user_id)
    if not user_alerts:
        return False
    for alert in user_alerts:
        delete_price_alert(user_id, alert['alert_id'])
    return True

inicializar_archivos()
