# handlers/pay.py

from telegram import Update, LabeledPrice, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from utils.file_manager import add_subscription_days, obtener_datos_usuario_seguro, add_log_line
from core.config import ADMIN_CHAT_IDS
from core.i18n import _
from datetime import datetime

# === LISTA DE PRECIOS (En Telegram Stars - XTR) ===
PRICE_BUNDLE      = 20    # Pack Control Total (Temp flexible + Ver x24 + Cambios ilimitados)
PRICE_COIN_SLOT   = 5     # +1 Capacidad en lista de monedas
PRICE_ALERT_SLOT  = 4     # +1 Alerta de Cruce (Par Arriba/Abajo)
PRICE_TASA_VIP    = 5     # Tasa x24 consultas diarias
PRICE_TA_VIP      = 10    # TA Ilimitado
PRICE_SP_SIGNALS  = 200   # SmartSignals Pro — Señales predictivas de trading


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
        # ── Premium destacado ──────────────────────────────────────────
        [InlineKeyboardButton(
            f"📡 SmartSignals Pro — {PRICE_SP_SIGNALS} ⭐  ✨ NUEVO",
            callback_data="buy_sp"
        )],
        # ── Packs y extras ────────────────────────────────────────────
        [InlineKeyboardButton(f"📦 Pack Total — {PRICE_BUNDLE} ⭐",       callback_data="buy_bundle")],
        [InlineKeyboardButton(f"📈 TA Pro — {PRICE_TA_VIP} ⭐",           callback_data="buy_ta")],
        [InlineKeyboardButton(f"💱 Tasa VIP — {PRICE_TASA_VIP} ⭐",       callback_data="buy_tasa")],
        [
            InlineKeyboardButton(f"🪙 +1 Moneda — {PRICE_COIN_SLOT} ⭐",  callback_data="buy_coin"),
            InlineKeyboardButton(f"🔔 +1 Alerta — {PRICE_ALERT_SLOT} ⭐", callback_data="buy_alert"),
        ],
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

    data    = query.data
    chat_id = query.message.chat_id
    user_id = query.from_user.id

    # ── CATÁLOGO DE PRODUCTOS ──────────────────────────────────────────────────
    products = {
        # ── SmartSignals Pro (NUEVO) ───────────────────────────────────────────
        "buy_sp": {
            "title":       "📡 SmartSignals Pro (30 días)",
            "description": (
                "Señales predictivas BUY/SELL con gráfico. "
                "Pre-aviso 10-30s antes del cierre de vela. "
                "BTC + 12 altcoins · Ciclo de 45 segundos."
            ),
            "payload":     "sub_sp_signals",
            "price":       PRICE_SP_SIGNALS,
            "item_name":   "📡 SmartSignals Pro",
        },
        # ── Pack Control Total ─────────────────────────────────────────────────
        "buy_bundle": {
            "title":       "📦 Pack Control Total (30 días)",
            "description": "Alertas cada 15min-24h + Cambios ilimitados + Comando /ver x24 diario.",
            "payload":     "sub_watchlist_bundle",
            "price":       PRICE_BUNDLE,
            "item_name":   "📦 Pack Control Total",
        },
        # ── TA Pro ────────────────────────────────────────────────────────────
        "buy_ta": {
            "title":       "📈 TA Pro (30 días)",
            "description": "Uso ilimitado del comando de análisis técnico /ta.",
            "payload":     "sub_ta_vip",
            "price":       PRICE_TA_VIP,
            "item_name":   "📈 TA Pro",
        },
        # ── Tasa VIP ──────────────────────────────────────────────────────────
        "buy_tasa": {
            "title":       "💱 Tasa VIP (30 días)",
            "description": "Aumenta el límite del comando /tasa a 24 veces por día.",
            "payload":     "sub_tasa_vip",
            "price":       PRICE_TASA_VIP,
            "item_name":   "💱 Tasa VIP",
        },
        # ── Extras de capacidad ───────────────────────────────────────────────
        "buy_coin": {
            "title":       "🪙 +1 Espacio Moneda (30 días)",
            "description": "Añade 1 moneda extra a tu lista de seguimiento /monedas.",
            "payload":     "sub_coins_extra",
            "price":       PRICE_COIN_SLOT,
            "item_name":   "🪙 +1 Moneda Extra",
        },
        "buy_alert": {
            "title":       "🔔 +1 Alerta Cruce (30 días)",
            "description": "Añade 1 par de alertas de precio (Arriba/Abajo) extra.",
            "payload":     "sub_alerts_extra",
            "price":       PRICE_ALERT_SLOT,
            "item_name":   "🔔 +1 Alerta Cruce",
        },
    }

    # ── Validar producto ──────────────────────────────────────────────────────
    if data not in products:
        await query.answer("❌ Producto no reconocido", show_alert=True)
        return

    product = products[data]

    try:
        await context.bot.send_invoice(
            chat_id=chat_id,
            title=product["title"],
            description=product["description"],
            payload=product["payload"],
            provider_token="",        # Vacío para Telegram Stars
            currency="XTR",           # Obligatorio para Stars
            prices=[
                LabeledPrice(
                    label=product["item_name"],
                    amount=product["price"]
                )
            ],
            start_parameter="pay_access"
        )
        add_log_line(
            f"💳 Invoice enviado: {product['item_name']} "
            f"({product['price']} XTR) a user {user_id}"
        )

    except Exception as e:
        add_log_line(f"❌ Error enviando invoice: {e}")
        await query.answer(f"❌ Error: {str(e)[:100]}", show_alert=True)


