# core/weather_loop_v2.py
import asyncio
from datetime import datetime, timedelta, timezone
from telegram import Bot
from telegram.constants import ParseMode
from utils.file_manager import add_log_line
from utils.weather_manager import (
load_weather_subscriptions,
should_send_alert_advanced,
mark_alert_sent_advanced,
get_recent_global_events
)
from utils.weather_api import get_current_weather, get_forecast, get_uv_index, get_air_qualit
from core.ai_logic import get_groq_weather_advice
from utils.ads_manager import get_random_ad_text
from core.i18n import _
# ---------------------------------------------------------------------------
# CONSTANTES
# ---------------------------------------------------------------------------
WEATHER_EMOJIS = {
"clear": "
", "clouds": "
", "rain": "
", "drizzle": "
",
"thunderstorm": "
", "snow": "
", "mist": "
", "fog": "
",
"tornado": "
", "haze": "
", "smoke": "
"
}
# Cooldowns diferenciados por tipo de alerta (Paso 9)
ALERT_COOLDOWNS = {
"rain": 4, # h — la lluvia puede cambiar rápido
"storm": 3, # h — tormentas cortas e intensas
"uv_high": 12, # h — fenómeno de día completo
"snow": 6,
"fog": 6,
"temp_high": 8,
"temp_low": 8,
"daily_summary": 22, # h — una vez al día con margen
}
# Ventana horaria en la que el UV puede ser realmente peligroso
UV_ALERT_HOUR_START = 10
UV_ALERT_HOUR_END = 16

# Horizonte máximo (horas) para alertar sobre lluvia/tormenta inminente
RAIN_HORIZON_HOURS = 3
STORM_HORIZON_HOURS = 3
# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------
def get_emoji(desc: str) -> str:
for key, emoji in WEATHER_EMOJIS.items():
if key in desc.lower():
return emoji
return "
"
def _get_weather_id(entry: dict) -> int:
"""Extrae el weather_id de un entry de forecast de forma segura."""
try:
return entry["weather"][0]["id"]
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
"""Devuelve el enfoque del resumen según la hora local (Paso 8)."""
if 6 <= local_hour < 11:
return "morning" # pronóstico del día completo
elif 12 <= local_hour < 19:
return "afternoon" # tarde/noche + mañana siguiente
else:
return "night" # exclusivamente mañana siguiente
# ---------------------------------------------------------------------------
# LOOP PRINCIPAL DE ALERTAS DE EMERGENCIA (cada 15 min)

