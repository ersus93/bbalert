# utils/file_manager.py

import os
import json
from datetime import datetime
import time 
import uuid # Para generar IDs únicos si es necesario
import openpyxl
from core.config import USUARIOS_PATH, LOG_LINES, LOG_MAX, CUSTOM_ALERT_HISTORY_PATH, PRICE_ALERTS_PATH, HBD_HISTORY_PATH, ELTOQUE_HISTORY_PATH


# === Inicialización de Archivos ===
def inicializar_archivos():
    """Crea los archivos si no existen."""
    
    try:
        if not os.path.exists(CUSTOM_ALERT_HISTORY_PATH):
            with open(CUSTOM_ALERT_HISTORY_PATH, 'w', encoding='utf-8') as f:
                json.dump({}, f, indent=4) # Guardar un diccionario vacío
            add_log_line(f"✅ Archivo de historial de alertas creado en: {CUSTOM_ALERT_HISTORY_PATH}")
    except Exception as e:
        add_log_line(f"❌ ERROR al inicializar el archivo de historial de alertas: {e}")



MAX_HISTORY_ENTRIES = 500 # Limita el archivo para que no crezca indefinidamente

def load_hbd_history():
    """Carga el historial de precios desde el archivo JSON."""
    if not os.path.exists(HBD_HISTORY_PATH):
        return []
    try:
        with open(HBD_HISTORY_PATH, "r", encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return []

def save_hbd_history(history):
    """Guarda el historial de precios en el archivo JSON."""
    try:
        with open(HBD_HISTORY_PATH, "w", encoding='utf-8') as f:
            json.dump(history, f, indent=4)
    except Exception as e:
        print(f"Error al guardar el historial de HBD: {e}") # O usar add_log_line

def leer_precio_anterior_alerta():
    """Lee el precio anterior de HBD del historial JSON."""
    history = load_hbd_history()
    if not history:
        return None
    # El último registro en la lista es el más reciente
    return history[-1].get("hbd")

def guardar_precios_alerta(precios):
    """Guarda los precios actuales en el historial JSON."""
    history = load_hbd_history()

    # Prepara el nuevo registro
    nuevo_registro = {
        "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "btc": precios.get('BTC'),
        "hive": precios.get('HIVE'),
        "hbd": precios.get('HBD'),
        "ton": precios.get('TON')
    }
    
    history.append(nuevo_registro)

    # Mantiene el archivo con un tamaño manejable
    if len(history) > MAX_HISTORY_ENTRIES:
        history = history[-MAX_HISTORY_ENTRIES:]

    save_hbd_history(history)
    add_log_line("✅ Precios de alerta guardados en hbd_price_history.json")


# === Funciones Auxiliares ===

def add_log_line(linea):
    """Añade una línea al log en memoria, manteniendo el tamaño máximo LOG_MAX."""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    # Corregimos el formato para que tenga el separador " | " que esperas en cmdt.py
    LOG_LINES.append(f"[{timestamp}] | {linea}") 
    
    # 💡 CORRECCIÓN CRÍTICA: Aseguramos que la lista no exceda LOG_MAX (20)
    if len(LOG_LINES) > LOG_MAX:
        del LOG_LINES[0]
    
    # Añadido: Imprimir a la consola para depuración
    print(LOG_LINES[-1]) 


# === Funciones para manejar el historial de alertas personalizadas ===
def cargar_custom_alert_history():
    """Carga el historial de precios de alertas personalizadas desde el JSON."""
    try:
        if os.path.exists(CUSTOM_ALERT_HISTORY_PATH):
            with open(CUSTOM_ALERT_HISTORY_PATH, 'r', encoding='utf-8') as f:
                history = json.load(f)
                add_log_line("✅ Historial de alertas personalizadas cargado exitosamente.")
                return history
        else:
            return {} # Retorna vacío si el archivo no se ha creado aún
    except json.JSONDecodeError:
        add_log_line("❌ ERROR: El archivo de historial no es un JSON válido. Se inicializa un diccionario vacío.")
        return {}
    except Exception as e:
        add_log_line(f"❌ ERROR al cargar el historial de alertas: {e}. Se inicializa un diccionario vacío.")
        return {}

def guardar_custom_alert_history(history_data: dict):
    """Guarda el historial de precios de alertas personalizadas en el JSON."""
    try:
        # Usamos un bloque with para garantizar que el archivo se cierre
        with open(CUSTOM_ALERT_HISTORY_PATH, 'w', encoding='utf-8') as f:
            json.dump(history_data, f, indent=4)
    except Exception as e:
        add_log_line(f"❌ ERROR al guardar el historial de alertas: {e}")


def delete_all_alerts(user_id: int) -> bool:
    """
    Elimina todas las alertas de precio del usuario.
    Devuelve True si se eliminó al menos una alerta.
    """
    user_alerts = get_user_alerts(user_id)
    if not user_alerts:
        return False

    for alert in user_alerts:
        delete_price_alert(user_id, alert['alert_id'])
        add_log_line(f"🗑️ Alerta {alert['alert_id']} eliminada para el usuario {user_id}.")

    return True




# Llamar a la inicialización al importar el módulo
inicializar_archivos()


# === Funciones de Gestión de Usuarios ===

def cargar_usuarios():
    """Carga el diccionario de usuarios desde users.json."""
    try:
        if not os.path.exists(USUARIOS_PATH):
            return {}
        with open(USUARIOS_PATH, 'r', encoding='utf-8') as f:
            usuarios = json.load(f)
            # Asegurarse de que todos los usuarios tienen los campos necesarios
            for chat_id, data in usuarios.items():
                if 'intervalo_alerta_h' not in data:
                    data['intervalo_alerta_h'] = 1.0 # Valor por defecto: 1.0 hora
                if 'monedas' not in data:
                    data['monedas'] = [] # Valor por defecto
            return usuarios
    except (FileNotFoundError, json.JSONDecodeError) as e:
        add_log_line(f"❌ ERROR: Falló la carga o decodificación de usuarios.json: {e}")
        return {}


def set_user_language(chat_id: int, lang_code: str):
    """Guarda el código de idioma para un usuario."""
    usuarios = cargar_usuarios()
    chat_id_str = str(chat_id)
    if chat_id_str in usuarios:
        usuarios[chat_id_str]['language'] = lang_code
        guardar_usuarios(usuarios)
        add_log_line(f"Idioma de usuario {chat_id_str} cambiado a: {lang_code}")

def get_user_language(chat_id: int) -> str:
    """Obtiene el código de idioma de un usuario, por defecto 'es' (español)."""
    usuarios = cargar_usuarios()
    return usuarios.get(str(chat_id), {}).get('language', 'es') # 'es' como valor predeterminado


# === Funciones de Gestión de Alertas de Precio ===

def load_price_alerts():
    """Carga todas las alertas de precio desde price_alerts.json."""
    if not os.path.exists(PRICE_ALERTS_PATH):
        return {}
    try:
        with open(PRICE_ALERTS_PATH, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return {}

def save_price_alerts(alerts):
    """Guarda el diccionario completo de alertas de precio."""
    try:
        with open(PRICE_ALERTS_PATH, "w") as f:
            json.dump(alerts, f, indent=4)
    except Exception as e:
        add_log_line(f"Error al guardar alertas de precio: {e}")

def add_price_alert(user_id, coin, target_price):
    """
    Añade automáticamente DOS alertas para un usuario (una para 'ABOVE' y otra para 'BELOW')
    y devuelve un mensaje de estado.
    """
    alerts = load_price_alerts()
    user_id_str = str(user_id)

    if user_id_str not in alerts:
        alerts[user_id_str] = []
    
    # Alerta 1: Cuando el precio sube por encima del objetivo
    alert_above = {
        "alert_id": str(uuid.uuid4())[:8],
        "coin": coin.upper(),
        "target_price": target_price,
        "condition": "ABOVE",
        "status": "ACTIVE"
    }

    # Alerta 2: Cuando el precio baja por debajo del objetivo
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
    add_log_line(f"✅ Nuevas alertas creadas para el usuario {user_id_str}: {alert_above['alert_id']} (ABOVE), {alert_below['alert_id']} (BELOW)")
    return (f"✅ ¡Alertas creadas! Te avisaré cuando *{coin.upper()}* cruce por encima o por debajo de *${target_price:,.4f}*.")


def get_user_alerts(user_id):
    """Obtiene todas las alertas activas de un usuario."""
    alerts = load_price_alerts()
    return [a for a in alerts.get(str(user_id), []) if a['status'] == 'ACTIVE']

def delete_price_alert(user_id, alert_id):
    """Elimina una alerta específica por su ID."""
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
    """Actualiza el estado de una alerta (ej. a 'TRIGGERED')."""
    alerts = load_price_alerts()
    user_id_str = str(user_id)
    if user_id_str in alerts:
        for alert in alerts[user_id_str]:
            if alert['alert_id'] == alert_id:
                alert['status'] = new_status
                save_price_alerts(alerts)
                return True
    return False

# ... (guardar_usuarios y registrar_usuario se mantienen iguales) ...

# 💡 NUEVA FUNCIÓN: para actualizar el intervalo
def actualizar_intervalo_alerta(chat_id, new_interval_h):
    """Actualiza el intervalo de alerta (en horas) para un usuario específico y guarda los cambios."""
    usuarios = cargar_usuarios()
    chat_id_str = str(chat_id)
    if chat_id_str in usuarios:
        try:
            usuarios[chat_id_str]['intervalo_alerta_h'] = float(new_interval_h)
            guardar_usuarios(usuarios)
            add_log_line(f"✅ Intervalo de alerta actualizado para {chat_id_str} a {new_interval_h} horas.")
            return True
        except ValueError:
            # Esto no debería pasar si la validación en cmdt.py es correcta, pero es un buen control
            add_log_line(f"❌ ERROR: El valor {new_interval_h} no es un flotante válido.")
            return False
    else:
        add_log_line(f"❌ ERROR: Intento de actualizar intervalo para usuario no registrado: {chat_id_str}")
        return False
    
# === Gestión de Usuarios (JSON) ===

def cargar_usuarios():
    """Carga el diccionario de usuarios."""
    if not os.path.exists(USUARIOS_PATH):
        return {}
    try:
        with open(USUARIOS_PATH, "r") as f:
            return json.load(f)
    except Exception as e:
        add_log_line(f"Error al cargar usuarios: {e}")
        return {}

def guardar_usuarios(usuarios):
    """Guarda el diccionario de usuarios."""
    try:
        with open(USUARIOS_PATH, "w") as f:
            json.dump(usuarios, f, indent=4)
    except Exception as e:
        add_log_line(f"Error al guardar usuarios: {e}")

def registrar_usuario(chat_id, user_lang_code: str = 'es'):
    """Registra un nuevo usuario si no existe."""
    usuarios = cargar_usuarios()
    chat_id_str = str(chat_id)
    
    if chat_id_str not in usuarios: # <--- Usar chat_id_str

        # --- INICIO DE LA CORRECCIÓN DE IDIOMA ---
        lang_to_save = 'es' # Por defecto
        if user_lang_code:
            if user_lang_code.startswith('en'):
                lang_to_save = 'en'
            elif user_lang_code.startswith('pt'):
                lang_to_save = 'pt'
            elif user_lang_code.startswith('de'):
                lang_to_save = 'de'
            # Si no es ninguno, se queda como 'es'
        # --- FIN DE LA CORRECCIÓN DE IDIOMA ---

        usuarios[chat_id_str] = {
            "monedas": ["BTC", "HIVE", "HBD", "TON"], # Monedas por defecto
            "hbd_alerts": False,  # Activar alertas de HBD por defecto
            "language": lang_to_save, # <-- ¡ESTA LÍNEA ES LA SOLUCIÓN!
            "intervalo_alerta_h": 1.0 # <-- Añadir esto también es buena idea
        }
     

        guardar_usuarios(usuarios)
        add_log_line(f"Nuevo usuario registrado: {chat_id} con idioma: {lang_to_save}") # Log mejorado

def actualizar_monedas(chat_id, lista_monedas):
    """Actualiza la lista de monedas de un usuario sin borrar otras configuraciones."""
    usuarios = cargar_usuarios()
    chat_id_str = str(chat_id)
    
    if chat_id_str not in usuarios:
        usuarios[chat_id_str] = {}
        
    usuarios[chat_id_str]["monedas"] = lista_monedas
    
    guardar_usuarios(usuarios)

def obtener_monedas_usuario(chat_id):
    """Obtiene la lista de monedas de un usuario."""
    usuarios = cargar_usuarios()
    return usuarios.get(str(chat_id), {}).get("monedas", [])

def toggle_hbd_alert_status(user_id: int) -> bool:
    """
    Cambia el estado de las alertas HBD para un usuario (de true a false y viceversa).
    Devuelve el nuevo estado (True si están activadas, False si no).
    """
    usuarios = cargar_usuarios()
    user_id_str = str(user_id)
    if user_id_str in usuarios:
        # Si la clave no existe, por defecto es True, así que al negarla se vuelve False
        current_status = usuarios[user_id_str].get('hbd_alerts', False)
        new_status = not current_status
        usuarios[user_id_str]['hbd_alerts'] = new_status
        guardar_usuarios(usuarios)
        add_log_line(f"Estado de alertas HBD para {user_id_str} cambiado a: {new_status}")
        return new_status
    return False # Devuelve False si el usuario no existe


def get_hbd_alert_recipients() -> list:
    """
    Devuelve una lista de IDs de chat de los usuarios que tienen las alertas HBD activadas.
    """
    usuarios = cargar_usuarios()
    recipients = []
    for chat_id, data in usuarios.items():
        # Si la clave 'hbd_alerts' no existe, se asume que es True por retrocompatibilidad
        if data.get('hbd_alerts', False):
            recipients.append(chat_id)
    return recipients

# === Funciones para manejar el historial de ElToque ===

def load_eltoque_history():
    """Carga el historial de tasas de ElToque desde el JSON."""
    if not os.path.exists(ELTOQUE_HISTORY_PATH):
        return {}
    try:
        with open(ELTOQUE_HISTORY_PATH, "r", encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        add_log_line("⚠️ Error cargando el historial de ElToque. Se retorna vacío.")
        return {}

def save_eltoque_history(tasas_dict: dict):
    """Guarda el diccionario de tasas actual de ElToque en el JSON."""
    try:
        with open(ELTOQUE_HISTORY_PATH, "w", encoding='utf-8') as f:
            json.dump(tasas_dict, f, indent=4)
    except Exception as e:
        add_log_line(f"❌ Error al guardar el historial de ElToque: {e}")