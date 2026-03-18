# handlers/sp_handlers.py
# Handlers del módulo SmartSignals (/sp).
# Comando /sp, menús interactivos, suscripciones y callbacks.
#
# BUGS CORREGIDOS (11 originales + 4 SSS v2 + 3 v2.1):
#  1.  [CRÍTICO] /sp BTC 4h siempre mostraba 5m — args no normalizados a lowercase
#  2.  [CRÍTICO] sp_main_callback — query.answer() doble (antes de check acceso)
#  3.  [CRÍTICO] sp_my_subs_callback — mismo doble answer que bug #2
#  4.  [CRÍTICO] sp_goto_shop_callback — crash: update.message=None en callbacks
#  5.  [MAYOR]   Botón 👁 4h ausente en _get_coin_keyboard
#  6.  [MAYOR]   sp_refresh_callback duplicaba mensajes (foto sin borrar la anterior)
#  7.  [MAYOR]   Última señal en menú moneda hardcodeada a "5m"
#  8.  [MAYOR]   Botón Refrescar del menú moneda siempre iba a 5m
#  9.  [MAYOR]   NEUTRAL se mostraba como SELL (en sp_loop.py/build_signal_message)
#  10. [MENOR]   Caption foto puede superar 1024 chars (límite Telegram)
#  11. [MENOR]   score_label NameError potencial si direction=NEUTRAL
#  12. [NUEVO]   Submenú de estrategias de trading SSS
#  13. [NUEVO]   Selección de estrategia por usuario (hot-reload)
#  14. [NUEVO]   Quick-notify: señal inmediata al activar suscripción
#  15. [NUEVO]   Vista de señal enriquecida con TP/SL/leverage
#  — v2.1 fixes —
#  16. [CRÍTICO] Botón 🔙 Monedas falla en mensajes con foto → _safe_nav()
#  17. [CRÍTICO] Botón 🔙 Lista falla en mensajes con foto → _safe_nav()
#  18. [MENOR]   Líneas de texto demasiado largas en bloques SSS
#  19. [NUEVO]   Submenú de subida de estrategias de usuario
#  — v2.2 (análisis de seguridad) —
#  20. [CRÍTICO] Race conditions en archivos JSON → threading.Lock por path
#  21. [CRÍTICO] Sin rate limiting → DoS flooding → Rate limiter por usuario
#  22. [CRÍTICO] Callback data no validada → inyección → _validate_symbol/_validate_tf
#  23. [RENDIMIENTO] DataFrame .copy() innecesario en SPSignalEngine.analyze()

import asyncio
import json
import os
import time
import pandas as pd
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Document
from telegram.ext import (
    ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters
)
from telegram.constants import ParseMode

from core.config import ADMIN_CHAT_IDS
from utils.file_manager import add_log_line
from utils.subscription_manager import (
    check_feature_access,
    registrar_uso_comando,
)
from utils.user_data import obtener_datos_usuario_seguro
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
    # SP Trading
    open_trade,
    get_open_trades,
    get_trade_by_id,
    close_trade,
    count_user_open_trades,
    get_trades_stats,
    cleanup_closed_trades,
    TRADE_CLEANUP_DAYS,
)
from utils.sp_chart import generate_sp_chart
from core.sp_loop import SPSignalEngine, _get_klines, build_signal_message, build_minimal_signal_message, _fmt_price

# SSS: estrategias como skills
try:
    from utils.sss_manager import (
        get_available_strategies,
        get_user_strategy,
        set_user_strategy,
        get_strategy_by_id,
        format_strategy_detail,
        apply_strategy_filter,
        enrich_signal,
        compute_extended_indicators,
        build_strategy_signal_block,
        save_user_strategy_file,
        validate_strategy_json,
        run_strategy_backtest,
        format_backtest_result,
        SSS_STRAT_DIR,
    )
    _SSS_OK = True
except ImportError:
    _SSS_OK = False
    run_strategy_backtest  = None
    format_backtest_result = None


# ─── RATE LIMITER ─────────────────────────────────────────────────────────────
# Previene abuso del comando /sp y ataques DoS por flooding de callbacks.
# Límite: MAX_CALLS llamadas dentro de WINDOW_S segundos por usuario.

_rl_calls: dict[int, list[float]] = {}   # user_id -> [timestamps]
_rl_lock = __import__('threading').Lock()
_RL_MAX_CALLS  = 8    # max solicitudes en la ventana
_RL_WINDOW_S   = 20   # ventana en segundos


def _check_rate_limit(user_id: int) -> bool:
    """
    Devuelve True si el usuario está dentro del límite permitido.
    Limpia timestamps caducados en cada llamada.
    """
    now = time.time()
    with _rl_lock:
        timestamps = _rl_calls.get(user_id, [])
        # Descartar llamadas fuera de la ventana
        timestamps = [t for t in timestamps if now - t < _RL_WINDOW_S]
        if len(timestamps) >= _RL_MAX_CALLS:
            _rl_calls[user_id] = timestamps
            return False
        timestamps.append(now)
        _rl_calls[user_id] = timestamps
        return True


# ─── HELPERS ──────────────────────────────────────────────────────────────────

def _check_sp_access(user_id: int) -> tuple[bool, str]:
    """Admins: acceso libre. Resto: necesita sub activa."""
    if user_id in ADMIN_CHAT_IDS:
        return True, "Admin"
    return check_feature_access(user_id, 'sp_signals')


def _validate_symbol(raw: str) -> str | None:
    """
    Valida y normaliza un símbolo de callback (e.g. 'BTCUSDT').
    Devuelve el símbolo si es válido, None si no lo es.
    """
    from utils.sp_manager import SP_COINS_MAP
    sym = raw.upper().strip()
    return sym if sym in SP_COINS_MAP else None


def _validate_tf(raw: str) -> str | None:
    """
    Valida y normaliza una temporalidad de callback (e.g. '5m').
    Devuelve el TF si es válido, None si no lo es.
    """
    tf = raw.lower().strip()
    return tf if tf in SP_TIMEFRAMES else None


def _best_display_tf(user_id: int, symbol: str) -> str:
    """
    Devuelve el TF más relevante para mostrar en el menú de moneda.
    Prioriza el primer TF activo del usuario (en orden 1m→4h).
    """
    user_subs  = get_user_sp_subscriptions(user_id)
    active_tfs = user_subs.get(symbol, [])
    if active_tfs:
        for tf in SP_TIMEFRAMES:
            if tf in active_tfs:
                return tf
    return "5m"


async def _safe_nav(query, text: str, reply_markup: InlineKeyboardMarkup) -> None:
    """
    FIX #16/#17: Navega de forma segura entre menús aunque el mensaje actual
    sea una foto (send_photo). Intenta edit_message_text primero; si falla
    (BadRequest en mensajes con media), borra el mensaje y envía uno nuevo.
    """
    try:
        await query.edit_message_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup,
        )
    except Exception:
        # El mensaje es una foto u otro tipo de media que no se puede editar
        try:
            await query.message.delete()
        except Exception:
            pass
        try:
            await query.message.chat.send_message(
                text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup,
            )
        except Exception:
            pass


# ─── TECLADOS ─────────────────────────────────────────────────────────────────

