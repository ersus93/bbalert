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
from handlers.weather import get_current_weather, get_forecast, get_uv_index, get_weather_emoji, get_daily_advice
from utils.weather_manager import load_weather_subscriptions, update_last_alert_time, should_send_alert
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


# === BUCLE DE CLIMA REESCRITO ===
async def weather_alerts_loop(bot: Bot):
    """Bucle inteligente de alertas de clima (Alertas escalonadas + Resumen Pro)."""
    
    add_log_line("🌦️ Iniciando Bucle de Clima Inteligente...")

    while True:
        try:
            subs = load_weather_subscriptions()
            if not subs:
                await asyncio.sleep(1800)  # Si no hay nadie, dormir 30 min
                continue
            
            # Recorremos usuarios
            for user_id_str, sub in subs.items():
                if not sub.get('alerts_enabled', True):
                    continue
                
                user_id = int(user_id_str)
                alert_types = sub.get('alert_types', {})
                city = sub['city']
                
                # 1. Obtener Datos
                # Nota: En producción idealmente cachearíamos esto para no llamar a la API por cada usuario de la misma ciudad
                from handlers.weather import geocode_location
                # Usamos location guardada si existe para ahorrar geocoding, sino buscamos
                lat = sub.get('lat')
                lon = sub.get('lon')
                
                if not lat or not lon:
                    loc_data = geocode_location(f"{city}, {sub['country']}")
                    if loc_data:
                        lat, lon = loc_data['lat'], loc_data['lon']
                    else:
                        continue

                forecast = get_forecast(lat, lon)
                current = get_current_weather(lat, lon)
                
                if not forecast or not current:
                    continue

                # Calcular offset horario del usuario
                utc_now = datetime.now(timezone.utc)
                tz_offset_sec = current.get("timezone", 0)
                user_now = utc_now + timedelta(seconds=tz_offset_sec)
                
                # ==========================================
                # A) LÓGICA DE ALERTAS ESCALONADAS (Lluvia/Tormenta)
                # ==========================================
                
                # Analizamos las próximas 8 horas (aprox 3 items del forecast, cada uno es 3h)
                # forecast['list'] trae datos cada 3 horas.
                
                check_rain = alert_types.get('rain', True)
                check_storm = alert_types.get('storm', True)
                
                upcoming_weather_event = None
                event_type = None
                event_time_user = None
                
                # Buscamos el PRIMER evento significativo en las próximas 9 horas
                for item in forecast.get('list', [])[:3]: 
                    w_id = item['weather'][0]['id']
                    dt_val = datetime.fromtimestamp(item['dt'], timezone.utc)
                    
                    # Filtro de tiempo: ¿Cuanto falta para este evento?
                    hours_diff = (dt_val - utc_now).total_seconds() / 3600
                    
                    if hours_diff < 0: continue # Evento pasado

                    # Detección
                    if check_storm and 200 <= w_id < 300:
                        upcoming_weather_event = item
                        event_type = 'storm'
                        event_time_user = dt_val + timedelta(seconds=tz_offset_sec)
                        break # Encontramos el más próximo, paramos
                    
                    elif check_rain and (300 <= w_id < 600):
                        upcoming_weather_event = item
                        event_type = 'rain'
                        event_time_user = dt_val + timedelta(seconds=tz_offset_sec)
                        break
                
                # Si encontramos algo, decidimos si avisar
                if upcoming_weather_event:
                    event_dt = datetime.fromtimestamp(upcoming_weather_event['dt'], timezone.utc)
                    hours_until = (event_dt - utc_now).total_seconds() / 3600
                    
                    desc = upcoming_weather_event['weather'][0]['description'].capitalize()
                    time_str = event_time_user.strftime('%H:%M')
                    
                    # 1. Alerta TEMPRANA (Pre-Aviso 4h - 8h)
                    # Usamos clave única 'rain_early' para el cooldown
                    if 3.5 <= hours_until <= 8.5:
                        alert_key = f"{event_type}_early"
                        if should_send_alert(user_id, alert_key, cooldown_hours=12):
                            emoji = "🌩️" if event_type == 'storm' else "🌦️"
                            title = "Posible Tormenta" if event_type == 'storm' else "Pronóstico de Lluvia"
                            
                            msg = _(
                                f"{emoji} *{title} (Pre-Aviso)*\n"
                                f"—————————————————\n"
                                f"Los modelos indican probabilidad de {desc} en tu zona.\n"
                                f"🕐 *Hora estimada:* Alrededor de las {time_str}\n\n"
                                f"💡 _Te aviso con tiempo para que tomes precauciones._",
                                user_id
                            )
                            await _enviar_mensaje_telegram_async_ref(msg, [user_id_str])
                            update_last_alert_time(user_id, alert_key)

                    # 2. Alerta INMINENTE (1h - 2.5h)
                    # Usamos clave única 'rain_near'
                    elif 0.5 <= hours_until < 2.5:
                        alert_key = f"{event_type}_near"
                        if should_send_alert(user_id, alert_key, cooldown_hours=4):
                            emoji = "⛈️" if event_type == 'storm' else "☔"
                            title = "Tormenta Inminente" if event_type == 'storm' else "Lluvia Inminente"
                            
                            msg = _(
                                f"{emoji} *{title} (<2h)*\n"
                                f"—————————————————\n"
                                f"Se aproxima {desc} a {city}.\n"
                                f"🕐 *Hora estimada:* {time_str} (Muy pronto)\n\n"
                                f"⚠️ _El clima puede variar localmente, pero ten precaución._",
                                user_id
                            )
                            await _enviar_mensaje_telegram_async_ref(msg, [user_id_str])
                            update_last_alert_time(user_id, alert_key)

                # ==========================================
                # B) LÓGICA DE UV ALTO
                # ==========================================
                # Obtenemos UV solo si es de día para ahorrar API calls o si la alerta está activa
                if alert_types.get('uv_high', True):
                    # Check rápido: si es entre las 10am y 4pm del usuario
                    if 10 <= user_now.hour <= 16:
                         # Solo comprobamos cada cierto tiempo (manejado por should_send_alert)
                         if should_send_alert(user_id, 'uv_high', cooldown_hours=4):
                             uv_val = get_uv_index(lat, lon)
                             if uv_val >= 6:
                                 msg = _(
                                     f"☀️ *Alerta UV Alto ({uv_val:.1f})*\n"
                                     f"El índice de radiación es alto en este momento en {city}.\n"
                                     f"🧴 Se recomienda usar protección solar.",
                                     user_id
                                 )
                                 await _enviar_mensaje_telegram_async_ref(msg, [user_id_str])
                                 update_last_alert_time(user_id, 'uv_high')

                # ==========================================
                # C) RESUMEN DIARIO INTELIGENTE
                # ==========================================
                alert_time_str = sub.get('alert_time', '07:00')
                try:
                    target_h, target_m = map(int, alert_time_str.split(':'))
                    
                    # Verificamos si es la hora exacta (con margen de 5 min)
                    if user_now.hour == target_h and 0 <= user_now.minute < 5:
                        # Para evitar enviar doble si el loop es muy rápido, usamos should_send_alert con cooldown de 20h
                        if should_send_alert(user_id, 'daily_summary', cooldown_hours=20):
                            
                            # --- PROCESAMIENTO DE DATOS PARA EL RESUMEN ---
                            # Tomamos las próximas 24h (8 items de 3h)
                            next_24h = forecast.get('list', [])[:8]
                            
                            temps = [x['main']['temp'] for x in next_24h]
                            w_ids = [x['weather'][0]['id'] for x in next_24h]
                            
                            min_temp = min(temps) if temps else current['main']['temp']
                            max_temp = max(temps) if temps else current['main']['temp']
                            
                            # Obtenemos UV máximo estimado (mediodía)
                            uv_today = get_uv_index(lat, lon) # Valor actual, aproximación
                            
                            # Generamos secciones del día
                            morning_cast = next_24h[0] if len(next_24h) > 0 else None
                            afternoon_cast = next_24h[2] if len(next_24h) > 2 else None # +6h
                            night_cast = next_24h[4] if len(next_24h) > 4 else None # +12h

                            def fmt_cast(item):
                                if not item: return "Sin datos"
                                t = item['main']['temp']
                                e = get_weather_emoji(item['weather'][0]['description'])
                                return f"{e} {t:.0f}°C"

                            # Generamos consejos
                            advice_text = get_daily_advice(min_temp, max_temp, w_ids, uv_today)

                            msg = _(
                                f"🌅 *Buenos Días, {city}*\n"
                                f"📅 *Resumen para hoy: {user_now.strftime('%d/%m')}*\n"
                                f"—————————————————\n\n"
                                f"🌡️ *Temperaturas:*\n"
                                f"   📉 Mín: *{min_temp:.0f}°C* |  📈 Máx: *{max_temp:.0f}°C*\n\n"
                                f"🕒 *Evolución:*\n"
                                f"   🌄 Mañana: {fmt_cast(morning_cast)}\n"
                                f"   ☀️ Tarde:    {fmt_cast(afternoon_cast)}\n"
                                f"   🌙 Noche:   {fmt_cast(night_cast)}\n\n"
                                f"💡 *Recomendaciones:*\n"
                                f"{advice_text}",
                                user_id
                            )
                            
                            msg += get_random_ad_text()
                            
                            await _enviar_mensaje_telegram_async_ref(msg, [user_id_str])
                            update_last_alert_time(user_id, 'daily_summary')

                except ValueError:
                    pass # Error parseando hora

            # Dormir 5 minutos (300 segundos) para ser precisos con las alertas
            await asyncio.sleep(300)

        except Exception as e:
            add_log_line(f"❌ Error en Loop Clima: {e}")
            await asyncio.sleep(60)