# core/loops.py

import asyncio
from datetime import datetime, timedelta, timezone
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram import Bot, Update
from telegram.ext import ContextTypes, Application
from utils.ads_manager import get_random_ad_text
from core.config import( PID, VERSION, STATE, INTERVALO_ALERTA, INTERVALO_CONTROL,
                        LOG_LINES, CUSTOM_ALERT_HISTORY_PATH, PRICE_ALERTS_PATH, USUARIOS_PATH, 
                            ADMIN_CHAT_IDS, PYTHON_VERSION, HBD_HISTORY_PATH)
from core.api_client import obtener_precios_alerta, generar_alerta, obtener_precios_control
from utils.file_manager import (
    cargar_usuarios, leer_precio_anterior_alerta, guardar_precios_alerta, add_log_line,
    load_price_alerts, update_alert_status, 
    cargar_custom_alert_history, guardar_custom_alert_history, get_hbd_alert_recipients,
    load_last_prices_status, save_last_prices_status, update_last_alert_timestamp
)

from core.i18n import _ # <-- Importar _

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
PRECIOS_CONTROL_ANTERIORES = load_last_prices_status()
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
    """
    Crea o reprograma el job de alerta periódica.
    Calcula el tiempo restante basado en la última alerta enviada para no reiniciar el ciclo.
    """
    if not _app_ref:
        add_log_line("❌ ERROR: La referencia a la aplicación (JobQueue) no está disponible.")
        return
        
    job_queue = _app_ref.job_queue
    chat_id = int(user_id)
    chat_id_str = str(chat_id)
    job_name = f"user_alert_{chat_id}"
    
    # Remover trabajos existentes
    jobs = job_queue.get_jobs_by_name(job_name)
    for job in jobs:
        job.schedule_removal()
    
    # --- LÓGICA DE PERSISTENCIA DE TIEMPO ---
    usuarios = cargar_usuarios() #
    user_data = usuarios.get(chat_id_str, {})
    last_timestamp_str = user_data.get('last_alert_timestamp')
    
    intervalo_segundos = intervalo_h * 3600
    first_run_delay = 10 # Por defecto: 10 segundos (si es usuario nuevo)

    if last_timestamp_str:
        try:
            last_run = datetime.strptime(last_timestamp_str, '%Y-%m-%d %H:%M:%S')
            next_run = last_run + timedelta(seconds=intervalo_segundos)
            now = datetime.now()
            
            # Calculamos cuántos segundos faltan para la siguiente ejecución
            remaining_seconds = (next_run - now).total_seconds()
            
            if remaining_seconds > 0:
                # Si falta tiempo, esperamos exactamente eso
                first_run_delay = remaining_seconds
                add_log_line(f"⏱️ Restaurando ciclo para {chat_id}: Próxima alerta en {remaining_seconds/60:.1f} min.")
            else:
                # Si el tiempo ya pasó (el bot estuvo apagado mucho tiempo),
                # ejecutamos casi de inmediato para "ponernos al día".
                first_run_delay = 5 
                add_log_line(f"⏱️ Alerta atrasada para {chat_id}. Se enviará en 5s.")
        except Exception as e:
            add_log_line(f"⚠️ Error calculando tiempo restante para {chat_id}: {e}. Usando default.")
            first_run_delay = 10
    else:
        # Si no hay registro previo, es la primera vez o actualización nueva
        add_log_line(f"🆕 Iniciando nuevo ciclo de alertas para {chat_id} en 10s.")

    # Programar el nuevo trabajo
    job_queue.run_repeating(
        alerta_trabajo_callback,
        interval=intervalo_segundos,
        first=first_run_delay,  # <--- Usamos el tiempo calculado
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

            for user_id_str, user_alerts in active_alerts.items():
                user_id = int(user_id_str) # <-- Obtener user_id como int
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
                        # --- PLANTILLA ENVUELTA ---
                        message_template = _(
                            "📈 ¡Alerta de Precio! 📈\n—————————————————\n\n"
                            "*{coin}* ha *SUPERADO* tu objetivo de *${target_price:,.4f}*.\n\n"
                            "Precio actual: *${current_price:,.4f}*",
                            user_id
                        )
                        message = message_template.format(
                            coin=coin,
                            target_price=target_price,
                            current_price=current_price
                        )
                    elif condition == 'BELOW' and previous_price > target_price and current_price <= target_price:
                        triggered = True
                        # --- PLANTILLA ENVUELTA ---
                        message_template = _(
                            "📉 ¡Alerta de Precio! 📉\n—————————————————\n\n"
                            "*{coin}* ha *CAÍDO POR DEBAJO* de tu objetivo de *${target_price:,.4f}*.\n\n"
                            "Precio actual: *${current_price:,.4f}*",
                            user_id
                        )
                        message = message_template.format(
                            coin=coin,
                            target_price=target_price,
                            current_price=current_price
                        )

                    if triggered:
                        # --- CORRECCIÓN: INYECCIÓN DE ANUNCIO ---
                        # Se mueve aquí para que aplique a ambos casos y se corrige 'messaje' a 'message'
                        message += get_random_ad_text() 
                        # ----------------------------------------

                        # --- TEXTO DE BOTÓN ENVUELTO ---
                        button_text = _("🗑️ Borrar esta alerta", user_id)
                        keyboard = [[InlineKeyboardButton(button_text, callback_data=f"delete_alert_{alert['alert_id']}")]]
                        reply_markup = InlineKeyboardMarkup(keyboard)
                        
                        await _enviar_mensaje_telegram_async_ref(message, [user_id], reply_markup=reply_markup)

                        # Mark alert as TRIGGERED to prevent infinite loop
                        update_alert_status(user_id, alert['alert_id'], 'TRIGGERED')
                        
                        add_log_line(
                            f"🔔 Alerta notificada a {user_id} para {coin}. "
                            f"(Cruce: {previous_price:.4f} -> {current_price:.4f} vs Target: {target_price:.4f})"
                        )
                        add_log_line(f"🔔 Alerta {alert['alert_id']} marcada como TRIGGERED.")
              
            for coin, price in current_prices.items():
                CUSTOM_ALERT_HISTORY[coin] = price
                
            guardar_custom_alert_history(CUSTOM_ALERT_HISTORY)

            add_log_line("✅ Historial de precios de alertas personalizadas (en memoria) actualizado.")
            
        except Exception as e:
            add_log_line(f"🚨 ERROR en check_custom_price_alerts: {e}")

        await asyncio.sleep(INTERVALO_CONTROL)

async def alerta_loop(bot: Bot):
    """Bucle de alerta HBD (cada N segundos)."""
    
    # 1. DIAGNÓSTICO: Imprimir el intervalo al iniciar para ver si es 0
    add_log_line(f"⏱️ Iniciando bucle HBD. Intervalo configurado: {INTERVALO_ALERTA} segundos.")

    while True:
        try:
            precios_actuales = obtener_precios_alerta()

            if precios_actuales and precios_actuales.get('HBD') is not None:
                precio_anterior_hbd = leer_precio_anterior_alerta()
                guardar_precios_alerta(precios_actuales)

                if precio_anterior_hbd:
                    # --- INICIO DE LA MODIFICACIÓN (I18N) ---
                    # get_hbd_alert_recipients() returns list of int
                    recipients = get_hbd_alert_recipients()
                    if recipients:
                        log_msg_to_send = None
                        trigger_detected = False

                        for user_id in recipients:
                            # user_id is already int, convert to str for message sending
                            alerta_msg, log_msg = generar_alerta(precios_actuales, precio_anterior_hbd, user_id)

                            if alerta_msg:
                                # --- INYECCIÓN DE ANUNCIO ---
                                alerta_msg += get_random_ad_text()
                                # ----------------------------
                                trigger_detected = True
                                if not log_msg_to_send:
                                    log_msg_to_send = log_msg

                                button_text = _("🔕 Desactivar estas alertas", user_id)
                                keyboard = [[
                                    InlineKeyboardButton(button_text, callback_data="toggle_hbd_alerts")
                                ]]
                                reply_markup = InlineKeyboardMarkup(keyboard)

                                await _enviar_mensaje_telegram_async_ref(
                                    alerta_msg,
                                    [str(user_id)],  # Convert int to str for sending
                                    reply_markup=reply_markup
                                )
                        
                        if trigger_detected and log_msg_to_send:
                            add_log_line(log_msg_to_send)
                        
            else:
                add_log_line("❌ Falló la obtención o validación del precio de HBD (o API agotada).")

        except Exception as e:
            add_log_line(f"Error crítico en alerta_loop: {e}")

        # 2. SEGURIDAD: Asegurar que el intervalo sea al menos 60 segundos
        tiempo_espera = INTERVALO_ALERTA
        if not isinstance(tiempo_espera, (int, float)) or tiempo_espera < 60:
            add_log_line(f"⚠️ ADVERTENCIA: INTERVALO_ALERTA es demasiado bajo ({tiempo_espera}). Forzando a 300s.")
            tiempo_espera = 300

        await asyncio.sleep(tiempo_espera)

# === Función de callback para JobQueue de usuarios ===
async def alerta_trabajo_callback(context: ContextTypes.DEFAULT_TYPE):
    """Función de callback del JobQueue para enviar la alerta de precios periódica."""
    chat_id = int(context.job.chat_id) 
    chat_id_str = str(chat_id) 
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

    mensaje_template = _("📊 *Alerta de tus monedas ({intervalo_h}h):*\n—————————————————\n\n", chat_id)
    mensaje = mensaje_template.format(intervalo_h=intervalo_h)
    
    precios_anteriores_usuario = PRECIOS_CONTROL_ANTERIORES.get(chat_id_str, {})
    precios_para_guardar = {} 
    
    for m in monedas:
        p_actual = precios_actuales_usuario.get(m)
        p_anterior = precios_anteriores_usuario.get(m)
        
        if p_actual:
            indicador = obtener_indicador(p_actual, p_anterior) 
            mensaje += f"*{m}/USD*: ${p_actual:.4f}{indicador}\n"
            precios_para_guardar[m] = p_actual
    
    current_time_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    mensaje_footer_template = _(
        "\n—————————————————\n📅 Fecha: {fecha}\n"
        "_🔰 Alerta configurada cada {intervalo_h} horas._",
        chat_id
    )
    mensaje += mensaje_footer_template.format(
        fecha=current_time_str,
        intervalo_h=intervalo_h
    )
    
    mensaje += get_random_ad_text()
    
    fallidos = {}
    if enviar_mensaje_ref:
        fallidos = await enviar_mensaje_ref(mensaje, [chat_id_str], parse_mode=ParseMode.MARKDOWN) #

    if chat_id_str not in fallidos:
        # 1. Actualizamos la memoria RAM para uso inmediato (precios anteriores)
        PRECIOS_CONTROL_ANTERIORES[chat_id_str] = precios_para_guardar
        save_last_prices_status(PRECIOS_CONTROL_ANTERIORES)
        
        # 2. NUEVO: Guardar el timestamp de éxito para persistencia del temporizador
        update_last_alert_timestamp(chat_id) # <--- AQUÍ GUARDAMOS LA HORA
        
        add_log_line(f"✅ Alerta enviada a {chat_id_str}. Precios y timestamp guardados.")
    else:
        add_log_line(f"❌ ERROR: Referencia de envío no disponible o fallo para {chat_id_str}.")
        