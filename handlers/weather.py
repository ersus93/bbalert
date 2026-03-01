# handlers/weather.py
import asyncio
from datetime import datetime, timedelta, timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters, CallbackQueryHandler
from telegram.constants import ParseMode
from telegram.error import BadRequest
from core.ai_logic import get_groq_weather_advice
from utils.weather_manager import (
    subscribe_user, unsubscribe_user, get_user_subscription, 
    toggle_alert_type, load_weather_subscriptions
)
from core.i18n import _
from utils.ads_manager import get_random_ad_text
from utils.file_manager import add_log_line
from utils.weather_api import get_current_weather, get_forecast, get_uv_index, get_air_quality, reverse_geocode, geocode_location

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

def get_aqi_text(aqi_value):
    """Traduce el valor numérico de AQI a texto (OpenWeather 1-5)."""
    if aqi_value == 1: return "Excelente"
    elif aqi_value == 2: return "Bueno"
    elif aqi_value == 3: return "Moderado"
    elif aqi_value == 4: return "Pobre"
    elif aqi_value == 5: return "Muy Pobre"
    return "No disponible"

# Alias para compatibilidad con código existente
get_location_from_query = geocode_location

# --- COMANDOS PRINCIPALES ---

# --- COMANDOS PRINCIPALES ---

