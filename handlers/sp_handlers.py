# handlers/sp_handlers.py
# Handlers del módulo SmartSignals (/sp).
# Comando /sp, menús interactivos, suscripciones y callbacks.
#
# BUGS CORREGIDOS (11 total):
#  1. [CRÍTICO] /sp BTC 4h siempre mostraba 5m — args no normalizados a lowercase
#  2. [CRÍTICO] sp_main_callback — query.answer() doble (antes de check acceso)
#  3. [CRÍTICO] sp_my_subs_callback — mismo doble answer que bug #2
#  4. [CRÍTICO] sp_goto_shop_callback — crash: update.message=None en callbacks
#  5. [MAYOR]   Botón 👁 4h ausente en _get_coin_keyboard
#  6. [MAYOR]   sp_refresh_callback duplicaba mensajes (foto sin borrar la anterior)
#  7. [MAYOR]   Última señal en menú moneda hardcodeada a "5m"
#  8. [MAYOR]   Botón Refrescar del menú moneda siempre iba a 5m
#  9. [MAYOR]   NEUTRAL se mostraba como SELL (en sp_loop.py/build_signal_message)
# 10. [MENOR]   Caption foto puede superar 1024 chars (límite Telegram)
# 11. [MENOR]   score_label NameError potencial si direction=NEUTRAL
#
# SSS v2 — SmartSignals Strategy:
# 12. [NUEVO]   Submenú de estrategias de trading (/sp estrategias)
# 13. [NUEVO]   Selección de estrategia por usuario (hot-reload, sin reinicio)
# 14. [NUEVO]   Quick-notify: señal inmediata al activar suscripción
# 15. [NUEVO]   Vista de señal enriquecida con TP/SL/leverage de la estrategia

import asyncio
import pandas as pd
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
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
    queue_quick_notify,
)
from utils.sp_chart import generate_sp_chart
from core.sp_loop import SPSignalEngine, _get_klines, build_signal_message, _fmt_price

# SSS: estrategias como skills
try:
    from utils.sss_manager import (
        get_available_strategies,
        get_user_strategy,
        set_user_strategy,
        get_strategy_by_id,
        format_strategy_detail,
        format_strategy_list_item,
        apply_strategy_filter,
        enrich_signal,
        compute_extended_indicators,
        build_strategy_signal_block,
    )
    _SSS_OK = True
except ImportError:
    _SSS_OK = False


# ─── HELPERS ──────────────────────────────────────────────────────────────────

def _check_sp_access(user_id: int) -> tuple[bool, str]:
    """Admins: acceso libre. Resto: necesita sub activa."""
    if user_id in ADMIN_CHAT_IDS:
        return True, "Admin"
    return check_feature_access(user_id, 'sp_signals')


def _best_display_tf(user_id: int, symbol: str) -> str:
    """
    Devuelve el TF más relevante para mostrar en el menú de moneda.
    Prioriza el primer TF activo del usuario (en orden 1m→4h).
    FIX #7 y #8: evita hardcodear '5m' en el menú de moneda.
    """
    user_subs  = get_user_sp_subscriptions(user_id)
    active_tfs = user_subs.get(symbol, [])
    if active_tfs:
        for tf in SP_TIMEFRAMES:   # Orden natural: 1m, 5m, 15m, 1h, 4h
            if tf in active_tfs:
                return tf
    return "5m"


# ─── TECLADOS ─────────────────────────────────────────────────────────────────