# ---------------------------------------------------------------------------
async def weather_alerts_loop(bot: Bot):
"""
Bucle de alertas de emergencia (lluvia, tormenta, UV).
Corre cada 15 minutos — separado del resumen diario (Paso 4).
"""
add_log_line("
Iniciando loop de alertas de emergencia (cada 15 min)...")
await asyncio.sleep(10)
while True:
try:
subs = load_weather_subscriptions()
if not subs:
await asyncio.sleep(900)
continue
for user_id_str, sub in subs.items():
if not sub.get("alerts_enabled", True):
continue
user_id = int(user_id_str)
alert_types = sub.get("alert_types", {})
city = sub["city"]
lat = sub.get("lat")
lon = sub.get("lon")
if not lat or not lon:
continue
# ── Obtener datos ──────────────────────────────────────────
try:
current = get_current_weather(lat, lon)
forecast = get_forecast(lat, lon)
uv_val = get_uv_index(lat, lon)
except Exception as e:
add_log_line(f"
Error API clima para {user_id}: {e}")
continue
if not current or not forecast:
continue
forecast_list = forecast.get("list", []) if isinstance(forecast, dict) else [
# ── Contexto temporal local ────────────────────────────────
tz_offset = current.get("timezone", 0)
local_now = datetime.now(timezone.utc) + timedelta(seconds=tz_offset)

 sunrise_dt = datetime.fromtimestamp(
current["sys"]["sunrise"], timezone.utc
) + timedelta(seconds=tz_offset)
sunset_dt = datetime.fromtimestamp(
current["sys"]["sunset"], timezone.utc
) + timedelta(seconds=tz_offset)
is_daytime = sunrise_dt < local_now < sunset_dt
# ── ALERTA: LLUVIA (Paso 2 — solo próximas RAIN_HORIZON_HOURS h) ──
if alert_types.get("rain", True):
upcoming_rain = next(
(
e for e in forecast_list
if 300 <= _get_weather_id(e) < 600
and _entry_within_hours(e, RAIN_HORIZON_HOURS)
),
None,
)
if upcoming_rain:
wid = _get_weather_id(upcoming_rain)
can_send, reason = should_send_alert_advanced(
user_id, "rain_early",
datetime.fromtimestamp(upcoming_rain["dt"]),
ALERT_COOLDOWNS["rain"],
weather_id=wid,
)
if can_send:
dt_rain = datetime.fromtimestamp(upcoming_rain["dt"])
desc = upcoming_rain["weather"][0]["description"].capitalize()
msg = _(
f"
*Alerta de Lluvia en {city}*\n"
f"—————————————————\n"
f"Se espera: *{desc}*\n"
f"
Hora aprox: {dt_rain.strftime('%H:%M')}\n"
f"
¡No olvides el paraguas!",
user_id,
)
msg += "\n\n" + get_random_ad_text()
await _enviar_seguro(bot, user_id, msg)
mark_alert_sent_advanced(
user_id, "rain_early",
datetime.fromtimestamp(upcoming_rain["dt"]),
weather_id=wid,
event_desc=desc,
)
# ── ALERTA: TORMENTA (Paso 2 — solo próximas STORM_HORIZON_HOURS h) ──

 if alert_types.get("storm", True):
upcoming_storm = next(
(
e for e in forecast_list
if 200 <= _get_weather_id(e) < 300
and _entry_within_hours(e, STORM_HORIZON_HOURS)
),
None,
)
if upcoming_storm:
wid = _get_weather_id(upcoming_storm)
can_send, reason = should_send_alert_advanced(
user_id, "storm_early",
datetime.fromtimestamp(upcoming_storm["dt"]),
ALERT_COOLDOWNS["storm"],
weather_id=wid,
)
if can_send:
dt_storm = datetime.fromtimestamp(upcoming_storm["dt"])
desc = upcoming_storm["weather"][0]["description"].capitalize
msg = _(
f"
*Alerta de Tormenta en {city}*\n"
f"—————————————————\n"
f"
Condición: *{desc}*\n"
f"
Hora aprox: {dt_storm.strftime('%H:%M')}\n"
f"
Toma precauciones.",
user_id,
)
msg += "\n\n" + get_random_ad_text()
await _enviar_seguro(bot, user_id, msg)
mark_alert_sent_advanced(
user_id, "storm_early",
datetime.fromtimestamp(upcoming_storm["dt"]),
weather_id=wid,
event_desc=desc,
)
# ── ALERTA: UV ALTO (Pasos 1 y 9) ─────────────────────────
# Solo durante franja solar real Y con hora local entre 10:00-16:00
uv_window = UV_ALERT_HOUR_START <= local_now.hour < UV_ALERT_HOUR_END
if (
alert_types.get("uv_high", True)
and is_daytime
and uv_window
and isinstance(uv_val, (int, float))
and uv_val >= 6
):

 can_send, reason = should_send_alert_advanced(
user_id, "uv_high_general",
local_now.replace(tzinfo=None),
ALERT_COOLDOWNS["uv_high"],
weather_id=0,
)
if can_send:
msg = _(
f"
*Alerta UV Alto en {city}*\n"
f"—————————————————\n"
f"Índice actual: *{uv_val:.1f}*\n"
f"
Usa protector solar si vas a salir.",
user_id,
)
msg += "\n\n" + get_random_ad_text()
await _enviar_seguro(bot, user_id, msg)
mark_alert_sent_advanced(
user_id, "uv_high_general",
local_now.replace(tzinfo=None),
weather_id=0,
event_desc=f"UV {uv_val:.1f}",
)
# Esperar 15 minutos (Paso 4)
await asyncio.sleep(900)
except Exception as e:
add_log_line(f"
Error CRÍTICO en Loop Alertas Emergencia: {e}")
await asyncio.sleep(60)
# ---------------------------------------------------------------------------
# LOOP DE RESUMEN DIARIO (verificación cada 30 min — Paso 4)
# ---------------------------------------------------------------------------
async def weather_daily_summary_loop(bot: Bot):
"""
Bucle exclusivo para el resumen diario.
Comprueba cada 30 minutos si es hora de enviar el resumen.
Solo envía si la hora local del usuario coincide con su preferencia.
"""
add_log_line("
Iniciando loop de resumen diario (cada 30 min)...")
await asyncio.sleep(30)
while True:
try:
subs = load_weather_subscriptions()

 if not subs:
await asyncio.sleep(1800)
continue
for user_id_str, sub in subs.items():
if not sub.get("alerts_enabled", True):
continue
if not sub.get("alert_types", {}).get("daily_summary", True):
continue
user_id = int(user_id_str)
lat = sub.get("lat")
lon = sub.get("lon")
if not lat or not lon:
continue
# ── Hora local del usuario ─────────────────────────────────
try:
current = get_current_weather(lat, lon)
if not current:
continue
except Exception as e:
add_log_line(f"
Error API resumen para {user_id}: {e}")
continue
tz_offset = current.get("timezone", 0)
local_now = datetime.now(timezone.utc) + timedelta(seconds=tz_offset)
# ── Ventana horaria configurada por el usuario ─────────────
try:
target_hour = int(sub.get("alert_time", "07:00").split(":")[0])
except (ValueError, IndexError):
target_hour = 7
# Ventana de 30 min para no perder el momento
in_window = (
local_now.hour == target_hour
and 0 <= local_now.minute < 30
)
if not in_window:
continue
# ── Cooldown (Paso 3 — lógica corregida) ──────────────────
# Usamos la hora exacta del resumen como event_time para deduplicar
event_time_today = local_now.replace(
hour=target_hour, minute=0, second=0, microsecond=0
).replace(tzinfo=None)

 can_send, reason = should_send_alert_advanced(
user_id, "daily_summary_general",
event_time_today,
ALERT_COOLDOWNS["daily_summary"],
weather_id=0,
)
if not can_send:
# Silencio total — no spam de logs (Paso 10)
continue
# ── Obtener todos los datos necesarios ─────────────────────
try:
forecast = get_forecast(lat, lon)
uv_val = get_uv_index(lat, lon)
aqi_val = get_air_quality(lat, lon)
except Exception as e:
add_log_line(f"
Error datos resumen {user_id}: {e}")
continue
forecast_list = (
forecast.get("list", []) if isinstance(forecast, dict) else []
)
add_log_line(
f"
Enviando resumen diario a {user_id} "
f"({sub['city']}) — contexto: {_build_daily_context(local_now.hour)}"
)
# ── Procesar datos ─────────────────────────────────────────
temps_today = [
item["main"]["temp"]
for item in forecast_list[:8]
]
max_temp = max(temps_today) if temps_today else current["main"]["temp"]
min_temp = min(temps_today) if temps_today else current["main"]["temp"]
temp = current["main"]["temp"]
feels_like = current["main"]["feels_like"]
humidity = current["main"]["humidity"]
wind_speed = current["wind"]["speed"]
description = current["weather"][0]["description"].capitalize()
uv_num = uv_val if isinstance(uv_val, (int, float)) else 0
aqi_num = aqi_val if isinstance(aqi_val, (int, float)) else 1
uv_text = (

 _("Alto", user_id) if uv_num > 5
else _("Bajo", user_id) if uv_num < 3
else _("Moderado", user_id)
)
aqi_labels = {
1: _("Bueno", user_id),
2: _("Justo", user_id),
3: _("Moderado", user_id),
4: _("Malo", user_id),
5: _("Pésimo", user_id),
}
aqi_text = aqi_labels.get(aqi_num, _("Desconocido", user_id))
emoji_weather = get_emoji(description)
sunrise_dt = datetime.fromtimestamp(
current["sys"]["sunrise"], timezone.utc
) + timedelta(seconds=tz_offset)
sunset_dt = datetime.fromtimestamp(
current["sys"]["sunset"], timezone.utc
) + timedelta(seconds=tz_offset)
city_name = current.get("name", _("Tu Ubicación", user_id))
country = current.get("sys", {}).get("country", "")
# ── Contexto del resumen según hora (Paso 8) ───────────────
daily_ctx = _build_daily_context(local_now.hour)
if daily_ctx == "morning":
ctx_label = _("Pronóstico del día completo", user_id)
elif daily_ctx == "afternoon":
ctx_label = _("Tarde, noche y mañana", user_id)
else:
ctx_label = _("Pronóstico de mañana", user_id)
# ── Construir mensaje ──────────────────────────────────────
msg = (
f"{emoji_weather} *{_('Resumen Diario', user_id)} — {city_name}, {country
f"—————————————————\n"
f"
*{local_now.strftime('%d/%m/%Y')}* |
*{local_now.strftime('%H:%M'
f"
_{ctx_label}_\n\n"
f"• {description}\n"
f"•
*{_('Temp', user_id)}:* {temp:.1f}°C "
f"({_('Sens', user_id)}: {feels_like:.1f}°C)\n"
f"•
*{_('Máx', user_id)}:* {max_temp:.1f}°C "
f"|
*{_('Mín', user_id)}:* {min_temp:.1f}°C\n"
f"•
*{_('Humedad', user_id)}:* {humidity}%\n"
f"•
*{_('Viento', user_id)}:* {wind_speed} m/s\n"
f"•
*UV:* {uv_num:.1f} ({uv_text})\n"

 f"•
*{_('Aire', user_id)}:* {aqi_text} (AQI: {aqi_num})\n"
f"•
*{_('Amanecer', user_id)}:* {sunrise_dt.strftime('%H:%M')} "
f"⇾
{sunset_dt.strftime('%H:%M')}\n\n"
)
# Pronóstico por horas — ajustado al contexto
if forecast_list:
msg += f"
*{_('Próximas horas', user_id)}:*\n"
# Noche: saltamos bloques del día actual, mostramos los de mañana
items_to_show = (
forecast_list[4:8] # ~12-24h desde ahora
if daily_ctx == "night"
else forecast_list[:4] # próximas ~12h
)
for item in items_to_show:
f_time = (
datetime.fromtimestamp(item["dt"], timezone.utc)
+ timedelta(seconds=tz_offset)
)
f_temp = item["main"]["temp"]
f_desc = item["weather"][0]["description"]
f_emoji = get_emoji(f_desc)
msg += f" {f_time.strftime('%H:%M')}: {f_temp:.0f}°C {f_emoji} {f_de
# ── IA ─────────────────────────────────────────────────────
try:
loop = asyncio.get_running_loop()
ai_rec = await loop.run_in_executor(
None, get_groq_weather_advice, msg
)
msg += f"\n
*{_('Consejo Inteligente', user_id)}:*\n{ai_rec}\n"
except Exception as e_ai:
add_log_line(f"
Error IA Clima: {e_ai}")
msg += (
f"\n
*{_('Consejo', user_id)}:* "
f"{_('Revisa el pronóstico antes de salir.', user_id)}"
)
msg += "\n\n" + get_random_ad_text()
await _enviar_seguro(bot, user_id, msg)
mark_alert_sent_advanced(
user_id, "daily_summary_general",
event_time_today,
weather_id=0,
event_desc="Resumen diario",
)

 # Esperar 30 minutos antes del siguiente ciclo (Paso 4)
await asyncio.sleep(1800)
except Exception as e:
add_log_line(f"
Error CRÍTICO en Loop Resumen Diario: {e}")
await asyncio.sleep(60)
# ---------------------------------------------------------------------------
# HELPER DE ENVÍO
# ---------------------------------------------------------------------------
async def _enviar_seguro(bot: Bot, user_id: int, text: str):
"""Envío seguro con manejo básico de errores."""
try:
await bot.send_message(
chat_id=user_id,
text=text,
parse_mode=ParseMode.MARKDOWN,
)
except Exception as e:
add_log_line(f"
No se pudo enviar mensaje a {user_id}: {e}")
