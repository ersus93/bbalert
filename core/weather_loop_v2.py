# core/weather_loop_v2.py - SISTEMA DE ALERTAS PROFESIONAL

import asyncio
from datetime import datetime, timedelta, timezone
from telegram import Bot
from telegram.constants import ParseMode

from utils.file_manager import add_log_line
from utils.weather_manager import weather_manager
from utils.weather_api import weather_api
from utils.ads_manager import get_random_ad_text

# Emojis
WEATHER_EMOJIS = {
    "clear": "☀️", "clouds": "☁️", "rain": "🌧️", "drizzle": "🌦️",
    "thunderstorm": "⛈️", "snow": "❄️", "mist": "🌫️", "fog": "🌁",
    "tornado": "🌪️", "haze": "😶‍🌫️", "smoke": "💨"
}

def get_emoji(desc: str) -> str:
    """Obtiene emoji según descripción."""
    for key, emoji in WEATHER_EMOJIS.items():
        if key in desc.lower():
            return emoji
    return "🌤️"

def get_smart_advice(min_temp: float, max_temp: float, weather_ids: list, uv: float) -> str:
    """Genera consejos personalizados."""
    advice = []
    
    # Lluvia/Nieve
    is_rainy = any(200 <= w < 600 for w in weather_ids)
    is_snowy = any(600 <= w < 700 for w in weather_ids)
    
    if is_snowy:
        advice.append("❄️ *Nieve:* Abrígate bien y cuidado al conducir.")
    elif is_rainy:
        advice.append("☔ *Lluvia:* No olvides el paraguas.")
    
    # Ropa según temperatura
    if max_temp >= 30:
        advice.append("👕 *Ropa:* Ropa muy ligera. ¡Hidrátate!")
    elif max_temp >= 20:
        advice.append("👕 *Ropa:* Camiseta o camisa ligera.")
    elif max_temp >= 15:
        advice.append("🧥 *Ropa:* Chaqueta ligera recomendada.")
    elif max_temp >= 10:
        advice.append("🧥 *Ropa:* Abrigo necesario.")
    elif max_temp >= 5:
        advice.append("🧣 *Ropa:* Abrigo grueso, bufanda.")
    else:
        advice.append("🧣 *Ropa:* ¡Mucho abrigo! Gorro y guantes.")
    
    # UV
    if uv >= 6:
        advice.append("🧴 *Sol:* Índice UV alto. Usa protector solar.")
    
    # Actividades
    if is_rainy:
        advice.append("🚗 *Hogar:* No es día para lavar el coche.")
    elif uv > 3 and not is_rainy:
        advice.append("🧺 *Hogar:* Buen día para secar ropa al sol.")
    
    return "\n".join(advice) if advice else "✅ *Todo tranquilo:* Disfruta tu día."

async def weather_alerts_loop(bot: Bot):
    """
    Loop principal de alertas de clima.
    
    Características:
    - Alertas de estado (lluvia, tormenta, nieve, UV)
    - Resúmenes diarios inteligentes
    - Manejo robusto de errores por usuario
    - Logs detallados
    """
    add_log_line("🌦️ Iniciando Sistema de Alertas de Clima v2...")
    
    # Esperar 30s para que el bot termine de inicializarse
    await asyncio.sleep(30)
    
    loop_count = 0
    
    while True:
        try:
            loop_count += 1
            add_log_line(f"🔄 Weather Loop Ciclo #{loop_count}")
            
            # Obtener usuarios suscritos
            user_ids = weather_manager.get_all_subscribed_users()
            
            if not user_ids:
                add_log_line("⏭️ No hay usuarios suscritos al clima")
                await asyncio.sleep(600)  # 10 minutos
                continue
            
            add_log_line(f"👥 Procesando {len(user_ids)} usuarios...")
            
            for user_id in user_ids:
                try:
                    await process_user_alerts(bot, user_id)
                
                except Exception as e:
                    # Error específico de usuario no detiene el loop
                    add_log_line(f"❌ Error procesando usuario {user_id}: {str(e)[:200]}")
                    import traceback
                    add_log_line(f"Traceback: {traceback.format_exc()[:500]}")
                    continue
                
                # Pequeña pausa entre usuarios
                await asyncio.sleep(1)
            
            add_log_line(f"✅ Weather Loop Ciclo #{loop_count} completado")
            
            # Esperar 5 minutos antes del siguiente ciclo
            await asyncio.sleep(300)
        
        except Exception as e:
            add_log_line(f"❌ Error crítico en weather_alerts_loop: {str(e)[:200]}")
            import traceback
            add_log_line(f"Traceback completo: {traceback.format_exc()[:1000]}")
            
            # Esperar 1 minuto antes de reintentar
            await asyncio.sleep(60)

