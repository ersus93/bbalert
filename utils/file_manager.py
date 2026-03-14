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

# === GESTIÓN DE USUARIOS ===

def migrate_user_timestamps():
    """
    Migra timestamps retroactivamente para usuarios existentes sin 'registered_at' o 'last_seen'.

    Returns:
        tuple: (migrated_count, skipped_count)
    """
    global _MIGRATION_TIMESTAMPS_DONE

    if _MIGRATION_TIMESTAMPS_DONE:
        return (0, 0)

    try:
        usuarios = cargar_usuarios()
        if not usuarios:
            _MIGRATION_TIMESTAMPS_DONE = True
            return (0, 0)

        migrated_count = 0
        skipped_count = 0

        # Obtener tiempo de modificacion del archivo como fallback
        file_mtime = None
        try:
            if os.path.exists(USUARIOS_PATH):
                file_mtime = datetime.fromtimestamp(os.path.getmtime(USUARIOS_PATH))
        except Exception:
            file_mtime = datetime.now()

        for chat_id_str, user_data in usuarios.items():
            needs_save = False

            # Migrar registered_at
            if not user_data.get('registered_at'):
                registered_at = None

                # Intentar usar last_alert_timestamp si existe
                if user_data.get('last_alert_timestamp'):
                    try:
                        registered_at = user_data['last_alert_timestamp']
                    except Exception:
                        pass

                # Fallback: usar fecha de modificacion del archivo
                if not registered_at and file_mtime:
                    registered_at = file_mtime.strftime('%Y-%m-%d %H:%M:%S')

                if registered_at:
                    user_data['registered_at'] = registered_at
                    needs_save = True

            # Migrar last_seen
            if not user_data.get('last_seen'):
                last_seen = None

                # Intentar usar last_alert_timestamp si existe
                if user_data.get('last_alert_timestamp'):
                    try:
                        last_seen = user_data['last_alert_timestamp']
                    except Exception:
                        pass

                # Si no hay last_alert_timestamp, dejar como None (no hay buen fallback)
                if last_seen:
                    user_data['last_seen'] = last_seen
                    needs_save = True

            if needs_save:
                migrated_count += 1
            else:
                skipped_count += 1

        if migrated_count > 0:
            guardar_usuarios(usuarios)
            logger.info(f"✅ Migracion completada: {migrated_count} usuarios actualizados, {skipped_count} sin cambios")
        else:
            logger.info(f"✅ Migracion: Todos los usuarios ya tenian timestamps ({skipped_count} verificados)")

        _MIGRATION_TIMESTAMPS_DONE = True
        return (migrated_count, skipped_count)

    except Exception as e:
        logger.error(f"❌ Error durante la migracion de timestamps: {e}")
        _MIGRATION_TIMESTAMPS_DONE = True
        return (0, 0)


def cargar_usuarios():
    global _USUARIOS_CACHE

    # Si ya está en memoria, usar memoria (rápido y seguro)
    if _USUARIOS_CACHE is not None:
        return _USUARIOS_CACHE

    if not os.path.exists(USUARIOS_PATH):
        _USUARIOS_CACHE = {}
        return _USUARIOS_CACHE

    try:
        with open(USUARIOS_PATH, 'r', encoding='utf-8') as f:
            _USUARIOS_CACHE = json.load(f)
            # Ejecutar migracion automaticamente despues de cargar
            migrate_user_timestamps()
            return _USUARIOS_CACHE
    except json.JSONDecodeError:
        # Si el archivo está roto, intentamos recuperar backup o iniciar vacío
        if os.path.exists(USUARIOS_PATH):
            shutil.copy(USUARIOS_PATH, f"{USUARIOS_PATH}.corrupto")
        _USUARIOS_CACHE = {}
        return _USUARIOS_CACHE
    except Exception:
        return {}

def guardar_usuarios(usuarios_data=None):
    global _USUARIOS_CACHE
    
    if usuarios_data is not None:
        _USUARIOS_CACHE = usuarios_data
    
    if _USUARIOS_CACHE is None:
        return

    try:
        # Guardado atómico: escribe en .tmp y renombra (evita corrupción)
        temp_path = f"{USUARIOS_PATH}.tmp"
        with open(temp_path, "w", encoding='utf-8') as f:
            json.dump(_USUARIOS_CACHE, f, indent=4)
        os.replace(temp_path, USUARIOS_PATH)
    except Exception as e:
        logger.error(f"❌ Error al guardar usuarios: {e}")

