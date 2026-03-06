# handlers/sp_handlers.py
# Handlers del módulo SmartSignals (/sp).
# Comando /sp, menús interactivos, suscripciones y callbacks.

import asyncio
import requests
import pandas as pd
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from core.config import ADMIN_CHAT_IDS
from utils.file_manager import (
    add_log_line,
    check_feature_access,
    obtener_datos_usuario_seguro,
    registrar_uso_comando,
)
from utils.sp_manager import (
    SP_SUPPORTED_COINS,
    SP_TIMEFRAMES,
    is_sp_subscribed,
    toggle_sp_subscription,
    get_user_sp_subscriptions,
    count_user_sp_subs,
    get_sp_state,
    get_signal_history,
    get_time_until_next,
    get_coin_info,
    estimate_time_to_candle_close,
)
from utils.sp_chart import generate_sp_chart
from core.sp_loop import SPSignalEngine, _get_klines, build_signal_message, _fmt_price


# ─── HELPERS ──────────────────────────────────────────────────────────────────

def _check_sp_access(user_id: int) -> tuple[bool, str]:
    """
    Verifica si el usuario puede usar SmartSignals.
    Admins tienen acceso gratis. Resto necesita sub activa.
    """
    if user_id in ADMIN_CHAT_IDS:
        return True, "Admin"
    return check_feature_access(user_id, 'sp_signals')


