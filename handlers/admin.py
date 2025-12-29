# handlers/admin.py

import os
import time
import psutil 
import json
import asyncio
import openpyxl 
from io import BytesIO
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import BadRequest  
from telegram.constants import ParseMode
from telegram.ext import (
    ContextTypes, 
    ConversationHandler, 
    CommandHandler, 
    MessageHandler, 
    CallbackQueryHandler,
    filters
)
from utils.weather_manager import load_weather_subscriptions
from utils.valerts_manager import get_active_symbols, get_valerts_subscribers
from utils.btc_manager import load_btc_subs
from collections import Counter
from utils.file_manager import cargar_usuarios, load_price_alerts, get_user_alerts, load_hbd_history
from utils.ads_manager import load_ads, add_ad, delete_ad
from core.config import ( 
    VERSION, PID, PYTHON_VERSION, STATE, ADMIN_CHAT_IDS, 
    USUARIOS_PATH, PRICE_ALERTS_PATH, HBD_HISTORY_PATH,
    CUSTOM_ALERT_HISTORY_PATH, ADS_PATH, ELTOQUE_HISTORY_PATH,
    LAST_PRICES_PATH, TEMPLATE_PATH, HBD_THRESHOLDS_PATH,
    WEATHER_SUBS_PATH, WEATHER_LAST_ALERTS_PATH
    )
from core.i18n import _

# Definimos los estados para nuestra conversación de mensaje masivo
AWAITING_CONTENT, AWAITING_CONFIRMATION, AWAITING_ADDITIONAL_TEXT, AWAITING_ADDITIONAL_PHOTO = range(4)