def _get_main_menu_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Lista de monedas con estado de suscripción (3 por fila)."""
    keyboard = []
    row      = []

    for coin in SP_SUPPORTED_COINS:
        sym     = coin['symbol']
        key     = coin['key']
        emoji   = coin['emoji']
        subs    = get_user_sp_subscriptions(user_id)
        icon    = "🔔" if subs.get(sym) else "○"

        row.append(InlineKeyboardButton(
            f"{icon} {emoji}{key}",
            callback_data=f"sp_coin|{sym}"
        ))
        if len(row) == 3:
            keyboard.append(row)
            row = []

    if row:
        keyboard.append(row)

    # ── Fila de acciones ──────────────────────────────────────────────────────
    keyboard.append([
        InlineKeyboardButton("📋 Mis señales activas", callback_data="sp_my_subs"),
        InlineKeyboardButton("❓ Ayuda",               callback_data="sp_help"),
    ])

    # ── Fila SSS ──────────────────────────────────────────────────────────────
    if _SSS_OK:
        active_strat = get_user_strategy(user_id)
        strat_label  = f"🧠 {active_strat['name'][:16]}" if active_strat else "🧠 Estrategias"
        keyboard.append([
            InlineKeyboardButton(strat_label, callback_data="sp_strategies"),
        ])

    return InlineKeyboardMarkup(keyboard)


def _get_coin_keyboard(user_id: int, symbol: str, current_tf: str = "5m") -> InlineKeyboardMarkup:
    """
    Teclado del menú de moneda.
    FIX #5: botones 👁 TF se generan dinámicamente desde SP_TIMEFRAMES (incluye 4h).
    FIX #8: current_tf llega desde el contexto real, no hardcodeado.
    """
    keyboard = []

    # ── Fila 1-2: botones toggle de suscripción por TF ────────────────────────
    tf_row = []
    for tf, tf_info in SP_TIMEFRAMES.items():
        icon = "🔔" if is_sp_subscribed(user_id, symbol, tf) else "○"
        tf_row.append(InlineKeyboardButton(
            f"{icon} {tf_info['label']}",
            callback_data=f"sp_toggle|{symbol}|{tf}"
        ))
        if len(tf_row) == 3:
            keyboard.append(tf_row)
            tf_row = []
    if tf_row:
        keyboard.append(tf_row)

    # ── Fila siguiente: botones 👁 VER para TODOS los TF ──────────────────────
    # FIX #5: generados dinámicamente, incluye 4h
    view_row = []
    for tf in SP_TIMEFRAMES:
        view_row.append(InlineKeyboardButton(
            f"👁 {tf}",
            callback_data=f"sp_view|{symbol}|{tf}"
        ))
    # 5 TF caben en una sola fila
    keyboard.append(view_row)

    # ── Navegación ────────────────────────────────────────────────────────────
    # FIX #8: Refrescar usa current_tf real
    keyboard.append([
        InlineKeyboardButton("🔄 Refrescar", callback_data=f"sp_view|{symbol}|{current_tf}"),
        InlineKeyboardButton("🔙 Lista",      callback_data="sp_main"),
    ])
    return InlineKeyboardMarkup(keyboard)


def _get_view_keyboard(user_id: int, symbol: str, tf: str) -> InlineKeyboardMarkup:
    """Teclado adjunto a la vista de señal."""
    is_sub    = is_sp_subscribed(user_id, symbol, tf)
    sub_label = "🔕 Desactivar" if is_sub else "🔔 Activar alertas"
    coin      = symbol.replace('USDT', '')

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(sub_label,        callback_data=f"sp_toggle|{symbol}|{tf}"),
            InlineKeyboardButton("🔄 Refrescar",   callback_data=f"sp_refresh|{symbol}|{tf}"),
        ],
        [
            InlineKeyboardButton("📊 Ver en TA",   callback_data=f"ta_switch|BINANCE|{coin}|USDT|{tf}"),
            InlineKeyboardButton("🔙 Monedas",     callback_data=f"sp_coin|{symbol}"),
        ],
    ])


# ─── TEXTOS ───────────────────────────────────────────────────────────────────

def _build_main_menu_text(user_id: int) -> str:
    n    = count_user_sp_subs(user_id)
    info = f"📊 Tienes *{n}* alerta(s) activa(s)." if n else "Aún no tienes alertas activas."
    return (
        "📡 *SmartSignals Pro*\n"
        "————————————————————\n\n"
        "Señales de trading en tiempo real con análisis predictivo.\n"
        "Recibirás alertas *antes de que la señal se confirme*.\n\n"
        "🔹 Ciclo de análisis: cada *45 segundos*\n"
        "🔹 Pre-aviso: *10–30s antes* del cierre de vela\n"
        "🔹 Gráfico predictivo con zonas de entrada\n"
        "🔹 BTC + 12 altcoins disponibles\n\n"
        f"{info}\n\n"
        "📌 Selecciona una moneda para ver su señal actual\n"
        "o activa/desactiva alertas automáticas:\n"
        "────────────────────"
    )


def _build_preview_text() -> str:
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


def _build_coin_menu_text(user_id: int, symbol: str, display_tf: str) -> str:
    """
    Texto del menú de moneda.
    FIX #7: usa display_tf (primer TF activo) para mostrar la última señal correcta.
    """
    coin_info  = get_coin_info(symbol) or {"label": symbol, "emoji": "📡"}
    label      = coin_info.get('label', symbol)
    emoji      = coin_info.get('emoji', '📡')
    user_subs  = get_user_sp_subscriptions(user_id)
    active_tfs = user_subs.get(symbol, [])

    sub_status = (
        f"🔔 Alertas activas en: *{', '.join(sorted(active_tfs))}*"
        if active_tfs else
        "Sin alertas activas — toca un botón para activar"
    )

    # Última señal del TF relevante (FIX #7)
    state    = get_sp_state(symbol, display_tf)
    last_sig = ""
    if state:
        dir_text   = state.get('last_signal', '')
        dir_emoji  = "🟢" if dir_text == 'BUY' else "🔴" if dir_text == 'SELL' else "⚖️"
        last_price = state.get('last_price', 0)
        if dir_text and last_price:
            last_sig = (
                f"\n📌 Última señal ({display_tf}): "
                f"{dir_emoji} `{dir_text}` @ `${_fmt_price(last_price)}`"
            )

    return (
        f"📡 *SmartSignals — {emoji} {label}*\n"
        f"────────────────────\n\n"
        f"{sub_status}{last_sig}\n\n"
        f"🔔 Toca una temporalidad para *activar/desactivar* alertas.\n"
        f"👁 Toca *Ver TF* para ver la señal actual sin suscribirte.\n"
        f"────────────────────"
    )


# ─── COMANDO /sp ──────────────────────────────────────────────────────────────

async def sp_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /sp           → Menú principal
    /sp BTC       → Señal BTC 5m
    /sp BTC 4h    → Señal BTC 4h
    FIX #1: args[1] normalizado a lowercase → '4H' → '4h' coincide con SP_TIMEFRAMES.
    """
    user_id = update.effective_user.id
    registrar_uso_comando(user_id, 'sp')
    obtener_datos_usuario_seguro(user_id)

    has_access, _ = _check_sp_access(user_id)

    if not has_access:
        await update.message.reply_text(
            _build_preview_text(),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🛒 Ir a la Tienda", callback_data="sp_goto_shop"),
            ]])
        )
        return

    args = context.args
    if not args:
        await update.message.reply_text(
            _build_main_menu_text(user_id),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=_get_main_menu_keyboard(user_id)
        )
        return

    # ── Con argumentos ────────────────────────────────────────────────────────
    coin_key = args[0].upper()
    # FIX #1: normalizar a lowercase; sin esto "4H" nunca está en SP_TIMEFRAMES
    tf = args[1].lower() if len(args) > 1 else "5m"
    if tf not in SP_TIMEFRAMES:
        tf = "5m"

    coin_info = get_coin_info(coin_key)
    if not coin_info:
        await update.message.reply_text(
            f"❌ Moneda `{coin_key}` no soportada.\n"
            f"Usa `/sp` para ver la lista.",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    symbol   = coin_info['symbol']
    msg_wait = await update.message.reply_text(
        f"⏳ _Analizando {coin_info['label']} ({tf})..._",
        parse_mode=ParseMode.MARKDOWN
    )
    await _show_signal_view(
        update=update, context=context,
        user_id=user_id, symbol=symbol, tf=tf, edit_msg=msg_wait,
    )


# ─── VISTA DE SEÑAL (REUTILIZABLE) ────────────────────────────────────────────

async def _show_signal_view(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    symbol: str,
    tf: str,
    edit_msg=None,
) -> None:
    """
    Descarga → analiza → genera gráfico → envía.
    FIX #10: caption truncado a 1024 chars (límite de Telegram para fotos).
    SSS v2: enriquece con estrategia activa del usuario si está disponible.
    """
    try:
        loop = asyncio.get_running_loop()

        df = await loop.run_in_executor(None, _get_klines, symbol, tf, 120)
        if df is None or len(df) < 30:
            err = f"❌ No se obtuvieron datos para *{symbol}* ({tf})."
            if edit_msg:
                await edit_msg.edit_text(err, parse_mode=ParseMode.MARKDOWN)
            return

        engine = SPSignalEngine()
        sig    = engine.analyze(df)

        try:
            sig['time_to_close'] = estimate_time_to_candle_close(
                int(df.iloc[-1]['open_time']), tf
            )
        except Exception:
            sig['time_to_close'] = 0

        # ── SSS: enriquecimiento con estrategia activa ────────────────────────
        strat_block = ""
        if _SSS_OK:
            strat = get_user_strategy(user_id)
            if strat and tf in strat.get('timeframes', []):
                df_ext = await loop.run_in_executor(
                    None, compute_extended_indicators, df, strat
                )
                passes, reason = apply_strategy_filter(strat, sig, df_ext)
                if passes and sig['direction'] != 'NEUTRAL':
                    sig_e       = enrich_signal(strat, sig, df_ext)
                    strat_block = "\n" + build_strategy_signal_block(sig_e)
                elif not passes and sig['direction'] != 'NEUTRAL':
                    strat_block = (
                        f"\n\n━━━━━━━━━━━━━━━━━━━━\n"
                        f"🧠 *{strat.get('name')}*\n"
                        f"⚠️ _Filtro de entrada: {reason}_\n"
                        f"━━━━━━━━━━━━━━━━━━━━"
                    )
        # ─────────────────────────────────────────────────────────────────────

        chart_buf = await loop.run_in_executor(
            None, generate_sp_chart, df, symbol, tf, sig, 60
        )

        msg_text = build_signal_message(symbol, tf, sig) + strat_block
        keyboard = _get_view_keyboard(user_id, symbol, tf)

        # FIX #10: Telegram limita captions a 1024 chars
        if chart_buf and len(msg_text) > 1024:
            msg_text = msg_text[:1020] + "…`"

        if chart_buf:
            chart_buf.seek(0)
            if edit_msg:
                try:
                    await edit_msg.delete()
                except Exception:
                    pass
            await context.bot.send_photo(
                chat_id=update.effective_chat.id,
                photo=chart_buf,
                caption=msg_text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard,
            )
        else:
            # Sin gráfico — editar o enviar texto
            if edit_msg:
                await edit_msg.edit_text(
                    msg_text, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard
                )
            else:
                await update.effective_message.reply_text(
                    msg_text, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard
                )

    except Exception as e:
        add_log_line(f"[SP Handlers] Error en _show_signal_view {symbol}/{tf}: {e}")
        err = "⚠️ Error al generar la señal. Intenta de nuevo."
        try:
            if edit_msg:
                await edit_msg.edit_text(err, parse_mode=ParseMode.MARKDOWN)
        except Exception:
            pass


# ─── CALLBACKS ────────────────────────────────────────────────────────────────

async def sp_main_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Volver al menú principal.
    FIX #2: acceso verificado ANTES del query.answer() para que show_alert funcione.
    """
    query   = update.callback_query
    user_id = query.from_user.id

    # FIX #2: primero verificar, luego responder
    has_access, _ = _check_sp_access(user_id)
    if not has_access:
        await query.answer("❌ Necesitas SmartSignals Pro.", show_alert=True)
        return

    await query.answer()
    try:
        await query.edit_message_text(
            _build_main_menu_text(user_id),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=_get_main_menu_keyboard(user_id)
        )
    except Exception:
        pass


async def sp_coin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Menú de temporalidades de una moneda.
    Callback: sp_coin|SYMBOL
    FIX #7 y #8: usa _best_display_tf() para señal y botón Refrescar.
    """
    query   = update.callback_query
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

    display_tf = _best_display_tf(user_id, symbol)   # FIX #7 y #8
    try:
        await query.edit_message_text(
            _build_coin_menu_text(user_id, symbol, display_tf),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=_get_coin_keyboard(user_id, symbol, current_tf=display_tf)
        )
    except Exception:
        pass


async def sp_toggle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Activa/desactiva alerta para symbol+tf.
    Callback: sp_toggle|SYMBOL|TF
    FIX #7 y #8: recalcula display_tf tras el toggle.
    NUEVO: queue_quick_notify al activar → señal inmediata en el próximo ciclo.
    """
    query   = update.callback_query
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
    coin_info = get_coin_info(symbol) or {"label": symbol}
    label     = coin_info.get('label', symbol)

    if new_state:
        await query.answer(f"🔔 Alertas {label} ({tf}) activadas.")
        add_log_line(f"📡 SP: user {user_id} activó {symbol}/{tf}")
        # NUEVO: señal inmediata en el próximo ciclo del loop
        queue_quick_notify(user_id, symbol, tf)
    else:
        await query.answer(f"🔕 Alertas {label} ({tf}) desactivadas.")
        add_log_line(f"📡 SP: user {user_id} desactivó {symbol}/{tf}")

    # FIX #7 y #8: recalcular después del cambio
    display_tf = _best_display_tf(user_id, symbol)
    try:
        await query.edit_message_text(
            _build_coin_menu_text(user_id, symbol, display_tf),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=_get_coin_keyboard(user_id, symbol, current_tf=display_tf)
        )
    except Exception:
        pass


async def sp_view_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Muestra la señal actual para symbol+tf.
    Callback: sp_view|SYMBOL|TF
    """
    query   = update.callback_query
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

    if tf not in SP_TIMEFRAMES:
        await query.answer(f"❌ Temporalidad '{tf}' no válida.", show_alert=True)
        return

    await query.answer("⏳ Analizando...")

    spinner_msg = None
    try:
        coin_info   = get_coin_info(symbol) or {"label": symbol}
        spinner_msg = await query.edit_message_text(
            f"⏳ _Analizando {coin_info.get('label', symbol)} ({tf})..._",
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception:
        pass

    await _show_signal_view(
        update=update, context=context,
        user_id=user_id, symbol=symbol, tf=tf, edit_msg=spinner_msg,
    )


async def sp_refresh_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Refresca la señal desde el botón de un mensaje con foto.
    Callback: sp_refresh|SYMBOL|TF
    FIX #6: borra el mensaje con foto anterior para evitar duplicados.
    Las fotos de Telegram no se pueden editar, hay que borrar y reenviar.
    """
    query   = update.callback_query
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

    # FIX #6: borrar foto anterior para no generar duplicados
    try:
        await query.message.delete()
    except Exception:
        pass

    await _show_signal_view(
        update=update, context=context,
        user_id=user_id, symbol=symbol, tf=tf, edit_msg=None,
    )


async def sp_my_subs_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Muestra las suscripciones activas del usuario.
    Callback: sp_my_subs
    FIX #3: acceso verificado ANTES del primer query.answer().
    """
    query   = update.callback_query
    user_id = query.from_user.id

    # FIX #3: primero verificar acceso
    has_access, _ = _check_sp_access(user_id)
    if not has_access:
        await query.answer("❌ Sin acceso.", show_alert=True)
        return

    await query.answer()

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
            coin_info  = get_coin_info(sym) or {"label": sym, "emoji": "📡"}
            emoji      = coin_info.get('emoji', '📡')
            label_full = coin_info.get('label', sym)
            # Quitar el prefijo de símbolo (ej "₿ Bitcoin" → "Bitcoin")
            label      = label_full.split(' ', 1)[-1] if ' ' in label_full else label_full
            tfs_str    = " · ".join(sorted(tfs))

            state     = get_sp_state(sym, tfs[0])
            last_info = ""
            if state:
                dir_text  = state.get('last_signal', '')
                dir_emoji = "🟢" if dir_text == 'BUY' else "🔴" if dir_text == 'SELL' else "⚖️"
                last_info = f" — última: {dir_emoji}"

            lines.append(f"{emoji} *{label}* · `{tfs_str}`{last_info}")

        total = count_user_sp_subs(user_id)
        text  = (
            f"📋 *Mis señales SmartSignals*\n"
            f"────────────────────\n\n"
            f"Tienes *{total}* alerta(s) activa(s):\n\n"
            + "\n".join(lines) +
            "\n\n_Toca 🔙 para volver a la lista de monedas._"
        )

    try:
        await query.edit_message_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Lista de monedas", callback_data="sp_main"),
            ]])
        )
    except Exception:
        pass