def _get_main_menu_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Teclado principal: lista de monedas con estado de suscripción."""
    keyboard = []
    row = []

    for coin in SP_SUPPORTED_COINS:
        sym = coin['symbol']
        key = coin['key']
        emoji = coin['emoji']

        # Verificar si tiene alguna suscripción activa para esta moneda
        user_subs = get_user_sp_subscriptions(user_id)
        has_any = sym in user_subs and bool(user_subs[sym])
        status_icon = "🔔" if has_any else "○"

        row.append(InlineKeyboardButton(
            f"{status_icon} {emoji}{key}",
            callback_data=f"sp_coin|{sym}"
        ))
        if len(row) == 3:
            keyboard.append(row)
            row = []

    if row:
        keyboard.append(row)

    keyboard.append([
        InlineKeyboardButton("📋 Mis señales activas", callback_data="sp_my_subs"),
        InlineKeyboardButton("❓ Ayuda", callback_data="sp_help"),
    ])
    return InlineKeyboardMarkup(keyboard)


def _get_coin_keyboard(user_id: int, symbol: str, current_tf: str = "5m") -> InlineKeyboardMarkup:
    """Teclado de temporalidades para una moneda concreta."""
    keyboard = []

    # Fila de temporalidades con estado
    tf_row = []
    for tf, tf_info in SP_TIMEFRAMES.items():
        is_sub = is_sp_subscribed(user_id, symbol, tf)
        icon = "🔔" if is_sub else "○"
        tf_row.append(InlineKeyboardButton(
            f"{icon} {tf_info['label']}",
            callback_data=f"sp_toggle|{symbol}|{tf}"
        ))
        if len(tf_row) == 3:
            keyboard.append(tf_row)
            tf_row = []
    if tf_row:
        keyboard.append(tf_row)

    # Fila de vista de análisis
    view_row = []
    for tf in ["1m", "5m", "15m", "1h"]:
        view_row.append(InlineKeyboardButton(
            f"👁 {tf}",
            callback_data=f"sp_view|{symbol}|{tf}"
        ))
    keyboard.append(view_row)

    keyboard.append([
        InlineKeyboardButton("🔄 Refrescar", callback_data=f"sp_view|{symbol}|{current_tf}"),
        InlineKeyboardButton("🔙 Lista", callback_data="sp_main"),
    ])
    return InlineKeyboardMarkup(keyboard)


def _get_view_keyboard(user_id: int, symbol: str, tf: str) -> InlineKeyboardMarkup:
    """Teclado de la vista de señal con suscripción y acciones."""
    is_sub = is_sp_subscribed(user_id, symbol, tf)
    sub_icon = "🔕 Desactivar" if is_sub else "🔔 Activar alertas"
    coin = symbol.replace('USDT', '')

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(sub_icon,       callback_data=f"sp_toggle|{symbol}|{tf}"),
            InlineKeyboardButton("🔄 Refrescar", callback_data=f"sp_refresh|{symbol}|{tf}"),
        ],
        [
            InlineKeyboardButton("📊 Ver en TA",  callback_data=f"ta_switch|BINANCE|{coin}|USDT|{tf}"),
            InlineKeyboardButton("🔙 Monedas",   callback_data=f"sp_coin|{symbol}"),
        ],
    ])


# ─── TEXTO DEL MENÚ PRINCIPAL ─────────────────────────────────────────────────

def _build_main_menu_text(user_id: int) -> str:
    n_subs = count_user_sp_subs(user_id)
    sub_info = f"📊 Tienes *{n_subs}* alerta(s) activa(s)." if n_subs else "Aún no tienes alertas activas."

    return (
        "📡 *SmartSignals Pro*\n"
        "————————————————————\n\n"
        "Señales de trading en tiempo real con análisis predictivo.\n"
        "Recibirás alertas *antes de que la señal se confirme*.\n\n"
        "🔹 Ciclo de análisis: cada *45 segundos*\n"
        "🔹 Pre-aviso: *10–30s antes* del cierre de vela\n"
        "🔹 Gráfico predictivo con zonas de entrada\n"
        "🔹 BTC + 12 altcoins disponibles\n\n"
        f"{sub_info}\n\n"
        "📌 Selecciona una moneda para ver su señal actual\n"
        "o activa/desactiva alertas automáticas:\n"
        "────────────────────"
    )


def _build_preview_text() -> str:
    """Texto para usuarios sin acceso."""
    return (
        "📡 *SmartSignals Pro*\n"
        "————————————————————\n\n"
        "Detecta señales de compra y venta con *análisis multi-indicador*\n"
        "y recibe alertas *10–30 segundos antes* de que se confirmen.\n\n"
        "✨ *Incluye:*\n"
        "  • Señales BUY/SELL con gráfico predictivo\n"
        "  • Pre-aviso antes del cierre de vela\n"
        "  • Targets y Stop-Loss calculados con ATR\n"
        "  • 13 monedas · 5 temporalidades\n"
        "  • Ciclo de 45 segundos\n\n"
        "💰 *Precio: 200 ⭐ (30 días)*\n\n"
        "————————————————————\n"
        "_Activa SmartSignals en la tienda para empezar._"
    )


# ─── COMANDO PRINCIPAL /sp ────────────────────────────────────────────────────

async def sp_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /sp                → Menú principal con lista de monedas
    /sp BTC            → Vista directa con última señal
    /sp BTC 5m         → Vista directa en temporalidad específica
    """
    user_id = update.effective_user.id
    registrar_uso_comando(user_id, 'sp')
    obtener_datos_usuario_seguro(user_id)

    # ── Verificar acceso ──────────────────────────────────────────────────────
    has_access, _ = _check_sp_access(user_id)

    if not has_access:
        preview_text = _build_preview_text()
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("🛒 Ir a la Tienda", callback_data="sp_goto_shop"),
        ]])
        await update.message.reply_text(
            preview_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard
        )
        return

    # ── Sin args: menú principal ──────────────────────────────────────────────
    args = context.args
    if not args:
        text = _build_main_menu_text(user_id)
        kb   = _get_main_menu_keyboard(user_id)
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)
        return

    # ── Con args: /sp BTC [5m] ────────────────────────────────────────────────
    raw = [a.upper() for a in args]
    coin_key = raw[0]
    tf = "5m"  # Default

    if len(raw) > 1 and raw[1] in SP_TIMEFRAMES:
        tf = raw[1].lower()

    # Buscar info de la moneda
    coin_info = get_coin_info(coin_key)
    if not coin_info:
        await update.message.reply_text(
            f"❌ Moneda `{coin_key}` no soportada.\n"
            f"Usa `/sp` para ver la lista de monedas disponibles.",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    symbol = coin_info['symbol']
    msg_wait = await update.message.reply_text(
        f"⏳ _Analizando {coin_info['label']} ({tf})..._",
        parse_mode=ParseMode.MARKDOWN
    )

    await _show_signal_view(
        update=update,
        context=context,
        user_id=user_id,
        symbol=symbol,
        tf=tf,
        edit_msg=msg_wait,
    )


# ─── VISTA DE SEÑAL (REUTILIZABLE) ───────────────────────────────────────────

async def _show_signal_view(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    symbol: str,
    tf: str,
    edit_msg=None,
    answer_callback: str | None = None,
) -> None:
    """
    Descarga datos, analiza la señal actual y envía/edita el mensaje con gráfico.
    edit_msg: si se pasa, edita ese mensaje (modo espera); si no, envía nuevo.
    """
    coin_info = get_coin_info(symbol) or {"label": symbol, "emoji": "📡", "key": symbol}
    label = coin_info.get('label', symbol)

    try:
        # 1. Descargar datos
        loop = asyncio.get_running_loop()
        df = await loop.run_in_executor(None, _get_klines, symbol, tf, 120)

        if df is None or len(df) < 30:
            err = f"❌ No se obtuvieron datos para *{symbol}* ({tf})."
            if edit_msg:
                await edit_msg.edit_text(err, parse_mode=ParseMode.MARKDOWN)
            return

        # 2. Analizar
        engine = SPSignalEngine()
        sig = engine.analyze(df)

        # Calcular tiempo hasta cierre
        try:
            open_time_ms = int(df.iloc[-1]['open_time'])
            sig['time_to_close'] = estimate_time_to_candle_close(open_time_ms, tf)
        except Exception:
            sig['time_to_close'] = 0

        # 3. Generar gráfico
        chart_buf = await loop.run_in_executor(
            None, generate_sp_chart, df, symbol, tf, sig, 60
        )

        # 4. Construir mensaje
        msg_text = build_signal_message(symbol, tf, sig)
        keyboard  = _get_view_keyboard(user_id, symbol, tf)

        # 5. Enviar o editar
        if chart_buf:
            chart_buf.seek(0)
            if edit_msg:
                # Borramos el mensaje de espera y enviamos nuevo con foto
                try:
                    await edit_msg.delete()
                except Exception:
                    pass
            chat_id = update.effective_chat.id
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=chart_buf,
                caption=msg_text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard,
            )
        else:
            # Fallback sin gráfico
            if edit_msg:
                await edit_msg.edit_text(msg_text, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)
            else:
                await update.effective_message.reply_text(msg_text, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)

        if answer_callback and update.callback_query:
            await update.callback_query.answer()

    except Exception as e:
        add_log_line(f"[SP Handlers] Error en _show_signal_view: {e}")
        err = "⚠️ Error al generar la señal. Intenta de nuevo."
        try:
            if edit_msg:
                await edit_msg.edit_text(err, parse_mode=ParseMode.MARKDOWN)
        except Exception:
            pass