async def process_user_alerts(bot: Bot, user_id: int):
    """✅ Con logs de debug mejorados."""
    sub = weather_manager.get_user_subscription(user_id)
    
    if not sub:
        add_log_line(f"⏭️ Usuario {user_id} sin suscripción")
        return
    
    if not sub.get('alerts_enabled', True):
        add_log_line(f"⏭️ Usuario {user_id} tiene alertas desactivadas")
        return
    
    # ✅ DEBUG: Verificar coordenadas
    lat = sub.get('lat')
    lon = sub.get('lon')
    city = sub.get('city', 'Ciudad')
    
    add_log_line(f"🔍 Procesando {user_id}: {city} | lat={lat}, lon={lon}")
    
    if not lat or not lon:
        add_log_line(f"❌ Usuario {user_id} sin coordenadas válidas en DB")
        return
    
    # Obtener datos del clima
    current = weather_api.get_current_weather(lat, lon)
    forecast = weather_api.get_forecast(lat, lon)
    
    if not current or not forecast:
        add_log_line(f"⚠️ No se pudo obtener clima para usuario {user_id}")
        return
    
    # Calcular hora local del usuario
    utc_now = datetime.now(timezone.utc)
    tz_offset_sec = current.get("timezone", 0)
    user_now = utc_now + timedelta(seconds=tz_offset_sec)
    
    alert_types = sub.get('alert_types', {})
    
    # ========================================
    # 1. ALERTAS DE ESTADO
    # ========================================
    
    # --- UV Alto (solo de día 10am-4pm) ---
    if alert_types.get('uv_high', True) and 10 <= user_now.hour <= 16:
        if weather_manager.should_send_alert(user_id, 'uv_high', cooldown_hours=4):
            uv_val = weather_api.get_uv_index(lat, lon)
            
            if uv_val >= 6:
                msg = (
                    f"☀️ *Alerta UV Alto*\n"
                    f"—————————————————\n"
                    f"📍 {city}\n"
                    f"📊 Índice UV: *{uv_val:.1f}*\n\n"
                    f"🧴 La radiación solar es fuerte. Usa protector solar si sales."
                )
                
                await bot.send_message(user_id, msg, parse_mode=ParseMode.MARKDOWN)
                weather_manager.mark_alert_sent(user_id, 'uv_high')
                add_log_line(f"☀️ Alerta UV enviada a {user_id}")
    
    # --- EVENTOS CLIMÁTICOS (Lluvia, Tormenta, Nieve) ---
    check_rain = alert_types.get('rain', True)
    check_storm = alert_types.get('storm', True)
    check_snow = alert_types.get('snow', True)
    
    # Analizar próximas 9 horas (3 intervalos de 3h)
    upcoming_event = None
    event_type = None
    
    for item in forecast.get('list', [])[:3]:
        w_id = item['weather'][0]['id']
        
        # Prioridad: Tormenta > Nieve > Lluvia
        if check_storm and 200 <= w_id < 300:
            upcoming_event, event_type = item, 'storm'
            break
        elif check_snow and 600 <= w_id < 700:
            upcoming_event, event_type = item, 'snow'
            break
        elif check_rain and 300 <= w_id < 600:
            upcoming_event, event_type = item, 'rain'
    
    if upcoming_event:
        dt_event = datetime.fromtimestamp(upcoming_event['dt'], timezone.utc)
        hours_until = (dt_event - utc_now).total_seconds() / 3600
        
        # Hora local del evento
        event_time_local = dt_event + timedelta(seconds=tz_offset_sec)
        time_str = event_time_local.strftime('%H:%M')
        desc = upcoming_event['weather'][0]['description'].capitalize()
        
        emoji_map = {'storm': '⛈️', 'snow': '❄️', 'rain': '🌧️'}
        title_map = {'storm': 'Tormenta', 'snow': 'Nieve/Escarcha', 'rain': 'Lluvia'}
        
        # PRE-AVISO (3.5h a 8.5h antes)
        if 3.5 <= hours_until <= 8.5:
            alert_key = f"{event_type}_early"
            
            if weather_manager.should_send_alert(user_id, alert_key, cooldown_hours=12):
                msg = (
                    f"{emoji_map[event_type]} *Posible {title_map[event_type]} (Pre-Aviso)*\n"
                    f"—————————————————\n"
                    f"📍 {city}\n"
                    f"🌦️ {desc}\n"
                    f"🕐 Hora estimada: ~{time_str}\n\n"
                    f"💡 _Te aviso con tiempo para que te organices._"
                )
                
                await bot.send_message(user_id, msg, parse_mode=ParseMode.MARKDOWN)
                weather_manager.mark_alert_sent(user_id, alert_key)
                add_log_line(f"{emoji_map[event_type]} Pre-aviso {event_type} enviado a {user_id}")
        
        # ALERTA INMINENTE (0.5h a 2.5h antes)
        elif 0.5 <= hours_until < 2.5:
            alert_key = f"{event_type}_near"
            
            if weather_manager.should_send_alert(user_id, alert_key, cooldown_hours=4):
                msg = (
                    f"⚠️ *{title_map[event_type]} Inminente (<2h)*\n"
                    f"—————————————————\n"
                    f"📍 {city}\n"
                    f"🌦️ {desc}\n"
                    f"🕐 Hora estimada: {time_str}\n\n"
                    f"☔ _Toma precauciones ahora._"
                )
                
                await bot.send_message(user_id, msg, parse_mode=ParseMode.MARKDOWN)
                weather_manager.mark_alert_sent(user_id, alert_key)
                add_log_line(f"⚠️ Alerta inminente {event_type} enviada a {user_id}")
    
    # ========================================
    # 2. RESUMEN DIARIO INTELIGENTE
    # ========================================
    
    target_time_str = sub.get('alert_time', '07:00')
    target_hour = int(target_time_str.split(':')[0])
    
    # Verificar si es hora de enviar resumen
    last_summary = weather_manager.get_last_daily_summary(user_id)
    
    # Debe ser la hora configurada Y que no se haya enviado hoy
    is_time_to_send = user_now.hour == target_hour and 0 <= user_now.minute < 10
    
    already_sent_today = False
    if last_summary:
        # Verificar si el último resumen fue hoy
        summary_date = last_summary.date()
        today = user_now.date()
        already_sent_today = (summary_date == today)
    
    if is_time_to_send and not already_sent_today:
        try:
            await send_daily_summary(bot, user_id, sub, current, forecast, user_now, tz_offset_sec)
        except Exception as e:
            add_log_line(f"❌ Error enviando resumen diario a {user_id}: {str(e)[:200]}")