async def sp_help_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Ayuda del módulo SP."""
    query = update.callback_query
    await query.answer()

    text = (
        "📡 *SmartSignals — Ayuda*\n"
        "————————————————————\n\n"
        "*¿Qué es SmartSignals?*\n"
        "Un radar de trading que analiza el mercado cada 45 segundos "
        "y te avisa cuando detecta señales de compra o venta.\n\n"
        "*¿Cómo funciona?*\n"
        "  • Descarga velas de Binance en tiempo real\n"
        "  • Aplica 7 indicadores (RSI, MACD, Stoch, CCI, BB, MFI, EMAs)\n"
        "  • Si hay confluencia (score ≥4.5), envía alerta con gráfico\n"
        "  • Si score ≥6.5 y la vela cierra pronto → *pre-aviso*\n\n"
        "*Comandos:*\n"
        "  `/sp` — Menú principal\n"
        "  `/sp BTC` — Señal BTC en 5m\n"
        "  `/sp ETH 1h` — Señal ETH en 1h\n"
        "  `/sp BTC 4h` — Señal BTC en 4h\n\n"
        "*Gestión de alertas:*\n"
        "  • Toca una moneda → menú de temporalidades\n"
        "  • Toca el TF para activar/desactivar (🔔 = activo)\n"
        "  • Usa los botones *👁 TF* para ver señal sin suscribirte\n\n"
        "*Cooldown entre señales:*\n"
        "  1m → 3 min · 5m → 5 min · 15m → 15 min\n"
        "  1h → 60 min · 4h → 120 min\n\n"
        "💡 _Las señales son informativas. Evalúa siempre el contexto._"
    )

    try:
        await query.edit_message_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Volver", callback_data="sp_main"),
            ]])
        )
    except Exception:
        pass


async def sp_goto_shop_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Redirige al shop desde el botón de preview.
    FIX #4: en callbacks update.message.reply_text() crashea (message puede ser None
    si fue editado). Usamos context.bot.send_message con chat_id explícito.
    """
    query = update.callback_query
    await query.answer()

    from handlers.pay import (
        PRICE_SP_SIGNALS, PRICE_BUNDLE, PRICE_TA_VIP,
        PRICE_TASA_VIP, PRICE_COIN_SLOT, PRICE_ALERT_SLOT,
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(
            f"📡 SmartSignals Pro — {PRICE_SP_SIGNALS} ⭐  ✨",
            callback_data="buy_sp"
        )],
        [InlineKeyboardButton(f"📦 Pack Total — {PRICE_BUNDLE} ⭐",   callback_data="buy_bundle")],
        [InlineKeyboardButton(f"📈 TA Pro — {PRICE_TA_VIP} ⭐",       callback_data="buy_ta")],
        [InlineKeyboardButton(f"💱 Tasa VIP — {PRICE_TASA_VIP} ⭐",   callback_data="buy_tasa")],
        [
            InlineKeyboardButton(f"🪙 +1 Moneda — {PRICE_COIN_SLOT} ⭐",  callback_data="buy_coin"),
            InlineKeyboardButton(f"🔔 +1 Alerta — {PRICE_ALERT_SLOT} ⭐", callback_data="buy_alert"),
        ],
    ])

    # FIX #4: send_message con chat_id explícito, no update.message que puede ser None
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=(
            "🛒 *Tienda de BitBread Alert* 🛒\n"
            "—————————————————\n\n"
            "Mejora tu experiencia con *Telegram Stars* ⭐.\n\n"
            "*Selecciona una opción 👇*"
        ),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboard,
    )