# ─── CALLBACKS ────────────────────────────────────────────────────────────────

async def sp_main_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Volver al menú principal de monedas."""
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    has_access, _ = _check_sp_access(user_id)
    if not has_access:
        await query.answer("❌ Necesitas SmartSignals Pro.", show_alert=True)
        return

    text = _build_main_menu_text(user_id)
    kb   = _get_main_menu_keyboard(user_id)
    try:
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)
    except Exception:
        pass


async def sp_coin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Muestra el menú de temporalidades para la moneda seleccionada.
    Callback: sp_coin|SYMBOL
    """
    query = update.callback_query
    user_id = query.from_user.id

    has_access, _ = _check_sp_access(user_id)
    if not has_access:
        await query.answer("❌ Necesitas SmartSignals Pro. Usa /shop.", show_alert=True)
        return

    try:
        _, symbol = query.data.split("|", 1)
    except ValueError:
        await query.answer("❌ Error de datos.", show_alert=True)
        return

    await query.answer()

    coin_info = get_coin_info(symbol) or {"label": symbol, "emoji": "📡"}
    label = coin_info.get('label', symbol)
    emoji = coin_info.get('emoji', '📡')

    # Estado actual de suscripciones para esta moneda
    user_subs = get_user_sp_subscriptions(user_id)
    active_tfs = user_subs.get(symbol, [])

    if active_tfs:
        sub_status = f"🔔 Alertas activas en: *{', '.join(active_tfs)}*"
    else:
        sub_status = "Sin alertas activas — toca un botón para activar"

    # Última señal registrada
    state = get_sp_state(symbol, "5m")
    last_sig = ""
    if state:
        dir_text = state.get('last_signal', '')
        dir_emoji = "🟢" if dir_text == 'BUY' else "🔴" if dir_text == 'SELL' else "⚖️"
        last_price = state.get('last_price', 0)
        last_sig = f"\n📌 Última señal 5m: {dir_emoji} `{dir_text}` @ `${_fmt_price(last_price)}`"

    text = (
        f"📡 *SmartSignals — {emoji} {label}*\n"
        f"────────────────────\n\n"
        f"{sub_status}{last_sig}\n\n"
        f"🔔 Toca una temporalidad para *activar/desactivar* alertas.\n"
        f"👁 Toca *Ver TF* para ver la señal actual sin suscribirte.\n"
        f"────────────────────"
    )
    kb = _get_coin_keyboard(user_id, symbol)
    try:
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)
    except Exception:
        pass