def _get_main_menu_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """
    Menú principal simplificado de SmartSignals.
    Máximo 5 opciones principales.
    """
    keyboard = []
    subs = get_user_sp_subscriptions(user_id)
    
    # Fila 1: Principales monedas (2 por fila para más espacio)
    keyboard.append([
        InlineKeyboardButton("₿ BTC", callback_data="sp_coin|BTCUSDT"),
        InlineKeyboardButton("Ξ ETH", callback_data="sp_coin|ETHUSDT"),
    ])
    keyboard.append([
        InlineKeyboardButton("◎ SOL", callback_data="sp_coin|SOLUSDT"),
        InlineKeyboardButton("⚡ XMR", callback_data="sp_coin|XMRUSDT"),
    ])
    
    # Fila 2: Mis suscripciones
    sub_count = sum(1 for s in subs.values() if s)
    sub_text = f"📋 Mis Señales ({sub_count})"
    keyboard.append([InlineKeyboardButton(sub_text, callback_data="sp_my_subs")])
    
    # Fila 3: Ayuda y Tienda
    keyboard.append([
        InlineKeyboardButton("❓ Ayuda", callback_data="sp_help"),
        InlineKeyboardButton("🛒 Tienda", callback_data="sp_goto_shop"),
    ])
    
    # Fila 4: Estrategias (SSS)
    if _SSS_OK:
        strat = get_user_strategy(user_id)
        if strat:
            strat_name = strat.get('name', 'Estrategia')[:20]
            strat_text = f"🧠 {strat_name}"
        else:
            strat_text = "🧠 Estrategias"
        keyboard.append([InlineKeyboardButton(strat_text, callback_data="sp_strategies")])
    
    return InlineKeyboardMarkup(keyboard)


def _get_coin_keyboard(user_id: int, symbol: str, current_tf: str = "5m") -> InlineKeyboardMarkup:
    """
    Teclado del menú de moneda.
    Fila 1-2: toggle de suscripción por TF.
    Fila 3:   botones 👁 VER (incluye 4h — fix #5).
    Fila 4:   Refrescar + 🔙 Lista.
    """
    keyboard = []

    # Fila(s) toggle TF
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

    # Fila ver TF (fix #5: generados dinámicamente, incluye 4h)
    keyboard.append([
        InlineKeyboardButton(f"👁 {tf}", callback_data=f"sp_view|{symbol}|{tf}")
        for tf in SP_TIMEFRAMES
    ])

    # Navegación (fix #8: Refrescar usa current_tf real)
    keyboard.append([
        InlineKeyboardButton("🔄 Refrescar", callback_data=f"sp_view|{symbol}|{current_tf}"),
        InlineKeyboardButton("📈 Operaciones", callback_data="sp_ops"),
    ])
    keyboard.append([
        InlineKeyboardButton("🔙 Lista",      callback_data="sp_main"),
    ])
    return InlineKeyboardMarkup(keyboard)


def _get_view_keyboard(user_id: int, symbol: str, tf: str, direction: str = None) -> InlineKeyboardMarkup:
    """Teclado adjunto a la vista de señal (caption de foto)."""
    is_sub    = is_sp_subscribed(user_id, symbol, tf)
    sub_label = "🔕 Desactivar" if is_sub else "🔔 Activar alertas"
    coin      = symbol.replace('USDT', '')

    keyboard = [
        [
            InlineKeyboardButton(sub_label,       callback_data=f"sp_toggle|{symbol}|{tf}"),
            InlineKeyboardButton("🔄 Refrescar",  callback_data=f"sp_refresh|{symbol}|{tf}"),
        ],
    ]
    
    # Botón ABRIR operación si hay señal válida
    if direction in ('BUY', 'SELL', 'BUY_STRONG', 'SELL_STRONG'):
        keyboard.append([
            InlineKeyboardButton("🚀 Abrir Operación", callback_data=f"sp_open_trade|{symbol}|{tf}"),
        ])
    
    keyboard.append([
        InlineKeyboardButton("📊 Ver en TA",  callback_data=f"ta_switch|BINANCE|{coin}|USDT|{tf}"),
        InlineKeyboardButton("🔙 Monedas",    callback_data=f"sp_coin|{symbol}"),
    ])
    
    return InlineKeyboardMarkup(keyboard)


# ─── TEXTOS ───────────────────────────────────────────────────────────────────

def _build_main_menu_text(user_id: int) -> str:
    """
    Texto simplificado del menú principal.
    """
    subs = get_user_sp_subscriptions(user_id)
    active_count = sum(1 for s in subs.values() if s)
    
    text = (
        "📊 *SmartSignals*\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Tus suscripciones activas: *{active_count}*\n\n"
        "Selecciona una moneda para ver señales.\n"
        "Usa /sp help para más opciones."
    )
    
    # Añadir sugerencia contextual
    if active_count == 0:
        text += "\n\n💡 *Tip:* Activa notificaciones para recibir alertas cuando haya señales."
    
    return text


def _build_preview_text() -> str:
    return (
        "📡 *SmartSignals Pro*\n"
        "—————————————————\n\n"
        "Detecta señales BUY/SELL con análisis\n"
        "multi-indicador y recibe alertas *10–30s*\n"
        "antes de que se confirmen.\n\n"
        "✨ *Incluye:*\n"
        "  • Señales con gráfico predictivo\n"
        "  • Pre-aviso antes del cierre de vela\n"
        "  • Targets y Stop-Loss con ATR\n"
        "  • 13 monedas · 5 temporalidades\n"
        "  • Estrategias SSS personalizadas\n\n"
        "💰 *Precio: 200 ⭐ (30 días)*\n\n"
        "—————————————————\n"
        "_Activa SmartSignals en la tienda._"
    )


def _build_coin_menu_text(user_id: int, symbol: str, display_tf: str) -> str:
    """Texto del menú de moneda."""
    coin_info  = get_coin_info(symbol) or {"label": symbol, "emoji": "📡"}
    label      = coin_info.get('label', symbol)
    emoji      = coin_info.get('emoji', '📡')
    user_subs  = get_user_sp_subscriptions(user_id)
    active_tfs = user_subs.get(symbol, [])

    sub_status = (
        f"🔔 Activa en: *{', '.join(sorted(active_tfs))}*"
        if active_tfs else
        "Sin alertas — toca un TF para activar"
    )

    state    = get_sp_state(symbol, display_tf)
    last_sig = ""
    if state:
        dir_text  = state.get('last_signal', '')
        dir_emoji = "🟢" if dir_text == 'BUY' else "🔴" if dir_text == 'SELL' else "⚖️"
        last_price = state.get('last_price', 0)
        if dir_text and last_price:
            last_sig = (
                f"\n📌 Última ({display_tf}): "
                f"{dir_emoji} `{dir_text}` @ `${_fmt_price(last_price)}`"
            )

    return (
        f"📡 *SmartSignals — {emoji} {label}*\n"
        f"—————————————————\n\n"
        f"{sub_status}{last_sig}\n\n"
        f"🔔 Toca un TF para activar/desactivar alertas.\n"
        f"👁 Toca *Ver TF* para ver señal sin suscribirte.\n"
        f"—————————————————"
    )


# ─── COMANDO /sp ──────────────────────────────────────────────────────────────

