# core/weather_loop.py

import asyncio
import requests
from datetime import datetime, timedelta, timezone
from telegram import Bot
from telegram.constants import ParseMode

from utils.file_manager import add_log_line
from utils.weather_manager import (
    get_all_subscribed_users, 
    get_user_subscription, 
    should_send_alert, 
    update_last_alert_time
)
from core.config import OPENWEATHER_API_KEY
from utils.ads_manager import get_random_ad_text

# --- CONFIGURACIÓN Y EMOJIS ---
WEATHER_EMOJIS = {
    "clear": "☀️", "clouds": "☁️", "rain": "🌧️", "drizzle": "🌦️",
    "thunderstorm": "⛈️", "snow": "❄️", "mist": "🌫️", "fog": "🌁",
    "tornado": "🌪️"
}

def get_emoji(desc):
    for k, v in WEATHER_EMOJIS.items():
        if k in desc.lower(): return v
    return "🌤️"

# --- HELPERS API ---
def get_current_weather(lat, lon):
    try:
        url = "https://api.openweathermap.org/data/2.5/weather"
        params = {"lat": lat, "lon": lon, "appid": OPENWEATHER_API_KEY, "units": "metric", "lang": "es"}
        r = requests.get(url, params=params, timeout=10)
        return r.json() if r.status_code == 200 else None
    except: return None

def get_forecast(lat, lon):
    try:
        url = "https://api.openweathermap.org/data/2.5/forecast"
        params = {"lat": lat, "lon": lon, "appid": OPENWEATHER_API_KEY, "units": "metric", "lang": "es"}
        r = requests.get(url, params=params, timeout=10)
        return r.json() if r.status_code == 200 else None
    except: return None

def get_uv_index(lat, lon):
    try:
        url = "https://api.openweathermap.org/data/2.5/uvi"
        params = {"lat": lat, "lon": lon, "appid": OPENWEATHER_API_KEY}
        r = requests.get(url, params=params, timeout=5)
        return r.json().get("value", 0)
    except: return 0

def get_smart_advice(min_temp, max_temp, weather_ids, uv_val):
    """Genera consejos basados en los datos."""
    advice = []
    # Lluvia/Nieve
    if any(200 <= w < 600 for w in weather_ids):
        advice.append("☔ *Lluvia:* Lleva paraguas.")
    elif any(600 <= w < 700 for w in weather_ids):
        advice.append("❄️ *Nieve:* Abrígate mucho y cuidado al conducir.")
    
    # Ropa
    if max_temp >= 30: advice.append("👕 *Ropa:* Ropa muy ligera, hidrátate.")
    elif max_temp < 10: advice.append("🧥 *Ropa:* Abrigo necesario.")
    elif max_temp < 5: advice.append("🧣 *Ropa:* Gorro, bufanda y guantes.")
    
    # UV
    if uv_val > 6: advice.append("🧴 *Sol:* Índice UV alto, usa protector.")
    
    return "\n".join(advice) if advice else "✅ *Todo tranquilo:* Disfruta tu día."