async def sp_toggle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Activa/desactiva alerta para symbol+tf.
    Callback: sp_toggle|SYMBOL|TF
    """
    query = update.callback_query
    user_id = query.from_user.id

    has_access, _ = _check_sp_access(user_id)
    if not has_access:
        await query.answer("❌ Necesitas SmartSignals Pro. Usa /shop.", show_alert=True)
        return

    try:
        _, symbol, tf = query.data.split("|")
    except ValueError:
        await query.answer("❌ Error de datos.", show_alert=True)
        return

    new_state = toggle_sp_subscription(user_id, symbol, tf)
    coin_info = get_coin_info(symbol) or {"label": symbol, "emoji": "📡"}
    label = coin_info.get('label', symbol)

    if new_state:
        await query.answer(f"🔔 Alertas {label} {tf} activadas.", show_alert=False)
        add_log_line(f"📡 SP suscripción: user {user_id} activó {symbol}/{tf}")
    else:
        await query.answer(f"🔕 Alertas {label} {tf} desactivadas.", show_alert=False)
        add_log_line(f"📡 SP suscripción: user {user_id} desactivó {symbol}/{tf}")

    # Refrescar el menú de la moneda
    user_subs = get_user_sp_subscriptions(user_id)
    active_tfs = user_subs.get(symbol, [])

    if active_tfs:
        sub_status = f"🔔 Alertas activas en: *{', '.join(active_tfs)}*"
    else:
        sub_status = "Sin alertas activas para esta moneda."

    emoji = coin_info.get('emoji', '📡')
    state = get_sp_state(symbol, "5m")
    last_sig = ""
    if state:
        dir_text = state.get('last_signal', '')
        dir_emoji = "🟢" if dir_text == 'BUY' else "🔴" if dir_text == 'SELL' else "⚖️"
        last_price = state.get('last_price', 0)
        last_sig = f"\n📌 Última señal 5m: {dir_emoji} `{dir_text}` @ `${_fmt_price(last_price)}`"

    text = (
        f"📡 *SmartSignals — {emoji} {label}*\n"
        f"────────────────────\n\n"
        f"{sub_status}{last_sig}\n\n"
        f"🔔 Toca una temporalidad para *activar/desactivar* alertas.\n"
        f"👁 Toca *Ver TF* para ver la señal actual sin suscribirte.\n"
        f"────────────────────"
    )
    kb = _get_coin_keyboard(user_id, symbol)
    try:
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)
    except Exception:
        pass


async def sp_view_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Muestra la señal actual para symbol+tf.
    Callback: sp_view|SYMBOL|TF
    """
    query = update.callback_query
    user_id = query.from_user.id

    has_access, _ = _check_sp_access(user_id)
    if not has_access:
        await query.answer("❌ Necesitas SmartSignals Pro. Usa /shop.", show_alert=True)
        return

    try:
        _, symbol, tf = query.data.split("|")
    except ValueError:
        await query.answer("❌ Error de datos.", show_alert=True)
        return

    await query.answer("⏳ Analizando...")

    # Editar el mensaje actual para mostrar el spinner y capturar referencia
    spinner_msg = None
    try:
        coin_info = get_coin_info(symbol) or {"label": symbol}
        label = coin_info.get('label', symbol)
        spinner_msg = await query.edit_message_text(
            f"⏳ _Analizando {label} ({tf})..._",
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception:
        pass

    # Pasamos el spinner_msg a _show_signal_view para que lo borre limpiamente
    # antes de enviar la foto (o lo edite si no hay gráfico)
    await _show_signal_view(
        update=update,
        context=context,
        user_id=user_id,
        symbol=symbol,
        tf=tf,
        edit_msg=spinner_msg,
    )


async def sp_refresh_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Refresca la señal desde el botón en un mensaje existente.
    Callback: sp_refresh|SYMBOL|TF
    """
    query = update.callback_query
    user_id = query.from_user.id

    has_access, _ = _check_sp_access(user_id)
    if not has_access:
        await query.answer("❌ Sin acceso.", show_alert=True)
        return

    try:
        _, symbol, tf = query.data.split("|")
    except ValueError:
        await query.answer("❌ Error de datos.", show_alert=True)
        return

    await query.answer("⏳ Actualizando señal...")

    await _show_signal_view(
        update=update,
        context=context,
        user_id=user_id,
        symbol=symbol,
        tf=tf,
    )


async def sp_my_subs_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Muestra las suscripciones activas del usuario.
    Callback: sp_my_subs
    """
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    has_access, _ = _check_sp_access(user_id)
    if not has_access:
        await query.answer("❌ Sin acceso.", show_alert=True)
        return

    user_subs = get_user_sp_subscriptions(user_id)

    if not user_subs:
        text = (
            "📋 *Mis señales SmartSignals*\n"
            "────────────────────\n\n"
            "Aún no tienes ninguna señal activa.\n\n"
            "_Selecciona una moneda y temporalidad\n"
            "para empezar a recibir alertas._"
        )
    else:
        lines = []
        for sym, tfs in user_subs.items():
            if not tfs:
                continue
            coin_info = get_coin_info(sym) or {"label": sym, "emoji": "📡"}
            emoji = coin_info.get('emoji', '📡')
            label = coin_info.get('label', sym).split(' ', 1)[-1]  # Sin el símbolo
            tfs_str = " · ".join(sorted(tfs))

            # Última señal
            state = get_sp_state(sym, tfs[0])
            last_info = ""
            if state:
                dir_text = state.get('last_signal', '')
                dir_emoji = "🟢" if dir_text == 'BUY' else "🔴" if dir_text == 'SELL' else "⚖️"
                last_info = f" — última: {dir_emoji}"

            lines.append(f"{emoji} *{label}* · `{tfs_str}`{last_info}")

        subs_text = "\n".join(lines)
        total = count_user_sp_subs(user_id)
        text = (
            f"📋 *Mis señales SmartSignals*\n"
            f"────────────────────\n\n"
            f"Tienes *{total}* alerta(s) activa(s):\n\n"
            f"{subs_text}\n\n"
            f"_Toca 🔙 para volver a la lista de monedas._"
        )

    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("🔙 Lista de monedas", callback_data="sp_main"),
    ]])

    try:
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)
    except Exception:
        pass