# === PRE-CHECKOUT (Verificación previa de Telegram) ===
async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Telegram consulta si todo está bien antes de cobrar.
    Siempre respondemos True si reconocemos el payload.
    """
    query   = update.pre_checkout_query
    user_id = query.from_user.id

    valid_payloads = [
        "sub_watchlist_bundle",
        "sub_coins_extra",
        "sub_alerts_extra",
        "sub_tasa_vip",
        "sub_ta_vip",
        "sub_sp_signals",        # ← SmartSignals Pro
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
    user    = update.effective_user

    add_log_line(f"💰 Pago recibido: {payload} ({payment.total_amount} XTR) de user {chat_id}")

    try:
        # ── Mapeo payload → acción ────────────────────────────────────────────
        if payload == "sub_sp_signals":
            add_subscription_days(chat_id, "sp_signals", days=30)
            item_name  = "📡 SmartSignals Pro"
            extra_msg  = "\n\nUsa /sp para empezar a recibir señales de trading."

        elif payload == "sub_watchlist_bundle":
            add_subscription_days(chat_id, "watchlist_bundle", days=30)
            item_name  = "📦 Pack Control Total"
            extra_msg  = ""

        elif payload == "sub_coins_extra":
            add_subscription_days(chat_id, "coins_extra", days=30, quantity=1)
            item_name  = "🪙 +1 Moneda Extra"
            extra_msg  = ""

        elif payload == "sub_alerts_extra":
            add_subscription_days(chat_id, "alerts_extra", days=30, quantity=1)
            item_name  = "🔔 +1 Alerta Cruce"
            extra_msg  = ""

        elif payload == "sub_tasa_vip":
            add_subscription_days(chat_id, "tasa_vip", days=30)
            item_name  = "💱 Tasa VIP"
            extra_msg  = ""

        elif payload == "sub_ta_vip":
            add_subscription_days(chat_id, "ta_vip", days=30)
            item_name  = "📈 TA Pro"
            extra_msg  = ""

        else:
            item_name  = "Producto desconocido"
            extra_msg  = ""

        # ── Confirmación al usuario ───────────────────────────────────────────
        await update.message.reply_text(
            f"✅ *¡Pago recibido con éxito!*\n"
            f"—————————————————\n\n"
            f"Has adquirido: *{item_name}*\n"
            f"Monto: *{payment.total_amount} Estrellas* ⭐\n"
            f"Tu suscripción ha sido activada por *30 días*."
            f"{extra_msg}\n\n"
            f"—————————————————\n"
            f"_Gracias por apoyar el desarrollo del bot._ 🤖❤️",
            parse_mode=ParseMode.MARKDOWN
        )

        # ── Notificación al administrador ─────────────────────────────────────
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
            "⚠️ Se recibió el pago pero hubo un error al procesarlo.\n"
            "Por favor, contacta con el administrador.",
            parse_mode=ParseMode.MARKDOWN
        )