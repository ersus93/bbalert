# core/weather_loop_v2.py - VERSIÓN v3.1 (FIX TIMEZONE + ANTI-SPAM)

import asyncio
from datetime import datetime, timedelta, timezone
from telegram import Bot
from telegram.constants import ParseMode

from utils.file_manager import add_log_line
from utils.weather_manager import (
    weather_manager,
    should_send_alert_advanced,
    mark_alert_sent_advanced
)
from utils.weather_api import weather_api
from utils.ads_manager import get_random_ad_text

# Emojis
WEATHER_EMOJIS = {
    "clear": "☀️", "clouds": "☁️", "rain": "🌧️", "drizzle": "🌦️",
    "thunderstorm": "⛈️", "snow": "❄️", "mist": "🌫️", "fog": "🌁",
    "tornado": "🌪️", "haze": "😶‍🌫️", "smoke": "💨"
}

# ========================================
# CONFIGURACIÓN DE VENTANAS TEMPORALES v3
# ========================================
PRE_WARNING_MIN_HOURS = 6.0
PRE_WARNING_MAX_HOURS = 8.0
IMMINENT_MIN_HOURS = 0.5  # 30 minutos
IMMINENT_MAX_HOURS = 2.0

# Cooldowns
PRE_WARNING_COOLDOWN = 18
IMMINENT_COOLDOWN = 6
UV_COOLDOWN = 8
DAILY_SUMMARY_COOLDOWN = 20

def get_emoji(desc: str) -> str:
    """Obtiene emoji según descripción."""
    for key, emoji in WEATHER_EMOJIS.items():
        if key in desc.lower():
            return emoji
    return "🌤️"

def get_smart_advice(min_temp, max_temp, weather_ids, uv):
    """Genera consejos personalizados."""
    advice = []
    
    is_rainy = any(200 <= w < 600 for w in weather_ids)
    is_snowy = any(600 <= w < 700 for w in weather_ids)
    
    if is_snowy:
        advice.append("❄️ *Nieve:* Abrígate bien y cuidado al conducir.")
    elif is_rainy:
        advice.append("☔ *Lluvia:* No olvides el paraguas.")
    
    if max_temp >= 30:
        advice.append("👕 *Ropa:* Ropa muy ligera. ¡Hidrátate!")
    elif max_temp >= 20:
        advice.append("👕 *Ropa:* Camiseta o camisa ligera.")
    elif max_temp >= 15:
        advice.append("🧥 *Ropa:* Chaqueta ligera recomendada.")
    elif max_temp >= 10:
        advice.append("🧥 *Ropa:* Abrigo necesario.")
    else:
        advice.append("🧣 *Ropa:* ¡Mucho abrigo! Gorro y guantes.")
    
    if uv >= 6:
        advice.append("🧴 *Sol:* Índice UV alto. Usa protector solar.")
    
    if is_rainy:
        advice.append("🚗 *Hogar:* No es día para lavar el coche.")
    elif uv > 3 and not is_rainy:
        advice.append("🧺 *Hogar:* Buen día para secar ropa al sol.")
    
    return "\n".join(advice) if advice else "✅ *Todo tranquilo:* Disfruta tu día."

async def weather_alerts_loop(bot: Bot):
    """Loop principal de alertas con sistema v3."""
    add_log_line("🌦️ Iniciando Sistema de Alertas de Clima v3 (Anti-Spam Total)...")
    
    await asyncio.sleep(30)
    
    loop_count = 0
    
    while True:
        try:
            loop_count += 1
            add_log_line(f"🔄 Weather Loop Ciclo #{loop_count}")
            
            user_ids = weather_manager.get_all_subscribed_users()
            
            if not user_ids:
                add_log_line("⏭️ No hay usuarios suscritos")
                await asyncio.sleep(600)
                continue
            
            add_log_line(f"👥 Procesando {len(user_ids)} usuarios...")
            
            for user_id in user_ids:
                try:
                    await process_user_alerts(bot, user_id)
                
                except Exception as e:
                    add_log_line(f"❌ Error procesando usuario {user_id}: {str(e)[:200]}")
                    import traceback
                    add_log_line(f"Traceback: {traceback.format_exc()[:500]}")
                    continue
                
                await asyncio.sleep(1)
            
            add_log_line(f"✅ Weather Loop Ciclo #{loop_count} completado")
            
            await asyncio.sleep(300)  # 5 minutos
        
        except Exception as e:
            add_log_line(f"❌ Error crítico en weather_alerts_loop: {str(e)[:200]}")
            import traceback
            add_log_line(f"Traceback completo: {traceback.format_exc()[:1000]}")
            
            await asyncio.sleep(60)