# === NUEVA FUNCIÓN MAESTRA PARA ENVIAR EL REPORTE ===
async def responder_clima_actual(update: Update, context: ContextTypes.DEFAULT_TYPE, lat: float, lon: float, ciudad_guardada=None):
    """
    Genera el reporte manual detallado + IA y lo responde al usuario.
    """
    user = update.effective_user
    
    # 1. Notificar que estamos 'escribiendo' (para dar feedback mientras la IA piensa)
    if update.message:
        await update.message.reply_chat_action("typing")

    # 2. Obtener datos técnicos (Paralelismo básico si quisieras, pero secuencial está bien por ahora)
    current = get_current_weather(lat, lon)
    if not current: return

    # OBTENER FORECAST
    forecast_data = get_forecast(lat, lon)
    forecast_list = []
    if isinstance(forecast_data, dict) and 'list' in forecast_data:
        forecast_list = forecast_data['list']
    elif isinstance(forecast_data, list):
        forecast_list = forecast_data
    uv_val = get_uv_index(lat, lon)
    air_data = get_air_quality(lat, lon)

    # 3. Procesar Máximas/Mínimas (usando próximas 24h del forecast)
    temps_today = []
    if forecast_list:
        for item in forecast_list[:8]:
            temps_today.append(item['main']['temp'])
    
    max_temp = max(temps_today) if temps_today else current['main']['temp']
    min_temp = min(temps_today) if temps_today else current['main']['temp']

    # 4. Extraer variables visuales
    temp = current['main']['temp']
    feels_like = current['main']['feels_like']
    humidity = current['main']['humidity']
    wind_speed = current['wind']['speed']
    description = current['weather'][0]['description'].capitalize()
    pressure = current['main']['pressure']
    clouds = current['clouds']['all']
    
    # UV y Aire
    aqi_val = air_data if air_data else 1
    uv_text = "Alto" if uv_val > 5 else "Bajo" if uv_val < 3 else "Moderado"
    
    aqi_text = {1: "Bueno", 2: "Justo", 3: "Moderado", 4: "Malo", 5: "Pésimo"}.get(aqi_val, "Desconocido")

    # Fechas y Sol
    timezone_offset = current.get('timezone', 0)
    local_time = datetime.now(timezone.utc) + timedelta(seconds=timezone_offset)
    sunrise = datetime.fromtimestamp(current['sys']['sunrise'], timezone.utc) + timedelta(seconds=timezone_offset)
    sunset = datetime.fromtimestamp(current['sys']['sunset'], timezone.utc) + timedelta(seconds=timezone_offset)

    # Emoji del clima (puedes usar tu función get_emoji si la tienes importada, o un map simple aquí)
    # Si tienes la funcion get_emoji definida en este archivo o importada, úsala:
    try:
        weather_emoji = WEATHER_EMOJIS.get(current['weather'][0]['main'].lower(), "🌤️")
    except:
        weather_emoji = "🌤️"

    city_name = ciudad_guardada if ciudad_guardada else current.get('name', 'Ubicación')
    country = current.get('sys', {}).get('country', '')

    # 5. CONSTRUCCIÓN DEL MENSAJE (Formato Rico)
    msg = (
        f"{weather_emoji} *Clima en {city_name}, {country}*\n"
        f"—————————————————\n"
        f"• {description}\n"
        f"• 🌡 *Temperatura:* {temp:.1f}°C\n"
        f"• 🤔 *Sensación:* {feels_like:.1f}°C\n"
        f"• 📈 *Máx:* {max_temp:.1f}°C | 📉 *Mín:* {min_temp:.1f}°C\n"
        f"• 💧 *Humedad:* {humidity}%\n"
        f"• 💨 *Viento:* {wind_speed} m/s\n"
        f"• ☁️ *Nubosidad:* {clouds}%\n"
        f"• 📊 *Presión:* {pressure} hPa\n"
        f"• ☀️ *UV:* {uv_val} ({uv_text})\n"
        f"• 🌫️ *Calidad aire:* {aqi_text} (AQI: {aqi_val})\n"
        f"• 🕐 *Hora local:* {local_time.strftime('%H:%M')}\n"
        f"• 🌅 *Amanecer:* {sunrise.strftime('%H:%M')}\n"
        f"• 🌇 *Atardecer:* {sunset.strftime('%H:%M')}\n\n"
    )

    # Añadir Pronóstico Breve (Próximas horas)
    if forecast_list:
        msg += "📅 *Próximas horas:*\n"
        # Usamos forecast_list en lugar de forecast
        for item in forecast_list[:4]: 
            f_time = datetime.fromtimestamp(item['dt'], timezone.utc) + timedelta(seconds=current.get('timezone', 0))
            f_temp = item['main']['temp']
            f_desc = item['weather'][0]['description'].capitalize()
            msg += f"  {f_time.strftime('%H:%M')}: {f_temp:.1f}°C - {f_desc}\n"

    # 6. INYECCIÓN DE INTELIGENCIA ARTIFICIAL (IA)
    # Llamamos a Groq sin bloquear el bot
    try:
        loop = asyncio.get_running_loop()
        # Pasamos el mensaje actual para que la IA lea los datos técnicos
        ai_recommendation = await loop.run_in_executor(
            None, 
            get_groq_weather_advice, 
            msg
        )
        msg += f"\n\n💡 *Consejos:*\n—————————————————\n{ai_recommendation}"
    except Exception as e:
        add_log_line(f"⚠️ Error IA Manual: {e}")
        msg += "\n💡 *Consejo:* Lleva lo necesario según el clima."

    # 7. Publicidad y Envío
    msg += "\n" + get_random_ad_text()

    if update.message:
        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
    elif update.callback_query:
        # Si venimos de un botón, usamos edit_text o send_message según prefieras
        await update.callback_query.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

