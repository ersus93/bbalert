# handlers/weather.py

import requests
from datetime import datetime, timedelta, timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters, CallbackQueryHandler
from telegram.constants import ParseMode
from core.config import OPENWEATHER_API_KEY
from utils.weather_manager import (
    subscribe_user, unsubscribe_user, get_user_subscription, 
    toggle_alert_type, load_weather_subscriptions
)
from core.i18n import _
from utils.ads_manager import get_random_ad_text

# Estados para la conversación
LOCATION_INPUT = range(1)

# Diccionario de emojis
WEATHER_EMOJIS = {
    "clear": "☀️", "clouds": "☁️", "rain": "🌧️", "drizzle": "🌦️",
    "thunderstorm": "⛈️", "snow": "❄️", "mist": "🌫️", "fog": "🌁",
    "haze": "😶‍🌫️", "smoke": "💨", "dust": "🌪️", "sand": "🏜️",
    "ash": "🌋", "squall": "💨", "tornado": "🌪️"
}

# === NUEVA FUNCIÓN AUXILIAR PARA CONSEJOS INTELIGENTES ===
def get_daily_advice(min_temp, max_temp, weather_ids, uv_max):
    """Genera consejos basados en el pronóstico del día."""
    advice = []
    
    # 1. Ropa (Basado en sensación térmica aprox)
    if max_temp >= 30:
        advice.append("👕 *Ropa:* Usa ropa ligera y transpirable. ¡Hace calor!")
    elif max_temp >= 20:
        advice.append("👕 *Ropa:* Camiseta o camisa ligera está bien.")
    elif max_temp >= 15:
        advice.append("🧥 *Ropa:* Lleva una chaqueta ligera o sudadera.")
    elif max_temp >= 10:
        advice.append("🧥 *Ropa:* Abrigo necesario, refresca bastante.")
    else:
        advice.append("🧣 *Ropa:* ¡Abrígate bien! Bufanda y abrigo grueso.")

    # 2. Lluvia / Paraguas
    # Códigos 2xx (Tormenta), 3xx (Llovizna), 5xx (Lluvia)
    is_rainy = any(200 <= wid < 600 for wid in weather_ids)
    if is_rainy:
        advice.append("☔ *Accesorio:* No olvides el paraguas o chubasquero.")
    
    # 3. UV (Protección)
    if uv_max >= 6:
        advice.append("🧴 *Salud:* Índice UV alto. Usa protector solar si sales.")

    # 4. Coche / Tender ropa
    if is_rainy:
        advice.append("🚗 *Coche:* No es buen día para lavarlo (lluvia probable).")
    elif uv_max > 3 and not is_rainy:
        advice.append("🧺 *Hogar:* Buen día para secar ropa al aire libre.")

    return "\n".join(advice)

def get_weather_emoji(condition):
    condition_lower = condition.lower()
    for key, emoji in WEATHER_EMOJIS.items():
        if key in condition_lower:
            return emoji
    return "🌤️"