async def sp_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /sp           → Menú principal
    /sp BTC       → Señal BTC 5m
    /sp BTC 4h    → Señal BTC 4h
    Fix #1: args[1] normalizado a lowercase.
    """
    user_id = update.effective_user.id
    registrar_uso_comando(user_id, 'sp')
    obtener_datos_usuario_seguro(user_id)

    # Rate limiting: previene flooding/DoS
    if not _check_rate_limit(user_id) and user_id not in ADMIN_CHAT_IDS:
        await update.message.reply_text(
            "⏳ _Demasiadas solicitudes. Espera unos segundos._",
            parse_mode=ParseMode.MARKDOWN
        )
        return

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

    coin_key = args[0].upper()
    tf       = args[1].lower() if len(args) > 1 else "5m"
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


async def sp_alertas_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /sp_alertas - Muestra las alertas activas del usuario como comando.
    Similar a sp_my_subs_callback pero como comando independiente.
    """
    user_id = update.effective_user.id
    registrar_uso_comando(user_id, 'sp_alertas')

    has_access, _ = _check_sp_access(user_id)
    if not has_access:
        await update.message.reply_text(
            "❌ Sin acceso.\n\nUsa /sp para ver el menú principal.",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    text, keyboard = _build_my_subs_content(user_id)

    await update.message.reply_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def sp_cleanup_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /sp_cleanup - Muestra estadísticas y limpia operaciones cerradas (solo admin).
    Sin args: muestra estadísticas.
    Con 'run': ejecuta cleanup.
    """
    user_id = update.effective_user.id

    if user_id not in ADMIN_CHAT_IDS:
        await update.message.reply_text("❌ Solo admin.")
        return

    args = context.args
    do_run = len(args) > 0 and args[0].lower() == "run"

    stats = get_trades_stats()

    text = (
        "🧹 *SP Trading Cleanup*\n"
        "────────────────────\n\n"
        f"📊 *Estadísticas actuales:*\n"
        f"  • Usuarios con trades: *{stats['total_users']}*\n"
        f"  • Operaciones abiertas: *{stats['open_trades']}*\n"
        f"  • Operaciones cerradas: *{stats['closed_trades']}*\n"
        f"  • Umbral de limpieza: *{TRADE_CLEANUP_DAYS} días*\n\n"
    )

    if do_run:
        result = cleanup_closed_trades()
        text += (
            f"✅ *Cleanup ejecutado:*\n"
            f"  • Eliminados: *{result['deleted_count']}* trades\n"
            f"  • Restantes: *{result['remaining_count']}* trades\n"
            f"  • Usuarios afectados: *{result['users_affected']}*\n\n"
            f"_Los trades cerrados hace más de {TRADE_CLEANUP_DAYS} días fueron eliminados._"
        )
    else:
        text += (
            "ℹ️ *Comandos:*\n"
            "  `/sp_cleanup` — Ver estadísticas\n"
            "  `/sp_cleanup run` — Ejecutar limpieza\n\n"
            "_El cleanup también se ejecuta automáticamente cada ~50 minutos._"
        )

    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


# ─── VISTA DE SEÑAL ───────────────────────────────────────────────────────────

async def _show_signal_view(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    symbol: str,
    tf: str,
    edit_msg=None,
) -> None:
    """
    Descarga → analiza → genera gráfico → envía señal.
    Fix #10: caption truncado a 1024 chars.
    SSS: enriquece con estrategia activa del usuario.
    """
    try:
        loop = asyncio.get_running_loop()

        df = await loop.run_in_executor(None, _get_klines, symbol, tf, 120)
        if df is None or len(df) < 30:
            err = f"❌ Sin datos para *{symbol}* ({tf})."
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

        # SSS: bloque de estrategia activa ─────────────────────────────────────
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
                    name = strat.get('name', '')[:20]
                    strat_block = (
                        f"\n\n—————————————————\n"
                        f"🧠 *{name}* — filtro activo\n"
                        f"⚠️ _{reason}_\n"
                        f"—————————————————"
                    )
        # ──────────────────────────────────────────────────────────────────────

        chart_buf = await loop.run_in_executor(
            None, generate_sp_chart, df, symbol, tf, sig, 60
        )

        msg_text = build_signal_message(symbol, tf, sig) + strat_block
        
        # Añadir sugerencia de siguientes pasos
        msg_text += "\n\n━━━━━━━━━━━━━━━━━━━━\n"
        msg_text += "📌 *Otras opciones:*\n"
        msg_text += "• /sp mis señales - Ver todas\n"
        msg_text += "• /sp tienda - Suscribirse\n"
        msg_text += "• /help - Otros comandos"
        
        keyboard = _get_view_keyboard(user_id, symbol, tf, sig.get('direction'))

        # Fix #10: límite de caption Telegram
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
    Fix #2: acceso verificado ANTES de query.answer().
    Fix #16: usa _safe_nav para manejar mensajes con foto.
    """
    query   = update.callback_query
    user_id = query.from_user.id

    has_access, _ = _check_sp_access(user_id)
    if not has_access:
        await query.answer("❌ Necesitas SmartSignals Pro.", show_alert=True)
        return

    await query.answer()
    await _safe_nav(
        query,
        _build_main_menu_text(user_id),
        _get_main_menu_keyboard(user_id),
    )


async def sp_coin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Menú de temporalidades de una moneda.
    Callback: sp_coin|SYMBOL
    Fix #7/#8: usa _best_display_tf().
    Fix #16: usa _safe_nav para manejar regreso desde foto.
    """
    query   = update.callback_query
    user_id = query.from_user.id

    has_access, _ = _check_sp_access(user_id)
    if not has_access:
        await query.answer("❌ Necesitas SmartSignals Pro.", show_alert=True)
        return

    try:
        _, raw_sym = query.data.split("|", 1)
    except ValueError:
        await query.answer("❌ Error de datos.", show_alert=True)
        return

    symbol = _validate_symbol(raw_sym)
    if not symbol:
        await query.answer("❌ Moneda no válida.", show_alert=True)
        return

    await query.answer()

    display_tf = _best_display_tf(user_id, symbol)
    await _safe_nav(
        query,
        _build_coin_menu_text(user_id, symbol, display_tf),
        _get_coin_keyboard(user_id, symbol, current_tf=display_tf),
    )


async def sp_toggle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Activa/desactiva alerta para symbol+tf.
    Callback: sp_toggle|SYMBOL|TF
    Fix #7/#8: recalcula display_tf tras toggle.
    Nuevo: queue_quick_notify al activar.
    Fix #16: _safe_nav para mensajes con foto.
    """
    query   = update.callback_query
    user_id = query.from_user.id

    has_access, _ = _check_sp_access(user_id)
    if not has_access:
        await query.answer("❌ Necesitas SmartSignals Pro.", show_alert=True)
        return

    try:
        _, raw_sym, raw_tf = query.data.split("|")
    except ValueError:
        await query.answer("❌ Error de datos.", show_alert=True)
        return

    symbol = _validate_symbol(raw_sym)
    tf     = _validate_tf(raw_tf)
    if not symbol or not tf:
        await query.answer("❌ Parámetros no válidos.", show_alert=True)
        return

    new_state = toggle_sp_subscription(user_id, symbol, tf)
    coin_info = get_coin_info(symbol) or {"label": symbol}
    label     = coin_info.get('label', symbol).split(' ', 1)[-1]

    if new_state:
        await query.answer(f"🔔 {label} ({tf}) activada.")
        add_log_line(f"📡 SP: user {user_id} activó {symbol}/{tf}")
        queue_quick_notify(user_id, symbol, tf)
    else:
        await query.answer(f"🔕 {label} ({tf}) desactivada.")
        add_log_line(f"📡 SP: user {user_id} desactivó {symbol}/{tf}")

    display_tf = _best_display_tf(user_id, symbol)
    await _safe_nav(
        query,
        _build_coin_menu_text(user_id, symbol, display_tf),
        _get_coin_keyboard(user_id, symbol, current_tf=display_tf),
    )


async def sp_view_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Muestra la señal actual para symbol+tf.
    Callback: sp_view|SYMBOL|TF
    """
    query   = update.callback_query
    user_id = query.from_user.id

    has_access, _ = _check_sp_access(user_id)
    if not has_access:
        await query.answer("❌ Necesitas SmartSignals Pro.", show_alert=True)
        return

    try:
        _, raw_sym, raw_tf = query.data.split("|")
    except ValueError:
        await query.answer("❌ Error de datos.", show_alert=True)
        return

    symbol = _validate_symbol(raw_sym)
    tf     = _validate_tf(raw_tf)
    if not symbol:
        await query.answer("❌ Moneda no válida.", show_alert=True)
        return
    if not tf:
        await query.answer(f"❌ Temporalidad no válida.", show_alert=True)
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
    Refresca la señal desde botón de mensaje con foto.
    Callback: sp_refresh|SYMBOL|TF
    Fix #6: borra foto anterior.
    """
    query   = update.callback_query
    user_id = query.from_user.id

    has_access, _ = _check_sp_access(user_id)
    if not has_access:
        await query.answer("❌ Sin acceso.", show_alert=True)
        return

    try:
        _, raw_sym, raw_tf = query.data.split("|")
    except ValueError:
        await query.answer("❌ Error de datos.", show_alert=True)
        return

    symbol = _validate_symbol(raw_sym)
    tf     = _validate_tf(raw_tf)
    if not symbol or not tf:
        await query.answer("❌ Parámetros no válidos.", show_alert=True)
        return

    await query.answer("⏳ Actualizando...")

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
    Suscripciones activas del usuario con botones interactivos.
    Callback: sp_my_subs
    """
    query   = update.callback_query
    user_id = query.from_user.id

    has_access, _ = _check_sp_access(user_id)
    if not has_access:
        await query.answer("❌ Sin acceso.", show_alert=True)
        return

    await query.answer()

    text, keyboard = _build_my_subs_content(user_id)

    await _safe_nav(
        query, text,
        InlineKeyboardMarkup(keyboard)
    )


def _build_my_subs_content(user_id: int) -> tuple[str, list[list[InlineKeyboardButton]]]:
    """
    Construye el contenido de Mis alertas: texto y teclado.
    Devuelve (texto, keyboard) para usar tanto en callback como en comando.
    """
    user_subs = get_user_sp_subscriptions(user_id)

    if not user_subs:
        text = (
            "📋 *Mis alertas SmartSignals*\n"
            "—————————————————\n\n"
            "Sin alertas activas.\n\n"
            "_Selecciona una moneda y temporalidad\n"
            "para empezar a recibir alertas._"
        )
        keyboard = [[InlineKeyboardButton("🔙 Lista de monedas", callback_data="sp_main")]]
        return text, keyboard

    lines = []
    keyboard = []

    for sym in sorted(user_subs.keys()):
        tfs = user_subs.get(sym, [])
        if not tfs:
            continue

        coin_info = get_coin_info(sym) or {"label": sym, "emoji": "📡"}
        emoji = coin_info.get('emoji', '📡')
        label_full = coin_info.get('label', sym)
        label = label_full.split(' ', 1)[-1] if ' ' in label_full else label_full

        tf_buttons = []
        for tf in sorted(tfs):
            state = get_sp_state(sym, tf)

            score = state.get('last_signal_score', 0) if state else 0
            dir_text = state.get('last_signal', '') if state else ''
            dir_emoji = "🟢" if dir_text == 'BUY' else "🔴" if dir_text == 'SELL' else "⚖️"
            
            score_str = f"_{score:.1f}_" if score else "_-_-"
            lines.append(f"{emoji} *{label}* `{tf}` · {score_str} {dir_emoji}")

            tf_buttons.append(InlineKeyboardButton(
                f"👁 {tf}",
                callback_data=f"sp_view|{sym}|{tf}"
            ))
            tf_buttons.append(InlineKeyboardButton(
                f"🔕",
                callback_data=f"sp_toggle|{sym}|{tf}"
            ))

        for i in range(0, len(tf_buttons), 2):
            row = tf_buttons[i:i+2]
            keyboard.append(row)

    total = count_user_sp_subs(user_id)
    text = (
        f"📋 *Mis alertas SmartSignals*\n"
        f"—————————————————\n\n"
        f"*{total}* alerta(s) activa(s):\n\n"
        + "\n".join(lines) +
        "\n\n_Toca 👁 para ver la señal.\n"
        "Toca 🔕 para desactivar._"
    )

    keyboard.append([InlineKeyboardButton("🔙 Lista de monedas", callback_data="sp_main")])

    return text, keyboard


async def sp_help_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Ayuda del módulo SP."""
    query = update.callback_query
    await query.answer()

    text = (
        "📡 *SmartSignals — Ayuda*\n"
        "—————————————————\n\n"
        "*¿Qué es SmartSignals?*\n"
        "Radar de trading que analiza el mercado\n"
        "cada 45s y avisa al detectar señales.\n\n"
        "*¿Cómo funciona?*\n"
        "  • Descarga velas de Binance en tiempo real\n"
        "  • Aplica 7 indicadores (RSI, MACD, Stoch…)\n"
        "  • Score ≥4.5 → alerta con gráfico\n"
        "  • Score ≥6.5 + vela cerrando → pre-aviso\n\n"
        "*Comandos rápidos:*\n"
        "  `/sp` — Menú principal\n"
        "  `/sp BTC` — Señal BTC en 5m\n"
        "  `/sp ETH 1h` — Señal ETH en 1h\n\n"
        "*Cooldown entre señales:*\n"
        "  1m → 3min · 5m → 5min · 15m → 15min\n"
        "  1h → 60min · 4h → 120min\n\n"
        "💡 _Señales informativas. Evalúa el contexto._"
    )

    await _safe_nav(
        query, text,
        InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 Volver", callback_data="sp_main"),
        ]])
    )