async def send_daily_summary(
    bot: Bot, 
    user_id: int, 
    sub: dict, 
    current: dict, 
    forecast: dict,
    user_now: datetime,
    tz_offset_sec: int
):
    """
    Envía resumen diario contextual.
    
    Args:
        bot: Instancia del bot
        user_id: ID del usuario
        sub: Datos de suscripción
        current: Datos del clima actual
        forecast: Pronóstico extendido
        user_now: Hora local del usuario
        tz_offset_sec: Offset de zona horaria en segundos
    """
    city = sub.get('city', 'Tu ciudad')
    f_list = forecast.get('list', [])
    
    if not f_list:
        add_log_line(f"⚠️ Forecast vacío para usuario {user_id}")
        return
    
    # Determinar contexto según hora
    target_hour = int(sub.get('alert_time', '07:00').split(':')[0])
    
    header = ""
    intro = ""
    items_to_show = []
    
    # MAÑANA (05:00 - 11:59)
    if 5 <= target_hour < 12:
        header = f"☀️ *Buenos días, {city}*"
        intro = f"📅 *Pronóstico para hoy {user_now.strftime('%d/%m')}:*"
        items_to_show = f_list[:4]  # Próximas 12h
    
    # TARDE (12:00 - 18:59)
    elif 12 <= target_hour < 19:
        header = f"🌤️ *Buenas tardes, {city}*"
        intro = "📅 *Resto de hoy y mañana por la mañana:*"
        items_to_show = f_list[:5]  # Próximas 15h
    
    # NOCHE (19:00 - 04:59)
    else:
        header = f"🌙 *Buenas noches, {city}*"
        intro = "📅 *Prepárate para mañana:*"
        items_to_show = f_list[2:7]  # Saltamos noche actual
    
    # Construir cuerpo del mensaje
    body_lines = []
    temps = []
    weather_codes = []
    
    for item in items_to_show:
        item_dt = datetime.fromtimestamp(item['dt'], timezone.utc) + timedelta(seconds=tz_offset_sec)
        item_hour = item_dt.strftime('%H:%M')
        item_temp = item['main']['temp']
        item_desc = item['weather'][0]['description']
        item_emoji = get_emoji(item_desc)
        
        # Etiqueta si es mañana
        day_label = ""
        if item_dt.day != user_now.day:
            day_label = " (Mañana)"
        
        body_lines.append(
            f"▪️ `{item_hour}{day_label}`: {item_temp:.0f}°C {item_emoji} {item_desc.capitalize()}"
        )
        
        temps.append(item_temp)
        weather_codes.append(item['weather'][0]['id'])
    
    # Consejos
    lat = sub.get('lat')
    lon = sub.get('lon')
    uv_est = weather_api.get_uv_index(lat, lon)
    
    min_temp = min(temps) if temps else 0
    max_temp = max(temps) if temps else 0
    
    advice = get_smart_advice(min_temp, max_temp, weather_codes, uv_est)
    
    # Mensaje final
    msg = (
        f"{header}\n"
        f"—————————————————\n"
        f"{intro}\n\n"
        + "\n".join(body_lines) + "\n\n"
        f"💡 *Consejos:*\n{advice}\n\n"
        + get_random_ad_text()
    )
    
    await bot.send_message(user_id, msg, parse_mode=ParseMode.MARKDOWN)
    weather_manager.mark_alert_sent(user_id, 'daily_summary')
    add_log_line(f"📰 Resumen diario enviado a {user_id} ({city})")