# --- INICIO: NUEVA LÓGICA PARA /ms INTERACTIVO ---
async def ms_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Inicia la conversación para el mensaje masivo."""
    chat_id = update.effective_chat.id
    chat_id_str = str(chat_id)
    
    if chat_id_str not in ADMIN_CHAT_IDS:
        # Mensaje 1: No autorizado
        await update.message.reply_text(
            _("🚫 Comando no autorizado.", chat_id),
            parse_mode=ParseMode.MARKDOWN
        )
        return ConversationHandler.END

    # Limpiamos datos de conversaciones anteriores
    context.user_data.pop('ms_text', None)
    context.user_data.pop('ms_photo_id', None)

    # Mensaje 2: Instrucciones
    mensaje_instrucciones = _(
        "✍️ *Creación de Mensaje Masivo*\n\n"
        "Por favor, envía el contenido principal del mensaje.\n"
        "Puedes enviar una imagen, un texto, o una imagen con texto.",
        chat_id
    )
    
    await update.message.reply_text(
        mensaje_instrucciones,
        parse_mode=ParseMode.MARKDOWN
    )
    return AWAITING_CONTENT
async def handle_initial_content(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Captura el primer contenido enviado (texto o foto)."""
    message = update.message
    chat_id = update.effective_chat.id
    
    # Textos de los botones
    btn_add_photo = _("🖼️ Añadir Imagen", chat_id)
    btn_send_only_text = _("➡️ Enviar Solo Texto", chat_id)
    btn_cancel = _("❌ Cancelar", chat_id)
    btn_add_edit_text = _("✍️ Añadir/Editar Texto", chat_id)
    btn_send_only_photo = _("➡️ Enviar Solo Imagen", chat_id)
    
    if message.text:
        context.user_data['ms_text'] = message.text
        keyboard = [
            [InlineKeyboardButton(btn_add_photo, callback_data="ms_add_photo")],
            [InlineKeyboardButton(btn_send_only_text, callback_data="ms_send_final")],
            [InlineKeyboardButton(btn_cancel, callback_data="ms_cancel")]
        ]
        # Mensaje 1: Texto recibido, ¿añadir imagen?
        mensaje_texto_recibido = _(
            "✅ Texto recibido. ¿Deseas añadir una imagen o enviar el mensaje?", 
            chat_id
        )
        await message.reply_text(
            mensaje_texto_recibido,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    elif message.photo:
        context.user_data['ms_photo_id'] = message.photo[-1].file_id
        # Si la imagen tiene un pie de foto, lo guardamos también
        if message.caption:
            context.user_data['ms_text'] = message.caption

        keyboard = [
            [InlineKeyboardButton(btn_add_edit_text, callback_data="ms_add_text")],
            [InlineKeyboardButton(btn_send_only_photo, callback_data="ms_send_final")],
            [InlineKeyboardButton(btn_cancel, callback_data="ms_cancel")]
        ]
        # Mensaje 2: Imagen recibida, ¿añadir/editar texto?
        mensaje_foto_recibida = _(
            "✅ Imagen recibida. ¿Deseas añadir o editar el texto del pie de foto?",
            chat_id
        )
        await message.reply_text(
            mensaje_foto_recibida,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        # Mensaje 3: Error de contenido
        mensaje_error_contenido = _("⚠️ Por favor, envía un texto o una imagen.", chat_id)
        await message.reply_text(mensaje_error_contenido)
        return AWAITING_CONTENT

    return AWAITING_CONFIRMATION

async def handle_confirmation_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Maneja los botones de confirmación."""
    query = update.callback_query
    await query.answer()
    choice = query.data
    user_id = query.from_user.id

    if choice == "ms_add_text":
        mensaje_add_text = _(
            "✍️ De acuerdo, por favor envía el texto que quieres usar como pie de foto.",
            user_id
        )
        await query.edit_message_text(mensaje_add_text)
        return AWAITING_ADDITIONAL_TEXT
    elif choice == "ms_add_photo":
        mensaje_add_photo = _(
            "🖼️ Entendido, por favor envía la imagen que quieres adjuntar.",
            user_id
        )
        await query.edit_message_text(mensaje_add_photo)
        return AWAITING_ADDITIONAL_PHOTO
    elif choice == "ms_send_final":
        return await send_broadcast(query, context)
    elif choice == "ms_cancel":
        mensaje_cancelar = _(
            "🚫 Operación cancelada.",
            user_id
        )
        await query.edit_message_text(mensaje_cancelar)
        return ConversationHandler.END

async def receive_additional_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recibe el texto adicional para una imagen."""
    chat_id = update.effective_chat.id
    context.user_data['ms_text'] = update.message.text
    
    # Textos de los botones
    btn_send = _("🚀 Enviar a todos los usuarios", chat_id)
    btn_cancel = _("❌ Cancelar", chat_id)
    
    keyboard = [
        [InlineKeyboardButton(btn_send, callback_data="ms_send_final")],
        [InlineKeyboardButton(btn_cancel, callback_data="ms_cancel")]
    ]
    
    # Mensaje de confirmación
    mensaje_confirmacion = _(
        "✅ Texto añadido. El mensaje está listo para ser enviado.",
        chat_id
    )
    
    await update.message.reply_text(
        mensaje_confirmacion,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return AWAITING_CONFIRMATION
    
async def receive_additional_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recibe la imagen adicional para un texto."""
    chat_id = update.effective_chat.id
    context.user_data['ms_photo_id'] = update.message.photo[-1].file_id
    
    # TextOS de los botones
    btn_send = _("🚀 Enviar a todos los usuarios", chat_id)
    btn_cancel = _("❌ Cancelar", chat_id)
    
    keyboard = [
        [InlineKeyboardButton(btn_send, callback_data="ms_send_final")],
        [InlineKeyboardButton(btn_cancel, callback_data="ms_cancel")]
    ]
    
    # Mensaje de confirmación
    mensaje_confirmacion = _(
        "✅ Imagen añadida. El mensaje está listo para ser enviado.",
        chat_id
    )
    
    await update.message.reply_text(
        mensaje_confirmacion,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return AWAITING_CONFIRMATION

async def send_broadcast(query, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Función final que envía el mensaje a todos los usuarios."""
    chat_id = query.from_user.id
    
    # Mensaje 1: Iniciando envío
    mensaje_iniciando = _(
        "⏳ *Enviando mensaje a todos los usuarios...*\nEsto puede tardar un momento.",
        chat_id
    )
    await query.edit_message_text(mensaje_iniciando, parse_mode=ParseMode.MARKDOWN)

    global _enviar_mensaje_telegram_async_ref
    if not _enviar_mensaje_telegram_async_ref:
        # Mensaje 2: Error interno
        mensaje_error_interno = _("❌ Error interno: La función de envío masivo no ha sido inicializada.", chat_id)
        await query.message.reply_text(mensaje_error_interno)
        return ConversationHandler.END

    text_to_send = context.user_data.get('ms_text', "")
    photo_id_to_send = context.user_data.get('ms_photo_id')
    
    usuarios = cargar_usuarios()
    chat_ids = list(usuarios.keys())
        
    fallidos = await _enviar_mensaje_telegram_async_ref(
        text_to_send, 
        chat_ids, 
        photo=photo_id_to_send
    )

    total_enviados = len(chat_ids) - len(fallidos)
    if fallidos:
        # Mensaje 3a: Reporte de fallos
        fallidos_reporte = [f"  - `{chat_id}`: _{error}_" for chat_id, error in fallidos.items()]
        fallidos_str = "\n".join(fallidos_reporte)
        
        mensaje_admin_base = _(
            "✅ Envío completado.\n\n"
            "Enviado a *{total_enviados}* de {total_usuarios} usuarios.\n\n"
            "❌ Fallos ({num_fallos}):\n{fallidos_str}",
            chat_id
        )
        mensaje_admin = mensaje_admin_base.format(
            total_enviados=total_enviados,
            total_usuarios=len(chat_ids),
            num_fallos=len(fallidos),
            fallidos_str=fallidos_str
        )
    else:
        # Mensaje 3b: Éxito total
        mensaje_admin_base = _(
            "✅ ¡Éxito! Mensaje enviado a todos los *{total_usuarios}* usuarios.",
            chat_id
        )
        mensaje_admin = mensaje_admin_base.format(total_usuarios=len(chat_ids))

    await query.message.reply_text(mensaje_admin, parse_mode=ParseMode.MARKDOWN)

    # Limpiar datos al finalizar
    context.user_data.pop('ms_text', None)
    context.user_data.pop('ms_photo_id', None)
    
    return ConversationHandler.END

async def cancel_ms(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Función para cancelar la conversación."""
    chat_id = update.effective_chat.id
    
    mensaje_cancelado = _(
        "🚫 Operación cancelada.",
        chat_id
    )
    
    await update.message.reply_text(mensaje_cancelado)
    
    # Limpiar datos al cancelar
    context.user_data.pop('ms_text', None)
    context.user_data.pop('ms_photo_id', None)
    
    return ConversationHandler.END

# Definición del ConversationHandler para el comando /ms
# Definición del ConversationHandler para el comando /ms
ms_conversation_handler = ConversationHandler(
    entry_points=[CommandHandler("ms", ms_start)],
    states={
        AWAITING_CONTENT: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_initial_content),
            MessageHandler(filters.PHOTO, handle_initial_content)
        ],
        AWAITING_CONFIRMATION: [
            CallbackQueryHandler(handle_confirmation_choice)
        ],
        AWAITING_ADDITIONAL_TEXT: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, receive_additional_text)
        ],
        AWAITING_ADDITIONAL_PHOTO: [
            MessageHandler(filters.PHOTO, receive_additional_photo)
        ],
    },
    fallbacks=[CommandHandler("cancelar", cancel_ms)],
    conversation_timeout=600, 
    #per_message=True # <---  COMENTANDO ESTA LÍNEA
)
# Referencias para inyección de funciones
# Estas referencias se inyectan desde bbalert para enviar mensajes masivos y obtener logs
_enviar_mensaje_telegram_async_ref = None
_get_logs_data_ref = None

def set_admin_util(func):
    """Permite a bbalert inyectar la función de envío masivo."""
    global _enviar_mensaje_telegram_async_ref
    _enviar_mensaje_telegram_async_ref = func

def set_logs_util(func):
    """Permite a bbalert inyectar la función para obtener los logs."""
    global _get_logs_data_ref
    _get_logs_data_ref = func


# ==============================================================================
# COMANDO /users (REFORMADO - DASHBOARD SUPER PRO)
# ==============================================================================

# --- DEFINICIÓN GLOBAL DEL OBJETO PSUTIL
# Al iniciarlo aquí, el objeto se mantiene vivo todo el tiempo que el bot corre.
proc_global = psutil.Process(os.getpid())
# Hacemos una primera lectura "falsa" al arrancar para iniciar el contador
proc_global.cpu_percent(interval=None)

async def users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Dashboard de Administración SUPER PRO.
    Muestra estadísticas de Usuarios, Negocio, Carga, BTC, HBD, Clima y Valerts.
    """
    chat_id = update.effective_chat.id
    chat_id_str = str(chat_id)
    
    # 1. CARGA DE DATOS (Centralizada)
    usuarios = cargar_usuarios()
    all_alerts = load_price_alerts()
    btc_subs = load_btc_subs()
    
    # Carga de datos de Clima y Valerts
    weather_subs = load_weather_subscriptions()
    valerts_symbols = get_active_symbols()
    
    # 2. VISTA DE USUARIO NORMAL (Perfil Propio)
    if chat_id_str not in ADMIN_CHAT_IDS:
        user_data = usuarios.get(chat_id_str)
        if not user_data:
            await update.message.reply_text("❌ No estás registrado.")
            return

        # Calcular datos del usuario
        monedas = user_data.get('monedas', [])
        alerts_count = len([a for a in all_alerts.get(chat_id_str, []) if a['status'] == 'ACTIVE'])
        
        # Estados de servicios
        btc_status = "✅ Activado" if btc_subs.get(chat_id_str, {}).get('active') else "❌ Desactivado"
        hbd_status = "✅ Activado" if user_data.get('hbd_alerts') else "❌ Desactivado"
        weather_status = "✅ Activado" if str(chat_id) in weather_subs else "❌ Desactivado"
        
        # Suscripciones activas
        subs = user_data.get('subscriptions', {})
        active_subs = []
        now = datetime.now()
        
        map_names = {
            'watchlist_bundle': '📦 Pack Control Total',
            'tasa_vip': '💱 Tasa VIP',
            'ta_vip': '📈 TA Pro',
            'coins_extra': '🪙 Slot Moneda',
            'alerts_extra': '🔔 Slot Alerta'
        }

        for key, val in subs.items():
            # Tipo A: Por tiempo (active + expires)
            if isinstance(val, dict) and val.get('active'):
                exp = val.get('expires')
                if exp:
                    try:
                        if datetime.strptime(exp, '%Y-%m-%d %H:%M:%S') > now:
                            active_subs.append(f"• {map_names.get(key, key)} (Vence: {exp.split()[0]})")
                    except: pass
            # Tipo B: Por cantidad (qty > 0)
            elif isinstance(val, dict) and val.get('qty', 0) > 0:
                active_subs.append(f"• {map_names.get(key, key)} (+{val['qty']})")

        subs_txt = "\n".join(active_subs) if active_subs else "_Sin suscripciones activas_"

        msg = (
            f"👤 *TU PERFIL BITBREAD*\n"
            f"—————————————————\n"
            f"🆔 ID: `{chat_id}`\n"
            f"🗣 Idioma: `{user_data.get('language', 'es')}`\n\n"
            f"📊 *Configuración:*\n"
            f"• Monedas Lista: `{', '.join(monedas)}`\n"
            f"• Alertas Cruce: `{alerts_count}` activas\n\n"
            f"📡 *Servicios Activos:*\n"
            f"• Monitor BTC: {btc_status}\n"
            f"• Monitor HBD: {hbd_status}\n"
            f"• Monitor Clima: {weather_status}\n\n"
            f"💎 *Suscripciones:*\n"
            f"{subs_txt}"
        )
        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
        return

    # 3. VISTA DE ADMINISTRADOR (DASHBOARD PRO)
    msg_loading = await update.message.reply_text("⏳ *Analizando Big Data...*", parse_mode=ParseMode.MARKDOWN)
    
    # --- A. CÁLCULOS DE USUARIOS ---
    total_users = len(usuarios)
    active_24h = 0
    lang_es = 0
    lang_en = 0
    
    # Contadores VIP
    vip_stats = {
        'watchlist_bundle': 0, 
        'tasa_vip': 0, 
        'ta_vip': 0,
        'coins_extra_users': 0,
        'alerts_extra_users': 0
    }
    
    # Contadores de Carga (Uso hoy)
    total_usage_today = 0
    usage_breakdown = Counter()
    
    now = datetime.now()
    
    for uid, u in usuarios.items():
        # 1. Actividad (Basado en si el loop de alertas corrió recientemente)
        last_alert = u.get('last_alert_timestamp')
        if last_alert:
            try:
                last_dt = datetime.strptime(last_alert, '%Y-%m-%d %H:%M:%S')
                if (now - last_dt).days < 1:
                    active_24h += 1
            except: pass
            
        # 2. Idioma
        if u.get('language') == 'en': lang_en += 1
        else: lang_es += 1
        
        # 3. VIP Check
        subs = u.get('subscriptions', {})
        # Check tiempo
        for k in ['watchlist_bundle', 'tasa_vip', 'ta_vip']:
            s = subs.get(k, {})
            if s.get('active') and s.get('expires'):
                try:
                    if datetime.strptime(s['expires'], '%Y-%m-%d %H:%M:%S') > now:
                        vip_stats[k] += 1
                except: pass
        # Check cantidad
        if subs.get('coins_extra', {}).get('qty', 0) > 0: vip_stats['coins_extra_users'] += 1
        if subs.get('alerts_extra', {}).get('qty', 0) > 0: vip_stats['alerts_extra_users'] += 1
        
        # 4. Uso Diario (Carga del Bot)
        daily = u.get('daily_usage', {})
        if daily.get('date') == now.strftime('%Y-%m-%d'):
            for cmd, count in daily.items():
                if cmd != 'date' and isinstance(count, int):
                    usage_breakdown[cmd] += count
                    total_usage_today += count

    # --- B. CÁLCULOS DE ALERTAS & MONEDAS ---
    total_alerts_active = 0
    coin_popularity = Counter()
    
    for uid, alerts in all_alerts.items():
        for a in alerts:
            if a['status'] == 'ACTIVE':
                total_alerts_active += 1
                coin_popularity[a['coin']] += 1
    
    top_coins = coin_popularity.most_common(5)
    top_coins_str = ", ".join([f"{c[0]} ({c[1]})" for c in top_coins]) if top_coins else "N/A"

    # --- C. CÁLCULOS DE SERVICIOS (BTC, HBD, CLIMA, VALERTS) ---
    
    # 1. BTC
    btc_subscribers = sum(1 for s in btc_subs.values() if s.get('active'))
    
    # 2. HBD
    hbd_subscribers = sum(1 for u in usuarios.values() if u.get('hbd_alerts'))
    
    # 3. CLIMA (Weather)
    weather_subscribers = len(weather_subs)
    
    # 4. VALERTS (Volatilidad)
    valerts_active_symbols_count = len(valerts_symbols)
    valerts_unique_users = set()
    
    for sym in valerts_symbols:
        # Obtenemos lista de IDs suscritos a cada símbolo
        subs_list = get_valerts_subscribers(sym)
        if subs_list:
            for uid in subs_list:
                valerts_unique_users.add(uid)
                
    valerts_total_users = len(valerts_unique_users)

    # --- D. CÁLCULOS DE RECURSOS (RAM, CPU, Uptime) ---
    # 0. Proceso actual
    process = psutil.Process(os.getpid())

    # 1. Uso de Memoria y CPU
    mem_usage = process.memory_info().rss / 1024 / 1024 # MB
    mem_asignada = process.memory_info().vms / 1024 / 1024 # MB
    cpu_percent = proc_global.cpu_percent(interval=None)

    # 2. Uptime
    process = psutil.Process(os.getpid())
    uptime_seconds = time.time() - process.create_time()
    uptime_str = str(timedelta(seconds=int(uptime_seconds)))

    # 3. Size file
    size={"file_size": 0}
    archivos = [
        USUARIOS_PATH, PRICE_ALERTS_PATH, HBD_HISTORY_PATH,
        CUSTOM_ALERT_HISTORY_PATH, ADS_PATH, ELTOQUE_HISTORY_PATH,
        LAST_PRICES_PATH, TEMPLATE_PATH, HBD_THRESHOLDS_PATH,
        WEATHER_SUBS_PATH, WEATHER_LAST_ALERTS_PATH
    ]
    
    total_kb = 0
    for ruta in archivos:
        try:
            if os.path.exists(ruta): # Verificamos que el archivo exista
                total_kb += os.path.getsize(ruta)
        except Exception:
            continue
            
    size["file_size"] = total_kb / 1024 / 1024  # MB

    # --- CONSTRUCCIÓN DEL DASHBOARD ---
    dashboard = (
        f"👮‍♂️ *PANEL DE CONTROL* v{VERSION}\n"
        f"📅 {now.strftime('%d/%m/%Y %H:%M')}\n"
        f"———————————————————\n\n"

        f"*🖥️ ESTADO DEL SISTEMA*\n"
        f"├ *Uptime:* `{uptime_str}`\n"
        f"├ *RAM:* `{mem_usage:.2f} MB`\n"
        f"├ *VMS:* `{mem_asignada:.2f} MB`\n"
        f"├ *CPU:* `{cpu_percent}%`\n"
        f"└ *DATA:* `{size['file_size']:.2f} MB`\n\n"

        f"⚙️ *CARGA DEL SISTEMA (Hoy)*\n"
        f"├ Comandos Procesados: `{total_usage_today}`\n"
        f"├ Desglose: Ver({usage_breakdown['ver']}) | Tasa({usage_breakdown['tasa']}) | TA({usage_breakdown['ta']})\n"
        f"└ Alertas Cruce Vigilando: `{total_alerts_active}`\n\n"

        f"👥 *USUARIOS*\n"
        f"├ Totales: `{total_users}`\n"
        f"├ Activos (24h): `{active_24h}` ({int(active_24h/total_users*100) if total_users else 0}%)\n"
        f"└ Idiomas: 🇪🇸 {lang_es} | 🇺🇸 {lang_en}\n\n"
        
        f"💎 *NEGOCIO (Suscripciones Activas)*\n"
        f"📦 Pack Control Total: `{vip_stats['watchlist_bundle']}`\n"
        f"💱 Tasa VIP: `{vip_stats['tasa_vip']}`\n"
        f"📈 TA Pro: `{vip_stats['ta_vip']}`\n"
        f"➕ Extras: `{vip_stats['coins_extra_users']}` Coins | `{vip_stats['alerts_extra_users']}` Alertas\n\n"
        
        f"📢 *SERVICIOS DE NOTIFICACIÓN*\n"
        f"🦁 Monitor BTC: `{btc_subscribers}` usuarios\n"
        f"🐝 Monitor HBD: `{hbd_subscribers}` usuarios\n"
        f"🌦️ Monitor Clima: `{weather_subscribers}` usuarios\n"
        f"🚀 Valerts (Volatilidad): `{valerts_total_users}` usuarios en `{valerts_active_symbols_count}` monedas\n\n"
        
        f"🏆 *TENDENCIAS DE MERCADO*\n"
        f"🔥 Top Monedas Vigiladas:\n"
        f"`{top_coins_str}`\n"
    )

    await msg_loading.edit_text(dashboard, parse_mode=ParseMode.MARKDOWN)



# COMANDO /logs para ver las últimas líneas del log
async def logs_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    current_chat_id = update.effective_chat.id # <-- Obtener chat_id
    global _get_logs_data_ref # <--- ¡ARREGLO 1: Mover esta línea aquí!
    
    # Comprobar si el ID está en la lista de administradores
    if str(current_chat_id) not in ADMIN_CHAT_IDS:
        # Obtener la última actualización desde el log si es posible
        # global _get_logs_data_ref <--- Quitarla de aquí
        ultima_actualizacion = "N/A"
        if _get_logs_data_ref:
            log_data_full = _get_logs_data_ref()
            if log_data_full:
                try:
                    timestamp_ms_part = log_data_full[-1].split(" | ")[0]
                    timestamp_part = timestamp_ms_part.split("[")[1].split("]")[0].strip()
                    ultima_actualizacion = f"{timestamp_part} UTC"
                except Exception:
                    pass

        # --- PLANTILLA ENVUELTA ---
        mensaje_template = _(
            "🤖 *Estado de BitBread Alert*\n\n"
            "—————————————————\n"
            "• Versión: {version} 🤖\n"
            "• Estado: {estado} 👌\n"
            "• Última Actualización: {ultima_actualizacion} 🕒 \n"
            "—————————————————\n\n"
            "_Ya, eso es todo lo que puedes ver 🙂👍_",
            current_chat_id
        )
        
        # --- ¡NUEVA SECCIÓN DE ESCAPE! ---
        # Escapamos las variables para evitar errores de Markdown
        safe_version = str(VERSION).replace("_", " ").replace("*", " ").replace("`", " ")
        safe_estado = str(STATE).replace("_", " ").replace("*", " ").replace("`", " ")
        safe_ultima_actualizacion = str(ultima_actualizacion).replace("_", " ").replace("*", " ").replace("`", " ")

        mensaje = mensaje_template.format(
            version=safe_version,
            estado=safe_estado,
            ultima_actualizacion=safe_ultima_actualizacion
        )
        await update.message.reply_text(mensaje, parse_mode=ParseMode.MARKDOWN)
        return

    # --- Lógica de Administrador ---
    
    # Verificar que la función de logs ha sido inyectada correctamente
    if not _get_logs_data_ref:
        await update.message.reply_text(_("❌ Error interno: La función de logs no ha sido inicializada.", current_chat_id))
        return

    # Obtener todas las líneas del log
    log_data_full = _get_logs_data_ref()

    # 1. Obtener argumento opcional: número de líneas (por defecto 10)
    n_lineas_default = 10
    try:
        n_lineas = int(context.args[0]) if context.args and context.args[0].isdigit() else n_lineas_default
        n_lineas = max(1, min(n_lineas, 100))
    except ValueError:
        # --- MENSAJE ENVUELTO ---
        await update.message.reply_text(_("⚠️ El argumento debe ser un número entero.", current_chat_id))
        return

    # 2. Extraer las últimas N líneas
    log_data_n_lines = log_data_full[-n_lineas:] if log_data_full else []
    
    # (Esta es tu limpieza de logs, que ya estaba bien)
    log_lines_cleaned = [
        line.replace("_", " ").replace("*", "#").replace("`", "'")
            .replace("[", "(").replace("]", ")")
        for line in log_data_n_lines
    ]

    log_str = "\n".join(log_lines_cleaned)

    # Extraer la marca de tiempo de la última línea del log
    ultima_actualizacion = "N/A"
    if log_data_full: 
        try:
            timestamp_ms_part = log_data_full[-1].split(" | ")[0] 
            timestamp_part = timestamp_ms_part.split("[")[1].split("]")[0].strip()
            ultima_actualizacion = f"{timestamp_part} UTC"
        except Exception:
            pass

    # 3. Mensaje de respuesta completo para administradores
    # --- PLANTILLA ENVUELTA ---
    mensaje_template = _(
        "🤖 *Estado de BitBread Alert*\n"
        "—————————————————\n"
        "• Versión: {version} 🤖\n"
        "• PID: {pid} 🪪\n"
        "• Python: {python_version} 🐍\n"
        "• Usuarios: {num_usuarios} 👥\n"
        "• Estado: {estado} 👌\n"
        "• Última Actualización: {ultima_actualizacion} 🕒 \n"
        "—————————————————\n"
        "•📜 *Últimas {num_lineas} líneas de {total_lineas} *\n ```{log_str}```\n",
        current_chat_id
    )

    # --- ¡NUEVA SECCIÓN DE ESCAPE (PARA ADMIN)! ---
    # Escapamos todas las variables que podrían contener _ * `
    safe_version = str(VERSION).replace("_", " ").replace("*", " ").replace("`", " ")
    safe_pid = str(PID).replace("_", " ").replace("*", " ").replace("`", " ")
    safe_python_version = str(PYTHON_VERSION).replace("_", " ").replace("*", " ").replace("`", " ")
    safe_estado = str(STATE).replace("_", " ").replace("*", " ").replace("`", " ")
    safe_ultima_actualizacion = str(ultima_actualizacion).replace("_", " ").replace("*", " ").replace("`", " ")

    mensaje = mensaje_template.format(
        version=safe_version,
        pid=safe_pid,
        python_version=safe_python_version,
        num_usuarios=len(cargar_usuarios()),
        estado=safe_estado,
        ultima_actualizacion=safe_ultima_actualizacion,
        num_lineas=len(log_data_n_lines),
        total_lineas=len(log_data_full),
        log_str=log_str
    )

    await update.message.reply_text(mensaje, parse_mode=ParseMode.MARKDOWN)


# --- COMANDO /ad SUPER ROBUSTO ---
async def ad_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Gestión de anuncios robusta.
    Si el Markdown del usuario falla, se envía en texto plano.
    """
    chat_id = update.effective_chat.id
    user_id_str = str(update.effective_user.id)

    if user_id_str not in ADMIN_CHAT_IDS:
        return 

    args = context.args

    # --- LISTAR ANUNCIOS ---
    if not args:
        ads = load_ads()
        if not ads:
            await update.message.reply_text("📭 No hay anuncios activos.\nUsa `/ad add Mi Anuncio` para crear uno.", parse_mode=ParseMode.MARKDOWN)
            return
        
        mensaje = "📢 *Lista de Anuncios Activos:*\n\n"
        for i, ad in enumerate(ads):
            # Intentamos preservar el formato que haya puesto el usuario
            mensaje += f"*{i+1}.* {ad}\n"
        
        mensaje += "\nPara borrar: `/ad del N` (ej: `/ad del 1`)"

        try:
            await update.message.reply_text(mensaje, parse_mode=ParseMode.MARKDOWN)
        except BadRequest:
            # FALLBACK: Si falla el Markdown (ej: un '_' sin cerrar), enviamos texto plano
            fallback_msg = "⚠️ *Error de visualización Markdown*\n" \
                           "Alguno de tus anuncios tiene caracteres especiales sin cerrar, pero aquí está la lista en texto plano:\n\n"
            for i, ad in enumerate(ads):
                fallback_msg += f"{i+1}. {ad}\n"
            
            fallback_msg += "\nUsa /ad del N para eliminar."
            await update.message.reply_text(fallback_msg) # Sin parse_mode
        return

    accion = args[0].lower()

    # --- AÑADIR ANUNCIO ---
    if accion == "add":
        if len(args) < 2:
            await update.message.reply_text("⚠️ Escribe el texto del anuncio.\nEj: `/ad add Visita mi canal @canal`", parse_mode=ParseMode.MARKDOWN)
            return
        
        texto_nuevo = ' '.join(args[1:]) 
        add_ad(texto_nuevo) # Guardamos EXACTAMENTE lo que escribió el usuario
        
        # Intentamos confirmar con Markdown bonito
        try:
            await update.message.reply_text(f"✅ Anuncio añadido:\n\n_{texto_nuevo}_", parse_mode=ParseMode.MARKDOWN)
        except BadRequest:
            # Si falla (ej: usuario puso 'pepe_bot' sin escapar), confirmamos en texto plano
            await update.message.reply_text(f"✅ Anuncio añadido (Sintaxis MD inválida, mostrado plano):\n\n{texto_nuevo}")

    # --- BORRAR ANUNCIO ---
    elif accion == "del":
        try:
            indice = int(args[1]) - 1 
            eliminado = delete_ad(indice)
            if eliminado:
                # Intentamos mostrar confirmación bonita
                try:
                    await update.message.reply_text(f"🗑️ Anuncio eliminado:\n\n_{eliminado}_", parse_mode=ParseMode.MARKDOWN)
                except BadRequest:
                     # Si falla, confirmamos en texto plano
                    await update.message.reply_text(f"🗑️ Anuncio eliminado:\n\n{eliminado}")
            else:
                await update.message.reply_text("⚠️ Número de anuncio no válido.", parse_mode=ParseMode.MARKDOWN)
        except (IndexError, ValueError):
            await update.message.reply_text("⚠️ Uso: `/ad del N` (N es el número del anuncio).", parse_mode=ParseMode.MARKDOWN)
    
    else:
        await update.message.reply_text("⚠️ Comandos: `/ad`, `/ad add <txt>`, `/ad del <num>`", parse_mode=ParseMode.MARKDOWN)