# core/weather_loop_v2.py

import asyncio
from datetime import datetime, timedelta, timezone
from telegram import Bot
from telegram.constants import ParseMode

from utils.file_manager import add_log_line
from utils.weather_manager import (
    load_weather_subscriptions,
    get_user_subscription,
    should_send_alert_advanced,
    mark_alert_sent_advanced,
    get_recent_global_events
)
from utils.weather_api import get_current_weather, get_forecast, get_uv_index, get_air_quality
from core.ai_logic import get_groq_weather_advice
from utils.ads_manager import get_random_ad_text
from core.i18n import _

# =============================================================================
# CONSTANTES
# =============================================================================

WEATHER_EMOJIS = {
    "clear": "☀️", "clouds": "☁️", "rain": "🌧️", "drizzle": "🌦️",
    "thunderstorm": "⛈️", "snow": "❄️", "mist": "🌫️", "fog": "🌁",
    "tornado": "🌪️", "haze": "😶‍🌫️", "smoke": "💨"
}

# Cooldowns diferenciados (Paso 9)
ALERT_COOLDOWNS = {
    "rain": 4,        # h — la lluvia puede cambiar rápido
    "storm": 3,       # h — tormentas cortas e intensas
    "uv_high": 12,    # h — fenómeno de día completo
    "daily_summary": 22,  # h — una vez al día con margen
    "temp_high": 8,
    "temp_low": 8,
}

# Ventana horaria para alertas UV (Paso 1)
UV_ALERT_HOUR_START = 10
UV_ALERT_HOUR_END = 16

# Horizonte temporal para alertas de lluvia/tormenta (Paso 2)
RAIN_HORIZON_HOURS = 3
STORM_HORIZON_HOURS = 3

# Intervalos de los loops
ALERTS_LOOP_INTERVAL = 900      # 15 minutos
DAILY_SUMMARY_LOOP_INTERVAL = 1800  # 30 minutos

# Ventana de tiempo para resumen diario (±30 minutos)
DAILY_SUMMARY_WINDOW_MINUTES = 30


# =============================================================================
# HELPERS
# =============================================================================

def get_emoji(desc: str) -> str:
    """Obtiene el emoji correspondiente a la descripción del clima."""
    for key, emoji in WEATHER_EMOJIS.items():
        if key in desc.lower():
            return emoji
    return "🌤️"


def _get_weather_id(entry: dict) -> int:
    """Extrae el weather_id de un entry de forecast."""
    try:
        return entry['weather'][0]['id']
    except (KeyError, IndexError):
        return 0


def _entry_within_hours(entry: dict, hours: float) -> bool:
    """True si el entry de forecast cae dentro de las próximas `hours` horas."""
    try:
        entry_dt = datetime.fromtimestamp(entry["dt"], tz=timezone.utc)
        diff = (entry_dt - datetime.now(tz=timezone.utc)).total_seconds() / 3600
        return 0 <= diff <= hours
    except Exception:
        return False


def _build_daily_context(local_hour: int) -> str:
    """Devuelve el enfoque del resumen según la hora local."""
    if 6 <= local_hour < 11:
        return "morning"  # pronóstico del día completo
    elif 12 <= local_hour < 19:
        return "afternoon"  # tarde/noche + mañana siguiente
    else:
        return "night"  # exclusivamente mañana siguiente


# =============================================================================
# ENVÍO SEGURO
# =============================================================================

async def _enviar_seguro(bot: Bot, user_id: int, text: str) -> bool:
    """Envío seguro con manejo de errores. Solo loguea errores."""
    try:
        await bot.send_message(chat_id=user_id, text=text, parse_mode=ParseMode.MARKDOWN)
        return True
    except Exception as e:
        add_log_line(f"❌ Error enviando mensaje a {user_id}: {e}")
        return False


# =============================================================================
# LOOP PRINCIPAL DE ALERTAS (15 minutos)
# =============================================================================

