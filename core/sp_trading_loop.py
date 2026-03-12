# core/sp_trading_loop.py
# Loop de monitoreo de operaciones de trading
#
# Lógica de cierre:
#   SL hit       → cierra inmediatamente
#   TP1/TP2 hit  → marca tp_hit, NO cierra (permite trailing)
#   TP3 hit      → cierra con all_tp_hit
#   Retrace      → notifica (precio regresa a entry tras TP1/TP2)
#   Manual       → cierre por usuario vía /sp_ops

import asyncio
import time
import requests
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode

from utils.sp_manager import (
    get_all_open_trades,
    update_trade_price,
    close_trade,
    check_trade_crosses,
    _load,
    _save,
    SP_TRADES_PATH,
    cleanup_closed_trades,
)

TRADE_CHECK_INTERVAL = 30
NOTIFY_COOLDOWN = 300
CLEANUP_INTERVAL_CYCLES = 100  # Cleanup cada ~50 minutos (100 * 30s)


def _get_binance_price(symbol):
    try:
        url = "https://api.binance.com/api/v3/ticker?symbol=" + symbol
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            return float(r.json()["lastPrice"])
    except:
        pass
    return None


async def sp_trading_monitor_loop(bot, add_log_line):
    add_log_line("[Trading] Iniciando monitor de operaciones (cada 30s)")
    last_notify = {}
    cycle_count = 0

    while True:
        try:
            # Cleanup periódico cada CLEANUP_INTERVAL_CYCLES
            cycle_count += 1
            if cycle_count >= CLEANUP_INTERVAL_CYCLES:
                cycle_count = 0
                try:
                    result = cleanup_closed_trades()
                    if result['deleted_count'] > 0:
                        add_log_line(
                            f"[Trading] Cleanup: {result['deleted_count']} trades eliminados, "
                            f"{result['users_affected']} usuarios afectados"
                        )
                except Exception as e:
                    add_log_line(f"[Trading] Cleanup error: {e}")

            open_trades = get_all_open_trades()
            if not open_trades:
                await asyncio.sleep(TRADE_CHECK_INTERVAL)
                continue

            symbols = {}
            for user_id, trade in open_trades:
                sym = trade.get("symbol")
                if sym not in symbols:
                    symbols[sym] = []
                symbols[sym].append((user_id, trade))

            for sym, trades_list in symbols.items():
                price = _get_binance_price(sym)
                if not price:
                    continue

                for user_id, trade in trades_list:
                    try:
                        trade_id = trade.get("trade_id")
                        update_trade_price(user_id, trade_id, price)
                        crosses = check_trade_crosses(trade, price)

                        direction = trade.get("direction", "BUY")
                        entry = trade.get("entry_price", 0)
                        coin = sym.replace("USDT", "")

                        if crosses.get("sl_hit"):
                            # SL tocado: cierra inmediatamente
                            key = trade_id + ":SL"
                            if _should_notify(key, last_notify):
                                pnl = _calc_pnl(direction, entry, trade.get("stop_loss", 0))
                                close_trade(user_id, trade_id, "SL_HIT", pnl)
                                await _notify_close(bot, user_id, trade, price, "SL", pnl, coin)
                                last_notify[key] = time.time()

                        elif crosses.get("all_tp_hit"):
                            # TP3 tocado: cierra con ganancia máxima
                            key = trade_id + ":TP3"
                            if _should_notify(key, last_notify):
                                tp_price = trade.get("tp3", 0) or price
                                pnl = _calc_pnl(direction, entry, tp_price)
                                close_trade(user_id, trade_id, "TP3_HIT", pnl)
                                await _notify_close(bot, user_id, trade, price, "TP3 ★", pnl, coin)
                                last_notify[key] = time.time()

                        elif crosses.get("tp_hit") and crosses["tp_hit"] != trade.get("tp_hit"):
                            # TP1 o TP2 tocado: marca pero NO cierra (trailing)
                            tp = crosses["tp_hit"]
                            key = trade_id + ":" + tp
                            if _should_notify(key, last_notify):
                                tp_price = trade.get(tp.lower(), 0)
                                pnl = _calc_pnl(direction, entry, tp_price)
                                _mark_tp_hit(user_id, trade_id, tp)
                                await _notify_tp_partial(bot, user_id, trade, price, tp, pnl, coin)
                                last_notify[key] = time.time()

                        elif crosses.get("retrace") and trade.get("tp_hit"):
                            # Retrace a entrada tras haber tocado TP parcial
                            key = trade_id + ":RETRACE"
                            if _should_notify(key, last_notify):
                                await _notify_retrace(bot, user_id, trade, price, coin)
                                last_notify[key] = time.time()

                    except Exception as e:
                        add_log_line("[Trading] Error: " + str(e))

            await asyncio.sleep(TRADE_CHECK_INTERVAL)

        except Exception as e:
            add_log_line("[Trading] Loop error: " + str(e))
            await asyncio.sleep(60)


def _should_notify(key, cache):
    last = cache.get(key, 0)
    return (time.time() - last) > NOTIFY_COOLDOWN


def _calc_pnl(direction, entry, exit_price):
    if direction in ("BUY", "BUY_STRONG") and entry > 0:
        return ((exit_price - entry) / entry) * 100
    elif direction in ("SELL", "SELL_STRONG") and entry > 0:
        return ((entry - exit_price) / entry) * 100
    return 0


