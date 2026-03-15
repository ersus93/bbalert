# handlers/general.py

import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
from utils.file_manager import (
    registrar_usuario,
    obtener_monedas_usuario,
    load_last_prices_status,
    obtener_datos_usuario,
    check_feature_access,
    registrar_uso_comando,
    get_user_meta,
    set_user_meta
)
from core.api_client import obtener_precios_control
from utils.ads_manager import get_random_ad_text
from core.config import ADMIN_CHAT_IDS
from locales.texts import HELP_MSG
from core.i18n import _
from handlers.trading import p_command

#  Telegram comando /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /start. Versión simplificada con CTA buttons."""
    user = update.effective_user
    user_id = user.id
    user_lang = user.language_code

    registrar_usuario(user_id, user_lang)

    # Mensaje corto (< 30 palabras)
    mensaje = _(
        "👋 ¡Hola {nombre}!\n\n"
        "¿Qué quieres hacer?",
        user_id
    ).format(nombre=user.first_name)

    # Botones CTA claros
    keyboard = [
        [InlineKeyboardButton("🚨 Crear Alerta", callback_data="start_create_alert")],
        [InlineKeyboardButton("📊 Ver Precios", callback_data="start_check_price")],
        [InlineKeyboardButton("📚 Ayuda", callback_data="start_help")]
    ]

    await update.message.reply_text(
        mensaje,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )


async def start_button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle callbacks from /start buttons."""
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    
    if data == "start_create_alert":
        await query.edit_message_text(
            _(
                "🚨 *Crear Alerta*\n\n"
                "Usa: /alerta MONEDA PRECIO\n\n"
                "Ejemplo: /alerta BTC 50000",
                user_id
            ),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "start_check_price":
        await query.edit_message_text(
            _(
                "📊 *Ver Precios*\n\n"
                "Usa: /p MONEDA\n\n"
                "Ejemplo: /p BTC",
                user_id
            ),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "start_help":
        await help_command(update, context)

# COMANDO /ver REFACTORIZADO
async def ver(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    # === DEPRECATION NOTICE ===
    # Only show once per user
    deprecated_notified = get_user_meta(user_id, 'ver_deprecated_notified')
    if not deprecated_notified:
        await update.message.reply_text(
            _(
                "💡 *Comando actualizado*\n\n"
                "Ahora usa `/precios` para ver tus precios.\n\n"
                "_Este mensaje solo se muestra una vez._",
                user_id
            ),
            parse_mode=ParseMode.MARKDOWN
        )
        set_user_meta(user_id, 'ver_deprecated_notified', True)
    
    # === GUARDIA DE PAGO ===
    # 1. Verificar acceso
    acceso, mensaje = check_feature_access(chat_id, 'ver_limit')
    if not acceso:
        # Si no tiene acceso, enviamos el mensaje de error (que contiene la info de venta) y paramos.
        await update.message.reply_text(mensaje, parse_mode=ParseMode.MARKDOWN)
        return

    # 2. Registrar el uso (se descuenta 1 del contador)
    registrar_uso_comando(chat_id, 'ver')
    # =======================
    # === LÓGICA DEL COMANDO /ver ====    
    # 1. Obtener las monedas configuradas por el usuario
    monedas = obtener_monedas_usuario(chat_id)
    
    if not monedas:
        await update.message.reply_text(
            _("⚠️ No tienes monedas configuradas. Usa /monedas para añadir algunas.", user_id),
            parse_mode=ParseMode.MARKDOWN
        )
        return

    # 2. Notificar que estamos cargando (ya que la API puede tardar un segundo)
    mensaje_espera = await update.message.reply_text(_("⏳ Consultando precios actuales...", user_id))

    # 3. Obtener precios en tiempo real
    precios_actuales = obtener_precios_control(monedas)
    
    if not precios_actuales:
        await mensaje_espera.edit_text(
            _("❌ No se pudieron obtener los precios en este momento. Intenta luego.", user_id)
        )
        return

    # 4. Cargar precios anteriores (SOLO LECTURA) para mostrar tendencias
    # No guardamos nada aquí para no romper la lógica de "cambio desde la última alerta".
    todos_precios_anteriores = load_last_prices_status()
    precios_anteriores_usuario = todos_precios_anteriores.get(str(chat_id), {})

    # 5. Construir el mensaje
    mensaje = _("📊 *Precios Actuales (Tu Lista):*\n—————————————————\n\n", user_id)
    
    TOLERANCIA = 0.0000001
    
    for moneda in monedas:
        p_actual = precios_actuales.get(moneda)
        p_anterior = precios_anteriores_usuario.get(moneda)
        
        if p_actual is not None:
            # Calcular indicador visual
            indicador = ""
            if p_anterior:
                if p_actual > p_anterior + TOLERANCIA:
                    indicador = " 🔺"
                elif p_actual < p_anterior - TOLERANCIA:
                    indicador = " 🔻"
                else:
                    indicador = " ▫️"
            
            mensaje += f"*{moneda}/USD*: ${p_actual:,.4f}{indicador}\n"
        else:
             mensaje += f"*{moneda}/USD*: N/A\n"

    # Añadir fecha
    fecha_actual = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    mensaje += f"\n—————————————————\n_📅 Consulta: {fecha_actual}_"

    mensaje += get_random_ad_text()

    # 6. Editar el mensaje de espera con el resultado final
    await mensaje_espera.edit_text(mensaje, parse_mode=ParseMode.MARKDOWN)

# ============================================================

# COMANDO /myid para ver datos del usuario
async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /myid. Muestra el ID de chat del usuario."""
    user_id = update.effective_user.id
    user = update.effective_user

    nombre_completo = user.first_name or 'N/A'
    username_str = f"@{user.username}" if user.username else 'N/A'


    mensaje_template = _(
        "Estos son tus datos de Telegram:\n—————————————————\n\n"
        "Nombre: {nombre}\n"
        "Usuario: {usuario}\n"
        "ID: `{id_chat}`",
        user_id 
    )


    mensaje = mensaje_template.format(
        nombre=nombre_completo,
        usuario=username_str,
        id_chat=user_id
    )

    await update.message.reply_text(mensaje, parse_mode=ParseMode.MARKDOWN)