# ─── SSS: CALLBACKS DE ESTRATEGIAS ───────────────────────────────────────────

async def sp_strategies_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Menú de estrategias SSS.
    Callback: sp_strategies
    """
    query   = update.callback_query
    user_id = query.from_user.id

    has_access, _ = _check_sp_access(user_id)
    if not has_access:
        await query.answer("❌ Necesitas SmartSignals Pro.", show_alert=True)
        return

    await query.answer()

    if not _SSS_OK:
        await query.edit_message_text(
            "⚠️ _El módulo de estrategias no está disponible._",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Volver", callback_data="sp_main"),
            ]])
        )
        return

    strategies  = get_available_strategies(user_id)
    active      = get_user_strategy(user_id)
    active_id   = active['id'] if active else None

    if not strategies:
        text = (
            "🧠 *SmartSignals Strategy*\n"
            "————————————————————\n\n"
            "_No hay estrategias disponibles en este momento._\n\n"
            "Las estrategias se cargan automáticamente desde `data/sss/strategies/`.\n"
            "Contacta al admin para obtener acceso."
        )
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 Volver", callback_data="sp_main"),
        ]])
    else:
        active_name = active.get('name', '') if active else 'Ninguna'
        active_emj  = active.get('emoji', '') if active else ''

        text = (
            "🧠 *SmartSignals Strategy (SSS)*\n"
            "————————————————————\n\n"
            "Aplica estrategias de trading sobre tus señales.\n"
            "Cada estrategia define *entrada, TP, SL y apalancamiento*.\n"
            "Se actualiza *sin reiniciar* el bot.\n\n"
            f"🎯 *Activa:* {active_emj} `{active_name}`\n\n"
            "Selecciona una estrategia para ver detalles:"
        )

        keyboard_rows = []
        for s in strategies:
            is_act  = s['id'] == active_id
            mark    = " ✅" if is_act else ""
            btn_lbl = f"{s.get('emoji','📊')} {s.get('name','')}{mark}"
            keyboard_rows.append([InlineKeyboardButton(
                btn_lbl,
                callback_data=f"sp_strat_detail|{s['id']}"
            )])

        if active_id:
            keyboard_rows.append([InlineKeyboardButton(
                "🚫 Desactivar estrategia",
                callback_data="sp_strat_deactivate"
            )])

        keyboard_rows.append([InlineKeyboardButton("🔙 Volver", callback_data="sp_main")])
        keyboard = InlineKeyboardMarkup(keyboard_rows)

    try:
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)
    except Exception:
        pass


async def sp_strat_detail_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Detalle de una estrategia.
    Callback: sp_strat_detail|STRATEGY_ID
    """
    query   = update.callback_query
    user_id = query.from_user.id

    has_access, _ = _check_sp_access(user_id)
    if not has_access:
        await query.answer("❌ Sin acceso.", show_alert=True)
        return

    try:
        _, strat_id = query.data.split("|", 1)
    except ValueError:
        await query.answer("❌ Error de datos.", show_alert=True)
        return

    await query.answer()

    if not _SSS_OK:
        await query.answer("⚠️ Módulo SSS no disponible.", show_alert=True)
        return

    strat = get_strategy_by_id(strat_id)
    if not strat:
        await query.answer("❌ Estrategia no encontrada.", show_alert=True)
        return

    active = get_user_strategy(user_id)
    is_act = active and active['id'] == strat_id

    text = format_strategy_detail(strat)

    if is_act:
        action_btn = InlineKeyboardButton("✅ Activa · Desactivar", callback_data="sp_strat_deactivate")
    else:
        action_btn = InlineKeyboardButton(
            f"✅ Activar {strat.get('emoji','')} {strat.get('name','')}",
            callback_data=f"sp_strat_activate|{strat_id}"
        )

    keyboard = InlineKeyboardMarkup([
        [action_btn],
        [InlineKeyboardButton("🔙 Lista", callback_data="sp_strategies")],
    ])

    try:
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)
    except Exception:
        pass


