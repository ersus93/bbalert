# core/weather_loop.py

import asyncio
import requests
import json
from datetime import datetime, timedelta, timezone
from telegram import Bot
from telegram.constants import ParseMode

from utils.file_manager import add_log_line
from utils.weather_manager import (
    get_all_subscribed_users, 
    get_user_subscription, 
    should_send_alert, 
    update_last_alert_time,
    save_weather_subscriptions, # Necesitamos esto para guardar correcciones
    load_weather_subscriptions,  # Necesitamos esto para cargar para correcciones
    update_user_coords
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
    desc_lower = desc.lower()
    for k, v in WEATHER_EMOJIS.items():
        if k in desc_lower: return v
    return "🌤️"

# --- HELPERS API ---
def get_coords_from_city(city_name):
    """Busca lat/lon por nombre de ciudad (Fallback para usuarios antiguos)."""
    try:
        url = "http://api.openweathermap.org/geo/1.0/direct"
        params = {"q": city_name, "limit": 1, "appid": OPENWEATHER_API_KEY}
        r = requests.get(url, params=params, timeout=5)
        data = r.json()
        if data:
            return data[0]['lat'], data[0]['lon']
    except Exception as e:
        add_log_line(f"⚠️ Error geocodificando {city_name}: {e}")
    return None, None

def update_user_coords(user_id, lat, lon):
    """
    Actualiza latitud y longitud de un usuario y GUARDA EN DISCO.
    Es vital para la integración con el bucle de autocalibración.
    """
    subs = load_weather_subscriptions() # Carga estado actual fresco
    user_key = str(user_id)
    
    if user_key in subs:
        subs[user_key]['lat'] = lat
        subs[user_key]['lon'] = lon
        save_weather_subscriptions(subs) # Escribe en disco inmediatamente
        return True
    return False

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
        val = r.json().get("value", 0)
        return val
    except: return 0

def get_smart_advice(min_temp, max_temp, weather_ids, uv_val):
    """Genera consejos basados en los datos."""
    advice = []
    # Lluvia/Nieve (Códigos 2xx, 3xx, 5xx, 6xx)
    if any(200 <= w < 600 for w in weather_ids):
        advice.append("☔ *Lluvia:* Lleva paraguas o impermeable.")
    elif any(600 <= w < 700 for w in weather_ids):
        advice.append("❄️ *Nieve:* Abrígate mucho y ten cuidado al desplazarte.")
    
    # Ropa
    if max_temp >= 30: advice.append("👕 *Calor:* Usa ropa ligera y bebe agua.")
    elif max_temp < 18: advice.append("🧥 *Frío:* Necesitas abrigo hoy.")
    elif max_temp < 12: advice.append("🧣 *Muy frío:* Gorro, bufanda y guantes recomendados.")
    
    # UV
    if uv_val > 6: advice.append("🧴 *UV Alto:* Usa protector solar si sales.")
    
    if not advice:
        advice.append("✅ *Todo tranquilo:* ¡Disfruta tu día!")
        
    return "\n".join(advice)

# --- BUCLE PRINCIPAL ---
async def weather_alerts_loop(bot: Bot):
    """
    Bucle híbrido: Alertas de Estado + Resumen Diario.
    Versión Depurada con Auto-fix de coordenadas.
    """
    add_log_line("🌦️ Monitor de Clima: INICIADO (Modo Depuración Activado)")

    # Espera inicial para asegurar que el bot cargó todo
    await asyncio.sleep(10)

    while True:
        try:
            # 1. Cargar usuarios
            users = get_all_subscribed_users()
            
            if not users:
                # add_log_line("🌦️ Monitor: No hay suscriptores activos. Durmiendo 10 min.")
                await asyncio.sleep(600) 
                continue
            
            # add_log_line(f"🌦️ Monitor: Revisando {len(users)} usuarios...")

            for user_id in users:
                try:
                    sub = get_user_subscription(user_id)
                    if not sub or not sub.get('alerts_enabled', True): continue

                    # --- CORRECCIÓN AUTOMÁTICA DE COORDENADAS ---
                    lat, lon = sub.get('lat'), sub.get('lon')
                    
                    # 1. RECUPERACIÓN DE COORDENADAS (INTEGRACIÓN CORREGIDA)
                    lat, lon = sub.get('lat'), sub.get('lon')
                    
                    if not lat or not lon:
                        city_name = sub.get('city')
                        
                        if city_name:
                            # add_log_line(f"⚠️ Recalibrando GPS para: {city_name}")
                            new_lat, new_lon = get_coords_from_city(city_name)
                            
                            if new_lat and new_lon:
                                lat, lon = new_lat, new_lon
                                # --- AQUÍ ESTABA EL CÓDIGO FALTANTE ---
                                # Usamos la función del manager para persistir el cambio
                                success = update_user_coords(user_id, lat, lon)
                                if success:
                                    add_log_line(f"✅ GPS Calibrado y guardado para {city_name}")
                                else:
                                    add_log_line(f"⚠️ Fallo al guardar GPS para {city_name}")
                            else:
                                # Si falla la API, saltamos este ciclo para no romper el bucle
                                continue
                        else:
                            # Usuario corrupto sin ciudad ni coords
                            continue

                    # Obtener datos API
                    current = get_current_weather(lat, lon)
                    if not current:
                        # add_log_line(f"⚠️ Fallo API actual para {user_id}")
                        continue
                        
                    forecast = get_forecast(lat, lon)
                    if not forecast: continue

                    # Calcular hora local del usuario
                    utc_now = datetime.now(timezone.utc)
                    tz_offset = current.get("timezone", 0)
                    user_now = utc_now + timedelta(seconds=tz_offset)

                    alert_types = sub.get('alert_types', {})

                    # ====================================================
                    # 1. ALERTAS DE ESTADO (Lluvia, Tormenta, UV)
                    # ====================================================
                    
                    # --- UV (Solo de día 10am - 4pm local) ---
                    if alert_types.get('uv_high', True) and 10 <= user_now.hour <= 16:
                        if should_send_alert(user_id, 'uv_high', cooldown_hours=4):
                            uv_val = get_uv_index(lat, lon)
                            if uv_val >= 6:
                                msg = f"☀️ *Alerta UV Alto ({uv_val:.1f})*\nEn {sub.get('city')} la radiación es fuerte. ¡Protégete!"
                                await bot.send_message(user_id, msg, parse_mode=ParseMode.MARKDOWN)
                                update_last_alert_time(user_id, 'uv_high')

                    # --- DETECCIÓN DE EVENTOS CLIMÁTICOS (Próximas 9 horas) ---
                    check_storm = alert_types.get('storm', True)
                    check_snow = alert_types.get('snow', True)
                    check_rain = alert_types.get('rain', True) # A veces no existe en JSON viejos, .get(key, True) es seguro

                    # forecast['list'] son intervalos de 3h. Miramos los 3 primeros (~9h)
                    for item in forecast.get('list', [])[:3]:
                        w_id = item['weather'][0]['id']
                        evt_type = None
                        
                        # Prioridad: Tormenta > Nieve > Lluvia
                        if check_storm and 200 <= w_id < 300: evt_type = 'storm'
                        elif check_snow and 600 <= w_id < 700: evt_type = 'snow'
                        elif check_rain and 300 <= w_id < 600: evt_type = 'rain'
                        
                        if evt_type:
                            dt_val = datetime.fromtimestamp(item['dt'], timezone.utc)
                            hours_until = (dt_val - utc_now).total_seconds() / 3600
                            
                            # Info para el mensaje
                            evt_time_local = dt_val + timedelta(seconds=tz_offset)
                            time_str = evt_time_local.strftime('%H:%M')
                            desc = item['weather'][0]['description'].capitalize()
                            
                            emoji_map = {'storm': '⛈️', 'snow': '❄️', 'rain': '🌧️'}
                            title_map = {'storm': 'Tormenta', 'snow': 'Nieve', 'rain': 'Lluvia'}
                            
                            # A) PRE-AVISO (3.5h a 8.5h antes)
                            if 3.5 <= hours_until <= 8.5:
                                alert_key = f"{evt_type}_early"
                                if should_send_alert(user_id, alert_key, cooldown_hours=12):
                                    msg = (
                                        f"{emoji_map[evt_type]} *Posible {title_map[evt_type]}*\n"
                                        f"El pronóstico indica {desc} en {sub.get('city')}.\n"
                                        f"🕐 Hora estimada: ~{time_str}"
                                    )
                                    await bot.send_message(user_id, msg, parse_mode=ParseMode.MARKDOWN)
                                    update_last_alert_time(user_id, alert_key)
                                    break # Avisado, salimos del loop de items para no spamear

                            # B) ALERTA INMINENTE (0.5h a 2.5h antes)
                            elif 0.5 <= hours_until < 2.5:
                                alert_key = f"{evt_type}_near"
                                if should_send_alert(user_id, alert_key, cooldown_hours=4):
                                    msg = (
                                        f"⚠️ *{title_map[evt_type]} Inminente (<2h)*\n"
                                        f"Se aproxima {desc}.\n"
                                        f"🕐 Hora estimada: {time_str}"
                                    )
                                    await bot.send_message(user_id, msg, parse_mode=ParseMode.MARKDOWN)
                                    update_last_alert_time(user_id, alert_key)
                                    break

                    # ====================================================
                    # 2. RESUMEN DIARIO INTELIGENTE
                    # ====================================================
                    target_time_str = sub.get('alert_time', '07:00')
                    # Asegurar formato HH:MM
                    try:
                        target_h = int(target_time_str.split(':')[0])
                    except:
                        target_h = 7

                    # Log de depuración para ver tiempos (Solo descomentar si es necesario, genera mucho spam)
                    # add_log_line(f"DEBUG: User {user_id} | Local: {user_now.hour}:{user_now.minute} | Target: {target_h}")

                    # Chequeamos si es la hora (margen 0 a 10 min)
                    if user_now.hour == target_h and 0 <= user_now.minute < 15: # Ampliado a 15 min por seguridad
                        if should_send_alert(user_id, 'daily_summary', cooldown_hours=20):
                            add_log_line(f"📤 Enviando resumen diario a {user_id} ({sub.get('city')})...")
                            
                            # --- LÓGICA DE CONTEXTO ---
                            f_list = forecast.get('list', [])
                            if not f_list: continue

                            header = ""
                            intro = ""
                            items_to_show = [] 
                            
                            # MAÑANA (05:00 - 11:59)
                            if 5 <= target_h < 12:
                                header = f"☀️ *Buenos días, {sub.get('city')}*"
                                intro = f"📅 *Pronóstico para hoy {user_now.strftime('%d/%m')}:*"
                                items_to_show = f_list[:4] 
                            # TARDE (12:00 - 18:59)
                            elif 12 <= target_h < 19:
                                header = f"🌤️ *Buenas tardes, {sub.get('city')}*"
                                intro = "📅 *Lo que queda de hoy y mañana:*"
                                items_to_show = f_list[:5]
                            # NOCHE
                            else:
                                header = f"🌙 *Buenas noches, {sub.get('city')}*"
                                intro = "📅 *Prepárate para mañana:*"
                                items_to_show = f_list[2:7] 

                            # Cuerpo del mensaje
                            body_lines = []
                            temps = []
                            w_codes = []

                            for item in items_to_show:
                                it_dt = datetime.fromtimestamp(item['dt'], timezone.utc) + timedelta(seconds=tz_offset)
                                it_h = it_dt.strftime('%H:%M')
                                it_temp = item['main']['temp']
                                it_desc = item['weather'][0]['description']
                                it_emoji = get_emoji(it_desc)
                                
                                day_label = " (Mañana)" if it_dt.day != user_now.day else ""
                                body_lines.append(f"▪️ `{it_h}{day_label}`: {it_temp:.0f}°C {it_emoji} {it_desc.capitalize()}")
                                
                                temps.append(it_temp)
                                w_codes.append(item['weather'][0]['id'])

                            # Consejos
                            min_t = min(temps) if temps else 0
                            max_t = max(temps) if temps else 0
                            uv_est = get_uv_index(lat, lon)
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
                            
                except Exception as e:
                    add_log_line(f"❌ Error procesando usuario {user_id} en Weather Loop: {e}")
                    continue

            # Esperamos 5 minutos
            await asyncio.sleep(300)

        except Exception as e:
            add_log_line(f"❌ Error CRÍTICO en bucle de clima: {e}")
            await asyncio.sleep(60)