async def sp_goto_shop_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Redirige al shop desde el botón de preview.
    Fix #4: send_message con chat_id explícito.
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
        [InlineKeyboardButton(f"📦 Pack Total — {PRICE_BUNDLE} ⭐",  callback_data="buy_bundle")],
        [InlineKeyboardButton(f"📈 TA Pro — {PRICE_TA_VIP} ⭐",      callback_data="buy_ta")],
        [InlineKeyboardButton(f"💱 Tasa VIP — {PRICE_TASA_VIP} ⭐",  callback_data="buy_tasa")],
        [
            InlineKeyboardButton(f"🪙 +1 Moneda — {PRICE_COIN_SLOT} ⭐", callback_data="buy_coin"),
            InlineKeyboardButton(f"🔔 +1 Alerta — {PRICE_ALERT_SLOT} ⭐", callback_data="buy_alert"),
        ],
    ])

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


# ─── SSS: CALLBACKS DE ESTRATEGIAS ────────────────────────────────────────────

def _build_strategies_text(active_name: str, active_emj: str) -> str:
    return (
        "🧠 *SmartSignals Strategy (SSS)*\n"
        "—————————————————\n\n"
        "Aplica estrategias de trading sobre tus señales.\n"
        "Cada estrategia define *entrada, TP, SL\n"
        "y apalancamiento*. Se actualiza sin reiniciar.\n\n"
        f"🎯 *Activa:* {active_emj} `{active_name}`\n\n"
        "Selecciona una estrategia para ver detalles:"
    )