# --- FUNCIONES API (Helpers) ---
def get_current_weather(lat, lon):
    """Obtiene el clima actual."""
    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {
        "lat": lat, "lon": lon, "appid": OPENWEATHER_API_KEY,
        "units": "metric", "lang": "es"
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error clima actual: {e}")
        return None

def get_forecast(lat, lon):
    """Obtiene el pronóstico (para las próximas horas)."""
    url = "https://api.openweathermap.org/data/2.5/forecast"
    params = {
        "lat": lat, "lon": lon, "appid": OPENWEATHER_API_KEY,
        "units": "metric", "lang": "es", "cnt": 5 # Pedimos los siguientes 5 periodos (15 horas aprox)
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except:
        return None

def get_uv_index(lat, lon):
    """Obtiene el índice UV."""
    url = "https://api.openweathermap.org/data/2.5/uvi"
    params = {"lat": lat, "lon": lon, "appid": OPENWEATHER_API_KEY}
    try:
        r = requests.get(url, params=params, timeout=5)
        return r.json().get("value", 0)
    except:
        return 0
    
def get_air_quality(lat, lon): # <--- NUEVA FUNCIÓN
    """Obtiene el índice de Calidad del Aire (AQI)."""
    url = "http://api.openweathermap.org/data/2.5/air_pollution"
    params = {"lat": lat, "lon": lon, "appid": OPENWEATHER_API_KEY}
    try:
        r = requests.get(url, params=params, timeout=5)
        data = r.json()
        if data and data['list']:
            return data['list'][0]['main']['aqi']
    except:
        return 0

def get_aqi_text(aqi_value):
    """Traduce el valor numérico de AQI a texto (OpenWeather 1-5)."""
    if aqi_value == 1: return "Excelente"
    elif aqi_value == 2: return "Bueno"
    elif aqi_value == 3: return "Moderado"
    elif aqi_value == 4: return "Pobre"
    elif aqi_value == 5: return "Muy Pobre"
    return "No disponible"

def get_location_from_query(query_text):
    """Geocodificación por texto."""
    url = "http://api.openweathermap.org/geo/1.0/direct"
    params = {"q": query_text, "limit": 1, "appid": OPENWEATHER_API_KEY}
    try:
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        if data:
            return {"lat": data[0]["lat"], "lon": data[0]["lon"], "name": data[0]["name"], "country": data[0].get("country", "")}
    except:
        pass
    return None

def geocode_location(query_text):
    """Alias de get_location_from_query para claridad en otros archivos."""
    return get_location_from_query(query_text)

# --- COMANDOS PRINCIPALES ---

def geocode_location(query_text): # <--- NUEVA FUNCIÓN para uso en loops
    """Alias de get_location_from_query para claridad en otros archivos."""
    return get_location_from_query(query_text)

# --- COMANDOS PRINCIPALES ---

async def weather_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra el clima detallado o el menú."""
    
    # Determinar user_id y función de respuesta según el origen (Callback o Mensaje)
    if update.callback_query:
        user_id = update.callback_query.from_user.id
        message_func = update.callback_query.message.edit_text
        await update.callback_query.answer()
    else:
        user_id = update.effective_user.id
        message_func = update.message.reply_text

    # 1. Si el usuario escribió argumentos: "/w Madrid"
    if context.args:
        query = ' '.join(context.args)
        loc = get_location_from_query(query)
        
        if loc:
            # Obtener todos los datos necesarios
            current = get_current_weather(loc['lat'], loc['lon'])
            forecast = get_forecast(loc['lat'], loc['lon'])
            uv = get_uv_index(loc['lat'], loc['lon'])
            aqi = get_air_quality(loc['lat'], loc['lon']) # <--- OBTENER AQI
            
            if current:
                # -- Cálculos de Tiempo Local --
                tz_offset = current.get("timezone", 0)
                local_now = datetime.now(timezone.utc) + timedelta(seconds=tz_offset)
                
                sunrise = datetime.fromtimestamp(current['sys']['sunrise'], timezone.utc) + timedelta(seconds=tz_offset)
                sunset = datetime.fromtimestamp(current['sys']['sunset'], timezone.utc) + timedelta(seconds=tz_offset)
                
                # -- Formateo de Datos --
                desc = current['weather'][0]['description'].capitalize()
                emoji_main = get_weather_emoji(desc)
                
                # Nivel UV Texto
                uv_text = "Bajo"
                if uv > 2: uv_text = "Moderado"
                if uv > 5: uv_text = "Alto"
                if uv > 7: uv_text = "Muy Alto"
                if uv > 10: uv_text = "Extremo"

                # Calidad Aire Texto
                aqi_text = get_aqi_text(aqi)

                # Construcción del Mensaje Detallado
                msg = (
                    f"{emoji_main} *Clima en {current['name']}, {current['sys']['country']}*\n"
                    f"—————————————————\n"
                    f"• *{desc}*\n"
                    f"• 🌡 Temperatura: *{current['main']['temp']:.1f}°C*\n"
                    f"• 🤔 Sensación: {current['main']['feels_like']:.1f}°C\n"
                    f"• 💧 Humedad: {current['main']['humidity']}%\n"
                    f"• 💨 Viento: {current['wind']['speed']:.1f} m/s\n"
                    f"• ☁️ Nubosidad: {current['clouds']['all']}%\n"
                    f"• 📊 Presión: {current['main']['pressure']} hPa\n"
                    f"• ☀️ UV: {uv:.1f} ({uv_text})\n"
                    f"• 🌫️ Calidad aire: {aqi_text} (AQI: {aqi})\n" # <--- LÍNEA AQI
                    f"• 🕐 Hora local: {local_now.strftime('%H:%M')}\n"
                    f"• 🌅 Amanecer: {sunrise.strftime('%H:%M')}\n"
                    f"• 🌇 Atardecer: {sunset.strftime('%H:%M')}\n\n"
                )
                
                # -- Añadir Pronóstico Corto --
                if forecast and 'list' in forecast:
                    msg += "📅 *Próximas horas:*\n"
                    # Aseguramos que solo mostramos los 4 más cercanos
                    for item in forecast['list'][:4]: 
                        # Calcular hora del item ajustada a la zona horaria de la ciudad
                        dt_item = datetime.fromtimestamp(item['dt'], timezone.utc) + timedelta(seconds=tz_offset)
                        t_str = dt_item.strftime('%H:%M')
                        t_temp = item['main']['temp']
                        t_desc = item['weather'][0]['description']
                        t_emoji = get_weather_emoji(t_desc)
                        msg += f"  `{t_str}`: {t_temp:.0f}°C {t_emoji} {t_desc}\n"
                
                msg += ""
                msg += get_random_ad_text() # Publicidad
                
                if update.message:
                    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
                else:
                    await context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text=msg,
                        parse_mode=ParseMode.MARKDOWN
                    )
                return

    # 2. Si NO hay argumentos, mostrar el Menú Principal
    sub = get_user_subscription(user_id)
    
    # Determinar el primer botón dinámico
    if sub:
        # Si está suscrito, el primer botón es la consulta rápida de su ciudad
        city_name = sub['city']
        keyboard_option1 = InlineKeyboardButton(f"📍 Consultar Clima en {city_name}", callback_data=f"weather_query_{city_name}")
        keyboard = [
            [keyboard_option1],
            [InlineKeyboardButton("🔔 Suscribirse a Alertas", callback_data="weather_subscribe_start")],
            [InlineKeyboardButton("⚙️ Configurar Mis Alertas", callback_data="weather_settings")]
        ]
    else:
        # Si no está suscrito, el primer botón son las instrucciones
        keyboard_option1 = InlineKeyboardButton("🔍 Consultar Clima Detallado", callback_data="weather_help")
        keyboard = [
            [keyboard_option1],
            [InlineKeyboardButton("🔔 Suscribirse a Alertas", callback_data="weather_subscribe_start")],
            [InlineKeyboardButton("⚙️ Configurar Mis Alertas", callback_data="weather_settings")]
        ]
    
    msg = _(
        "🌤️ *Centro de Clima BitBread*\n\n"
        "Consulta el clima detallado de cualquier ciudad o gestiona tus alertas automáticas.\n\n"
        "Selecciona una opción:",
        user_id
    )
    
    await message_func(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)

# --- NUEVA FUNCIÓN PARA EL BOTÓN DE AYUDA / CONSULTA RÁPIDA ---
async def weather_default_query_or_help_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja el callback del primer botón: consulta rápida de ciudad por defecto O ayuda."""
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    
    if data == "weather_help":
        # Mostrar las instrucciones de ayuda (no suscrito)
        msg = (
            "📍 *¿Cómo consultar el clima?*\n\n"
            "Para ver el reporte detallado, simplemente escribe el comando `/w` seguido del nombre de la ciudad.\n\n"
            "*Ejemplos:*\n"
            "👉 `/w Madrid`\n"
            "👉 `/w Buenos Aires`\n"
            "👉 `/w Tokyo`\n\n"
            "¡Inténtalo ahora en el chat!"
        )
        # Añadimos botón para volver
        kb = [[InlineKeyboardButton("🔙 Volver al Menú", callback_data="weather_menu")]]
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)
        
    elif data.startswith("weather_query_"):
        # Consulta rápida de la ciudad por defecto (suscrito)
        city_query = data.split("weather_query_")[1]
        
        # Simulamos la ejecución de /w [ciudad]
        context.args = [city_query]
        # Eliminamos el menú para enviar el reporte detallado como un nuevo mensaje de respuesta
        await query.message.delete()
        
        # Usamos el handler de comando con el argumento de la ciudad
        await weather_command(update, context)


async def weather_subscribe_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inicia la suscripción pidiendo ubicación."""
    user_id = update.effective_user.id
    
    # Verificar si ya existe
    if get_user_subscription(user_id):
        await weather_settings_command(update, context) # Redirigir a configuración
        return ConversationHandler.END

    # Botón especial para pedir ubicación
    location_keyboard = ReplyKeyboardMarkup(
        [[KeyboardButton(text="📍 Compartir Ubicación GPS", request_location=True)]],
        one_time_keyboard=True,
        resize_keyboard=True
    )
    
    msg = _(
        "📍 *Suscripción a Alertas*\n\n"
        "Para enviarte alertas precisas y configurar tu zona horaria automáticamente, necesito tu ubicación.\n\n"
        "👇 *Pulsa el botón de abajo para compartirla:*",
        user_id
    )
    
    if update.callback_query:
        await update.callback_query.answer()
        # Los botones de ReplyKeyboard no funcionan en mensajes editados, hay que enviar uno nuevo
        await update.callback_query.message.reply_text(msg, reply_markup=location_keyboard, parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(msg, reply_markup=location_keyboard, parse_mode=ParseMode.MARKDOWN)
        
    return LOCATION_INPUT

# handlers/weather.py - LÍNEA 230 (DENTRO DE location_handler)

async def location_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """✅ Recibe ubicación y configura zona horaria automáticamente."""
    user_id = update.effective_user.id
    
    # ✅ LOG DE DEBUG
    from utils.file_manager import add_log_line
    add_log_line(f"🔍 location_handler llamado para usuario {user_id}")
    
    lat = None
    lon = None
    
    # ✅ Procesar ubicación GPS
    if update.message.location:
        lat = update.message.location.latitude
        lon = update.message.location.longitude
        add_log_line(f"📍 GPS recibido: {lat}, {lon}")
    
    # ✅ Procesar texto (nombre de ciudad)
    elif update.message.text:
        text = update.message.text
        add_log_line(f"📝 Texto recibido: {text}")
        
        loc = get_location_from_query(text)
        if loc:
            lat = loc['lat']
            lon = loc['lon']
            add_log_line(f"🗺️ Geocodificado: {lat}, {lon}")
        else:
            add_log_line(f"❌ Geocodificación falló para: {text}")
            await update.message.reply_text(
                "❌ No encontré esa ubicación. Intenta compartir tu ubicación GPS o escribe una ciudad más conocida.",
                reply_markup=ReplyKeyboardRemove()
            )
            return LOCATION_INPUT
    
    # ✅ Si no hay coordenadas válidas
    if not lat or not lon:
        add_log_line("❌ No se obtuvieron coordenadas válidas")
        await update.message.reply_text(
            "❌ No pude obtener tu ubicación. Por favor, usa el botón 'Compartir Ubicación'.",
            reply_markup=ReplyKeyboardRemove()
        )
        return LOCATION_INPUT
    
    # ✅ Obtener datos del clima
    add_log_line(f"🌐 Consultando API de clima para {lat}, {lon}")
    weather_data = get_current_weather(lat, lon)
    
    if not weather_data:
        add_log_line("❌ API de clima no respondió")
        await update.message.reply_text(
            "❌ Error conectando con el servicio de clima. Intenta de nuevo más tarde.",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END
    
    # ✅ Extraer ciudad y país
    city_name = weather_data.get("name", "")
    country = weather_data.get("sys", {}).get("country", "")
    
    add_log_line(f"🏙️ Ciudad detectada: {city_name}, {country}")
    
    # ✅ Si no hay nombre de ciudad, usar geocoding reverso
    if not city_name or city_name == "Ubicación":
        add_log_line("🔄 Intentando geocoding reverso...")
        from utils.weather_api import reverse_geocode
        result = reverse_geocode(lat, lon)
        
        if result:
            city_name, country = result
            add_log_line(f"✅ Geocoding reverso exitoso: {city_name}, {country}")
        else:
            city_name = f"Ubicación ({lat:.2f}, {lon:.2f})"
            add_log_line(f"⚠️ Geocoding reverso falló, usando coordenadas")
    
    # ✅ Calcular zona horaria
    offset_sec = weather_data.get("timezone", 0)
    offset_hours = offset_sec / 3600
    tz_str = f"UTC{offset_hours:+.0f}"
    
    add_log_line(f"🕐 Zona horaria: {tz_str}")
    
    # ✅ Guardar en contexto de usuario
    context.user_data['weather_sub'] = {
        'city': city_name,
        'country': country,
        'timezone': tz_str,
        'lat': float(lat),
        'lon': float(lon)
    }
    
    add_log_line(f"💾 Datos guardados en context.user_data")
    
    # ✅ Crear teclado de selección de hora
    keyboard = [
        [
            InlineKeyboardButton("07:00", callback_data="weather_time_07"),
            InlineKeyboardButton("08:00", callback_data="weather_time_08")
        ],
        [
            InlineKeyboardButton("09:00", callback_data="weather_time_09"),
            InlineKeyboardButton("20:00", callback_data="weather_time_20")
        ]
    ]
    
    msg = (
        f"✅ *Ubicación recibida correctamente*\n\n"
        f"📍 *Ciudad:* {city_name}, {country}\n"
        f"🌍 *Zona Horaria:* {tz_str}\n\n"
        f"📅 *Último paso:* ¿A qué hora quieres recibir el resumen diario del clima?"
    )
    
    await update.message.reply_text(
        msg,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )
    
    # ✅ Eliminar teclado de ubicación
    await update.message.reply_text(
        "🔽 Menú cerrado",
        reply_markup=ReplyKeyboardRemove()
    )
    
    add_log_line(f"✅ location_handler completado exitosamente")
    
    return ConversationHandler.END



async def weather_time_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """✅ Finaliza suscripción pasando TODAS las coordenadas."""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    from utils.file_manager import add_log_line
    add_log_line(f"🔍 weather_time_callback llamado para usuario {user_id}")
    
    if "weather_time_" not in data:
        add_log_line(f"⚠️ Callback data inválido: {data}")
        return
    
    hour = data.split("_")[2]
    alert_time = f"{hour}:00"
    
    add_log_line(f"⏰ Hora seleccionada: {alert_time}")
    
    sub_data = context.user_data.get('weather_sub')
    if not sub_data:
        add_log_line("❌ No hay datos en context.user_data")
        await query.edit_message_text("❌ Error: Datos perdidos. Intenta de nuevo con /w")
        return
    
    add_log_line(f"📦 Datos recuperados: {sub_data}")
    
    # ✅ Validar coordenadas
    if 'lat' not in sub_data or 'lon' not in sub_data:
        add_log_line("❌ Faltan coordenadas en sub_data")
        await query.edit_message_text("❌ Error: Coordenadas no válidas.")
        return
    
    # ✅ Llamar a subscribe_user
    add_log_line(f"💾 Intentando suscribir usuario {user_id}...")
    
    success = subscribe_user(
        user_id,
        sub_data['city'],
        sub_data['country'],
        sub_data['timezone'],
        sub_data['lat'],
        sub_data['lon'],
        alert_time
    )
    
    if not success:
        add_log_line(f"❌ subscribe_user falló para {user_id}")
        await query.edit_message_text("❌ Error al guardar suscripción. Revisa los logs.")
        return
    
    add_log_line(f"✅ Usuario {user_id} suscrito exitosamente")
    
    msg = (
        f"🎉 *¡Suscripción Activada!*\n\n"
        f"📍 *{sub_data['city']}* ({sub_data['timezone']})\n"
        f"⏰ Resumen diario: *{alert_time}*\n\n"
        f"Te avisaré sobre lluvia, tormentas y UV alto."
    )
    
    from utils.ads_manager import get_random_ad_text
    msg += "\n\n" + get_random_ad_text()
    
    await context.bot.send_message(
        chat_id=user_id,
        text=msg,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=ReplyKeyboardRemove()
    )
    
    try:
        await query.message.delete()
    except:
        pass



async def weather_settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra el panel de configuración."""
    if update.callback_query:
        user_id = update.callback_query.from_user.id
        message_func = update.callback_query.message.edit_text
        await update.callback_query.answer()
    else:
        user_id = update.effective_user.id
        message_func = update.message.reply_text

    sub = get_user_subscription(user_id)
    if not sub:
        await message_func(
            _("❌ No tienes suscripción activa. Usa /weather_sub.", user_id),
            parse_mode=ParseMode.MARKDOWN
        )
        return

    alert_types = sub.get('alert_types', {})
    
    def btn(key, label):
        status = "✅" if alert_types.get(key, True) else "❌"
        return InlineKeyboardButton(f"{status} {label}", callback_data=f"weather_toggle_{key}")

    keyboard = [
        # <--- Nuevos botones de alerta y reorganización
        [btn("rain", "Lluvia"), btn("storm", "Tormenta"), btn("snow", "Nieve/Escarcha")],
        [btn("uv_high", "UV Alto"), btn("fog", "Niebla")],
        [btn("temp_high", "Calor Intenso"), btn("temp_low", "Frío Intenso")],
        [InlineKeyboardButton(_("🗑️ Eliminar Suscripción", user_id), callback_data="weather_unsub_confirm")],
        [InlineKeyboardButton(_("🔙 Volver", user_id), callback_data="weather_menu")]
    ]

    text = _(
        f"⚙️ *Configuración de Clima*\n"
        f"📍 {sub['city']}\n"
        f"⏰ Resumen: {sub['alert_time']}\n\n"
        f"Toca los botones para activar/desactivar alertas:",
        user_id
    )

    await message_func(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)

async def weather_toggle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Toggle de alertas."""
    query = update.callback_query
    user_id = query.from_user.id
    alert_type = query.data.split("_")[2]
    
    toggle_alert_type(user_id, alert_type)
    await weather_settings_command(update, context)

async def weather_unsub_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manejo de desuscripción."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    if query.data == "weather_unsub_confirm":
        kb = [
            [InlineKeyboardButton("✅ Sí, eliminar", callback_data="weather_unsub_do")],
            [InlineKeyboardButton("❌ Cancelar", callback_data="weather_settings")]
        ]
        await query.message.edit_text(
            _("¿Seguro que quieres dejar de recibir alertas de clima?", user_id),
            reply_markup=InlineKeyboardMarkup(kb)
        )
    elif query.data == "weather_unsub_do":
        unsubscribe_user(user_id)
        await query.message.edit_text(_("🗑️ Suscripción eliminada.", user_id))

# --- REGISTRO DE HANDLERS ---
weather_conversation_handler = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(weather_subscribe_command, pattern="^weather_subscribe_start$")
    ],
    states={
        LOCATION_INPUT: [
            MessageHandler(filters.LOCATION, location_handler),
            MessageHandler(filters.TEXT & ~filters.COMMAND, location_handler)
        ]
    },
    fallbacks=[
        CommandHandler("cancel", weather_command),
        CallbackQueryHandler(weather_command, pattern="^weather_menu$")
    ],
    per_message=False,  # ✅ Cambiado de True a False
    allow_reentry=True,
    name="weather_subscription"
)

weather_callback_handlers = [
    CallbackQueryHandler(weather_time_callback, pattern="^weather_time_"),
    CallbackQueryHandler(weather_toggle_callback, pattern="^weather_toggle_"),
    CallbackQueryHandler(weather_settings_command, pattern="^weather_settings$"),
    CallbackQueryHandler(weather_unsub_flow, pattern="^weather_unsub_"),
    CallbackQueryHandler(weather_default_query_or_help_callback, pattern="^weather_(help|query_)"), 
    CallbackQueryHandler(weather_command, pattern="^weather_menu$")
]