async def sp_strat_activate_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Activa una estrategia para el usuario.
    Callback: sp_strat_activate|STRATEGY_ID
    """
    query   = update.callback_query
    user_id = query.from_user.id

    has_access, _ = _check_sp_access(user_id)
    if not has_access:
        await query.answer("❌ Sin acceso.", show_alert=True)
        return

    try:
        _, strat_id = query.data.split("|", 1)
    except ValueError:
        await query.answer("❌ Error de datos.", show_alert=True)
        return

    if not _SSS_OK:
        await query.answer("⚠️ Módulo SSS no disponible.", show_alert=True)
        return

    ok = set_user_strategy(user_id, strat_id)
    if not ok:
        await query.answer("❌ No se pudo activar la estrategia.", show_alert=True)
        return

    strat = get_strategy_by_id(strat_id)
    name  = strat.get('name', strat_id) if strat else strat_id
    await query.answer(f"✅ Estrategia '{name}' activada.", show_alert=True)
    add_log_line(f"[SSS] user {user_id} activó estrategia {strat_id}")

    # Refrescar la vista de detalle
    if strat:
        text     = format_strategy_detail(strat)
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Activa · Desactivar", callback_data="sp_strat_deactivate")],
            [InlineKeyboardButton("🔙 Lista", callback_data="sp_strategies")],
        ])
        try:
            await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)
        except Exception:
            pass


async def sp_strat_deactivate_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Desactiva la estrategia del usuario.
    Callback: sp_strat_deactivate
    """
    query   = update.callback_query
    user_id = query.from_user.id

    has_access, _ = _check_sp_access(user_id)
    if not has_access:
        await query.answer("❌ Sin acceso.", show_alert=True)
        return

    if _SSS_OK:
        set_user_strategy(user_id, None)
        add_log_line(f"[SSS] user {user_id} desactivó estrategia")

    await query.answer("🚫 Estrategia desactivada.", show_alert=True)

    # Volver al menú de estrategias
    strategies  = get_available_strategies(user_id) if _SSS_OK else []
    text = (
        "🧠 *SmartSignals Strategy (SSS)*\n"
        "————————————————————\n\n"
        "Aplica estrategias de trading sobre tus señales.\n"
        "Cada estrategia define *entrada, TP, SL y apalancamiento*.\n"
        "Se actualiza *sin reiniciar* el bot.\n\n"
        "🎯 *Activa:* `Ninguna`\n\n"
        "Selecciona una estrategia para ver detalles:"
    )
    keyboard_rows = [
        [InlineKeyboardButton(
            f"{s.get('emoji','📊')} {s.get('name','')}",
            callback_data=f"sp_strat_detail|{s['id']}"
        )]
        for s in strategies
    ]
    keyboard_rows.append([InlineKeyboardButton("🔙 Volver", callback_data="sp_main")])
    try:
        await query.edit_message_text(
            text, parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard_rows)
        )
    except Exception:
        pass