def _build_strategies_keyboard(strategies: list, active_id: str | None) -> InlineKeyboardMarkup:
    rows = []
    # Agrupar 2 por fila
    row = []
    for s in strategies:
        is_act  = s['id'] == active_id
        mark    = " ✅" if is_act else ""
        btn_lbl = f"{s.get('emoji','📊')} {s.get('name','')}{mark}"
        row.append(InlineKeyboardButton(btn_lbl, callback_data=f"sp_strat_detail|{s['id']}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)

    # Acciones
    action_row = []
    if active_id:
        action_row.append(InlineKeyboardButton(
            "🚫 Desactivar", callback_data="sp_strat_deactivate"
        ))
    action_row.append(InlineKeyboardButton(
        "📤 Mi Estrategia", callback_data="sp_strat_upload"
    ))
    rows.append(action_row)

    rows.append([InlineKeyboardButton("🔙 Volver", callback_data="sp_main")])
    return InlineKeyboardMarkup(rows)


async def sp_strategies_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Menú de estrategias SSS. Callback: sp_strategies"""
    query   = update.callback_query
    user_id = query.from_user.id

    has_access, _ = _check_sp_access(user_id)
    if not has_access:
        await query.answer("❌ Necesitas SmartSignals Pro.", show_alert=True)
        return

    await query.answer()

    if not _SSS_OK:
        await _safe_nav(query,
            "⚠️ _Módulo de estrategias no disponible._",
            InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Volver", callback_data="sp_main")]])
        )
        return

    strategies = get_available_strategies(user_id)
    active     = get_user_strategy(user_id)
    active_id  = active['id'] if active else None
    active_name = active.get('name', 'Ninguna') if active else 'Ninguna'
    active_emj  = active.get('emoji', '')       if active else ''

    if not strategies:
        await _safe_nav(query,
            "🧠 *SmartSignals Strategy (SSS)*\n"
            "————————————————————\n\n"
            "_Sin estrategias disponibles._\n\n"
            "Contacta al admin para obtener acceso.",
            InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Volver", callback_data="sp_main")]])
        )
        return

    await _safe_nav(
        query,
        _build_strategies_text(active_name, active_emj),
        _build_strategies_keyboard(strategies, active_id),
    )


async def sp_strat_detail_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Detalle de una estrategia. Callback: sp_strat_detail|STRATEGY_ID"""
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
    text   = format_strategy_detail(strat)

    # Elegir símbolo para el test: primera suscripción activa o BTC
    test_sym = _best_test_symbol(user_id)

    if is_act:
        action_btn = InlineKeyboardButton(
            "✅ Activa · Desactivar", callback_data="sp_strat_deactivate"
        )
    else:
        action_btn = InlineKeyboardButton(
            f"✅ Activar {strat.get('emoji','')} {strat.get('name','')}",
            callback_data=f"sp_strat_activate|{strat_id}"
        )

    await _safe_nav(query, text, InlineKeyboardMarkup([
        [
            action_btn,
            InlineKeyboardButton("🧪 Test", callback_data=f"sp_strat_test|{strat_id}|{test_sym}"),
        ],
        [InlineKeyboardButton("🔙 Estrategias", callback_data="sp_strategies")],
    ]))


async def sp_strat_activate_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Activa una estrategia. Callback: sp_strat_activate|STRATEGY_ID"""
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
        await query.answer("❌ No se pudo activar.", show_alert=True)
        return

    strat = get_strategy_by_id(strat_id)
    name  = strat.get('name', strat_id) if strat else strat_id
    await query.answer(f"✅ '{name}' activada.", show_alert=True)
    add_log_line(f"[SSS] user {user_id} activó estrategia {strat_id}")

    if strat:
        test_sym = _best_test_symbol(user_id)
        text     = format_strategy_detail(strat)
        await _safe_nav(query, text, InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Activa · Desactivar", callback_data="sp_strat_deactivate"),
                InlineKeyboardButton("🧪 Test", callback_data=f"sp_strat_test|{strat_id}|{test_sym}"),
            ],
            [InlineKeyboardButton("🔙 Estrategias", callback_data="sp_strategies")],
        ]))


async def sp_strat_deactivate_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Desactiva la estrategia activa. Callback: sp_strat_deactivate"""
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

    strategies = get_available_strategies(user_id) if _SSS_OK else []
    await _safe_nav(
        query,
        _build_strategies_text("Ninguna", ""),
        _build_strategies_keyboard(strategies, None),
    )


# ─── SSS: BACKTEST DE ESTRATEGIA ─────────────────────────────────────────────

_BT_SYMBOLS = ["BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT","ADAUSDT","DOGEUSDT"]


def _best_test_symbol(user_id: int) -> str:
    """Elige símbolo para el test: primera suscripción activa o BTCUSDT."""
    user_subs = get_user_sp_subscriptions(user_id)
    for sym in _BT_SYMBOLS:
        if sym in user_subs and user_subs[sym]:
            return sym
    return "BTCUSDT"


def _test_keyboard(strat_id: str, current_sym: str) -> InlineKeyboardMarkup:
    """Botones rápidos para cambiar el par del backtest."""
    quick = []
    for sym in ["BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT"]:
        lbl = sym.replace("USDT","") + (" ✓" if sym == current_sym else "")
        quick.append(InlineKeyboardButton(lbl, callback_data=f"sp_strat_test|{strat_id}|{sym}"))
    return InlineKeyboardMarkup([
        quick,
        [
            InlineKeyboardButton("🔄 Repetir", callback_data=f"sp_strat_test|{strat_id}|{current_sym}"),
            InlineKeyboardButton("🔙 Estrategia", callback_data=f"sp_strat_detail|{strat_id}"),
        ],
    ])


async def sp_strat_test_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Ejecuta backtest de la estrategia sobre velas históricas de Binance.
    Callback: sp_strat_test|STRATEGY_ID|SYMBOL
    - Muestra spinner mientras calcula (3–10 segundos).
    - Edita el mensaje con resultados estadísticos.
    - Botones para cambiar par (BTC/ETH/SOL/BNB) y repetir.
    """
    query   = update.callback_query
    user_id = query.from_user.id

    has_access, _ = _check_sp_access(user_id)
    if not has_access:
        await query.answer("❌ Necesitas SmartSignals Pro.", show_alert=True)
        return

    try:
        parts    = query.data.split("|")
        strat_id = parts[1]
        symbol   = parts[2] if len(parts) > 2 else "BTCUSDT"
    except (IndexError, ValueError):
        await query.answer("❌ Error de datos.", show_alert=True)
        return

    if not _SSS_OK or run_strategy_backtest is None:
        await query.answer("⚠️ Módulo SSS no disponible.", show_alert=True)
        return

    strat = get_strategy_by_id(strat_id)
    if not strat:
        await query.answer("❌ Estrategia no encontrada.", show_alert=True)
        return

    await query.answer("⏳ Ejecutando backtest…")

    tf = strat.get('timeframes', ['5m'])[0]
    try:
        await query.edit_message_text(
            f"🧪 *Backtest — {strat.get('emoji','')} {strat.get('name','')}*\n"
            f"—————————————————\n\n"
            f"⏳ _Analizando `{symbol}` · `{tf}`…_\n\n"
            f"Descargando 500 velas y aplicando la\n"
            f"estrategia sobre operaciones pasadas…",
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception:
        pass

    loop = asyncio.get_running_loop()
    try:
        result = await loop.run_in_executor(
            None, run_strategy_backtest, strat, symbol, 500
        )
    except Exception as e:
        add_log_line(f"[SSS Test] Excepción en backtest {strat_id}/{symbol}: {e}")
        result = {'error': f'Error inesperado: {e}', 'trades': [], 'stats': {}, 'diagnostics': {}}

    text     = format_backtest_result(result, strat)
    keyboard = _test_keyboard(strat_id, symbol)

    stats   = result.get('stats', {})
    add_log_line(
        f"[SSS Test] user {user_id} testó '{strat_id}' en {symbol}/{tf} "
        f"— {stats.get('total',0)} ops, WR={stats.get('win_rate',0)}% "
        f"diag={result.get('diagnostics',{})}"
    )

    try:
        await query.edit_message_text(
            text[:4000],
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard,
        )
    except Exception:
        pass


# ─── SSS: SUBIDA DE ESTRATEGIAS DE USUARIO ────────────────────────────────────

_SSS_JSON_TEMPLATE = """{
  "id": "mi_estrategia_unica",
  "name": "Nombre visible",
  "version": "1.0.0",
  "author": "TuNombre",
  "tier": "base",
  "style": "swing",
  "emoji": "⚡",
  "description": "Descripción breve de la estrategia.",
  "timeframes": ["5m", "15m", "1h"],
  "entry_filter": {
    "min_score": 5.0,
    "supertrend_align": false,
    "ash_signal": false,
    "volume_spike": false,
    "adx_min": 0,
    "adx_di_confirm": false,
    "macd_cross_required": false
  },
  "risk": {
    "sl_type": "atr",
    "sl_atr_mult": 1.5,
    "tp1_atr_mult": 2.0,  "tp1_close_pct": 50,
    "tp2_atr_mult": 3.5,  "tp2_close_pct": 30,
    "tp3_atr_mult": 5.5,  "tp3_close_pct": 20,
    "trailing_after_tp1": false,
    "trailing_type": null
  },
  "leverage": {
    "default": 5,
    "max": 20,
    "volatile_reduce": true,
    "volatile_threshold": 0.03,
    "volatile_max": 10
  },
  "capital": {
    "small_threshold": 22,
    "small_exit": "full_tp1",
    "large_exit": "partial_trail"
  },
  "meta": {
    "win_rate_est": "N/A",
    "rr_ratio": "1:2 / 1:3.5",
    "best_markets": "Describe cuando usar esta estrategia",
    "avoid_markets": "Describe cuando NO usarla"
  }
}"""


def _build_upload_text() -> str:
    return (
        "📤 *Subir mi Estrategia SSS*\n"
        "—————————————————\n\n"
        "Puedes crear y subir tu propia estrategia\n"
        "en formato JSON. Se carga automáticamente\n"
        "*sin reiniciar el bot*.\n\n"
        "📋 *Campos obligatorios:*\n"
        "  • `id` — identificador único (sin espacios)\n"
        "  • `name` — nombre visible en el menú\n"
        "  • `timeframes` — TFs válidos: 1m 5m 15m 1h 4h\n"
        "  • `entry_filter` → `min_score` (ej. 4.5–7.0)\n"
        "  • `risk` → multiplicadores de ATR para SL/TP\n"
        "  • `leverage` → `default` y `max`\n\n"
        "🔒 *Filtros de entrada disponibles:*\n"
        "  • `supertrend_align` — true/false\n"
        "  • `ash_signal` — true/false\n"
        "  • `volume_spike` — true/false\n"
        "  • `adx_min` — número (0 = desactivado)\n"
        "  • `macd_cross_required` — true/false\n\n"
        "📐 *Referencia de R:R típicos:*\n"
        "  SL ×1.5 · TP1 ×2.0 → R:R 1:1.3\n"
        "  SL ×1.5 · TP2 ×3.5 → R:R 1:2.3\n\n"
        "—————————————————\n"
        "⬇️ Envía el archivo `.json` directamente\n"
        "en este chat para subirlo."
    )


async def sp_strat_upload_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Submenú de instrucciones para subir estrategia propia.
    Callback: sp_strat_upload
    """
    query   = update.callback_query
    user_id = query.from_user.id

    has_access, _ = _check_sp_access(user_id)
    if not has_access:
        await query.answer("❌ Necesitas SmartSignals Pro.", show_alert=True)
        return

    await query.answer()

    # Guardar en contexto que el usuario está esperando un JSON
    context.user_data['sss_awaiting_upload'] = True

    await _safe_nav(
        query,
        _build_upload_text(),
        InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Estrategias", callback_data="sp_strategies")],
        ])
    )