async def sp_help_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Muestra la ayuda del módulo SP."""
    query = update.callback_query
    await query.answer()

    text = (
        "📡 *SmartSignals — Ayuda*\n"
        "————————————————————\n\n"
        "*¿Qué es SmartSignals?*\n"
        "Un radar de trading que analiza el mercado cada 45 segundos "
        "y te avisa cuando detecta una señal de compra o venta.\n\n"
        "*¿Cómo funciona?*\n"
        "  • Descarga velas de Binance en tiempo real\n"
        "  • Aplica 7 indicadores técnicos (RSI, MACD, Stoch, CCI, BB, MFI, EMAs)\n"
        "  • Si hay confluencia (score ≥4.5/8), envía alerta\n"
        "  • Si la señal es fuerte (≥6.5) y la vela está a punto de cerrar, "
        "envía un *pre-aviso*\n\n"
        "*Comandos:*\n"
        "  • `/sp` — Abre este menú\n"
        "  • `/sp BTC` — Señal actual de BTC en 5m\n"
        "  • `/sp ETH 1h` — Señal actual de ETH en 1h\n\n"
        "*Gestión de alertas:*\n"
        "  • Toca el nombre de una moneda para ver temporalidades\n"
        "  • Toca la temporalidad para activar/desactivar alertas\n"
        "  • El icono 🔔 indica que la alerta está activa\n\n"
        "*¿Cuándo envía señales?*\n"
        "  • Solo cuando hay confluencia suficiente (no spam)\n"
        "  • Hay un cooldown entre señales del mismo par\n"
        "  • Máximo por día por temporalidad (varía según TF)\n\n"
        "💡 _Las señales son informativas. Siempre evalúa el contexto._"
    )

    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("🔙 Volver", callback_data="sp_main"),
    ]])
    try:
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)
    except Exception:
        pass


async def sp_goto_shop_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Redirige al shop cuando el usuario sin acceso toca el botón."""
    query = update.callback_query
    await query.answer()
    # Simplemente llamamos al shop_command
    from handlers.pay import shop_command
    await shop_command(update, context)


# ─── LISTA DE HANDLERS PARA REGISTRAR EN bbalert.py ─────────────────────────
# Se usa en bbalert.py para registrar todos los callbacks del módulo SP.

from telegram.ext import CommandHandler, CallbackQueryHandler

sp_handlers_list = [
    CommandHandler("sp", sp_command),
    CallbackQueryHandler(sp_main_callback,      pattern=r"^sp_main$"),
    CallbackQueryHandler(sp_coin_callback,      pattern=r"^sp_coin\|"),
    CallbackQueryHandler(sp_toggle_callback,    pattern=r"^sp_toggle\|"),
    CallbackQueryHandler(sp_view_callback,      pattern=r"^sp_view\|"),
    CallbackQueryHandler(sp_refresh_callback,   pattern=r"^sp_refresh\|"),
    CallbackQueryHandler(sp_my_subs_callback,   pattern=r"^sp_my_subs$"),
    CallbackQueryHandler(sp_help_callback,      pattern=r"^sp_help$"),
    CallbackQueryHandler(sp_goto_shop_callback, pattern=r"^sp_goto_shop$"),
]