# COMANDO /help
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra el menú de ayuda simplificado (nivel 1)."""
    user = update.effective_user
    user_id = user.id

    # Check if user wants full help
    args = context.args
    if args and args[0].lower() in ['completo', 'full', 'all']:
        await show_full_help(update, context)
        return

    # Level 1: Category navigation
    keyboard = [
        [InlineKeyboardButton("🚨 Alertas", callback_data="help_alerts")],
        [InlineKeyboardButton("📊 Trading", callback_data="help_trading")],
        [InlineKeyboardButton("🌤️ Clima", callback_data="help_weather")],
        [InlineKeyboardButton("⚙️ Ajustes", callback_data="help_settings")],
        [InlineKeyboardButton("📋 Ver TODOS los comandos", callback_data="help_all")]
    ]

    # Get localized message
    datos_usuario = obtener_datos_usuario(user_id)
    lang = datos_usuario.get('language', 'es')
    if lang not in ['es', 'en']:
        lang = 'es'
    
    texto = HELP_MSG.get(lang, HELP_MSG['es'])

    await update.message.reply_text(
        text=texto,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN,
        disable_web_page_preview=True
    )


async def help_category_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle callbacks from help category buttons."""
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    
    # Get localized category content
    datos_usuario = obtener_datos_usuario(user_id)
    lang = datos_usuario.get('language', 'es')
    if lang not in ['es', 'en']:
        lang = 'es'
    
    help_categories = HELP_CATEGORIES.get(lang, HELP_CATEGORIES['es'])
    content = help_categories.get(data, "❌ Opción no válida")
    
    # Add back button
    keyboard = [[InlineKeyboardButton("← Volver", callback_data="help_back")]]
    
    await query.edit_message_text(
        content,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )


async def help_back_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Return to main help menu."""
    query = update.callback_query
    await query.answer()
    # Re-show main help
    await help_command(update, context)


async def show_full_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show full help menu (all commands)."""
    user = update.effective_user
    user_id = user.id

    datos_usuario = obtener_datos_usuario(user_id)
    lang = datos_usuario.get('language', 'es')
    if lang not in ['es', 'en']:
        lang = 'es'
    
    texto = HELP_FULL.get(lang, HELP_FULL['es'])
    
    # Add back button
    keyboard = [[InlineKeyboardButton("← Volver a categorías", callback_data="help_back")]]

    await update.message.reply_text(
        text=texto,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN,
        disable_web_page_preview=True
    )