async def _notify_close(bot, user_id, trade, price, reason, pnl, coin):
    """Notificación de cierre de operación (SL o TP3)."""
    direction = trade.get("direction", "BUY")
    entry = trade.get("entry_price", 0)
    tf = trade.get("timeframe", "")
    pnl_str = f"+{pnl:.2f}" if pnl >= 0 else f"{pnl:.2f}"
    pnl_icon = "✅" if pnl >= 0 else "🚨"
    dir_emoji = "🟢" if direction in ("BUY", "BUY_STRONG") else "🔴"
    msg = (
        f"{pnl_icon} *Operación Cerrada*\n"
        f"────────────────────\n\n"
        f"{dir_emoji} *{coin}* `{direction}` ({tf})\n"
        f"💰 Entry: `${entry:.4f}` → Exit: `${price:.4f}`\n"
        f"🔵 Razón: *{reason}*\n"
        f"PnL: *{pnl_str}%*\n\n"
        f"_Usa /sp\_ops para ver operaciones._"
    )
    try:
        await bot.send_message(
            chat_id=user_id, text=msg, parse_mode=ParseMode.MARKDOWN
        )
    except Exception:
        pass


async def _notify_open(bot, user_id, trade, price, coin):
    """Notificación cuando se abre una operación."""
    direction = trade.get("direction", "BUY")
    entry = trade.get("entry_price", 0)
    tf = trade.get("timeframe", "")
    sl = trade.get("stop_loss", 0)
    tp1 = trade.get("tp1", 0)
    tp2 = trade.get("tp2", 0)
    tp3 = trade.get("tp3", 0)
    trade_id = trade.get("trade_id", "")
    dir_emoji = "🟢" if direction in ("BUY", "BUY_STRONG") else "🔴"

    msg = (
        f"🚀 *Operación Abierta*\n"
        f"────────────────────\n\n"
        f"{dir_emoji} *{coin}* `{direction}` ({tf})\n"
        f"💰 Entry: `${entry:.4f}`\n"
        f"🛡 SL: `${sl:.4f}`\n"
        f"🎯 TP1: `${tp1:.4f}` | TP2: `${tp2:.4f}` | TP3: `${tp3:.4f}`\n\n"
        f"_Usa /sp\_ops para seguir la operación._"
    )
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton(
            f"🔒 Cerrar {coin}",
            callback_data=f"sp_close_trade|{trade_id}"
        )
    ]])
    try:
        await bot.send_message(
            chat_id=user_id, text=msg,
            parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard
        )
    except Exception:
        pass


async def _notify_tp_partial(bot, user_id, trade, price, tp, pnl, coin):
    """Notificación de TP1/TP2 alcanzado (la operación sigue abierta)."""
    direction = trade.get("direction", "BUY")
    entry = trade.get("entry_price", 0)
    tf = trade.get("timeframe", "")
    trade_id = trade.get("trade_id", "")
    pnl_str = f"+{pnl:.2f}" if pnl >= 0 else f"{pnl:.2f}"
    dir_emoji = "🟢" if direction in ("BUY", "BUY_STRONG") else "🔴"
    msg = (
        f"🎯 *{tp} Alcanzado!*\n"
        f"────────────────────\n\n"
        f"{dir_emoji} *{coin}* `{direction}` ({tf})\n"
        f"💰 Entry: `${entry:.4f}` | Precio: `${price:.4f}`\n"
        f"Parcial: *{pnl_str}%*\n\n"
        f"La operación *sigue abierta* esperando {_next_tp(tp)}.\n"
        f"Cierra ahora si quieres asegurar ganancias."
    )
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton(
            f"🔒 Cerrar {coin} ahora",
            callback_data=f"sp_close_trade|{trade_id}"
        )
    ]])
    try:
        await bot.send_message(
            chat_id=user_id, text=msg,
            parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard
        )
    except Exception:
        pass


def _next_tp(tp: str) -> str:
    """Devuelve el siguiente objetivo tras el TP actual."""
    return {"TP1": "TP2", "TP2": "TP3"}.get(tp, "TP3")


async def _notify_retrace(bot, user_id, trade, price, coin):
    """Notificación de retroceso al precio de entrada tras TP parcial."""
    direction = trade.get("direction", "BUY")
    entry = trade.get("entry_price", 0)
    tf = trade.get("timeframe", "")
    tp_hit = trade.get("tp_hit", "?")
    trade_id = trade.get("trade_id", "")
    dir_emoji = "🟢" if direction in ("BUY", "BUY_STRONG") else "🔴"
    msg = (
        f"⚠️ *Retroceso a entrada tras {tp_hit}*\n"
        f"────────────────────\n\n"
        f"{dir_emoji} *{coin}* `{direction}` ({tf})\n"
        f"💰 Entry: `${entry:.4f}` | Actual: `${price:.4f}`\n\n"
        f"El precio regresó al punto de entrada después de tocar *{tp_hit}*.\n"
        f"Cierra ahora para proteger las ganancias parciales."
    )
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton(
            f"🔒 Cerrar {coin} (proteger ganancias)",
            callback_data=f"sp_close_trade|{trade_id}"
        )
    ]])
    try:
        await bot.send_message(
            chat_id=user_id, text=msg,
            parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard
        )
    except Exception:
        pass


def _mark_tp_hit(user_id, trade_id, tp):
    trades = _load(SP_TRADES_PATH)
    uid = str(user_id)
    if uid in trades:
        for t in trades[uid]:
            if t.get("trade_id") == trade_id:
                t["tp_hit"] = tp
                _save(SP_TRADES_PATH, trades)
                break