async def sp_strategy_document_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    MessageHandler: recibe documentos .json y los guarda como estrategias SSS.
    Solo actúa si el usuario tiene acceso SP y estaba esperando un upload.
    """
    user_id = update.effective_user.id

    # Solo procesar si el usuario inició el flujo de upload
    if not context.user_data.get('sss_awaiting_upload'):
        return

    has_access, _ = _check_sp_access(user_id)
    if not has_access:
        return

    doc: Document = update.message.document
    if not doc or not doc.file_name.endswith('.json'):
        await update.message.reply_text(
            "⚠️ Solo se aceptan archivos `.json`.\n"
            "Envía el archivo de estrategia en formato JSON.",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    if doc.file_size > 50_000:  # 50KB máximo
        await update.message.reply_text(
            "❌ El archivo es demasiado grande (máx. 50KB)."
        )
        return

    # Descargar y parsear
    try:
        file = await context.bot.get_file(doc.file_id)
        raw_bytes = await file.download_as_bytearray()
        raw_str   = raw_bytes.decode('utf-8')
        data      = json.loads(raw_str)
    except json.JSONDecodeError as e:
        await update.message.reply_text(
            f"❌ *JSON inválido:* `{e}`\n\n"
            f"Revisa la sintaxis del archivo e intenta de nuevo.",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    except Exception as e:
        add_log_line(f"[SSS Upload] Error descargando archivo de {user_id}: {e}")
        await update.message.reply_text("❌ Error al descargar el archivo. Intenta de nuevo.")
        return

    # Validar y guardar
    if not _SSS_OK:
        await update.message.reply_text("⚠️ Módulo SSS no disponible.")
        return

    ok, error_msg = validate_strategy_json(data)
    if not ok:
        await update.message.reply_text(
            f"❌ *Estrategia inválida:*\n`{error_msg}`\n\n"
            f"Corrige el campo indicado e intenta de nuevo.",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    saved_path = save_user_strategy_file(user_id, data)
    if not saved_path:
        await update.message.reply_text("❌ Error al guardar. Contacta al admin.")
        return

    context.user_data.pop('sss_awaiting_upload', None)

    name  = data.get('name', data.get('id', '?'))
    emoji = data.get('emoji', '📊')
    tfs   = ", ".join(data.get('timeframes', []))

    add_log_line(f"[SSS Upload] user {user_id} subió estrategia '{data.get('id')}'")

    await update.message.reply_text(
        f"✅ *Estrategia guardada*\n"
        f"—————————————————\n\n"
        f"{emoji} *{name}*\n"
        f"TF: `{tfs}`\n\n"
        f"Disponible en *SmartSignals → Estrategias*.\n"
        f"Usa `/sp` → 🧠 para activarla.",
        parse_mode=ParseMode.MARKDOWN
    )

    # Notificar a admins sobre nueva estrategia de usuario
    strat_id = data.get('id', '?')
    for admin_id in ADMIN_CHAT_IDS:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=(
                    f"📤 *Nueva estrategia SSS subida*\n"
                    f"Usuario: `{user_id}`\n"
                    f"ID: `{strat_id}` · Nombre: *{name}*"
                ),
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception:
            pass


# ─── REGISTRO DE HANDLERS ─────────────────────────────────────────────────────

# SP TRADING - OPERACIONES
# ═══════════════════════════════════════════════════════════════════════════════

async def sp_open_trade_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Abre una operación desde el botón de señal."""
    print(f"[DEBUG] sp_open_trade_callback: data={update.callback_query.data}, user={update.callback_query.from_user.id}")
    query = update.callback_query
    user_id = query.from_user.id
    
    has_access, _ = _check_sp_access(user_id)
    if not has_access:
        await query.answer("⚠️ Necesitas SmartSignals Pro.", show_alert=True)
        return
    
    try:
        _, raw_sym, raw_tf = query.data.split("|")
    except ValueError:
        await query.answer("❌ Error de datos.", show_alert=True)
        return
    
    symbol = _validate_symbol(raw_sym)
    tf = _validate_tf(raw_tf)
    if not symbol or not tf:
        await query.answer("❌ Parámetros no válidos.", show_alert=True)
        return
    
    await _do_open_trade(update, context, query, user_id, symbol, tf, is_prealert=False)