# --- BUCLE PRINCIPAL ---
async def weather_alerts_loop(bot: Bot):
    """
    Bucle híbrido: 
    1. Alertas de Estado (Lluvia/Tormenta) con lógica de pre-aviso vs inminente.
    2. Resumen Diario Inteligente (Contexto Mañana/Tarde/Noche).
    """
    add_log_line("🌦️ Iniciando Monitor de Clima (Smart + Robust Alerts)...")

    while True:
        try:
            # Obtenemos usuarios suscritos y activos
            users = get_all_subscribed_users()
            
            if not users:
                await asyncio.sleep(600) # Dormir 10 min si no hay nadie
                continue

            for user_id in users:
                try:
                    sub = get_user_subscription(user_id)
                    if not sub or not sub.get('alerts_enabled', True): continue

                    # Datos básicos
                    lat, lon = sub.get('lat'), sub.get('lon')
                    city = sub.get('city', 'Tu ciudad')
                    if not lat or not lon: continue # Saltamos si no hay coords

                    # Obtener datos API
                    current = get_current_weather(lat, lon)
                    forecast = get_forecast(lat, lon)
                    
                    if not current or not forecast: continue

                    # Calcular hora local del usuario
                    utc_now = datetime.now(timezone.utc)
                    tz_offset = current.get("timezone", 0)
                    user_now = utc_now + timedelta(seconds=tz_offset)

                    alert_types = sub.get('alert_types', {})

                    # ====================================================
                    # 1. ALERTAS DE ESTADO (Lluvia, Tormenta, Nieve, UV)
                    # ====================================================
                    
                    # --- UV (Solo de día 10am - 4pm) ---
                    if alert_types.get('uv_high', True) and 10 <= user_now.hour <= 16:
                        if should_send_alert(user_id, 'uv_high', cooldown_hours=4):
                            uv_val = get_uv_index(lat, lon)
                            if uv_val >= 6:
                                msg = f"☀️ *Alerta UV Alto ({uv_val:.1f})*\nEn {city} la radiación es fuerte. Usa protección solar."
                                await bot.send_message(user_id, msg, parse_mode=ParseMode.MARKDOWN)
                                update_last_alert_time(user_id, 'uv_high')

                    # --- DETECCIÓN DE EVENTOS CLIMÁTICOS (Próximas 9 horas) ---
                    check_rain = alert_types.get('rain', True)
                    check_storm = alert_types.get('storm', True)
                    check_snow = alert_types.get('snow', True)

                    upcoming_event = None
                    evt_type = None

                    # forecast['list'] son intervalos de 3h. Miramos los 3 primeros (9h)
                    for item in forecast.get('list', [])[:3]:
                        w_id = item['weather'][0]['id']
                        
                        # Prioridad: Tormenta > Nieve > Lluvia
                        if check_storm and 200 <= w_id < 300:
                            upcoming_event, evt_type = item, 'storm'
                            break
                        elif check_snow and 600 <= w_id < 700:
                            upcoming_event, evt_type = item, 'snow'
                            break
                        elif check_rain and 300 <= w_id < 600:
                            upcoming_event, evt_type = item, 'rain'
                            break # No paramos loop aquí, porque tormenta es peor, pero simplificamos tomando el primero encontrado
                    
                    if upcoming_event:
                        dt_val = datetime.fromtimestamp(upcoming_event['dt'], timezone.utc)
                        hours_until = (dt_val - utc_now).total_seconds() / 3600
                        
                        # Ajustar hora evento a local
                        evt_time_local = dt_val + timedelta(seconds=tz_offset)
                        time_str = evt_time_local.strftime('%H:%M')
                        desc = upcoming_event['weather'][0]['description'].capitalize()

                        emoji_map = {'storm': '⛈️', 'snow': '❄️', 'rain': '🌧️'}
                        title_map = {'storm': 'Tormenta', 'snow': 'Nieve', 'rain': 'Lluvia'}
                        
                        # A) PRE-AVISO (3.5h a 8.5h antes) - Solo 1 vez cada 12h
                        if 3.5 <= hours_until <= 8.5:
                            alert_key = f"{evt_type}_early"
                            if should_send_alert(user_id, alert_key, cooldown_hours=12):
                                msg = (
                                    f"{emoji_map[evt_type]} *Posible {title_map[evt_type]} (Pre-Aviso)*\n"
                                    f"—————————————————\n"
                                    f"Los modelos indican {desc} en {city}.\n"
                                    f"🕐 Hora estimada: ~{time_str}\n"
                                    f"💡 _Te aviso con tiempo para que te organices._"
                                )
                                await bot.send_message(user_id, msg, parse_mode=ParseMode.MARKDOWN)
                                update_last_alert_time(user_id, alert_key)

                        # B) ALERTA INMINENTE (0.5h a 2.5h antes) - Solo 1 vez cada 4h
                        elif 0.5 <= hours_until < 2.5:
                            alert_key = f"{evt_type}_near"
                            if should_send_alert(user_id, alert_key, cooldown_hours=4):
                                msg = (
                                    f"⚠️ *{title_map[evt_type]} Inminente (<2h)*\n"
                                    f"—————————————————\n"
                                    f"Se aproxima {desc} a tu zona.\n"
                                    f"🕐 Hora estimada: {time_str}\n"
                                    f"☔ _Toma precauciones ahora._"
                                )
                                await bot.send_message(user_id, msg, parse_mode=ParseMode.MARKDOWN)
                                update_last_alert_time(user_id, alert_key)

                    # ====================================================
                    # 2. RESUMEN DIARIO INTELIGENTE (Contextual)
                    # ====================================================
                    target_time_str = sub.get('alert_time', '07:00')
                    target_h = int(target_time_str.split(':')[0])

                    # Chequeamos si es la hora del resumen (margen 10 min)
                    if user_now.hour == target_h and 0 <= user_now.minute < 10:
                        if should_send_alert(user_id, 'daily_summary', cooldown_hours=20):
                            
                            # --- LÓGICA DE CONTEXTO ---
                            # Obtenemos lista de pronóstico
                            f_list = forecast.get('list', [])
                            
                            header = ""
                            intro = ""
                            items_to_show = [] # Lista de items del forecast a mostrar
                            
                            # MAÑANA (05:00 - 11:59) -> Resumen del día actual
                            if 5 <= target_h < 12:
                                header = f"☀️ *Buenos días, {city}*"
                                intro = f"📅 *Pronóstico para hoy {user_now.strftime('%d/%m')}:*"
                                items_to_show = f_list[:4] # Próximas ~12h

                            # TARDE (12:00 - 18:59) -> Resto de hoy + Mañana por la mañana
                            elif 12 <= target_h < 19:
                                header = f"🌤️ *Buenas tardes, {city}*"
                                intro = "📅 *Lo que queda de hoy y mañana por la mañana:*"
                                items_to_show = f_list[:5] # Próximas ~15h

                            # NOCHE (19:00 - 04:59) -> Resumen de mañana completo
                            else:
                                header = f"🌙 *Buenas noches, {city}*"
                                intro = "📅 *Prepárate para mañana:*"
                                # Saltamos las primeras horas (noche actual) y mostramos el día siguiente
                                items_to_show = f_list[2:7] 

                            # Construcción del cuerpo del mensaje
                            body_lines = []
                            temps = []
                            w_codes = []

                            for item in items_to_show:
                                it_dt = datetime.fromtimestamp(item['dt'], timezone.utc) + timedelta(seconds=tz_offset)
                                it_h = it_dt.strftime('%H:%M')
                                it_temp = item['main']['temp']
                                it_desc = item['weather'][0]['description']
                                it_emoji = get_emoji(it_desc)
                                
                                # Detectar si el item es de "Mañana" para etiquetarlo
                                day_label = ""
                                if it_dt.day != user_now.day:
                                    day_label = " (Mañana)"
                                
                                body_lines.append(f"▪️ `{it_h}{day_label}`: {it_temp:.0f}°C {it_emoji} {it_desc.capitalize()}")
                                
                                temps.append(it_temp)
                                w_codes.append(item['weather'][0]['id'])

                            # Consejos
                            min_t = min(temps) if temps else 0
                            max_t = max(temps) if temps else 0
                            uv_est = get_uv_index(lat, lon) # Estimado actual
                            advice = get_smart_advice(min_t, max_t, w_codes, uv_est)

                            msg_final = (
                                f"{header}\n"
                                f"—————————————————\n"
                                f"{intro}\n\n"
                                + "\n".join(body_lines) + "\n\n"
                                f"💡 *Consejo:* {advice}"
                            )
                            msg_final += get_random_ad_text()

                            await bot.send_message(user_id, msg_final, parse_mode=ParseMode.MARKDOWN)
                            update_last_alert_time(user_id, 'daily_summary')
                            add_log_line(f"🌦️ Resumen diario enviado a {user_id}")

                except Exception as e:
                    print(f"Error procesando usuario {user_id}: {e}")
                    continue

            # Esperamos 5 minutos antes de la siguiente revisión general
            await asyncio.sleep(300)

        except Exception as e:
            add_log_line(f"❌ Error crítico en weather_loop: {e}")
            await asyncio.sleep(60)