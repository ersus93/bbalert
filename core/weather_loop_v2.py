# core/weather_loop_v2.py

import asyncio
from datetime import datetime, timedelta, timezone
from telegram import Bot
from telegram.constants import ParseMode

from utils.file_manager import add_log_line
from utils.weather_manager import (
    load_weather_subscriptions, 
    update_last_alert_time, 
    should_send_alert,
    get_recent_global_events  
)
from utils.weather_api import get_current_weather, get_forecast, get_uv_index, get_air_quality # <--- Añadido air_quality
from core.ai_logic import get_groq_weather_advice
from utils.ads_manager import get_random_ad_text
from core.i18n import _

# --- HERRAMIENTAS VISUALES (Del código nuevo) ---
WEATHER_EMOJIS = {
    "clear": "☀️", "clouds": "☁️", "rain": "🌧️", "drizzle": "🌦️",
    "thunderstorm": "⛈️", "snow": "❄️", "mist": "🌫️", "fog": "🌁",
    "tornado": "🌪️", "haze": "😶‍🌫️", "smoke": "💨"
}

def get_emoji(desc: str) -> str:
    for key, emoji in WEATHER_EMOJIS.items():
        if key in desc.lower():
            return emoji
    return "🌤️"

def get_smart_advice(min_temp, max_temp, weather_ids, uv):
    """Consejos inteligentes (Logica V2)."""
    advice = []
    is_rainy = any(200 <= w < 600 for w in weather_ids)
    
    if max_temp >= 30:
        advice.append("👕 *Ropa:* Ropa muy ligera. ¡Hidrátate!")
    elif max_temp >= 25:
        advice.append("👕 *Ropa:* Camiseta o camisa ligera.")
    elif max_temp >= 20:
        advice.append("🧥 *Ropa:* Chaqueta ligera recomendada.")
    elif max_temp >= 15:
        advice.append("🧥 *Ropa:* Abrigo necesario.")
    else:
        advice.append("🧣 *Ropa:* ¡Mucho abrigo! Gorro y guantes.")
    
    if uv >= 5.5:
        advice.append("🧴 *Sol:* UV alto. Usa protector solar.")
    if is_rainy:
        advice.append("☔ *Lluvia:* No olvides el paraguas.")
        advice.append("🚗 *Coche:* No lo laves hoy.")
    elif uv > 3 and not is_rainy:
        advice.append("🧺 *Hogar:* Buen día para secar ropa.")
        
    return "\n".join(advice) if advice else "✅ Todo tranquilo por hoy."