async def weather_alerts_loop(bot: Bot):
    """
    Loop de alertas de emergencia: lluvia, tormenta, UV alto.
    Corre cada 15 minutos. Usa sistema V3 de anti-spam.
    """
    await asyncio.sleep(10)

    while True:
        try:
            subs = load_weather_subscriptions()
            if not subs:
                await asyncio.sleep(ALERTS_LOOP_INTERVAL)
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

                # Obtener datos climáticos
                try:
                    current = get_current_weather(lat, lon)
                    forecast = get_forecast(lat, lon)
                    uv_val = get_uv_index(lat, lon)
                except Exception as e:
                    add_log_line(f"⚠️ Error API clima para {user_id}: {e}")
                    continue

                if not current or not forecast:
                    continue

                # Cálculos de tiempo local
                tz_offset = current.get("timezone", 0)
                utc_now = datetime.now(timezone.utc)
                local_now = utc_now + timedelta(seconds=tz_offset)

                sunrise = datetime.fromtimestamp(current['sys']['sunrise'], timezone.utc) + timedelta(seconds=tz_offset)
                sunset = datetime.fromtimestamp(current['sys']['sunset'], timezone.utc) + timedelta(seconds=tz_offset)
                is_daytime = sunrise < local_now < sunset

                forecast_list = forecast.get('list', [])

                # =============================================================
                # ALERTA 1: LLUVIA (solo próximas 3 horas)
                # =============================================================
                if alert_types.get('rain', True):
                    upcoming_rain = None
                    rain_entry = None

                    for entry in forecast_list:
                        if not _entry_within_hours(entry, RAIN_HORIZON_HOURS):
                            continue
                        wid = _get_weather_id(entry)
                        if 300 <= wid < 600:
                            upcoming_rain = entry
                            rain_entry = entry
                            break

                    if upcoming_rain:
                        dt_rain = datetime.fromtimestamp(upcoming_rain['dt'], tz=timezone.utc)
                        should_send, reason = should_send_alert_advanced(
                            user_id=user_id,
                            alert_type='rain_imminent',
                            event_time=dt_rain,
                            cooldown_hours=ALERT_COOLDOWNS['rain'],
                            weather_id=_get_weather_id(upcoming_rain)
                        )

                        if should_send:
                            desc = upcoming_rain['weather'][0]['description'].capitalize()
                            msg = _(
                                f"🌧️ *Alerta de Lluvia en {city}*\n"
                                f"—————————————————\n"
                                f"Se espera: *{desc}*\n"
                                f"🕐 Hora aprox: {dt_rain.strftime('%H:%M')}\n"
                                f"☔ ¡No olvides el paraguas!",
                                user_id
                            )
                            msg += get_random_ad_text()

                            if await _enviar_seguro(bot, user_id, msg):
                                mark_alert_sent_advanced(
                                    user_id=user_id,
                                    alert_type='rain_imminent',
                                    event_time=dt_rain,
                                    weather_id=_get_weather_id(upcoming_rain),
                                    event_desc=desc
                                )

                # =============================================================
                # ALERTA 2: TORMENTA (solo próximas 3 horas)
                # =============================================================
                if alert_types.get('storm', True):
                    upcoming_storm = None
                    storm_entry = None

                    for entry in forecast_list:
                        if not _entry_within_hours(entry, STORM_HORIZON_HOURS):
                            continue
                        wid = _get_weather_id(entry)
                        if 200 <= wid < 300:
                            upcoming_storm = entry
                            storm_entry = entry
                            break

                    if upcoming_storm:
                        dt_storm = datetime.fromtimestamp(upcoming_storm['dt'], tz=timezone.utc)
                        should_send, reason = should_send_alert_advanced(
                            user_id=user_id,
                            alert_type='storm_imminent',
                            event_time=dt_storm,
                            cooldown_hours=ALERT_COOLDOWNS['storm'],
                            weather_id=_get_weather_id(upcoming_storm)
                        )

                        if should_send:
                            desc = upcoming_storm['weather'][0]['description'].capitalize()
                            msg = _(
                                f"⛈️ *Alerta de Tormenta en {city}*\n"
                                f"—————————————————\n"
                                f"⚠️ Condición: *{desc}*\n"
                                f"🕐 Hora aprox: {dt_storm.strftime('%H:%M')}\n"
                                f"⚡ Toma precauciones.",
                                user_id
                            )
                            msg += get_random_ad_text()

                            if await _enviar_seguro(bot, user_id, msg):
                                mark_alert_sent_advanced(
                                    user_id=user_id,
                                    alert_type='storm_imminent',
                                    event_time=dt_storm,
                                    weather_id=_get_weather_id(upcoming_storm),
                                    event_desc=desc
                                )

                # =============================================================
                # ALERTA 3: UV ALTO (solo entre 10:00 y 16:00)
                # =============================================================
                if alert_types.get('uv_high', True):
                    uv_window = UV_ALERT_HOUR_START <= local_now.hour < UV_ALERT_HOUR_END

                    if is_daytime and uv_window and isinstance(uv_val, (int, float)) and uv_val >= 6:
                        should_send, reason = should_send_alert_advanced(
                            user_id=user_id,
                            alert_type='uv_high',
                            event_time=local_now,
                            cooldown_hours=ALERT_COOLDOWNS['uv_high'],
                            weather_id=0
                        )

                        if should_send:
                            msg = _(
                                f"☀️ *Alerta UV Alto en {city}*\n"
                                f"—————————————————\n"
                                f"Índice actual: *{uv_val:.1f}*\n"
                                f"🧴 Usa protector solar si vas a salir.",
                                user_id
                            )
                            msg += get_random_ad_text()

                            if await _enviar_seguro(bot, user_id, msg):
                                mark_alert_sent_advanced(
                                    user_id=user_id,
                                    alert_type='uv_high',
                                    event_time=local_now,
                                    weather_id=0,
                                    event_desc=f"UV {uv_val:.1f}"
                                )

            await asyncio.sleep(ALERTS_LOOP_INTERVAL)

        except Exception as e:
            add_log_line(f"❌ Error CRÍTICO en weather_alerts_loop: {e}")
            await asyncio.sleep(60)