async def sp_preopen_trade_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Abre una operación desde el botón de prealerta.
    Muestra confirmación previa porque la señal puede cambiar al cierre de vela.
    """
    print(f"[DEBUG] sp_preopen_trade_callback: data={update.callback_query.data}, user={update.callback_query.from_user.id}")
    query = update.callback_query
    user_id = query.from_user.id
    
    has_access, _ = _check_sp_access(user_id)
    if not has_access:
        await query.answer("⚠️ Necesitas SmartSignals Pro.", show_alert=True)
        return
    
    try:
        _, raw_sym, raw_tf = query.data.split("|")
    except ValueError:
        await query.answer("❌ Error de datos.", show_alert=True)
        return
    
    symbol = _validate_symbol(raw_sym)
    tf = _validate_tf(raw_tf)
    if not symbol or not tf:
        await query.answer("❌ Parámetros no válidos.", show_alert=True)
        return
    
    coin = symbol.replace("USDT", "")
    
    confirm_text = (
        f"⚠️ *Apertura desde prealerta*\n"
        f"—————————————————\n\n"
        f"Esta es una prealerta. *La señal puede cambiar*\n"
        f"*al cierre de vela*.\n\n"
        f"¿Estás seguro de que quieres abrir la operación\n"
        f"al precio actual en `{coin}/{tf}`?"
    )
    
    confirm_kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Sí, abrir", callback_data=f"sp_confirm_open|{symbol}|{tf}"),
            InlineKeyboardButton("❌ Cancelar", callback_data=f"sp_view|{symbol}|{tf}"),
        ]
    ])
    
    try:
        await query.edit_message_text(
            text=confirm_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=confirm_kb,
        )
    except Exception:
        await query.answer("⚠️ No se pudo mostrar confirmación.", show_alert=True)


async def sp_confirm_open_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Confirma y ejecuta la apertura de operación desde prealerta.
    Callback: sp_confirm_open|SYMBOL|TF
    """
    query = update.callback_query
    user_id = query.from_user.id
    
    has_access, _ = _check_sp_access(user_id)
    if not has_access:
        await query.answer("⚠️ Necesitas SmartSignals Pro.", show_alert=True)
        return
    
    try:
        _, raw_sym, raw_tf = query.data.split("|")
    except ValueError:
        await query.answer("❌ Error de datos.", show_alert=True)
        return
    
    symbol = _validate_symbol(raw_sym)
    tf = _validate_tf(raw_tf)
    if not symbol or not tf:
        await query.answer("❌ Parámetros no válidos.", show_alert=True)
        return
    
    await _do_open_trade(update, context, query, user_id, symbol, tf, is_prealert=True)


async def _do_open_trade(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    query,
    user_id: int,
    symbol: str,
    tf: str,
    is_prealert: bool = False
) -> None:
    """Función común para abrir una operación."""
    open_count = count_user_open_trades(user_id)
    if open_count >= 5:
        await query.answer("⚠️ Máximo 5 operaciones abiertas.", show_alert=True)
        return
    
    await query.answer("⏳ Abriendo operación...")
    
    try:
        loop = asyncio.get_running_loop()
        df = await loop.run_in_executor(None, _get_klines, symbol, tf, 120)
        if df is None or len(df) < 30:
            await query.answer("❌ Sin datos suficientes.", show_alert=True)
            return
        
        engine = SPSignalEngine()
        sig = engine.analyze(df)
        
        direction = sig.get("direction")
        if direction not in ("BUY", "SELL"):
            await query.answer("❌ No hay señal válida.", show_alert=True)
            return
        
        entry_price = sig.get("price", 0)
        stop_loss = sig.get("stop", 0)
        tp1 = sig.get("target1", 0)
        tp2 = sig.get("target2", 0)
        
        trade_id = open_trade(
            user_id=user_id,
            symbol=symbol,
            timeframe=tf,
            direction=direction,
            entry_price=entry_price,
            stop_loss=stop_loss,
            tp1=tp1,
            tp2=tp2,
            tp3=0,
            tp1_pct=50,
            tp2_pct=30,
            tp3_pct=20,
        )
        
        coin = symbol.replace("USDT", "")
        dir_emoji = "🟢" if direction in ("BUY", "BUY_STRONG") else "🔴"
        
        prealert_note = (
            "\n⚠️ <b>Nota:</b> Operación abierta desde prealerta.\n"
            "La señal puede variar al cierre de vela."
        ) if is_prealert else ""
        
        trade_text = (
            f"✅ <b>Operación Abierta</b> {dir_emoji}\n"
            f"────────────────────\n\n"
            f"📡 <b>{coin}</b> ({tf}) · {direction}\n"
            f"💰 Entrada: <code>{_fmt_price(entry_price)}</code>\n"
            f"🛡 SL: <code>{_fmt_price(stop_loss)}</code>\n"
            f"🎯 TP1: <code>{_fmt_price(tp1)}</code>\n"
            f"🎯 TP2: <code>{_fmt_price(tp2)}</code>\n\n"
            f"🆔 ID: <code>{trade_id}</code>{prealert_note}\n\n"
            f"ℹ️ Te notificaré al tocar SL o TP.\n"
            "Usa /sp_ops para ver operaciones."
        )
        trade_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 Mis Operaciones", callback_data="sp_ops")],
            [InlineKeyboardButton("🔙 Volver", callback_data=f"sp_view|{symbol}|{tf}")]
        ])
        
        try:
            await query.edit_message_caption(
                caption=trade_text,
                parse_mode=ParseMode.HTML,
                reply_markup=trade_kb,
            )
        except Exception:
            try:
                await query.message.delete()
            except Exception:
                pass
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=trade_text,
                parse_mode=ParseMode.HTML,
                reply_markup=trade_kb,
            )
    except Exception as e:
        add_log_line(f"[SP Trading] Error open_trade: {e}")
        await query.answer("❌ Error al abrir operación.", show_alert=True)


async def sp_close_trade_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Cierra una operación manualmente."""
    query = update.callback_query
    user_id = query.from_user.id
    
    has_access, _ = _check_sp_access(user_id)
    if not has_access:
        await query.answer("⚠️ Necesitas SmartSignals Pro.", show_alert=True)
        return
    
    try:
        _, trade_id = query.data.split("|", 1)
    except ValueError:
        await query.answer("❌ Error de datos.", show_alert=True)
        return
    
    trade = get_trade_by_id(user_id, trade_id)
    if not trade:
        await query.answer("❌ Operación no encontrada.", show_alert=True)
        return
    
    if trade.get("status") != "OPEN":
        await query.answer("⚠️ La operación ya está cerrada.", show_alert=True)
        return
    
    entry = trade.get("entry_price", 0)
    current = trade.get("current_price", entry)
    direction = trade.get("direction", "BUY")
    
    if direction in ("BUY", "BUY_STRONG") and entry > 0:
        pnl = ((current - entry) / entry) * 100
    elif direction in ("SELL", "SELL_STRONG") and entry > 0:
        pnl = ((entry - current) / entry) * 100
    else:
        pnl = 0
    
    close_trade(user_id, trade_id, "MANUAL", pnl)
    
    coin = trade.get("symbol", "").replace("USDT", "")
    pnl_emoji = "🟢" if pnl >= 0 else "🔴"
    
    await query.answer()
    await query.edit_message_text(
        f"✅ *Operación Cerrada* {pnl_emoji}\n"
        f"────────────────────\n\n"
        f"📡 {coin} · {trade.get('direction')}\n"
        f"💰 Entry: ${_fmt_price(entry)} → Exit: ${_fmt_price(current)}\n"
        f"PnL: {pnl_emoji} {pnl:+.2f}%\n\n"
        f"Razón: *Cierre manual*",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Mis Operaciones", callback_data="sp_ops")]
        ])
    )


async def sp_ops_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Comando /sp_ops - Lista de operaciones."""
    user_id = update.effective_user.id
    registrar_uso_comando(user_id, "sp_ops")
    
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
    
    open_trades = get_open_trades(user_id)
    
    if not open_trades:
        await update.message.reply_text(
            "📡 *SmartSignals — Operaciones*\n"
            "────────────────────\n\n"
            "No tienes operaciones abiertas.\n\n"
            "Usa /sp para ver señales y abrir operaciones.",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    lines = []
    keyboard = []
    
    for t in open_trades:
        coin = t.get("symbol", "").replace("USDT", "")
        direction = t.get("direction", "?")
        entry = t.get("entry_price", 0)
        current = t.get("current_price", entry)
        sl = t.get("stop_loss", 0)
        tp1 = t.get("tp1", 0)
        tp2 = t.get("tp2", 0)
        
        dir_emoji = "🟢" if direction in ("BUY", "BUY_STRONG") else "🔴"
        
        if direction in ("BUY", "BUY_STRONG") and entry > 0 and sl > 0:
            dist_sl = ((entry - sl) / entry) * 100
            dist_tp1 = ((tp1 - entry) / entry) * 100 if tp1 > 0 else 0
        elif direction in ("SELL", "SELL_STRONG") and entry > 0 and sl > 0:
            dist_sl = ((sl - entry) / entry) * 100
            dist_tp1 = ((entry - tp1) / entry) * 100 if tp1 > 0 else 0
        else:
            dist_sl = dist_tp1 = 0
        
        lines.append(
            f"{dir_emoji} *{coin}* `{direction}`\n"
            f"   Entry: ${_fmt_price(entry)} | Curr: ${_fmt_price(current)}\n"
            f"   🛡 SL: ${_fmt_price(sl)} ({dist_sl:.1f}%)\n"
            f"   🎯 TP1: ${_fmt_price(tp1)} (+{dist_tp1:.1f}%)"
        )
        
        keyboard.append([
            InlineKeyboardButton(
                f"🔒 Cerrar {coin}",
                callback_data=f"sp_close_trade|{t.get('trade_id')}"
            )
        ])
    
    total = len(open_trades)
    msg = (
        f"📡 *SmartSignals — Operaciones*\n"
        f"────────────────────\n\n"
        f"Tienes *{total}* operación(es) abierta(s):\n\n"
        + "\n\n".join(lines) +
        "\n\n────────────────────\n"
        "ℹ️ Te notifico cuando el precio toque SL o TP."
    )
    
    await update.message.reply_text(
        msg,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard + [[InlineKeyboardButton("🔙 Menú Principal", callback_data="sp_main")]])
    )


