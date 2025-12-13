# handlers/pay.py - VERSIÓN CORREGIDA Y FUNCIONAL

from telegram import Update, LabeledPrice, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from utils.file_manager import add_subscription_days, obtener_datos_usuario_seguro, add_log_line
from core.config import ADMIN_CHAT_IDS
from utils.rss_manager_v2 import add_purchased_slot
from core.i18n import _
from datetime import datetime

# === LISTA DE PRECIOS (En Telegram Stars - XTR) ===
PRICE_BUNDLE = 20           # Temp flexible + Ver x24 + Cambios ilimitados
PRICE_COIN_SLOT = 5         # +1 Capacidad en lista
PRICE_ALERT_SLOT = 4        # +1 Alerta de Cruce (Par Arriba/Abajo)
PRICE_TASA_VIP = 5          # Tasa x24 consultas
PRICE_TA_VIP = 10           # TA Ilimitado
PRICE_RSS_CHANNEL = 100     # Precio de Channel Slot (CORREGIDO: era 1000)
PRICE_RSS_FEED = 50         # Precio de Feed Slot (CORREGIDO: era 250)

# === MENÚ DE LA TIENDA ===
async def shop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra el menú de suscripciones y compras disponibles."""
    user_id = update.effective_user.id
    
    # Aseguramos que el usuario tenga estructura de datos
    obtener_datos_usuario_seguro(user_id)
    
    titulo = (
        "🛒 *Tienda de BitBread Alert* 🛒\n"
        "—————————————————\n\n"
        "Mejora tu experiencia adquiriendo capacidades extra con *Telegram Stars* ⭐.\n\n"
        "—————————————————\n"
        "*Selecciona una opción 👇*"
    )
    
    keyboard = [
        [InlineKeyboardButton(f"📦 Pack Total - {PRICE_BUNDLE} ⭐", callback_data="buy_bundle")],
        [InlineKeyboardButton(f"🪙 +1 Moneda - {PRICE_COIN_SLOT} ⭐", callback_data="buy_coin")],
        [InlineKeyboardButton(f"🔔 +1 Alerta - {PRICE_ALERT_SLOT} ⭐", callback_data="buy_alert")],
        [InlineKeyboardButton(f"💱 Tasa VIP - {PRICE_TASA_VIP} ⭐", callback_data="buy_tasa")],
        [InlineKeyboardButton(f"📈 TA Pro - {PRICE_TA_VIP} ⭐", callback_data="buy_ta")],
        [InlineKeyboardButton(f"📺 +1 Canal RSS - {PRICE_RSS_CHANNEL} ⭐", callback_data="buy_rss_channel")],
        [InlineKeyboardButton(f"🔗 +1 Feed RSS - {PRICE_RSS_FEED} ⭐", callback_data="buy_rss_feed")],
    ]
    
    await update.message.reply_text(
        titulo, 
        reply_markup=InlineKeyboardMarkup(keyboard), 
        parse_mode=ParseMode.MARKDOWN
    )


# === MANEJADOR DE BOTONES DE COMPRA ===
async def shop_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Genera la factura (Invoice) cuando el usuario pulsa un botón."""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    chat_id = query.message.chat_id
    user_id = query.from_user.id
    
    # ✅ MAPEO COMPLETO DE PRODUCTOS
    products = {
        "buy_bundle": {
            "title": "📦 Pack Control Total (30 días)",
            "description": "Alertas cada 15min-24h + Cambios ilimitados + Comando /ver x24 diario.",
            "payload": "sub_watchlist_bundle",
            "price": PRICE_BUNDLE,
            "item_name": "📦 Pack Control Total"
        },
        "buy_coin": {
            "title": "🪙 +1 Espacio Moneda (30 días)",
            "description": "Añade 1 moneda extra a tu lista de seguimiento /monedas.",
            "payload": "sub_coins_extra",
            "price": PRICE_COIN_SLOT,
            "item_name": "🪙 +1 Moneda Extra"
        },
        "buy_alert": {
            "title": "🔔 +1 Alerta Cruce (30 días)",
            "description": "Añade 1 par de alertas de precio (Arriba/Abajo) extra.",
            "payload": "sub_alerts_extra",
            "price": PRICE_ALERT_SLOT,
            "item_name": "🔔 +1 Alerta Cruce"
        },
        "buy_tasa": {
            "title": "💱 Tasa VIP (30 días)",
            "description": "Aumenta el límite del comando /tasa a 24 veces por día.",
            "payload": "sub_tasa_vip",
            "price": PRICE_TASA_VIP,
            "item_name": "💱 Tasa VIP"
        },
        "buy_ta": {
            "title": "📈 TA Pro (30 días)",
            "description": "Uso ilimitado del comando de análisis técnico /ta.",
            "payload": "sub_ta_vip",
            "price": PRICE_TA_VIP,
            "item_name": "📈 TA Pro"
        },
        "buy_rss_channel": {
            "title": "📺 Slot Canal RSS (Permanente)",
            "description": "Añade capacidad para 1 canal/grupo de destino extra.",
            "payload": "sub_rss_channel",
            "price": PRICE_RSS_CHANNEL,
            "item_name": "📺 +1 Slot Canal RSS"
        },
        "buy_rss_feed": {
            "title": "🔗 Slot Feed RSS (Permanente)",
            "description": "Añade capacidad para 1 enlace RSS extra.",
            "payload": "sub_rss_feed",
            "price": PRICE_RSS_FEED,
            "item_name": "🔗 +1 Slot Feed RSS"
        }
    }
    
    # ✅ VALIDAR QUE EL PRODUCTO EXISTE
    if data not in products:
        await query.answer("❌ Producto no reconocido", show_alert=True)
        return
    
    product = products[data]
    
    try:
        # ✅ ENVIAR INVOICE CON TELEGRAM STARS
        await context.bot.send_invoice(
            chat_id=chat_id,
            title=product["title"],
            description=product["description"],
            payload=product["payload"],
            provider_token="",  # ✅ VACÍO para Telegram Stars
            currency="XTR",  # ✅ OBLIGATORIO para Stars
            prices=[
                LabeledPrice(
                    label=product["item_name"],
                    amount=product["price"]  # ✅ Cantidad de Stars
                )
            ],
            start_parameter="pay_access"
        )
        
        add_log_line(f"💳 Invoice enviado: {product['item_name']} ({product['price']} XTR) a user {user_id}")
        
    except Exception as e:
        add_log_line(f"❌ Error enviando invoice: {e}")
        await query.answer(f"❌ Error: {str(e)[:100]}", show_alert=True)


