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
from utils.weather_api import get_current_weather, get_forecast, get_uv_index
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
                    if should_send_alert(user_id, 'daily_summary', cooldown_hours=20):
                        
                        # Generar Resumen Estilo V2
                        today_forecast = forecast.get('list', [])[:8] # Próximas 24h
                        if not today_forecast: continue

                        # Estadísticas para el consejo inteligente
                        temps = [x['main']['temp'] for x in today_forecast]
                        w_ids = [x['weather'][0]['id'] for x in today_forecast]
                        
                        advice = get_smart_advice(min(temps), max(temps), w_ids, uv_index)
                        
                        msg = _(
                            f"🌅 *Resumen Diario - {city}*\n"
                            f"—————————————————\n"
                            f"📅 {local_now.strftime('%d/%m/%Y')} | 🕐 {local_now.strftime('%H:%M')}\n\n"
                            f"*Actual:* {current['weather'][0]['description'].capitalize()}, {current['main']['temp']:.1f}°C\n"
                            f"💧 Humedad: {current['main']['humidity']}%\n"
                            f"💨 Viento: {current['wind']['speed']:.1f} m/s\n\n",
                            user_id
                        )
                        
                        msg += "*Pronóstico Hoy:*\n"
                        for entry in today_forecast[:4]: # Próximas 12h
                            dt_entry = datetime.fromtimestamp(entry['dt']) + timedelta(seconds=tz_offset)
                            emoji = get_emoji(entry['weather'][0]['description'])
                            temp = entry['main']['temp']
                            msg += f"`{dt_entry.strftime('%H:%M')}` {emoji} {temp:.0f}°C\n"

                        msg += f"\n💡 *Consejo:* {advice}\n"

                        # --- INYECCIÓN DE DESASTRES GLOBALES ---
                        if alert_types.get('global_disasters', True):
                            # Obtenemos eventos de las últimas 24 horas
                            global_events = get_recent_global_events(hours=24)
                            
                            if global_events:
                                msg += "\n🌍 *Actualidad Global (últimas 24h):*\n"
                                for event in global_events:
                                    # Icono según severidad
                                    icon = "🔴" if event['severity'] == 'Red' else "🟠" if event['severity'] == 'Orange' else "⚠️"
                                    msg += f"{icon} *{event['title']}*\n"
                        # ---------------------------------------

                        msg += "\n" + get_random_ad_text()
                        
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