async def process_user_alerts(bot: Bot, user_id: int):
    """Procesa alertas con sistema v3 anti-spam."""
    sub = weather_manager.get_user_subscription(user_id)
    
    if not sub or not sub.get('alerts_enabled', True):
        return
    
    lat = sub.get('lat')
    lon = sub.get('lon')
    city = sub.get('city', 'Ciudad')
    
    if not lat or not lon:
        add_log_line(f"❌ Usuario {user_id} sin coordenadas")
        return
    
    current = weather_api.get_current_weather(lat, lon)
    forecast = weather_api.get_forecast(lat, lon)
    
    if not current or not forecast:
        add_log_line(f"⚠️ No se pudo obtener clima para {user_id}")
        return
    
    utc_now = datetime.now(timezone.utc)
    tz_offset_sec = current.get("timezone", 0)
    user_now = utc_now + timedelta(seconds=tz_offset_sec)
    
    alert_types = sub.get('alert_types', {})
    
    # ========================================
    # 1. ALERTA UV (MEJORADA)
    # ========================================
    if alert_types.get('uv_high', True) and 10 <= user_now.hour <= 16:
        uv_val = weather_api.get_uv_index(lat, lon)
        
        if uv_val >= 6:
            should_send, reason = should_send_alert_advanced(
                user_id,
                'uv_high',
                event_time=user_now,
                cooldown_hours=UV_COOLDOWN,
                weather_id=800,
                event_desc=f"UV {uv_val:.1f}"
            )
            
            if should_send:
                msg = (
                    f"☀️ *Alerta UV Alto*\n"
                    f"—————————————————\n"
                    f"📍 {city}\n"
                    f"📊 Índice UV: *{uv_val:.1f}*\n\n"
                    f"🧴 La radiación solar es fuerte. Usa protector solar si sales."
                )
                
                await bot.send_message(user_id, msg, parse_mode=ParseMode.MARKDOWN)
                
                mark_alert_sent_advanced(
                    user_id,
                    'uv_high',
                    event_time=user_now,
                    weather_id=800,
                    event_desc=f"UV {uv_val:.1f}"
                )
                
                add_log_line(f"☀️ Alerta UV enviada a {user_id}")
            else:
                add_log_line(f"🚫 UV bloqueado: {reason}")
    
    # ========================================
    # 2. EVENTOS CLIMÁTICOS (SISTEMA v3)
    # ========================================
    check_rain = alert_types.get('rain', True)
    check_storm = alert_types.get('storm', True)
    check_snow = alert_types.get('snow', True)
    
    processed_event_ids = set()
    
    for item in forecast.get('list', [])[:16]:
        w_id = item['weather'][0]['id']
        
        event_type = None
        if check_storm and 200 <= w_id < 300:
            event_type = 'storm'
        elif check_snow and 600 <= w_id < 700:
            event_type = 'snow'
        elif check_rain and 300 <= w_id < 600:
            event_type = 'rain'
        
        if not event_type:
            continue
        
        dt_event = datetime.fromtimestamp(item['dt'], timezone.utc)
        desc = item['weather'][0]['description'].capitalize()
        
        hours_until = (dt_event - utc_now).total_seconds() / 3600
        
        if hours_until < -0.5 or hours_until > 48:
            continue
        
        from utils.weather_manager import WeatherAlertManager
        event_unique_id = WeatherAlertManager.generate_event_id(
            user_id, event_type, dt_event, w_id, lat, lon
        )
        
        if event_unique_id in processed_event_ids:
            continue
        
        processed_event_ids.add(event_unique_id)
        
        event_time_local = dt_event + timedelta(seconds=tz_offset_sec)
        time_str = event_time_local.strftime('%H:%M')
        
        emoji_map = {'storm': '⛈️', 'snow': '❄️', 'rain': '🌧️'}
        title_map = {'storm': 'Tormenta', 'snow': 'Nieve/Escarcha', 'rain': 'Lluvia'}
        
        # PRE-AVISO (6h a 8h antes)
        if PRE_WARNING_MIN_HOURS <= hours_until <= PRE_WARNING_MAX_HOURS:
            alert_key = f"{event_type}_early"
            
            should_send, reason = should_send_alert_advanced(
                user_id,
                alert_key,
                event_time=dt_event,
                cooldown_hours=PRE_WARNING_COOLDOWN,
                weather_id=w_id,
                event_desc=desc[:30]
            )
            
            if should_send:
                msg = (
                    f"{emoji_map[event_type]} *Posible {title_map[event_type]} (Pre-Aviso)*\n"
                    f"—————————————————\n"
                    f"📍 {city}\n"
                    f"🌦️ {desc}\n"
                    f"🕐 Hora estimada: ~{time_str}\n"
                    f"⏰ En aproximadamente {hours_until:.1f} horas\n\n"
                    f"💡 _Te aviso con tiempo para que te organices._"
                )
                
                await bot.send_message(user_id, msg, parse_mode=ParseMode.MARKDOWN)
                
                mark_alert_sent_advanced(
                    user_id,
                    alert_key,
                    event_time=dt_event,
                    weather_id=w_id,
                    event_desc=desc[:30]
                )
                
                add_log_line(f"{emoji_map[event_type]} Pre-aviso enviado a {user_id}")
            else:
                add_log_line(f"🚫 Pre-aviso bloqueado: {reason}")
        
        # ALERTA INMINENTE (30min a 2h antes)
        elif IMMINENT_MIN_HOURS <= hours_until < IMMINENT_MAX_HOURS:
            alert_key = f"{event_type}_imminent"
            
            should_send, reason = should_send_alert_advanced(
                user_id,
                alert_key,
                event_time=dt_event,
                cooldown_hours=IMMINENT_COOLDOWN,
                weather_id=w_id,
                event_desc=desc[:30]
            )
            
            if should_send:
                if hours_until < 1:
                    minutes = int(hours_until * 60)
                    time_text = f"{minutes} minutos"
                else:
                    time_text = f"{hours_until:.1f} horas"
                
                msg = (
                    f"⚠️ *{title_map[event_type]} Inminente*\n"
                    f"—————————————————\n"
                    f"📍 {city}\n"
                    f"🌦️ {desc}\n"
                    f"🕐 Hora estimada: {time_str}\n"
                    f"⏰ En aproximadamente {time_text}\n\n"
                    f"☔ _¡Toma precauciones ahora!_"
                )
                
                await bot.send_message(user_id, msg, parse_mode=ParseMode.MARKDOWN)
                
                mark_alert_sent_advanced(
                    user_id,
                    alert_key,
                    event_time=dt_event,
                    weather_id=w_id,
                    event_desc=desc[:30]
                )
                
                add_log_line(f"⚠️ Alerta inminente enviada a {user_id}")
            else:
                add_log_line(f"🚫 Alerta inminente bloqueada: {reason}")
    
    # ========================================
    # 3. RESUMEN DIARIO (TIMEZONE FIX v3.1)
    # ========================================
    target_time_str = sub.get('alert_time', '07:00')
    target_hour = int(target_time_str.split(':')[0])
    
    last_summary = weather_manager.get_last_daily_summary(user_id)
    
    is_time_to_send = (
        user_now.hour == target_hour 
        and 0 <= user_now.minute < 10
    )
    
    already_sent_today = False
    if last_summary:
        # ✅ FIX CRÍTICO: Normalizar ambos datetimes a naive
        user_now_naive = user_now.replace(tzinfo=None)
        
        if last_summary.tzinfo is not None:
            last_summary_naive = last_summary.replace(tzinfo=None)
        else:
            last_summary_naive = last_summary
        
        try:
            hours_since = (user_now_naive - last_summary_naive).total_seconds() / 3600
            already_sent_today = (hours_since < DAILY_SUMMARY_COOLDOWN)
            
            add_log_line(
                f"📊 Resumen diario: última vez hace {hours_since:.1f}h "
                f"(cooldown: {DAILY_SUMMARY_COOLDOWN}h)"
            )
        except Exception as e:
            add_log_line(f"⚠️ Error calculando cooldown resumen: {e}")
            already_sent_today = False
    
    if is_time_to_send and not already_sent_today:
        try:
            await send_daily_summary(bot, user_id, sub, current, forecast, user_now, tz_offset_sec)
        except Exception as e:
            add_log_line(f"❌ Error resumen diario: {str(e)[:200]}")
            import traceback
            add_log_line(f"Traceback: {traceback.format_exc()[:500]}")