async def sp_ops_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback para actualizar lista de operaciones (inline desde menú)."""
    query = update.callback_query
    user_id = query.from_user.id

    has_access, _ = _check_sp_access(user_id)
    if not has_access:
        await query.answer("❌ Sin acceso.", show_alert=True)
        return

    await query.answer()

    open_trades = get_open_trades(user_id)

    if not open_trades:
        await _safe_nav(
            query,
            "📡 *SmartSignals — Operaciones*\n"
            "────────────────────\n\n"
            "No tienes operaciones abiertas.\n\n"
            "_Usa /sp para ver señales y abrir operaciones._",
            InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Menú Principal", callback_data="sp_main")
            ]])
        )
        return

    lines = []
    keyboard = []

    for t in open_trades:
        coin = t.get("symbol", "").replace("USDT", "")
        direction = t.get("direction", "?")
        entry = t.get("entry_price", 0)
        current = t.get("current_price", entry)
        sl = t.get("stop_loss", 0)
        tp1 = t.get("tp1", 0)
        tp_hit = t.get("tp_hit", None)
        dir_emoji = "🟢" if direction in ("BUY", "BUY_STRONG") else "🔴"
        tp_badge = f" ✅{tp_hit}" if tp_hit else ""

        if direction in ("BUY", "BUY_STRONG") and entry > 0:
            dist_sl = ((entry - sl) / entry) * 100 if sl > 0 else 0
            dist_tp1 = ((tp1 - entry) / entry) * 100 if tp1 > 0 else 0
            pnl = ((current - entry) / entry) * 100
        elif direction in ("SELL", "SELL_STRONG") and entry > 0:
            dist_sl = ((sl - entry) / entry) * 100 if sl > 0 else 0
            dist_tp1 = ((entry - tp1) / entry) * 100 if tp1 > 0 else 0
            pnl = ((entry - current) / entry) * 100
        else:
            dist_sl = dist_tp1 = pnl = 0

        pnl_str = f"+{pnl:.2f}%" if pnl >= 0 else f"{pnl:.2f}%"
        pnl_icon = "🟢" if pnl >= 0 else "🔴"

        lines.append(
            f"{dir_emoji} *{coin}* `{direction}`{tp_badge}\n"
            f"   Entry: `${_fmt_price(entry)}` | Actual: `${_fmt_price(current)}`\n"
            f"   PnL: {pnl_icon} `{pnl_str}` | SL: `${_fmt_price(sl)}` ({dist_sl:.1f}%)\n"
            f"   🎯 TP1: `${_fmt_price(tp1)}` (+{dist_tp1:.1f}%)"
        )
        keyboard.append([InlineKeyboardButton(
            f"🔒 Cerrar {coin} ({pnl_str})",
            callback_data=f"sp_close_trade|{t.get('trade_id')}"
        )])

    total = len(open_trades)
    msg = (
        f"📡 *SmartSignals — Operaciones Abiertas*\n"
        f"────────────────────\n\n"
        f"Tienes *{total}* operación(es):\n\n"
        + "\n\n".join(lines) +
        "\n\n────────────────────\n"
        "_Toca Cerrar para salir manualmente._"
    )

    await _safe_nav(
        query, msg,
        InlineKeyboardMarkup(keyboard + [[
            InlineKeyboardButton("🔙 Menú Principal", callback_data="sp_main")
        ]])
    )


sp_handlers_list = [
    CommandHandler("sp", sp_command),
    CommandHandler("sp_ops", sp_ops_command),
    CommandHandler("sp_alertas", sp_alertas_command),
    CommandHandler("sp_cleanup", sp_cleanup_command),
    # Navegación principal
    CallbackQueryHandler(sp_main_callback,      pattern=r"^sp_main$"),
    CallbackQueryHandler(sp_coin_callback,      pattern=r"^sp_coin\|"),
    CallbackQueryHandler(sp_toggle_callback,    pattern=r"^sp_toggle\|"),
    CallbackQueryHandler(sp_view_callback,      pattern=r"^sp_view\|"),
    CallbackQueryHandler(sp_refresh_callback, pattern=r"^sp_refresh\|"),
    CallbackQueryHandler(sp_open_trade_callback,   pattern=r"^sp_open_trade\|"),
    CallbackQueryHandler(sp_preopen_trade_callback, pattern=r"^sp_preopen_trade\|"),
    CallbackQueryHandler(sp_confirm_open_callback, pattern=r"^sp_confirm_open\|"),
    CallbackQueryHandler(sp_close_trade_callback,  pattern=r"^sp_close_trade\|"),
    CallbackQueryHandler(sp_ops_callback,           pattern=r"^sp_ops$"),
    CallbackQueryHandler(sp_my_subs_callback,   pattern=r"^sp_my_subs$"),
    CallbackQueryHandler(sp_help_callback,      pattern=r"^sp_help$"),
    CallbackQueryHandler(sp_goto_shop_callback, pattern=r"^sp_goto_shop$"),
    # SSS — Estrategias
    CallbackQueryHandler(sp_strategies_callback,       pattern=r"^sp_strategies$"),
    CallbackQueryHandler(sp_strat_detail_callback,     pattern=r"^sp_strat_detail\|"),
    CallbackQueryHandler(sp_strat_activate_callback,   pattern=r"^sp_strat_activate\|"),
    CallbackQueryHandler(sp_strat_deactivate_callback, pattern=r"^sp_strat_deactivate$"),
    CallbackQueryHandler(sp_strat_test_callback,       pattern=r"^sp_strat_test\|"),
    CallbackQueryHandler(sp_strat_upload_callback,     pattern=r"^sp_strat_upload$"),
    # SSS — Subida de estrategias de usuario (documentos JSON)
    MessageHandler(
        filters.Document.MimeType("application/json") | filters.Document.FileExtension("json"),
        sp_strategy_document_handler
    ),
]

# ═══════════════════════════════════════════════════════════════════════════════