# --- FASE 1: NUEVAS FUNCIONES DE SUSCRIPCIÓN Y LÍMITES ---
def obtener_datos_usuario_seguro(chat_id):
    """
    Obtiene los datos del usuario asegurando que existan los campos de suscripción
    y uso diario. Si faltan claves, las crea.
    """
    usuarios = cargar_usuarios()
    chat_id_str = str(chat_id)
    
    if chat_id_str not in usuarios:
        return None 

    usuario = usuarios[chat_id_str]
    guardar = False
    
    today_str = datetime.now().strftime('%Y-%m-%d')
    
    # 1. Estructura de Uso Diario (Inicialización y Reinicio)
    if 'daily_usage' not in usuario or usuario['daily_usage'].get('date') != today_str:
        # Si no existe o es un día nuevo, reiniciamos todo a 0
        usuario['daily_usage'] = {
            'date': today_str,
            'ver': 0,
            'tasa': 0,
            'ta': 0,
            'temp_changes': 0,
            'reminders': 0,
            'weather': 0,
            'btc': 0,
        }
        guardar = True
    else:
        # IMPORTANTE: Si ya existe el registro de hoy, verificamos que tenga TODAS las claves nuevas.
        # Esto soluciona el bug de usuarios antiguos que tienen acceso ilimitado.
        keys_necesarias = ['ver', 'tasa', 'ta', 'temp_changes', 'reminders', 'weather', 'btc']
        for key in keys_necesarias:
            if key not in usuario['daily_usage']:
                usuario['daily_usage'][key] = 0
                guardar = True

    # 2. Suscripciones (Relleno de estructura si falta)
    if 'subscriptions' not in usuario:
        usuario['subscriptions'] = {
            'alerts_extra':     {'qty': 0,     'expires': None},
            'coins_extra':      {'qty': 0,     'expires': None},
            'watchlist_bundle': {'active': False, 'expires': None},
            'tasa_vip':         {'active': False, 'expires': None},
            'ta_vip':           {'active': False, 'expires': None},
            'sp_signals':       {'active': False, 'expires': None},  # SmartSignals Pro
        }
        guardar = True
    else:
        # Migración: usuarios existentes que aún no tienen sp_signals
        if 'sp_signals' not in usuario['subscriptions']:
            usuario['subscriptions']['sp_signals'] = {'active': False, 'expires': None}
            guardar = True

    # 3. Campos de tracking (Relleno si faltan — compatibilidad con usuarios antiguos)
    if 'last_seen' not in usuario:
        usuario['last_seen'] = None
        guardar = True
    if 'registered_at' not in usuario:
        usuario['registered_at'] = None
        guardar = True
        
    if guardar:
        guardar_usuarios(usuarios)
        
    return usuario