# =============================================================================
# LOOP DE RESUMEN DIARIO (30 minutos)
# =============================================================================

async def weather_daily_summary_loop(bot: Bot):
    """
    Loop de resumen diario personalizado.
    Corre cada 30 minutos. Usa sistema V3 de anti-spam.
    """
    await asyncio.sleep(30)

    while True:
        try:
            subs = load_weather_subscriptions()
            if not subs:
                await asyncio.sleep(DAILY_SUMMARY_LOOP_INTERVAL)
                continue

            for user_id_str, sub in subs.items():
                if not sub.get('alerts_enabled', True):
                    continue

                user_id = int(user_id_str)
                alert_types = sub.get('alert_types', {})

                if not alert_types.get('daily_summary', True):
                    continue

                city = sub['city']
                lat = sub.get('lat')
                lon = sub.get('lon')

                if not lat or not lon:
                    continue

                # Verificar ventana horaria
                alert_time_conf = sub.get('alert_time', '07:00')
                try:
                    target_hour = int(alert_time_conf.split(':')[0])
                    target_minute = int(alert_time_conf.split(':')[1])
                except (ValueError, IndexError):
                    target_hour = 7
                    target_minute = 0

                # Obtener datos para calcular hora local
                try:
                    current = get_current_weather(lat, lon)
                    forecast = get_forecast(lat, lon)
                    uv_val = get_uv_index(lat, lon)
                    aqi_val = get_air_quality(lat, lon)
                except Exception as e:
                    add_log_line(f"⚠️ Error API clima para resumen {user_id}: {e}")
                    continue

                if not current or not forecast:
                    continue

                tz_offset = current.get("timezone", 0)
                utc_now = datetime.now(timezone.utc)
                local_now = utc_now + timedelta(seconds=tz_offset)

                # Verificar si estamos en la ventana horaria (±30 min)
                target_time = local_now.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)
                diff_minutes = abs((local_now - target_time).total_seconds() / 60)

                if diff_minutes > DAILY_SUMMARY_WINDOW_MINUTES:
                    continue

                # Sistema V3: verificar cooldown
                should_send, reason = should_send_alert_advanced(
                    user_id=user_id,
                    alert_type='daily_summary',
                    event_time=local_now,
                    cooldown_hours=ALERT_COOLDOWNS['daily_summary'],
                    weather_id=0
                )

                if not should_send:
                    continue

                add_log_line(f"🚀 Procesando Resumen Diario para {user_id} ({city})...")

                # Contexto según hora del día
                context = _build_daily_context(local_now.hour)

                # Procesar datos
                forecast_list = forecast.get('list', [])
                temps_today = []

                if forecast_list:
                    for item in forecast_list[:8]:
                        temps_today.append(item['main']['temp'])

                max_temp = max(temps_today) if temps_today else current['main']['temp']
                min_temp = min(temps_today) if temps_today else current['main']['temp']

                temp = current['main']['temp']
                feels_like = current['main']['feels_like']
                humidity = current['main']['humidity']
                wind_speed = current['wind']['speed']
                description = current['weather'][0]['description'].capitalize()

                uv_num = uv_val if isinstance(uv_val, (int, float)) else 0
                uv_text = _("Alto", user_id) if uv_num > 5 else _("Bajo", user_id) if uv_num < 3 else _("Moderado", user_id)

                aqi_num = aqi_val if isinstance(aqi_val, (int, float)) else 1
                aqi_labels = {
                    1: _("Bueno", user_id),
                    2: _("Justo", user_id),
                    3: _("Moderado", user_id),
                    4: _("Malo", user_id),
                    5: _("Pésimo", user_id)
                }
                aqi_text = aqi_labels.get(int(aqi_num), _("Desconocido", user_id))

                emoji_weather = get_emoji(description)
                city_name = current.get('name', _('Tu Ubicación', user_id))
                country = current.get('sys', {}).get('country', '')

                sunrise = datetime.fromtimestamp(current['sys']['sunrise'], timezone.utc) + timedelta(seconds=tz_offset)
                sunset = datetime.fromtimestamp(current['sys']['sunset'], timezone.utc) + timedelta(seconds=tz_offset)

                # Construir mensaje según contexto
                msg = (
                    f"{emoji_weather} *{_('Resumen Diario', user_id)} - {city_name}, {country}*\n"
                    f"—————————————————\n"
                    f"📅 *{local_now.strftime('%d/%m/%Y')}* | 🕐 *{local_now.strftime('%H:%M')}*\n\n"
                    f"• {description}\n"
                    f"• 🌡 *{_('Temp', user_id)}:* {temp:.1f}°C ({_('Sens', user_id)}: {feels_like:.1f}°C)\n"
                    f"• 📈 *{_('Máx', user_id)}:* {max_temp:.1f}°C | 📉 *{_('Mín', user_id)}:* {min_temp:.1f}°C\n"
                    f"• 💧 *{_('Humedad', user_id)}:* {humidity}%\n"
                    f"• 💨 *{_('Viento', user_id)}:* {wind_speed} m/s\n"
                    f"• ☀️ *UV:* {uv_num:.1f} ({uv_text})\n"
                    f"• 🌫️ *{_('Aire', user_id)}:* {aqi_text} (AQI: {aqi_num})\n"
                    f"• 🌅 *{_('Sol', user_id)}:* {sunrise.strftime('%H:%M')} ⇾ 🌇 {sunset.strftime('%H:%M')}\n\n"
                )

                # Pronóstico contextual según hora del día
                if context == "morning":
                    msg += f"📅 *{_('Pronóstico del día', user_id)}:*\n"
                    count = 0
                    for item in forecast_list:
                        f_time = datetime.fromtimestamp(item['dt'], timezone.utc) + timedelta(seconds=tz_offset)
                        if f_time.date() == local_now.date() and count < 4:
                            f_temp = item['main']['temp']
                            f_desc = item['weather'][0]['description']
                            f_emoji = get_emoji(f_desc)
                            msg += f"  {f_time.strftime('%H:%M')}: {f_temp:.0f}°C {f_emoji} {f_desc}\n"
                            count += 1

                elif context == "afternoon":
                    msg += f"📅 *{_('Esta tarde y mañana', user_id)}:*\n"
                    count = 0
                    for item in forecast_list:
                        f_time = datetime.fromtimestamp(item['dt'], timezone.utc) + timedelta(seconds=tz_offset)
                        if f_time > local_now and count < 4:
                            f_temp = item['main']['temp']
                            f_desc = item['weather'][0]['description']
                            f_emoji = get_emoji(f_desc)
                            msg += f"  {f_time.strftime('%H:%M')}: {f_temp:.0f}°C {f_emoji} {f_desc}\n"
                            count += 1

                else:  # night
                    msg += f"📅 *{_('Mañana', user_id)}:*\n"
                    count = 0
                    tomorrow = local_now.date() + timedelta(days=1)
                    for item in forecast_list:
                        f_time = datetime.fromtimestamp(item['dt'], timezone.utc) + timedelta(seconds=tz_offset)
                        if f_time.date() == tomorrow and count < 4:
                            f_temp = item['main']['temp']
                            f_desc = item['weather'][0]['description']
                            f_emoji = get_emoji(f_desc)
                            msg += f"  {f_time.strftime('%H:%M')}: {f_temp:.0f}°C {f_emoji} {f_desc}\n"
                            count += 1

                # Integración IA
                try:
                    loop = asyncio.get_running_loop()
                    ai_recommendation = await loop.run_in_executor(
                        None, get_groq_weather_advice, msg
                    )
                    msg += f"\n💡 *{_('Consejo Inteligente', user_id)}:*\n{ai_recommendation}\n"
                except Exception as e_ai:
                    add_log_line(f"⚠️ Error IA Clima: {e_ai}")
                    msg += f"\n💡 *{_('Consejo', user_id)}:* {_('Revisa el pronóstico antes de salir.', user_id)}"

                msg += get_random_ad_text()

                # Enviar y registrar
                if await _enviar_seguro(bot, user_id, msg):
                    mark_alert_sent_advanced(
                        user_id=user_id,
                        alert_type='daily_summary',
                        event_time=local_now,
                        weather_id=0,
                        event_desc=f"Resumen {context}"
                    )
                    add_log_line(f"✅ Resumen diario enviado a {user_id}")

            await asyncio.sleep(DAILY_SUMMARY_LOOP_INTERVAL)

        except Exception as e:
            add_log_line(f"❌ Error CRÍTICO en weather_daily_summary_loop: {e}")
            await asyncio.sleep(60)
