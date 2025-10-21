# core/loops.py

import asyncio
from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram import Bot, Update
from telegram.ext import ContextTypes, Application
from core.config import( PID, VERSION, STATE, INTERVALO_ALERTA, INTERVALO_CONTROL,
                        LOG_LINES, CUSTOM_ALERT_HISTORY_PATH, PRICE_ALERTS_PATH, USUARIOS_PATH, 
                            ADMIN_CHAT_IDS, PYTHON_VERSION, HBD_HISTORY_PATH)
from core.api_client import obtener_precios_alerta, generar_alerta, obtener_precios_control
from utils.file_manager import (
    cargar_usuarios, leer_precio_anterior_alerta, guardar_precios_alerta, add_log_line,
    load_price_alerts, update_alert_status, 
    cargar_custom_alert_history, guardar_custom_alert_history, get_hbd_alert_recipients
)

# Variable global para guardar la función de envío de mensajes y la app
_enviar_mensaje_telegram_async_ref = None
_app_ref = None
# Función para inyectar la función de envío de mensajes y la app
def set_enviar_mensaje_telegram_async(func, app: Application):
    """Permite a bbalert.py inyectar la función de envío de mensajes y la app."""
    global _enviar_mensaje_telegram_async_ref, _app_ref
    _enviar_mensaje_telegram_async_ref = func
    _app_ref = app

# Variables globales para los loops
PRECIOS_CONTROL_ANTERIORES = {} 
CUSTOM_ALERT_HISTORY = {} 

def obtener_indicador(precio_actual, precio_anterior):
    """Retorna 🔺, 🔻, o ▫️ basado en la comparación de precios."""
    if precio_anterior is None: return ""
    TOLERANCIA = 0.0000001 
    if precio_actual > precio_anterior + TOLERANCIA: return " 🔺" 
    elif precio_actual < precio_anterior - TOLERANCIA: return " 🔻" 
    else: return " ▫️"
    
def set_custom_alert_history_util(coin, price):
    global CUSTOM_ALERT_HISTORY
    if not price or price == 0:
        add_log_line(f"⚠️ Precio inválido para {coin.upper()}, no se pudo guardar en historial.")
        return
    
    CUSTOM_ALERT_HISTORY[coin.upper()] = price
    add_log_line(f"✅ Precio inicial ${price:,.4f} de {coin.upper()} guardado en historial al crear la alerta")
    guardar_custom_alert_history(CUSTOM_ALERT_HISTORY)

# === FUNCIONES DE UTILIDAD PARA EXPORTAR ===
def programar_alerta_usuario(user_id: int, intervalo_h: float):
    """Crea o reprograma el job de alerta periódica para un usuario."""
    if not _app_ref:
        add_log_line("❌ ERROR: La referencia a la aplicación (JobQueue) no está disponible.")
        return
        
    job_queue = _app_ref.job_queue
    chat_id = int(user_id)
    job_name = f"user_alert_{chat_id}"
    # Remover trabajos existentes para este usuario para evitar duplicados
    jobs = job_queue.get_jobs_by_name(job_name)
    for job in jobs:
        job.schedule_removal()
        add_log_line(f"🛠️ Job anterior '{job_name}' eliminado para reprogramación.")
    # Programar el nuevo trabajo
    job_queue.run_repeating(
        alerta_trabajo_callback,
        interval=intervalo_h * 3600,  # Convertir horas a segundos
        first=10,  # Empezar 10 segundos después de programar
        chat_id=chat_id,
        name=job_name,
        data={'enviar_mensaje_ref': _enviar_mensaje_telegram_async_ref}
    )
    add_log_line(f"✅ Job '{job_name}' programado para ejecutarse cada {intervalo_h} horas.")

def get_logs_data():
    """Devuelve las líneas de log REALES que están en memoria."""
    global LOG_LINES
    return LOG_LINES

# === TAREAS ASÍNCRONAS (LOOPS DE FONDO) ===
# Cargar el historial de alertas personalizadas al iniciar
async def check_custom_price_alerts(bot: Bot):
    """Verifica y notifica las alertas de precio personalizadas de los usuarios."""
    global CUSTOM_ALERT_HISTORY
    # Cargar el historial de alertas personalizadas desde el archivo al iniciar
    CUSTOM_ALERT_HISTORY = cargar_custom_alert_history()
    add_log_line(f"Historial de alertas personalizadas cargado. {len(CUSTOM_ALERT_HISTORY)} monedas en memoria.")

    while True:
        try:
            active_alerts = load_price_alerts()
            if not active_alerts:
                await asyncio.sleep(INTERVALO_CONTROL)
                continue

            coins_to_check = set(alert['coin'] for user_alerts in active_alerts.values() for alert in user_alerts if alert['status'] == 'ACTIVE')
            if not coins_to_check:
                await asyncio.sleep(INTERVALO_CONTROL)
                continue

            current_prices = obtener_precios_control(list(coins_to_check))
            if not current_prices:
                add_log_line("⚠️ No se pudieron obtener precios para alertas personalizadas.")
                await asyncio.sleep(INTERVALO_CONTROL)
                continue

            for user_id, user_alerts in active_alerts.items():
                for alert in user_alerts:
                    if alert['status'] != 'ACTIVE':
                        continue

                    coin = alert['coin']
                    current_price = current_prices.get(coin)
                    previous_price = CUSTOM_ALERT_HISTORY.get(coin)
                    
                    if current_price is None or previous_price is None:
                        continue 

                    target_price = alert['target_price']
                    condition = alert['condition']
                    triggered = False
                    message = ""

                    if condition == 'ABOVE' and previous_price < target_price and current_price >= target_price:
                        triggered = True
                        message = f"📈 ¡Alerta de Precio! 📈\n\n*{coin}* ha *SUPERADO* tu objetivo de *${target_price:,.4f}*.\n\nPrecio actual: *${current_price:,.4f}*"
                    elif condition == 'BELOW' and previous_price > target_price and current_price <= target_price:
                        triggered = True
                        message = f"📉 ¡Alerta de Precio! 📉\n\n*{coin}* ha *CAÍDO POR DEBAJO* de tu objetivo de *${target_price:,.4f}*.\n\nPrecio actual: *${current_price:,.4f}*"

                    if triggered:
                        keyboard = [[InlineKeyboardButton("🗑️ Borrar esta alerta", callback_data=f"delete_alert_{alert['alert_id']}")]]
                        reply_markup = InlineKeyboardMarkup(keyboard)
                        await _enviar_mensaje_telegram_async_ref(message, [user_id], reply_markup=reply_markup)
                        
                        add_log_line(
                            f"🔔 Alerta notificada a {user_id} para {coin}. "
                            f"(Cruce: {previous_price:.4f} -> {current_price:.4f} vs Target: {target_price:.4f})"
                        )
              
            for coin, price in current_prices.items():
                CUSTOM_ALERT_HISTORY[coin] = price
                
            guardar_custom_alert_history(CUSTOM_ALERT_HISTORY)

            add_log_line("✅ Historial de precios de alertas personalizadas (en memoria) actualizado.")
            
        except Exception as e:
            add_log_line(f"🚨 ERROR en check_custom_price_alerts: {e}")

        await asyncio.sleep(INTERVALO_CONTROL)