def check_feature_access(chat_id, feature_type, current_count=None):
    """
    Verifica si el usuario tiene permiso o si alcanzó su límite.
    Retorna: (Bool, Mensaje) -> (True, "OK") o (False, "Razón")
    """
    # 1. Los Admins siempre tienen pase VIP (Ilimitado)
    if chat_id in ADMIN_CHAT_IDS:
        if feature_type == 'temp_min_val': return 0.25, "Admin Mode" # Mínimo flexible
        return True, "Admin Mode"

    user_data = obtener_datos_usuario_seguro(chat_id)
    if not user_data:
        return False, "Usuario no registrado. Usa /start."

    subs = user_data['subscriptions']
    daily = user_data['daily_usage']
    now = datetime.now()

    # Helper para verificar si una subscripción está activa y vigente
    def is_active(sub_key):
        if not subs.get(sub_key): return False
        if not subs[sub_key]['active']: return False
        if not subs[sub_key]['expires']: return False
        try:
            exp_date = datetime.strptime(subs[sub_key]['expires'], '%Y-%m-%d %H:%M:%S')
            return exp_date > now
        except ValueError:
            return False

    # --- REGLA 1: Comando /ver ---
    if feature_type == 'ver_limit':
        limit = 8  # Gratis
        if is_active('watchlist_bundle'):
            limit = 48 # Pago (Pack Control Total)
        
        if daily['ver'] >= limit:
            return False, (
                f"🔒 *Límite Diario Alcanzado ({limit}/{limit})*\n—————————————————\n\n"
                f"Has usado tus {limit} consultas gratuitas de /ver por hoy.\n\n—————————————————\n"
                f"Adquiere el 'Pack Control Total' en /shop para aumentar a 48 consultas diarias, entre otras funciones"
                )
        return True, "OK"

    # --- REGLA 2: Comando /tasa ---
    if feature_type == 'tasa_limit':
        limit = 8 # Gratis
        if is_active('tasa_vip'):
            limit = 24 # Pago (Tasa VIP)
        
        if daily['tasa'] >= limit:
            return False, (
                f"🔒 *Límite Diario Alcanzado ({limit}/{limit})*\n—————————————————\n\n"
                f"Has usado tus {limit} consultas de /tasa por hoy.\n\n—————————————————\n"
                f"Adquiere 'Tasa VIP' en /shop para aumentar a 24 consultas diarias durante 30 días."
                )
        return True, "OK"

    # --- REGLA 3: Comando /ta ---
    if feature_type == 'ta_limit':
        limit = 21 # Gratis
        if is_active('ta_vip'):
            limit = 999999 # Pago (Ilimitado)
            
        if daily['ta'] >= limit:
            return False, (
                f"🔒 *Límite Diario Alcanzado ({limit}/{limit})*\n—————————————————\n\n"
                f"Has realizado {limit} análisis técnicos hoy.\n\n—————————————————\n"
                f"Adquiere 'TA Pro' en /shop para uso ILIMITADO por 30 días."
                )
        return True, "OK"
    
    # --- REGLA 4: Cambios de Temporalidad ---    
    if feature_type == 'temp_min_val':
        min_val = 8.0
        if is_active('watchlist_bundle'):
            min_val = 0.25
        return min_val, "Valor Mínimo"
    
    # --- REGLA 5: Cambios de Temporalidad ---
    if feature_type == 'temp_change_limit':
        if is_active('watchlist_bundle'):
            return True, "OK" # Ilimitado con el pack
        
        # Plan Gratis: Solo 1 cambio al día
        if daily.get('temp_changes', 0) >= 1:
            return False, (
                f"🔒 *Límite Diario Alcanzado*\n—————————————————\n\n"
                f"Solo puedes cambiar la temporalidad 1 vez al día en el plan gratuito.\n"
                f"Adquiere el 'Pack Control Total' para cambios ilimitados durante 30 días, entre otras finciones."
                )
        return True, "OK"

    # --- REGLA 6: Capacidad de Lista de Monedas (/monedas) ---
    if feature_type == 'coins_capacity':
        # current_count es la cantidad de monedas que el usuario INTENTA guardar
        base_capacity = 5
        
        # Verificamos extras comprados
        extra_capacity = 0
        if is_active('coins_extra'):
            extra_capacity = subs['coins_extra']['qty']
            
        total_capacity = base_capacity + extra_capacity
        
        if current_count > total_capacity:
            return False, (
                f"🔒 *Capacidad Excedida ({current_count}/{total_capacity})*\n—————————————————\n\n"
                f"Tu límite actual es de {total_capacity} monedas.\n"
                f"Has intentado guardar {current_count}.\n\n—————————————————\n"
                f"🛒 Ve a /shop para comprar '+1 Espacio Moneda'."
            )
        return True, "OK"

    # --- REGLA 7: Capacidad de Alertas de Cruce (/alerta) ---
    if feature_type == 'alerts_capacity':
        # current_count aquí será el total de alertas ACTIVAS en la BD
        # Recordar: 1 alerta de usuario = 2 registros en BD (Arriba + Abajo)
        
        base_pairs = 10  # 10 alertas del usuario (20 registros)
        extra_pairs = 0
        
        if is_active('alerts_extra'):
            extra_pairs = subs['alerts_extra']['qty']
            
        total_pairs = base_pairs + extra_pairs
        total_slots_db = total_pairs * 2 # Capacidad real en base de datos
        
        # Al crear una alerta nueva, se suman 2 slots. Verificamos si caben.
        if (current_count + 2) > total_slots_db:
            return False, (
                f"🔒 *Capacidad de Alertas Llena*\n—————————————————\n\n"
                f"Tienes ocupados tus {total_pairs} espacios para alertas.\n"
                f"Elimina alguna con /misalertas o compra '+1 Alerta Cruce' en /shop."
            )
        return True, "OK"

    # --- REGLA 8: SmartSignals Pro (/sp) ---
    if feature_type == 'sp_signals':
        if is_active('sp_signals'):
            return True, "OK"
        return False, (
            "🔒 *SmartSignals Pro*\n—————————————————\n\n"
            "Esta función es exclusiva para suscriptores.\n\n"
            "📡 Recibe señales predictivas de compra/venta con gráfico,\n"
            "pre-aviso 10-30s antes del cierre de vela y soporte para\n"
            "BTC + 12 altcoins — todo por solo *200 ⭐ / 30 días*.\n\n"
            "—————————————————\n"
            "Usa /shop para activar SmartSignals Pro."
        )

    return True, "OK"

