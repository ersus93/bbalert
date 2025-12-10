# core/loops.py

import asyncio
from datetime import datetime, timedelta
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
from handlers.weather import get_weather_emoji
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
                    recipients = get_hbd_alert_recipients()
                    if recipients:
                        log_msg_to_send = None
                        trigger_detected = False
                        
                        for user_id_str in recipients:
                            user_id = int(user_id_str)
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
                                    [user_id_str], 
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


# Weather alert manager
async def weather_alerts_loop(bot: Bot):
    """Bucle de fondo para alertas de clima."""
    from utils.weather_manager import load_weather_subscriptions, update_last_alert_time, should_send_alert
    from handlers.weather import get_current_weather, get_forecast, get_uv_index
    
    while True:
        try:
            subs = load_weather_subscriptions()
            if not subs:
                await asyncio.sleep(1800)  # 30 minutos
                continue
            
            for user_id_str, sub in subs.items():
                if not sub.get('alerts_enabled', True):
                    continue
                
                user_id = int(user_id_str)
                alert_types = sub.get('alert_types', {})
                
                # Obtener ubicación
                city = sub['city']
                country = sub['country']
                
                # Geocodificar (simplificado - en producción cachear)
                from handlers.weather import geocode_location
                location = geocode_location(f"{city}, {country}")
                
                if not location:
                    continue
                
                # Obtener datos del clima
                current = get_current_weather(location['lat'], location['lon'])
                forecast = get_forecast(location['lat'], location['lon'])
                uv_index = get_uv_index(location['lat'], location['lon'])
                
                if not current or not forecast:
                    continue
                
                # Verificar lluvia
                if alert_types.get('rain', True) and should_send_alert(user_id, 'rain'):
                    for entry in forecast.get('list', [])[:4]:
                        weather_code = entry['weather'][0]['id']
                        if weather_code < 600:
                            time_str = datetime.fromtimestamp(entry['dt']).strftime('%H:%M')
                            message = _(
                                f"🌧️ *Alerta de Lluvia en {city}*\n"
                                f"—————————————————\n"
                                f"Se espera lluvia alrededor de las {time_str}.\n"
                                f"Intensidad: {entry['weather'][0]['description']}\n\n"
                                f"☔ ¡Paraguas recomendado!",
                                user_id
                            )
                            # --- INYECCIÓN DE ANUNCIO ---
                            message += get_random_ad_text()
                            # ----------------------------
                            
                            await _enviar_mensaje_telegram_async_ref(message, [user_id_str])
                            update_last_alert_time(user_id, 'rain')
                            break
                
                # Verificar UV
                if alert_types.get('uv_high', True) and uv_index >= 6 and should_send_alert(user_id, 'uv_high'):
                    message = _(
                        f"☀️ *Alerta UV Alto en {city}*\n"
                        f"—————————————————\n"
                        f"Índice UV actual: {uv_index:.1f} (Alto)\n"
                        f"🧴 Usa protector solar.",
                        user_id
                    )
                    # --- INYECCIÓN DE ANUNCIO ---
                    message += get_random_ad_text()
                    # ----------------------------

                    await _enviar_mensaje_telegram_async_ref(message, [user_id_str])
                    update_last_alert_time(user_id, 'uv_high')

                # Verificar Tormenta
                if alert_types.get('storm', True) and should_send_alert(user_id, 'storm'):
                    for entry in forecast.get('list', []):
                        weather_code = entry['weather'][0]['id']
                        if 200 <= weather_code < 300:
                            message = _(
                                f"⛈️ *Alerta de Tormenta en {city}*\n"
                                f"—————————————————\n"
                                f"Se acercan condiciones de tormenta.\n"
                                f"⚠️ Toma precauciones.",
                                user_id
                            )
                            # --- INYECCIÓN DE ANUNCIO ---
                            message += get_random_ad_text()
                            # ----------------------------

                            await _enviar_mensaje_telegram_async_ref(message, [user_id_str])
                            update_last_alert_time(user_id, 'storm')
                            break
                
                # Enviar resumen diario a la hora configurada
                alert_time = sub.get('alert_time', '07:00')
                try:
                    alert_hour, alert_minute = map(int, alert_time.split(':'))
                    
                    # Obtener hora actual en UTC
                    utc_now = datetime.utcnow()
                    
                    # Aplicar diferencia horaria (simplificado)
                    timezone_str = sub.get('timezone', 'UTC+0')
                    if timezone_str.startswith('UTC'):
                        try:
                            offset = int(timezone_str[3:])
                            local_hour = (utc_now.hour + offset) % 24
                            
                            # Verificar si es hora de enviar resumen
                            if local_hour == alert_hour and utc_now.minute < 5:
                                # Crear resumen diario
                                today_forecast = forecast.get('list', [])[:8]  # 24 horas
                                
                                message = _(
                                    f"🌅 *Resumen Climático Diario - {city}*\n"
                                    f"—————————————————\n"
                                    f"Fecha: {utc_now.strftime('%Y-%m-%d')}\n"
                                    f"Hora local: {alert_time}\n\n",
                                    user_id
                                )
                                
                                # Añadir condiciones principales
                                message += f"*Condición actual:* {current['weather'][0]['description'].capitalize()}\n"
                                message += f"*Temperatura:* {current['main']['temp']:.1f}°C\n"
                                message += f"*Humedad:* {current['main']['humidity']}%\n"
                                message += f"*Viento:* {current['wind']['speed']:.1f} m/s\n\n"
                                
                                message += _("*Pronóstico hoy:*\n", user_id)
                                for i, entry in enumerate(today_forecast[:4]):  # Próximas 12 horas
                                    time = datetime.fromtimestamp(entry['dt']).strftime('%H:%M')
                                    temp = entry['main']['temp']
                                    desc = entry['weather'][0]['description']
                                    emoji = get_weather_emoji(desc)
                                    message += f"  {time}: {temp:.0f}°C {emoji} {desc}\n"
                                
                                message += _("\n💡 *Recomendaciones del día:*\n", user_id)
                                
                                # Recomendaciones basadas en condiciones
                                if uv_index > 6:
                                    message += "• ☀️ Protector solar recomendado\n"
                                if any('rain' in entry['weather'][0]['description'].lower() for entry in today_forecast):
                                    message += "• 🌧️ Lleva paraguas\n"
                                if current['main']['temp'] < 19:
                                    message += "• 🧥 Abrígate bien\n"
                                if current['main']['temp'] > 30:
                                    message += "• 🥤 Mantente hidratado\n"
                                
                                message += get_random_ad_text()
                                
                                await _enviar_mensaje_telegram_async_ref(message, [user_id_str])
                                
                        except:
                            pass
                            
                except:
                    pass
            
            # Esperar 5 minutos antes de la siguiente verificación
            await asyncio.sleep(300)
            
        except Exception as e:
            add_log_line(f"Error en weather_alerts_loop: {e}")
            await asyncio.sleep(60)