async def alerta_loop(bot: Bot):
    """Bucle de alerta HBD (cada N segundos)."""
    while True:
        try:
            precios_actuales = obtener_precios_alerta()

            if precios_actuales and precios_actuales.get('HBD') is not None:
                precio_anterior_hbd = leer_precio_anterior_alerta()
                guardar_precios_alerta(precios_actuales)

                if precio_anterior_hbd:
                    alerta_msg, log_msg = generar_alerta(precios_actuales, precio_anterior_hbd)
                    if alerta_msg:
                       
                        # 1. Obtener solo los usuarios que quieren la alerta
                        recipients = get_hbd_alert_recipients()

                        if not recipients:
                            if log_msg: add_log_line(f"{log_msg} (No se envió a nadie)")
                            continue # Salta el resto del bucle si no hay nadie a quien notificar

                        # 2. Crear el botón interactivo
                        keyboard = [[
                            InlineKeyboardButton("🔕 Desactivar estas alertas", callback_data="toggle_hbd_alerts")
                        ]]
                        reply_markup = InlineKeyboardMarkup(keyboard)

                        # 3. Enviar el mensaje a los destinatarios con el botón
                        await _enviar_mensaje_telegram_async_ref(alerta_msg, recipients, reply_markup=reply_markup)

                    
                    if log_msg:
                         add_log_line(log_msg)
            else:
                add_log_line("❌ Falló la obtención o validación del precio de HBD.")

        except Exception as e:
            add_log_line(f"Error crítico en alerta_loop: {e}")

        await asyncio.sleep(INTERVALO_ALERTA)

# === Función de callback para JobQueue de usuarios ===
async def alerta_trabajo_callback(context: ContextTypes.DEFAULT_TYPE):
    """Función de callback del JobQueue para enviar la alerta de precios periódica."""
    chat_id_str = str(context.job.chat_id) 
    enviar_mensaje_ref = context.job.data.get('enviar_mensaje_ref')
    
    usuarios = cargar_usuarios()
    datos_usuario = usuarios.get(chat_id_str)

    if not datos_usuario:
        add_log_line(f"⚠️ JobQueue: Usuario {chat_id_str} no encontrado. Removiendo job.")
        context.job.schedule_removal() 
        return

    monedas = datos_usuario.get("monedas", [])
    intervalo_h = datos_usuario.get("intervalo_alerta_h", 1.0) 
    
    if not monedas:
        return

    precios_actuales_usuario = obtener_precios_control(monedas) 

    if not precios_actuales_usuario:
        add_log_line(f"❌ Falló obtención de precios para usuario {chat_id_str}.")
        return

    mensaje = f"📊 *Alerta de tus monedas ({intervalo_h}h):*\n\n"
    precios_anteriores_usuario = PRECIOS_CONTROL_ANTERIORES.get(chat_id_str, {})
    precios_para_guardar = {} 
    
    for m in monedas:
        p_actual = precios_actuales_usuario.get(m)
        p_anterior = precios_anteriores_usuario.get(m)
        
        if p_actual:
            indicador = obtener_indicador(p_actual, p_anterior) 
            mensaje += f"*{m}/USD*: ${p_actual:.4f}{indicador}\n"
            precios_para_guardar[m] = p_actual
    
    mensaje += (
        f"\n📅 Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        f"_🔰 Alerta configurada cada {intervalo_h} horas._"
    )
    
    if enviar_mensaje_ref:
        # 1. Capturamos el resultado del envío
        fallidos = await enviar_mensaje_ref(mensaje, [chat_id_str], parse_mode=ParseMode.MARKDOWN)

    # 2. Comprobamos si el envío para este chat_id falló
    if chat_id_str not in fallidos:
        PRECIOS_CONTROL_ANTERIORES[chat_id_str] = precios_para_guardar
        add_log_line(f"✅ Alerta de control enviada a {chat_id_str} con intervalo {intervalo_h}h.")
    # Si falló, el log de error ya fue registrado por la función 'enviar_mensajes',
    # así que no necesitamos hacer nada más aquí.

    # --- FIN DE LA MODIFICACIÓN ---
    else:
        add_log_line(f"❌ ERROR: Referencia de envío no disponible para {chat_id_str}.")