# core/sp_trading_loop.py
# Loop de monitoreo de operaciones de trading

import asyncio
import time
import requests
from telegram.constants import ParseMode

from utils.sp_manager import (
    get_all_open_trades,
    update_trade_price,
    check_trade_crosses,
    _load,
    _save,
    SP_TRADES_PATH,
)

TRADE_CHECK_INTERVAL = 30
NOTIFY_COOLDOWN = 300


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

    while True:
        try:
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
                            key = trade_id + ":SL"
                            if _should_notify(key, last_notify):
                                pnl = _calc_pnl(direction, entry, trade.get("stop_loss", 0))
                                await _notify_close(bot, user_id, trade, price, "SL", pnl, coin)
                                last_notify[key] = time.time()

                        elif crosses.get("tp_hit") and not trade.get("tp_hit"):
                            tp = crosses.get("tp_hit")
                            key = trade_id + ":" + tp
                            if _should_notify(key, last_notify):
                                tp_price = trade.get(tp.lower(), 0)
                                pnl = _calc_pnl(direction, entry, tp_price)
                                await _notify_close(bot, user_id, trade, price, tp, pnl, coin)
                                _mark_tp_hit(user_id, trade_id, tp)
                                last_notify[key] = time.time()

                        elif crosses.get("retrace") and trade.get("tp_hit"):
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
    if direction == "BUY" and entry > 0:
        return ((exit_price - entry) / entry) * 100
    elif direction == "SELL" and entry > 0:
        return ((entry - exit_price) / entry) * 100
    return 0


async def _notify_close(bot, user_id, trade, price, reason, pnl, coin):
    direction = trade.get("direction", "BUY")
    entry = trade.get("entry_price", 0)
    pnl_str = "+%.2f" % pnl if pnl >= 0 else "%.2f" % pnl
    msg = "OPERACION CERRADA (" + pnl_str + "%)" + chr(10)
    msg = msg + "-------------------------" + chr(10) + chr(10)
    msg = msg + coin + " | " + direction + chr(10)
    msg = msg + "Entry: $%.4f | Exit: $%.4f" % (entry, price) + chr(10)
    msg = msg + "Razon: " + reason + chr(10)
    msg = msg + "PnL: " + pnl_str + "%" + chr(10) + chr(10)
    msg = msg + "Usa /sp_ops para mas operaciones."
    try:
        await bot.send_message(chat_id=user_id, text=msg, parse_mode=ParseMode.MARKDOWN)
    except:
        pass


async def _notify_retrace(bot, user_id, trade, price, coin):
    direction = trade.get("direction", "BUY")
    entry = trade.get("entry_price", 0)
    tp_hit = trade.get("tp_hit", "?")
    msg = "ALERTA: Se toco " + tp_hit + " y retraceo" + chr(10)
    msg = msg + "-------------------------" + chr(10) + chr(10)
    msg = msg + coin + " | " + direction + chr(10)
    msg = msg + "Entry: $%.4f | Actual: $%.4f" % (entry, price) + chr(10) + chr(10)
    msg = msg + "Cerrar operacion?" + chr(10)
    msg = msg + "Usa /sp_ops para decidir."
    try:
        await bot.send_message(chat_id=user_id, text=msg, parse_mode=ParseMode.MARKDOWN)
    except:
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