async def weather_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Maneja el comando /w.
    - Si tiene argumentos (/w Madrid): Muestra el reporte.
    - Si NO tiene argumentos (/w): Muestra el MENÚ (Botones).
    """
    
    # Determinar origen (Callback o Mensaje)
    if update.callback_query:
        user_id = update.callback_query.from_user.id
        message_func = update.callback_query.message.edit_text
        await update.callback_query.answer()
    else:
        user_id = update.effective_user.id
        message_func = update.message.reply_text

    # CASO 1: El usuario escribió una ciudad (/w Madrid)
    # O el sistema le pasó argumentos internamente
    if context.args:
        query = ' '.join(context.args)
        
        # Usamos tu función helper para buscar coordenadas
        loc = get_location_from_query(query)
        
        if loc:
            # ✅ Usamos la NUEVA función maestra para que salga con IA, AQI, etc.
            await responder_clima_actual(update, context, loc['lat'], loc['lon'], loc['name'])
        else:
            await message_func("❌ No encontré esa ciudad. Intenta con un nombre más común.")
        return

    # CASO 2: Sin argumentos -> MOSTRAR MENÚ (Lógica antigua restaurada)
    sub = get_user_subscription(user_id)
    
    if sub:
        # Si está suscrito, mostramos botón para consultar SU ciudad
        city_name = sub['city']
        keyboard = [
            [InlineKeyboardButton(f"📍 Consultar Clima en {city_name}", callback_data=f"weather_query_{city_name}")],
            [InlineKeyboardButton("🔔 Suscribirse a Alertas", callback_data="weather_subscribe_start")],
            [InlineKeyboardButton("⚙️ Configurar Mis Alertas", callback_data="weather_settings")]
        ]
    else:
        # Si NO está suscrito, mostramos ayuda
        keyboard = [
            [InlineKeyboardButton("🔍 Consultar Clima Detallado", callback_data="weather_help")],
            [InlineKeyboardButton("🔔 Suscribirse a Alertas", callback_data="weather_subscribe_start")],
            [InlineKeyboardButton("⚙️ Configurar Mis Alertas", callback_data="weather_settings")]
        ]
    
    msg = _(
        "🌤️ *Centro de Clima BitBread*\n\n"
        "Consulta el clima detallado de cualquier ciudad o gestiona tus alertas automáticas.\n\n"
        "Selecciona una opción:",
        user_id
    )
    
    # Enviamos el menú
    try:
        await message_func(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
    except BadRequest:
        # A veces telegram da error si intentas editar un mensaje con el mismo contenido
        pass

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
        await weather_settings_command(update, context)
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
        await update.callback_query.message.reply_text(msg, reply_markup=location_keyboard, parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(msg, reply_markup=location_keyboard, parse_mode=ParseMode.MARKDOWN)
        
    return LOCATION_INPUT

# handlers/weather.py - LÍNEA 230 (DENTRO DE location_handler)

async def location_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """✅ Recibe ubicación con más opciones de horario."""
    user_id = update.effective_user.id
    
    from utils.file_manager import add_log_line
    add_log_line(f"🔍 location_handler llamado para usuario {user_id}")
    
    lat = None
    lon = None
    
    # Procesar ubicación GPS
    if update.message.location:
        lat = update.message.location.latitude
        lon = update.message.location.longitude
        add_log_line(f"📍 GPS recibido: {lat}, {lon}")
    
    # Procesar texto (nombre de ciudad)
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
    
    if not lat or not lon:
        add_log_line("❌ No se obtuvieron coordenadas válidas")
        await update.message.reply_text(
            "❌ No pude obtener tu ubicación. Por favor, usa el botón 'Compartir Ubicación'.",
            reply_markup=ReplyKeyboardRemove()
        )
        return LOCATION_INPUT
    
    # Obtener datos del clima
    add_log_line(f"🌐 Consultando API de clima para {lat}, {lon}")
    weather_data = get_current_weather(lat, lon)
    
    if not weather_data:
        add_log_line("❌ API de clima no respondió")
        await update.message.reply_text(
            "❌ Error conectando con el servicio de clima. Intenta de nuevo más tarde.",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END
    
    city_name = weather_data.get("name", "")
    country = weather_data.get("sys", {}).get("country", "")
    
    add_log_line(f"🏙️ Ciudad detectada: {city_name}, {country}")
    
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
    
    offset_sec = weather_data.get("timezone", 0)
    offset_hours = offset_sec / 3600
    tz_str = f"UTC{offset_hours:+.0f}"
    
    add_log_line(f"🕐 Zona horaria: {tz_str}")
    
    context.user_data['weather_sub'] = {
        'city': city_name,
        'country': country,
        'timezone': tz_str,
        'lat': float(lat),
        'lon': float(lon)
    }
    
    add_log_line(f"💾 Datos guardados en context.user_data")

    await responder_clima_actual(update, context, lat, lon, city_name)
    
    # ✅ TECLADO MEJORADO CON MÁS OPCIONES
    keyboard = [
        [
            InlineKeyboardButton("06:00 🌅", callback_data="weather_time_06"),
            InlineKeyboardButton("07:00 ☀️", callback_data="weather_time_07"),
            InlineKeyboardButton("08:00", callback_data="weather_time_08")
        ],
        [
            InlineKeyboardButton("09:00", callback_data="weather_time_09"),
            InlineKeyboardButton("10:00", callback_data="weather_time_10"),
            InlineKeyboardButton("12:00 🌤️", callback_data="weather_time_12")
        ],
        [
            InlineKeyboardButton("14:00", callback_data="weather_time_14"),
            InlineKeyboardButton("18:00 🌆", callback_data="weather_time_18"),
            InlineKeyboardButton("20:00", callback_data="weather_time_20")
        ],
        [
            InlineKeyboardButton("21:00 🌙", callback_data="weather_time_21"),
            InlineKeyboardButton("22:00", callback_data="weather_time_22")
        ]
    ]
    
    msg = (
        f"✅ *Ubicación recibida correctamente*\n\n"
        f"📍 *Ciudad:* {city_name}, {country}\n"
        f"🌍 *Zona Horaria:* {tz_str}\n\n"
        f"📅 *Último paso:* ¿A qué hora quieres recibir el resumen diario?\n\n"
        f"💡 _El resumen se adaptará al horario elegido:_\n"
        f"• *Mañana* (06-11h): Pronóstico del día completo\n"
        f"• *Tarde* (12-18h): Tarde, noche y mañana siguiente\n"
        f"• *Noche* (20-22h): Pronóstico para el día siguiente"
    )
    
    await update.message.reply_text(
        msg,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )
    
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
    """✅ Panel de configuración CON alertas globales."""
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
        # Alertas climáticas locales
        [btn("rain", "Lluvia"), btn("storm", "Tormenta"), btn("snow", "Nieve/Escarcha")],
        [btn("uv_high", "UV Alto"), btn("fog", "Niebla")],
        [btn("temp_high", "Calor Intenso"), btn("temp_low", "Frío Intenso")],
        
        # ✅ NUEVA OPCIÓN: Alertas Globales
        [btn("global_disasters", "🌍 Desastres Naturales Globales")],
        
        [InlineKeyboardButton(_("🗑️ Eliminar Suscripción", user_id), callback_data="weather_unsub_confirm")],
        [InlineKeyboardButton(_("🔙 Volver", user_id), callback_data="weather_menu")]
    ]

    text = _(
        f"⚙️ *Configuración de Clima*\n"
        f"📍 {sub['city']}\n"
        f"⏰ Resumen: {sub['alert_time']}\n\n"
        f"*Alertas Locales:*\n"
        f"Recibe avisos sobre el clima en tu zona.\n\n"
        f"*Alertas Globales:*\n"
        f"Terremotos, tsunamis, huracanes y volcanes de impacto mundial.\n\n"
        f"Toca los botones para activar/desactivar:",
        user_id
    )

    try:
        await message_func(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
    except BadRequest as e:
        # ✅ CAPTURA: Si el mensaje es idéntico, solo responde al callback sin hacer nada
        if "Message is not modified" in str(e):
            if update.callback_query:
                await update.callback_query.answer("✅ Cambio aplicado")
        else:
            # Si es otro tipo de BadRequest, lo lanzamos
            raise


async def weather_toggle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Toggle de alertas con manejo de errores."""
    query = update.callback_query
    user_id = query.from_user.id
    alert_type = query.data.split("_", 2)[2]  # ✅ Corregido: split con límite
    
    # Responder inmediatamente al callback
    await query.answer("⏳ Actualizando...")
    
    # Hacer el cambio
    toggle_alert_type(user_id, alert_type)
    
    # Actualizar el menú
    try:
        await weather_settings_command(update, context)
    except BadRequest as e:
        if "Message is not modified" in str(e):
            # Si el mensaje no cambió, está bien, no hacer nada
            pass
        else:
            add_log_line(f"❌ Error al actualizar menú de clima: {e}")

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
