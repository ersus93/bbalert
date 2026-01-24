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
            
            for user_id_str, sub in subs.items():
                if not sub.get('alerts_enabled', True):
                    continue
                
                user_id = int(user_id_str)
                alert_types = sub.get('alert_types', {})
                city = sub['city']
                lat = sub.get('lat')
                lon = sub.get('lon')
                
                if not lat or not lon:
                    continue

                # ==========================================================
                # 1. OBTENCIÓN DE DATOS (Una sola vez para todo el ciclo)
                # ==========================================================
                try:
                    current = get_current_weather(lat, lon)
                    forecast = get_forecast(lat, lon)
                    # CORRECCIÓN: get_uv_index y get_air_quality devuelven números, no dicts
                    uv_val = get_uv_index(lat, lon) 
                    aqi_val = get_air_quality(lat, lon)
                except Exception as e:
                    add_log_line(f"⚠️ Error API clima para {user_id}: {e}")
                    continue

                if not current or not forecast:
                    continue

                # --- 1.1 CÁLCULOS DE TIEMPO (CRUCIAL PARA LA LÓGICA) ---
                # Calculamos esto ANTES de verificar alertas para saber si es de día o noche
                tz_offset = current.get("timezone", 0)
                utc_now = datetime.now(timezone.utc)
                local_now = utc_now + timedelta(seconds=tz_offset)
                
                # Convertir amanecer/atardecer a objetos datetime conscientes de zona horaria
                sunrise = datetime.fromtimestamp(current['sys']['sunrise'], timezone.utc) + timedelta(seconds=tz_offset)
                sunset = datetime.fromtimestamp(current['sys']['sunset'], timezone.utc) + timedelta(seconds=tz_offset)

                # Flag para saber si hay sol (para UV y temperaturas)
                is_daytime = sunrise < local_now < sunset

                # ==========================================================
                # 2. ALERTAS DE EMERGENCIA (Lluvia, Tormenta, UV)
                # ==========================================================

                # --- ALERTA 1: LLUVIA ---
                if alert_types.get('rain', True) and should_send_alert(user_id, 'rain', cooldown_hours=6):
                    upcoming_rain = None
                    for entry in forecast.get('list', [])[:4]:
                        wid = entry['weather'][0]['id']
                        if 300 <= wid < 600:
                            upcoming_rain = entry
                            break
                    
                    if upcoming_rain:
                        dt_rain = datetime.fromtimestamp(upcoming_rain['dt'])
                        desc = upcoming_rain['weather'][0]['description'].capitalize()
                        msg = _(f"🌧️ *Alerta de Lluvia en {city}*\n—————————————————\nSe espera: *{desc}*\n🕐 Hora aprox: {dt_rain.strftime('%H:%M')}\n☔ ¡No olvides el paraguas!", user_id)
                        msg += "" + get_random_ad_text()
                        await _enviar_seguro(bot, user_id, msg)
                        update_last_alert_time(user_id, 'rain')

                # --- ALERTA 2: TORMENTA ---
                if alert_types.get('storm', True) and should_send_alert(user_id, 'storm', cooldown_hours=6):
                    upcoming_storm = None
                    for entry in forecast.get('list', [])[:4]:
                        wid = entry['weather'][0]['id']
                        if 200 <= wid < 300:
                            upcoming_storm = entry
                            break
                    
                    if upcoming_storm:
                        dt_storm = datetime.fromtimestamp(upcoming_storm['dt'])
                        desc = upcoming_storm['weather'][0]['description'].capitalize()
                        msg = _(f"⛈️ *Alerta de Tormenta en {city}*\n—————————————————\n⚠️ Condición: *{desc}*\n🕐 Hora aprox: {dt_storm.strftime('%H:%M')}\n⚡ Toma precauciones.", user_id)
                        msg += "" + get_random_ad_text()
                        await _enviar_seguro(bot, user_id, msg)
                        update_last_alert_time(user_id, 'storm')

                # --- ALERTA 3: UV ALTO (Solo si es de día) ---
                # Usamos uv_val y verificamos que haya sol (is_daytime)
                if alert_types.get('uv_high', True) and is_daytime and uv_val >= 6:
                    if should_send_alert(user_id, 'uv_high', cooldown_hours=6):
                        msg = _(f"☀️ *Alerta UV Alto en {city}*\n—————————————————\nÍndice actual: *{uv_val:.1f}*\n🧴 Usa protector solar si vas a salir.", user_id)
                        msg += "" + get_random_ad_text()
                        await _enviar_seguro(bot, user_id, msg)
                        update_last_alert_time(user_id, 'uv_high')

                # ==========================================================
                # 3. RESUMEN DIARIO
                # ==========================================================
                
                alert_time_conf = sub.get('alert_time', '07:00')
                try:
                    target_hour = int(alert_time_conf.split(':')[0])
                except:
                    target_hour = 7
                
                # Usamos local_now que calculamos al principio del bucle
                # CONDICIÓN: Hora coincide + Minutos dentro de rango
                is_time_window = (local_now.hour == target_hour and 0 <= local_now.minute < 30)
                
                if is_time_window and alert_types.get('daily_summary', True):
                    
                    should_send = should_send_alert(user_id, 'daily_summary', cooldown_hours=20)
                    
                    if should_send:
                        add_log_line(f"🚀 Procesando Resumen Diario para {user_id} ({city})...")
                        
                        # --- Procesar Datos (Reutilizamos current, forecast, uv_val, aqi_val) ---
                        temps_today = []
                        forecast_list = forecast.get('list', []) # Extraemos la lista de forma segura

                        if forecast_list:
                            # Tomamos los próximos 8 registros (aprox 24h)
                            for item in forecast_list[:8]: 
                                temps_today.append(item['main']['temp'])

                        max_temp = max(temps_today) if temps_today else current['main']['temp']
                        min_temp = min(temps_today) if temps_today else current['main']['temp']

                        temp = current['main']['temp']
                        feels_like = current['main']['feels_like']
                        humidity = current['main']['humidity']
                        wind_speed = current['wind']['speed']
                        description = current['weather'][0]['description'].capitalize()
                        
                        # Textos para UV y AQI (Validando que sean números)
                        uv_num = uv_val if isinstance(uv_val, (int, float)) else 0
                        uv_text = "Alto" if uv_num > 5 else "Bajo" if uv_num < 3 else "Moderado"
                        
                        aqi_num = aqi_val if isinstance(aqi_val, (int, float)) else 1
                        aqi_text = {1: "Bueno", 2: "Justo", 3: "Moderado", 4: "Malo", 5: "Pésimo"}.get(aqi_num, "Desconocido")

                        # Iconos y Fechas
                        emoji_weather = get_emoji(description)
                        local_time = datetime.now(timezone.utc) + timedelta(seconds=current.get('timezone', 0))
                        sunrise = datetime.fromtimestamp(current['sys']['sunrise'], timezone.utc) + timedelta(seconds=current.get('timezone', 0))
                        sunset = datetime.fromtimestamp(current['sys']['sunset'], timezone.utc) + timedelta(seconds=current.get('timezone', 0))

                        # Construir Mensaje
                        city_name = current.get('name', 'Tu Ubicación')
                        country = current.get('sys', {}).get('country', '')

                        msg = (
                            f"{emoji_weather} *Resumen Diario - {city_name}, {country}*\n"
                            f"—————————————————\n"
                            f"📅 *{local_time.strftime('%d/%m/%Y')}* | 🕐 *{local_time.strftime('%H:%M')}*\n\n"
                            f"• {description}\n"
                            f"• 🌡 *Temp:* {temp:.1f}°C (Sens: {feels_like:.1f}°C)\n"
                            f"• 📈 *Máx:* {max_temp:.1f}°C | 📉 *Mín:* {min_temp:.1f}°C\n"
                            f"• 💧 *Humedad:* {humidity}%\n"
                            f"• 💨 *Viento:* {wind_speed} m/s\n"
                            f"• ☀️ *UV:* {uv_num:.1f} ({uv_text})\n"
                            f"• 🌫️ *Aire:* {aqi_text} (AQI: {aqi_num})\n"
                            f"• 🌅 *Sol:* {sunrise.strftime('%H:%M')} ⇾ 🌇 {sunset.strftime('%H:%M')}\n\n"
                        )

                        # Pronóstico Breve
                        if forecast_list: # Usar la variable forecast_list que creamos arriba
                            msg += "📅 *Próximas horas:*\n"
                            for item in forecast_list[:4]: # Cambiado de forecast[:4] a forecast_list[:4]
                                f_time = datetime.fromtimestamp(item['dt'], timezone.utc) + timedelta(seconds=current.get('timezone', 0))
                                f_temp = item['main']['temp']
                                f_desc = item['weather'][0]['description']
                                f_emoji = get_emoji(f_desc)
                                msg += f"  {f_time.strftime('%H:%M')}: {f_temp:.0f}°C {f_emoji} {f_desc}\n"
                        
                        # Integración IA
                        try:
                            loop = asyncio.get_running_loop()
                            ai_recommendation = await loop.run_in_executor(
                                None, get_groq_weather_advice, msg
                            )
                            msg += f"\n💡 *Consejo Inteligente:*\n{ai_recommendation}\n"
                        except Exception as e_ai:
                            add_log_line(f"⚠️ Error IA Clima: {e_ai}")
                            msg += "\n💡 *Consejo:* Revisa el pronóstico antes de salir."

                        msg += "" + get_random_ad_text()
                        
                        # ENVIAR Y REGISTRAR
                        await _enviar_seguro(bot, user_id, msg)
                        update_last_alert_time(user_id, 'daily_summary')

                else:
                        # ESTO ES LO QUE TE FALTABA: Un log para saber por qué falló
                    add_log_line(f"⏳ Resumen diario saltado para {user_id}: Cooldown activo (ya se envió en las últimas 20h)")

            # Esperar 5 minutos antes de la siguiente vuelta
            await asyncio.sleep(300)

        except Exception as e:
            add_log_line(f"❌ Error CRÍTICO en Loop Clima: {e}")
            await asyncio.sleep(60)

async def _enviar_seguro(bot, user_id, text):
    """Envío seguro con manejo básico de errores."""
    try:
        await bot.send_message(chat_id=user_id, text=text, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        add_log_line(f"No se pudo enviar mensaje a {user_id}: {e}")