def registrar_uso_comando(chat_id, comando):
    """Incrementa el contador de uso para un comando específico y actualiza last_seen."""
    # Los admins no registran uso (son ilimitados)
    if chat_id in ADMIN_CHAT_IDS:
        return

    # Aseguramos que la estructura exista antes de escribir
    obtener_datos_usuario_seguro(chat_id)
    
    usuarios = cargar_usuarios()
    chat_id_str = str(chat_id)
    
    if chat_id_str in usuarios:
        daily = usuarios[chat_id_str].get('daily_usage', {})
        
        # Incrementamos de forma segura (creando la clave si por alguna razón no está)
        actual = daily.get(comando, 0)
        daily[comando] = actual + 1
        
        usuarios[chat_id_str]['daily_usage'] = daily # Asegurar asignación
        
        # MEJORA: Actualizar last_seen con cada uso de comando (actividad real del usuario)
        usuarios[chat_id_str]['last_seen'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        guardar_usuarios(usuarios)
        
        # LOG DE DEBUG (Opcional: te ayudará a ver en consola si cuenta)
        print(f"DEBUG: Usuario {chat_id} usó {comando}. Nuevo total: {daily[comando]}")

def add_subscription_days(chat_id, sub_type, days=30, quantity=0):
    usuarios = cargar_usuarios()
    obtener_datos_usuario_seguro(chat_id)
    usuarios = cargar_usuarios()
    
    chat_id_str = str(chat_id)
    user = usuarios[chat_id_str]
    subs = user['subscriptions']
    now = datetime.now()
    
    if sub_type in ['watchlist_bundle', 'tasa_vip', 'ta_vip', 'sp_signals']:
        current_exp_str = subs[sub_type]['expires']
        if current_exp_str:
            current_exp = datetime.strptime(current_exp_str, '%Y-%m-%d %H:%M:%S')
            new_exp = (current_exp if current_exp > now else now) + timedelta(days=days)
        else:
            new_exp = now + timedelta(days=days)
            
        subs[sub_type]['active'] = True
        subs[sub_type]['expires'] = new_exp.strftime('%Y-%m-%d %H:%M:%S')
        logger.info(f"💰 Usuario {chat_id} compró {sub_type}. Expira: {subs[sub_type]['expires']}")

    elif sub_type in ['coins_extra', 'alerts_extra']:
        subs[sub_type]['qty'] += quantity
        current_exp_str = subs[sub_type]['expires']
        if current_exp_str:
            current_exp = datetime.strptime(current_exp_str, '%Y-%m-%d %H:%M:%S')
            new_exp = (current_exp if current_exp > now else now) + timedelta(days=days)
        else:
            new_exp = now + timedelta(days=days)
            
        subs[sub_type]['expires'] = new_exp.strftime('%Y-%m-%d %H:%M:%S')
        logger.info(f"💰 Usuario {chat_id} añadió +{quantity} a {sub_type}.")

    guardar_usuarios(usuarios)
# ------------------------------------------------------------------

def set_user_language(chat_id: int, lang_code: str):
    usuarios = cargar_usuarios()
    chat_id_str = str(chat_id)
    if chat_id_str in usuarios:
        usuarios[chat_id_str]['language'] = lang_code
        guardar_usuarios(usuarios)

def get_user_language(chat_id: int) -> str:
    usuarios = cargar_usuarios()
    return usuarios.get(str(chat_id), {}).get('language', 'es')


# === GESTIÓN DE ALERTAS DE PRECIO ===
def load_price_alerts():
    if not os.path.exists(PRICE_ALERTS_PATH):
        return {}
    try:
        with open(PRICE_ALERTS_PATH, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return {}

def save_price_alerts(alerts):
    try:
        with open(PRICE_ALERTS_PATH, "w") as f:
            json.dump(alerts, f, indent=4)
    except Exception as e:
        logger.error(f"Error al guardar alertas de precio: {e}")

def add_price_alert(user_id, coin, target_price):
    alerts = load_price_alerts()
    user_id_str = str(user_id)
    if user_id_str not in alerts:
        alerts[user_id_str] = []
    
    alert_above = {
        "alert_id": str(uuid.uuid4())[:8],
        "coin": coin.upper(),
        "target_price": target_price,
        "condition": "ABOVE",
        "status": "ACTIVE"
    }
    alert_below = {
        "alert_id": str(uuid.uuid4())[:8],
        "coin": coin.upper(),
        "target_price": target_price,
        "condition": "BELOW",
        "status": "ACTIVE"
    }
    alerts[user_id_str].append(alert_above)
    alerts[user_id_str].append(alert_below)
    save_price_alerts(alerts)
    return (f"✅ ¡Alertas creadas!")

def get_user_alerts(user_id):
    alerts = load_price_alerts()
    return [a for a in alerts.get(str(user_id), []) if a['status'] == 'ACTIVE']

def delete_price_alert(user_id, alert_id):
    alerts = load_price_alerts()
    user_id_str = str(user_id)
    if user_id_str in alerts:
        original_count = len(alerts[user_id_str])
        alerts[user_id_str] = [a for a in alerts[user_id_str] if a['alert_id'] != alert_id]
        if len(alerts[user_id_str]) < original_count:
            save_price_alerts(alerts)
            return True
    return False

def update_alert_status(user_id, alert_id, new_status):
    alerts = load_price_alerts()
    user_id_str = str(user_id)
    if user_id_str in alerts:
        for alert in alerts[user_id_str]:
            if alert['alert_id'] == alert_id:
                alert['status'] = new_status
                save_price_alerts(alerts)
                return True
    return False

def actualizar_intervalo_alerta(chat_id, new_interval_h):
    usuarios = cargar_usuarios()
    chat_id_str = str(chat_id)
    if chat_id_str in usuarios:
        try:
            usuarios[chat_id_str]['intervalo_alerta_h'] = float(new_interval_h)
            guardar_usuarios(usuarios)
            return True
        except ValueError:
            return False
    return False

def update_last_alert_timestamp(chat_id):
    usuarios = cargar_usuarios()
    chat_id_str = str(chat_id)
    if chat_id_str in usuarios:
        usuarios[chat_id_str]['last_alert_timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        guardar_usuarios(usuarios)

def registrar_usuario(chat_id, user_lang_code: str = 'es'):
    usuarios = cargar_usuarios()
    chat_id_str = str(chat_id)
    if chat_id_str not in usuarios:
        lang_to_save = 'es'
        if user_lang_code and user_lang_code.startswith('en'):
            lang_to_save = 'en'
        usuarios[chat_id_str] = {
            "monedas": ["BTC", "HIVE", "HBD", "TON"],
            "hbd_alerts": False,
            "language": lang_to_save,
            "intervalo_alerta_h": 1.0,
            # MEJORA: Campos de tracking para estadísticas del dashboard
            "registered_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "last_seen": None,
        }
        guardar_usuarios(usuarios)

def actualizar_monedas(chat_id, lista_monedas):
    usuarios = cargar_usuarios()
    chat_id_str = str(chat_id)
    if chat_id_str not in usuarios:
        usuarios[chat_id_str] = {}
    usuarios[chat_id_str]["monedas"] = lista_monedas
    guardar_usuarios(usuarios)

def obtener_monedas_usuario(chat_id):
    usuarios = cargar_usuarios()
    return usuarios.get(str(chat_id), {}).get("monedas", [])

def obtener_datos_usuario(chat_id):
    usuarios = cargar_usuarios()
    return usuarios.get(str(chat_id), {})

def toggle_hbd_alert_status(user_id: int) -> bool:
    usuarios = cargar_usuarios()
    user_id_str = str(user_id)
    if user_id_str in usuarios:
        current_status = usuarios[user_id_str].get('hbd_alerts', False)
        new_status = not current_status
        usuarios[user_id_str]['hbd_alerts'] = new_status
        guardar_usuarios(usuarios)
        return new_status
    return False

def get_hbd_alert_recipients() -> list:
    usuarios = cargar_usuarios()
    recipients = []
    for chat_id, data in usuarios.items():
        if data.get('hbd_alerts', False):
            recipients.append(chat_id)
    return recipients


# === UX Metrics Helper Functions ===

def get_user_meta(user_id: int, key: str, default=None):
    """
    Get user metadata value for a specific key.
    Used for UX metrics tracking and feature flags.
    """
    usuarios = cargar_usuarios()
    user_id_str = str(user_id)
    if user_id_str in usuarios:
        return usuarios[user_id_str].get(key, default)
    return default


def set_user_meta(user_id: int, key: str, value):
    """
    Set user metadata value for a specific key.
    Used for UX metrics tracking and feature flags.
    """
    usuarios = cargar_usuarios()
    user_id_str = str(user_id)
    if user_id_str not in usuarios:
        # Create new user entry if doesn't exist
        usuarios[user_id_str] = {'registered_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    
    usuarios[user_id_str][key] = value
    guardar_usuarios(usuarios)