# ─── REGISTRO DE HANDLERS ─────────────────────────────────────────────────────

sp_handlers_list = [
    CommandHandler("sp",    sp_command),
    # Menú principal y navegación
    CallbackQueryHandler(sp_main_callback,      pattern=r"^sp_main$"),
    CallbackQueryHandler(sp_coin_callback,      pattern=r"^sp_coin\|"),
    CallbackQueryHandler(sp_toggle_callback,    pattern=r"^sp_toggle\|"),
    CallbackQueryHandler(sp_view_callback,      pattern=r"^sp_view\|"),
    CallbackQueryHandler(sp_refresh_callback,   pattern=r"^sp_refresh\|"),
    CallbackQueryHandler(sp_my_subs_callback,   pattern=r"^sp_my_subs$"),
    CallbackQueryHandler(sp_help_callback,      pattern=r"^sp_help$"),
    CallbackQueryHandler(sp_goto_shop_callback, pattern=r"^sp_goto_shop$"),
    # SSS: estrategias de trading
    CallbackQueryHandler(sp_strategies_callback,      pattern=r"^sp_strategies$"),
    CallbackQueryHandler(sp_strat_detail_callback,    pattern=r"^sp_strat_detail\|"),
    CallbackQueryHandler(sp_strat_activate_callback,  pattern=r"^sp_strat_activate\|"),
    CallbackQueryHandler(sp_strat_deactivate_callback,pattern=r"^sp_strat_deactivate$"),
]