# === PRE-CHECKOUT (Verificación previa de Telegram) ===
async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Telegram consulta si todo está bien antes de cobrar.
    Siempre respondemos True si reconocemos el payload.
    """
    query = update.pre_checkout_query
    user_id = query.from_user.id
    
    # ✅ VALIDAR PAYLOAD
    valid_payloads = [
        "sub_watchlist_bundle",
        "sub_coins_extra",
        "sub_alerts_extra",
        "sub_tasa_vip",
        "sub_ta_vip",
        "sub_rss_channel",
        "sub_rss_feed"
    ]
    
    if query.invoice_payload in valid_payloads:
        await query.answer(ok=True)
        add_log_line(f"✅ Pre-checkout OK: {query.invoice_payload} (user {user_id})")
    else:
        await query.answer(
            ok=False,
            error_message="Error en la orden. Intente de nuevo."
        )
        add_log_line(f"❌ Pre-checkout FAILED: {query.invoice_payload} (user {user_id})")


# === PAGO EXITOSO (Activación del Servicio) ===
async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Se ejecuta cuando el pago se ha completado.
    Aquí activamos los beneficios en la base de datos.
    """
    payment = update.message.successful_payment
    payload = payment.invoice_payload
    chat_id = update.effective_chat.id
    user = update.effective_user
    
    add_log_line(f"💰 Pago recibido: {payload} ({payment.total_amount} XTR) de user {chat_id}")
    
    # ✅ MAPEO DE PAYLOADS A ACCIONES
    try:
        if payload == "sub_watchlist_bundle":
            add_subscription_days(chat_id, "watchlist_bundle", days=30)
            item_name = "📦 Pack Control Total"
            
        elif payload == "sub_coins_extra":
            add_subscription_days(chat_id, "coins_extra", days=30, quantity=1)
            item_name = "🪙 +1 Moneda Extra"
            
        elif payload == "sub_alerts_extra":
            add_subscription_days(chat_id, "alerts_extra", days=30, quantity=1)
            item_name = "🔔 +1 Alerta Cruce"
            
        elif payload == "sub_tasa_vip":
            add_subscription_days(chat_id, "tasa_vip", days=30)
            item_name = "💱 Tasa VIP"
            
        elif payload == "sub_ta_vip":
            add_subscription_days(chat_id, "ta_vip", days=30)
            item_name = "📈 TA Pro"
            
        elif payload == "sub_rss_channel":
            add_purchased_slot(chat_id, 'channels', 1)
            add_subscription_days(chat_id, "rss_channel_slot", days=9999)  # Permanente
            item_name = "📺 +1 Slot Canal RSS"
            
        elif payload == "sub_rss_feed":
            add_purchased_slot(chat_id, 'feeds', 1)
            add_subscription_days(chat_id, "rss_feed_slot", days=9999)  # Permanente
            item_name = "🔗 +1 Slot Feed RSS"
            
        else:
            item_name = "Producto desconocido"
        
        # ✅ MENSAJE AL USUARIO
        await update.message.reply_text(
            f"✅ *¡Pago recibido con éxito!*\n"
            f"—————————————————\n\n"
            f"Has adquirido: *{item_name}*\n"
            f"Monto: *{payment.total_amount} Estrellas* ⭐\n"
            f"Tu suscripción/extra ha sido activado.\n\n"
            f"—————————————————\n"
            f"_Gracias por apoyar el desarrollo del bot._ 🤖❤️",
            parse_mode=ParseMode.MARKDOWN
        )
        
        # ✅ NOTIFICACIÓN AL ADMINISTRADOR
        reporte_admin = (
            f"💰 *¡NUEVA VENTA REALIZADA!* 💰\n"
            f"—————————————————\n"
            f"👤 *Usuario:* {user.first_name} (@{user.username or 'SinAlias'})\n"
            f"🆔 *ID:* `{chat_id}`\n"
            f"🛒 *Producto:* {item_name}\n"
            f"⭐ *Monto:* {payment.total_amount} XTR\n"
            f"📅 *Fecha:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"💳 *Payload:* `{payload}`"
        )
        
        # Enviar a todos los admins
        for admin_id in ADMIN_CHAT_IDS:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=reporte_admin,
                    parse_mode=ParseMode.MARKDOWN
                )
            except Exception as e:
                add_log_line(f"⚠️ Error notificando admin {admin_id}: {e}")
        
        add_log_line(f"✅ Pago procesado correctamente: {item_name}")
        
    except Exception as e:
        add_log_line(f"❌ Error procesando pago: {e}")
        await update.message.reply_text(
            f"⚠️ Se recibió el pago pero hubo un error al procesarlo.\n"
            f"Por favor, contacta con el administrador.",
            parse_mode=ParseMode.MARKDOWN
        )
