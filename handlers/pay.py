# handlers/pay.py

from telegram import Update, LabeledPrice, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from utils.file_manager import add_subscription_days, obtener_datos_usuario_seguro
from core.config import ADMIN_CHAT_IDS
from core.i18n import _

# === LISTA DE PRECIOS (En Telegram Stars - XTR) ===
PRICE_BUNDLE = 20      # Temp flexible + Ver x24 + Cambios ilimitados
PRICE_COIN_SLOT = 5    # +1 Capacidad en lista
PRICE_ALERT_SLOT = 4   # +1 Alerta de Cruce (Par Arriba/Abajo)
PRICE_TASA_VIP = 5     # Tasa x24 consultas
PRICE_TA_VIP = 10      # TA Ilimitado

# === MENÚ DE LA TIENDA ===
async def shop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra el menú de suscripciones y compras disponibles."""
    user_id = update.effective_user.id
    
    # Aseguramos que el usuario tenga estructura de datos
    obtener_datos_usuario_seguro(user_id)
    
    # Textos (puedes ajustarlos a tu gusto)
    titulo = "🛒 *Tienda de BitBread Alert* 🛒\n—————————————————\n\nMejora tu experiencia adquiriendo capacidades extra con *Telegram Stars* ⭐.\n\n—————————————————\n*Selecciona una opción 👇*"
    
    keyboard = [
        [InlineKeyboardButton(f"📦 Pack Control Total - {PRICE_BUNDLE} ⭐️", callback_data="buy_bundle")],
        [InlineKeyboardButton(f"🪙 +1 Moneda en Lista - {PRICE_COIN_SLOT} ⭐️", callback_data="buy_coin")],
        [InlineKeyboardButton(f"🔔 +1 Alerta Cruce - {PRICE_ALERT_SLOT} ⭐️", callback_data="buy_alert")],
        [InlineKeyboardButton(f"💱 Tasa VIP (24/día) - {PRICE_TASA_VIP} ⭐️", callback_data="buy_tasa")],
        [InlineKeyboardButton(f"📈 TA Pro (Ilimitado) - {PRICE_TA_VIP} ⭐️", callback_data="buy_ta")]
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
    
    title = ""
    description = ""
    payload = ""
    price_amount = 0
    
    # Configuración de productos según el botón pulsado
    if data == "buy_bundle":
        title = "📦 Pack Control Total (30 días)"
        description = "Alertas cada 15min-24h + Cambios ilimitados + Comando /ver x24 diario."
        payload = "sub_watchlist_bundle"
        price_amount = PRICE_BUNDLE

    elif data == "buy_coin":
        title = "🪙 +1 Espacio Moneda (30 días)"
        description = "Añade 1 moneda extra a tu lista de seguimiento /monedas."
        payload = "sub_coins_extra"
        price_amount = PRICE_COIN_SLOT

    elif data == "buy_alert":
        title = "🔔 +1 Alerta Cruce (30 días)"
        description = "Añade 1 par de alertas de precio (Arriba/Abajo) extra."
        payload = "sub_alerts_extra"
        price_amount = PRICE_ALERT_SLOT

    elif data == "buy_tasa":
        title = "💱 Tasa VIP (30 días)"
        description = "Aumenta el límite del comando /tasa a 24 veces por día."
        payload = "sub_tasa_vip"
        price_amount = PRICE_TASA_VIP

    elif data == "buy_ta":
        title = "📈 TA Pro (30 días)"
        description = "Uso ilimitado del comando de análisis técnico /ta."
        payload = "sub_ta_vip"
        price_amount = PRICE_TA_VIP
    
    else:
        return

    # Enviar Factura (Invoice)
    # NOTA: currency="XTR" es obligatorio para Telegram Stars
    await context.bot.send_invoice(
        chat_id=chat_id,
        title=title,
        description=description,
        payload=payload,
        provider_token="", # DEJAR VACÍO para Telegram Stars
        currency="XTR",
        prices=[LabeledPrice(title, price_amount)], # El precio en XTR es entero (1 = 1 estrella)
        start_parameter="pay_access"
    )

# === PRE-CHECKOUT (Verificación previa de Telegram) ===
async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Telegram consulta si todo está bien antes de cobrar.
    Siempre respondemos True si reconocemos el payload.
    """
    query = update.pre_checkout_query
    # Podrías validar el payload aquí si quisieras lógica compleja
    if query.invoice_payload.startswith("sub_"):
        await query.answer(ok=True)
    else:
        await query.answer(ok=False, error_message="Error en la orden. Intente de nuevo.")

# === PAGO EXITOSO (Activación del Servicio) ===
async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Se ejecuta cuando el pago se ha completado.
    Aquí activamos los beneficios en la base de datos.
    """
    payment = update.message.successful_payment
    payload = payment.invoice_payload
    chat_id = update.effective_chat.id
    user = update.effective_user # Obtenemos datos del usuario para el reporte
    
    # Determinamos qué compró basándonos en el payload
    sub_type = payload.replace("sub_", "")
    
    qty = 0
    item_name = "Suscripción" # Nombre legible para el reporte

    # Asignar nombres legibles según el payload
    if sub_type == 'watchlist_bundle':
        item_name = "📦 Pack Control Total"
    elif sub_type == 'tasa_vip':
        item_name = "💱 Tasa VIP"
    elif sub_type == 'ta_vip':
        item_name = "📈 TA Pro"
    elif sub_type == 'coins_extra':
        item_name = "🪙 +1 Moneda Extra"
        qty = 1
    elif sub_type == 'alerts_extra':
        item_name = "🔔 +1 Alerta Cruce"
        qty = 1
        
    # Llamamos a la función de file_manager para guardar los cambios
    add_subscription_days(chat_id, sub_type, days=30, quantity=qty)
    
    # Mensaje al USUARIO
    await update.message.reply_text(
        f"✅ *¡Pago recibido con éxito!*\n—————————————————\n\n"
        f"Has adquirido: *{item_name}*\n"
        f"Monto: *{payment.total_amount} Estrellas*.\n"
        f"Tu suscripción/extra ha sido activado por 30 días.\n\n—————————————————\n"
        f"_Gracias por apoyar el desarrollo del bot._ 🤖❤️",
        parse_mode=ParseMode.MARKDOWN
    )

    # --- NOTIFICACIÓN AL ADMINISTRADOR ---
    # Construimos el mensaje de reporte
    reporte_admin = (
        f"💰 *¡NUEVA VENTA REALIZADA!* 💰\n—————————————————\n"
        f"👤 *Usuario:* {user.first_name} (@{user.username or 'SinAlias'})\n"
        f"🆔 *ID:* `{user.id}`\n"
        f"🛒 *Producto:* {item_name}\n"
        f"⭐️ *Monto:* {payment.total_amount} XTR\n"
        f"📅 *Fecha:* {payment.invoice_payload}" # O timestamp actual
    )

    # Enviamos a todos los admins configurados
    for admin_id in ADMIN_CHAT_IDS:
        try:
            await context.bot.send_message(chat_id=admin_id, text=reporte_admin, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            print(f"No se pudo enviar reporte de venta al admin {admin_id}: {e}")