async def send_daily_summary(
    bot: Bot, 
    user_id: int, 
    sub: dict, 
    current: dict, 
    forecast: dict,
    user_now: datetime,
    tz_offset_sec: int
):
    """✅ RESUMEN DIARIO CORREGIDO - Solo muestra el día actual."""
    city = sub.get('city', 'Tu ciudad')
    f_list = forecast.get('list', [])
    
    if not f_list:
        return
    
    target_hour = int(sub.get('alert_time', '07:00').split(':')[0])
    
    # FILTRAR POR DÍA ACTUAL
    if 5 <= target_hour < 12:
        header = f"☀️ *Buenos días, {city}*"
        intro = f"📅 *Pronóstico para hoy {user_now.strftime('%d/%m')}:*"
        today_end = user_now.replace(hour=23, minute=59, second=59)
        
    elif 12 <= target_hour < 19:
        header = f"🌤️ *Buenas tardes, {city}*"
        intro = f"📅 *Resto de hoy {user_now.strftime('%d/%m')} y mañana:*"
        today_end = (user_now + timedelta(days=1)).replace(hour=23, minute=59)
        
    else:
        header = f"🌙 *Buenas noches, {city}*"
        tomorrow = user_now + timedelta(days=1)
        intro = f"📅 *Pronóstico para mañana {tomorrow.strftime('%d/%m')}:*"
        
        tomorrow_start = tomorrow.replace(hour=0, minute=0, second=0)
        tomorrow_end = tomorrow.replace(hour=23, minute=59, second=59)
        today_end = tomorrow_end
        
        f_list = [
            item for item in f_list
            if datetime.fromtimestamp(item['dt'], timezone.utc) >= tomorrow_start
        ]
    
    # FILTRADO TEMPORAL PRECISO
    items_to_show = []
    for item in f_list:
        item_dt = datetime.fromtimestamp(item['dt'], timezone.utc) + timedelta(seconds=tz_offset_sec)
        
        if item_dt <= today_end:
            items_to_show.append(item)
        else:
            break
        
        if len(items_to_show) >= 16:
            break
    
    if not items_to_show:
        add_log_line(f"⚠️ No hay datos de forecast para el período")
        return
    
    # CONSTRUCCIÓN DEL MENSAJE
    temps = []
    winds = []
    pressures = []
    weather_codes = []
    rain_probs = []
    
    body_lines = []
    current_day = None
    
    for item in items_to_show:
        item_dt = datetime.fromtimestamp(item['dt'], timezone.utc) + timedelta(seconds=tz_offset_sec)
        item_temp = item['main']['temp']
        item_desc = item['weather'][0]['description']
        item_emoji = get_emoji(item_desc)
        item_wind = item['wind']['speed']
        item_pressure = item['main']['pressure']
        item_rain_prob = item.get('pop', 0) * 100
        
        temps.append(item_temp)
        winds.append(item_wind)
        pressures.append(item_pressure)
        weather_codes.append(item['weather'][0]['id'])
        rain_probs.append(item_rain_prob)
        
        if current_day != item_dt.day:
            if current_day is not None:
                body_lines.append("")
            
            day_name = item_dt.strftime('%A %d/%m')
            body_lines.append(f"*{day_name}:*")
            current_day = item_dt.day
        
        hour_str = item_dt.strftime('%H:%M')
        rain_text = f" (☔ {item_rain_prob:.0f}%)" if item_rain_prob > 30 else ""
        
        body_lines.append(
            f"  `{hour_str}`: {item_temp:.0f}°C {item_emoji} {item_desc.capitalize()}{rain_text}"
        )
    
    temp_min = min(temps)
    temp_max = max(temps)
    wind_max = max(winds)
    pressure_avg = sum(pressures) / len(pressures)
    rain_prob_max = max(rain_probs)
    
    lat = sub.get('lat')
    lon = sub.get('lon')
    uv_max = weather_api.get_uv_index(lat, lon)
    
    stats = (
        f"\n📊 *Resumen del Período:*\n"
        f"🌡️ Temperatura: {temp_min:.0f}°C - {temp_max:.0f}°C\n"
        f"💨 Viento máximo: {wind_max:.1f} m/s ({wind_max * 3.6:.0f} km/h)\n"
        f"☔ Probabilidad máx. lluvia: {rain_prob_max:.0f}%\n"
        f"☀️ Índice UV máximo: {uv_max:.1f}\n"
        f"📊 Presión promedio: {pressure_avg:.0f} hPa\n"
    )
    
    advice = get_smart_advice(temp_min, temp_max, weather_codes, uv_max)
    
    msg = (
        f"{header}\n"
        f"—————————————————\n"
        f"{intro}\n\n"
        + "\n".join(body_lines) + "\n"
        + stats + "\n"
        f"💡 *Consejos del Día:*\n{advice}\n\n"
        + get_random_ad_text()
    )
    
    await bot.send_message(user_id, msg, parse_mode=ParseMode.MARKDOWN)
    weather_manager.mark_daily_summary_sent(user_id)
    add_log_line(f"📰 Resumen diario enviado a {user_id} ({city})")