async def weather_alerts_loop(bot: Bot):
    """Bucle de fondo ROBUSTO (Estilo V1) con Mensajes INTELIGENTES (Estilo V2)."""
    add_log_line("🌦️ Iniciando Sistema de Clima Híbrido (Robustez V1 + Inteligencia V2)...")
    await asyncio.sleep(10)

    while True:
        try:
            subs = load_weather_subscriptions()
            if not subs:
                await asyncio.sleep(600)
                continue
            
            # Cargamos eventos globales UNA VEZ por ciclo para tenerlos listos si hay resumenes
            # Nota: Solo los leemos/borramos si realmente vamos a enviar un resumen,
            # pero para simplificar, los leeremos dentro de la función de resumen.
            
            for user_id_str, sub in subs.items():
                if not sub.get('alerts_enabled', True):
                    continue
                
                user_id = int(user_id_str)
                alert_types = sub.get('alert_types', {})
                city = sub['city']
                lat = sub.get('lat')
                lon = sub.get('lon')
                
                # Sin coordenadas no podemos trabajar
                if not lat or not lon:
                    continue

                # 1. Obtener Datos API
                try:
                    current = get_current_weather(lat, lon)
                    forecast = get_forecast(lat, lon) # Forecast de 5 dias / 3 horas
                    uv_index = get_uv_index(lat, lon)
                except Exception as e:
                    add_log_line(f"⚠️ Error API clima para {user_id}: {e}")
                    continue

                if not current or not forecast:
                    continue

                # --- ALERTA 1: LLUVIA (Lógica V1: Forecast próximos 4 items ~12h) ---
                if alert_types.get('rain', True) and should_send_alert(user_id, 'rain', cooldown_hours=6):
                    # Buscamos lluvia en las próximas 12 horas (4 periodos de 3h)
                    upcoming_rain = None
                    for entry in forecast.get('list', [])[:4]:
                        wid = entry['weather'][0]['id']
                        if 300 <= wid < 600: # Códigos de llovizna/lluvia
                            upcoming_rain = entry
                            break
                    
                    if upcoming_rain:
                        # Crear mensaje estilo V2
                        dt_rain = datetime.fromtimestamp(upcoming_rain['dt'])
                        desc = upcoming_rain['weather'][0]['description'].capitalize()
                        
                        msg = _(
                            f"🌧️ *Alerta de Lluvia en {city}*\n"
                            f"—————————————————\n"
                            f"Se espera: *{desc}*\n"
                            f"🕐 Hora aprox: {dt_rain.strftime('%H:%M')}\n"
                            f"☔ ¡No olvides el paraguas!",
                            user_id
                        )
                        msg += "\n\n" + get_random_ad_text()
                        
                        await _enviar_seguro(bot, user_id, msg)
                        update_last_alert_time(user_id, 'rain')

                # --- ALERTA 2: TORMENTA (Lógica V1) ---
                if alert_types.get('storm', True) and should_send_alert(user_id, 'storm', cooldown_hours=6):
                    upcoming_storm = None
                    for entry in forecast.get('list', [])[:4]:
                        wid = entry['weather'][0]['id']
                        if 200 <= wid < 300: # Códigos de tormenta
                            upcoming_storm = entry
                            break
                    
                    if upcoming_storm:
                        dt_storm = datetime.fromtimestamp(upcoming_storm['dt'])
                        desc = upcoming_storm['weather'][0]['description'].capitalize()
                        
                        msg = _(
                            f"⛈️ *Alerta de Tormenta en {city}*\n"
                            f"—————————————————\n"
                            f"⚠️ Condición: *{desc}*\n"
                            f"🕐 Hora aprox: {dt_storm.strftime('%H:%M')}\n"
                            f"⚡ Toma precauciones y resguárdate.",
                            user_id
                        )
                        msg += "\n\n" + get_random_ad_text()
                        
                        await _enviar_seguro(bot, user_id, msg)
                        update_last_alert_time(user_id, 'storm')

                # --- ALERTA 3: UV ALTO (Lógica V1) ---
                if alert_types.get('uv_high', True) and uv_index >= 6 and should_send_alert(user_id, 'uv_high', cooldown_hours=6):
                    msg = _(
                        f"☀️ *Alerta UV Alto en {city}*\n"
                        f"—————————————————\n"
                        f"Índice actual: *{uv_index:.1f}*\n"
                        f"🧴 Usa protector solar si vas a salir.",
                        user_id
                    )
                    msg += "\n\n" + get_random_ad_text()
                    await _enviar_seguro(bot, user_id, msg)
                    update_last_alert_time(user_id, 'uv_high')

                # --- ALERTA 4: RESUMEN DIARIO (Con Global Disasters) ---
                # Verificar hora local
                alert_time_conf = sub.get('alert_time', '07:00')
                target_hour = int(alert_time_conf.split(':')[0])
                
                # Calcular hora local del usuario
                utc_now = datetime.utcnow()
                tz_offset = current.get("timezone", 0)
                local_now = utc_now + timedelta(seconds=tz_offset)
                
                # Ventana de 10 minutos para enviar el resumen y comprobación de 'daily' en last_alerts
                if local_now.hour == target_hour and 0 <= local_now.minute < 10:
                    if alert_types.get('daily_summary', True):
                        # 1. Obtener Datos Completos (Igual que en manual)
                        current = get_current_weather(lat, lon)
                        forecast = get_forecast(lat, lon)
                        uv_data = get_uv_index(lat, lon)
                        air_data = get_air_quality(lat, lon) # Nuevo
                        
                        if not current:
                            continue

                        # 2. Procesar Datos para Resumen (Max/Min del día)
                        # El forecast trae datos cada 3 horas. Tomamos las próximas 24h (8 items)
                        temps_today = []
                        if forecast:
                            for item in forecast[:8]: 
                                temps_today.append(item['main']['temp'])
                        
                        max_temp = max(temps_today) if temps_today else current['main']['temp']
                        min_temp = min(temps_today) if temps_today else current['main']['temp']

                        # Datos básicos
                        temp = current['main']['temp']
                        feels_like = current['main']['feels_like']
                        humidity = current['main']['humidity']
                        wind_speed = current['wind']['speed']
                        description = current['weather'][0]['description'].capitalize()
                        clouds = current['clouds']['all']
                        pressure = current['main']['pressure']
                        
                        # Datos Extra (UV / Aire)
                        uv_val = uv_data.get('value', 0) if uv_data else 0
                        uv_text = "Alto" if uv_val > 5 else "Bajo" if uv_val < 3 else "Moderado"
                        
                        aqi_val = air_data.get('main', {}).get('aqi', 1) if air_data else 1
                        aqi_text = {1: "Bueno", 2: "Justo", 3: "Moderado", 4: "Malo", 5: "Pésimo"}.get(aqi_val, "Desconocido")

                        # Iconos y Fechas
                        emoji_weather = get_emoji(description)
                        local_time = datetime.now(timezone.utc) + timedelta(seconds=current.get('timezone', 0))
                        sunrise = datetime.fromtimestamp(current['sys']['sunrise'], timezone.utc) + timedelta(seconds=current.get('timezone', 0))
                        sunset = datetime.fromtimestamp(current['sys']['sunset'], timezone.utc) + timedelta(seconds=current.get('timezone', 0))

                        # 3. Construir el Mensaje "Rico" (Estilo Manual)
                        city_name = current.get('name', 'Tu Ubicación')
                        country = current.get('sys', {}).get('country', '')

                        msg = (
                            f"{emoji_weather} *Resumen Diario - {city_name}, {country}*\n"
                            f"—————————————————\n"
                            f"📅 *{local_time.strftime('%d/%m/%Y')}* | 🕐 *{local_time.strftime('%H:%M')}*\n\n"
                            f"• {description}\n"
                            f"• 🌡 *Temp:* {temp:.1f}°C (Sens: {feels_like:.1f}°C)\n"
                            f"• 📈 *Máx:* {max_temp:.1f}°C | 📉 *Mín:* {min_temp:.1f}°C\n" # Línea nueva importante
                            f"• 💧 *Humedad:* {humidity}%\n"
                            f"• 💨 *Viento:* {wind_speed} m/s\n"
                            f"• ☀️ *UV:* {uv_val} ({uv_text})\n"
                            f"• 🌫️ *Aire:* {aqi_text} (AQI: {aqi_val})\n"
                            f"• 🌅 *Sol:* {sunrise.strftime('%H:%M')} ⇾ 🌇 {sunset.strftime('%H:%M')}\n\n"
                        )

                        # 4. Sección Pronóstico (Breve, próximas 4 lecturas)
                        if forecast:
                            msg += "📅 *Próximas horas:*\n"
                            for item in forecast[:4]:
                                f_time = datetime.fromtimestamp(item['dt'], timezone.utc) + timedelta(seconds=current.get('timezone', 0))
                                f_temp = item['main']['temp']
                                f_desc = item['weather'][0]['description']
                                f_emoji = get_emoji(f_desc)
                                msg += f"  {f_time.strftime('%H:%M')}: {f_temp:.0f}°C {f_emoji} {f_desc}\n"
                        
                        # 5. INTEGRACIÓN IA (Nuevo)
                        # Usamos run_in_executor para no bloquear el bot mientras la IA piensa
                        try:
                            loop = asyncio.get_running_loop()
                            # Pasamos 'msg' que contiene todos los datos técnicos para que la IA los lea
                            ai_recommendation = await loop.run_in_executor(
                                None, 
                                get_groq_weather_advice, 
                                msg
                            )
                            
                            # Añadimos la respuesta de la IA
                            msg += f"\n💡 *Consejo Inteligente:*\n{ai_recommendation}\n"
                        
                        except Exception as e_ai:
                            add_log_line(f"⚠️ Error IA Clima: {e_ai}")
                            # Fallback simple si la IA falla
                            msg += "\n💡 *Consejo:* Revisa el pronóstico antes de salir."

                        # 6. Publicidad (Opcional, ya estaba en tu código)
                        msg += "\n" + get_random_ad_text()
                        
                        # 7. Enviar
                        await _enviar_seguro(bot, user_id, msg)
                        update_last_alert_time(user_id, 'daily_summary')

            # Esperar 5 minutos antes de la siguiente vuelta (Estilo V1)
            await asyncio.sleep(300)

        except Exception as e:
            add_log_line(f"❌ Error en Loop Clima: {e}")
            await asyncio.sleep(60)

async def _enviar_seguro(bot, user_id, text):
    """Envío seguro con manejo básico de errores."""
    try:
        await bot.send_message(chat_id=user_id, text=text, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        add_log_line(f"No se pudo enviar mensaje a {user_id}: {e}")