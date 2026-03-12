# utils/sp_manager.py
# Gestor de suscripciones, estados e historial del módulo SmartSignals (/sp).
# v2 — Añade SP_QUICK_NOTIFY_PATH para señal inmediata al suscribirse.

import json
import os
import time
import threading
from datetime import datetime
from core.config import DATA_DIR

# ─── PATHS ────────────────────────────────────────────────────────────────────
SP_SUBS_PATH         = os.path.join(DATA_DIR, "sp_subs.json")
SP_STATE_PATH        = os.path.join(DATA_DIR, "sp_state.json")
SP_HIST_PATH         = os.path.join(DATA_DIR, "sp_history.json")
SP_QUICK_NOTIFY_PATH = os.path.join(DATA_DIR, "sp_quick_notify.json")
SP_TRADES_PATH       = os.path.join(DATA_DIR, "sp_trades.json")

# ─── CONFIGURACIÓN DE MONEDAS SOPORTADAS ──────────────────────────────────────
SP_SUPPORTED_COINS = [
    # Tier 1 — Core
    {"key": "BTC",  "label": "₿ Bitcoin",     "symbol": "BTCUSDT",   "emoji": "🟠"},
    {"key": "ETH",  "label": "⟠ Ethereum",    "symbol": "ETHUSDT",   "emoji": "🔵"},
    {"key": "BNB",  "label": "⬡ BNB",         "symbol": "BNBUSDT",   "emoji": "🟡"},
    {"key": "SOL",  "label": "◎ Solana",      "symbol": "SOLUSDT",   "emoji": "🟣"},
    {"key": "XRP",  "label": "✕ XRP",         "symbol": "XRPUSDT",   "emoji": "⚫"},
    # Tier 2 — Popular
    {"key": "ADA",  "label": "₳ Cardano",     "symbol": "ADAUSDT",   "emoji": "🔷"},
    {"key": "AVAX", "label": "▲ Avalanche",   "symbol": "AVAXUSDT",  "emoji": "🔴"},
    {"key": "LINK", "label": "⬡ Chainlink",   "symbol": "LINKUSDT",  "emoji": "🔵"},
    {"key": "DOT",  "label": "● Polkadot",    "symbol": "DOTUSDT",   "emoji": "🟤"},
    {"key": "LTC",  "label": "Ł Litecoin",    "symbol": "LTCUSDT",   "emoji": "⚪"},
    # Tier 3 — Trending
    {"key": "DOGE", "label": "Ð Dogecoin",    "symbol": "DOGEUSDT",  "emoji": "🐕"},
    {"key": "SHIB", "label": "🐕 Shiba Inu",  "symbol": "SHIBUSDT",  "emoji": "🐾"},
    {"key": "PEPE", "label": "🐸 Pepe",       "symbol": "PEPEUSDT",  "emoji": "🐸"},
]

# Mapa rápido symbol -> info
SP_COINS_MAP = {c["symbol"]: c for c in SP_SUPPORTED_COINS}
SP_KEYS_MAP  = {c["key"]: c for c in SP_SUPPORTED_COINS}

# Temporalidades disponibles y sus cooldowns
SP_TIMEFRAMES = {
    "1m":  {"label": "1 min",  "min_gap": 180,  "max_day": 60, "interval_s": 60},
    "5m":  {"label": "5 min",  "min_gap": 300,  "max_day": 36, "interval_s": 300},
    "15m": {"label": "15 min", "min_gap": 900,  "max_day": 18, "interval_s": 900},
    "1h":  {"label": "1 hora", "min_gap": 3600, "max_day": 8,  "interval_s": 3600},
    "4h":  {"label": "4 horas","min_gap": 7200, "max_day": 4,  "interval_s": 14400},
}

# Cleanup config
TRADE_CLEANUP_DAYS = 7  # Días después de cerrar para eliminar

# ─── HELPERS JSON ─────────────────────────────────────────────────────────────

# Lock por archivo para evitar race conditions en acceso concurrente
_file_locks: dict[str, threading.Lock] = {}
_file_locks_registry = threading.Lock()


def _get_lock(path: str) -> threading.Lock:
    """Devuelve (o crea) el lock asociado al path de archivo."""
    with _file_locks_registry:
        if path not in _file_locks:
            _file_locks[path] = threading.Lock()
        return _file_locks[path]


def _load(path: str) -> dict:
    lock = _get_lock(path)
    with lock:
        if not os.path.exists(path):
            return {}
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}


def _save(path: str, data: dict) -> None:
    lock = _get_lock(path)
    with lock:
        try:
            tmp = f"{path}.tmp"
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.replace(tmp, path)
        except Exception as e:
            print(f"[SP Manager] Error guardando {path}: {e}")

# ─── SUSCRIPCIONES ────────────────────────────────────────────────────────────

def is_sp_subscribed(user_id, symbol: str, timeframe: str) -> bool:
    """Verifica si el usuario está suscrito a symbol+timeframe."""
    subs = _load(SP_SUBS_PATH)
    uid = str(user_id)
    return (
        uid in subs and
        symbol in subs[uid] and
        isinstance(subs[uid][symbol], list) and
        timeframe in subs[uid][symbol]
    )

def toggle_sp_subscription(user_id, symbol: str, timeframe: str) -> bool:
    """
    Activa/desactiva la suscripción. Devuelve True si quedó activada.
    """
    subs = _load(SP_SUBS_PATH)
    uid = str(user_id)

    if uid not in subs:
        subs[uid] = {}
    if symbol not in subs[uid] or not isinstance(subs[uid][symbol], list):
        subs[uid][symbol] = []

    if timeframe in subs[uid][symbol]:
        subs[uid][symbol].remove(timeframe)
        result = False
        if not subs[uid][symbol]:
            del subs[uid][symbol]
        if not subs[uid]:
            del subs[uid]
    else:
        subs[uid][symbol].append(timeframe)
        result = True

    _save(SP_SUBS_PATH, subs)
    return result

def get_sp_subscribers(symbol: str, timeframe: str) -> list:
    """Lista de user_ids suscritos a un par/TF concreto."""
    subs = _load(SP_SUBS_PATH)
    result = []
    for uid, coins in subs.items():
        if symbol in coins and isinstance(coins[symbol], list) and timeframe in coins[symbol]:
            result.append(uid)
    return result

def get_active_sp_pairs() -> list:
    """
    Devuelve lista de tuplas (symbol, timeframe) que tienen al menos 1 suscriptor.
    """
    subs = _load(SP_SUBS_PATH)
    pairs = set()
    for uid, coins in subs.items():
        for sym, tfs in coins.items():
            if isinstance(tfs, list):
                for tf in tfs:
                    pairs.add((sym, tf))
    return list(pairs)

def get_user_sp_subscriptions(user_id) -> dict:
    """
    Devuelve las suscripciones del usuario: {symbol: [tfs]}
    """
    subs = _load(SP_SUBS_PATH)
    return subs.get(str(user_id), {})

def count_user_sp_subs(user_id) -> int:
    """Cuántas suscripciones activas tiene el usuario."""
    user_subs = get_user_sp_subscriptions(user_id)
    total = 0
    for tfs in user_subs.values():
        if isinstance(tfs, list):
            total += len(tfs)
    return total

# ─── ESTADOS DE SEÑALES ───────────────────────────────────────────────────────

def get_sp_state(symbol: str, timeframe: str) -> dict:
    """Estado actual del par (última señal, cooldown, etc.)."""
    state = _load(SP_STATE_PATH)
    key = f"{symbol}_{timeframe}"
    return state.get(key, {})

def update_sp_state(symbol: str, timeframe: str, signal_data: dict) -> None:
    """Guarda el estado tras emitir una señal."""
    state = _load(SP_STATE_PATH)
    key = f"{symbol}_{timeframe}"
    today = datetime.now().strftime('%Y-%m-%d')

    existing = state.get(key, {})
    daily = existing.get('daily_count', 0) if existing.get('daily_date') == today else 0

    state[key] = {
        "last_signal":       signal_data.get('direction', 'NEUTRAL'),
        "last_signal_time":  int(time.time()),
        "last_signal_score": signal_data.get('score', 0),
        "last_price":        signal_data.get('price', 0),
        "cooldown_until":    int(time.time()) + SP_TIMEFRAMES.get(timeframe, {}).get('min_gap', 300),
        "daily_count":       daily + 1,
        "daily_date":        today,
    }
    _save(SP_STATE_PATH, state)

def can_send_signal(symbol: str, timeframe: str) -> bool:
    """
    Verifica si se puede enviar una señal (cooldown + límite diario).
    """
    state = get_sp_state(symbol, timeframe)
    if not state:
        return True

    now = int(time.time())
    today = datetime.now().strftime('%Y-%m-%d')

    # Verificar cooldown
    if now < state.get('cooldown_until', 0):
        return False

    # Verificar límite diario
    if state.get('daily_date') == today:
        max_day = SP_TIMEFRAMES.get(timeframe, {}).get('max_day', 24)
        if state.get('daily_count', 0) >= max_day:
            return False

    return True

def get_time_until_next(symbol: str, timeframe: str) -> int:
    """Segundos hasta que se pueda enviar la próxima señal (0 = ya se puede)."""
    state = get_sp_state(symbol, timeframe)
    if not state:
        return 0
    return max(0, state.get('cooldown_until', 0) - int(time.time()))

# ─── HISTORIAL ────────────────────────────────────────────────────────────────

def record_signal_history(symbol: str, timeframe: str, signal_data: dict) -> None:
    """Guarda la señal en el historial (máximo 500 por par)."""
    hist = _load(SP_HIST_PATH)
    key = f"{symbol}_{timeframe}"

    if key not in hist:
        hist[key] = []

    entry = {
        "ts":        int(time.time()),
        "datetime":  datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "direction": signal_data.get('direction', 'NEUTRAL'),
        "score":     round(signal_data.get('score', 0), 2),
        "strength":  signal_data.get('strength', 'WEAK'),
        "price":     signal_data.get('price', 0),
        "target1":   signal_data.get('target1', 0),
        "stop":      signal_data.get('stop', 0),
    }

    hist[key].insert(0, entry)
    # Limitar historial a 500 entradas por par
    hist[key] = hist[key][:500]
    _save(SP_HIST_PATH, hist)

def get_signal_history(symbol: str, timeframe: str, limit: int = 10) -> list:
    """Últimas N señales registradas para un par."""
    hist = _load(SP_HIST_PATH)
    key = f"{symbol}_{timeframe}"
    return hist.get(key, [])[:limit]

# ─── UTILIDADES ───────────────────────────────────────────────────────────────

# ─── QUICK-NOTIFY (señal inmediata al suscribirse) ────────────────────────────

def queue_quick_notify(user_id, symbol: str, timeframe: str) -> None:
    """
    Marca que el usuario quiere recibir la señal actual de symbol/tf
    en el próximo ciclo del loop (sin esperar cooldown).
    """
    data = _load(SP_QUICK_NOTIFY_PATH)
    key  = f"{symbol}_{timeframe}"
    if key not in data:
        data[key] = []
    uid = str(user_id)
    if uid not in data[key]:
        data[key].append(uid)
    _save(SP_QUICK_NOTIFY_PATH, data)


def pop_quick_notify(symbol: str, timeframe: str) -> list:
    """
    Devuelve y vacía la lista de usuarios que esperan señal inmediata
    para el par/TF indicado.
    """
    data = _load(SP_QUICK_NOTIFY_PATH)
    key  = f"{symbol}_{timeframe}"
    users = data.pop(key, [])
    if users:
        _save(SP_QUICK_NOTIFY_PATH, data)
    return users


def get_coin_info(key_or_symbol: str) -> dict | None:
    """Devuelve la info de una moneda por su key (BTC) o symbol (BTCUSDT)."""
    # Intentar por key primero
    info = SP_KEYS_MAP.get(key_or_symbol.upper())
    if info:
        return info
    # Intentar por symbol
    return SP_COINS_MAP.get(key_or_symbol.upper())

def estimate_time_to_candle_close(open_time_ms: int, interval: str) -> int:
    """
    Calcula segundos restantes hasta que cierra la vela actual.
    open_time_ms: timestamp de apertura de la vela en milisegundos.
    """
    interval_s = SP_TIMEFRAMES.get(interval, {}).get('interval_s', 300)
    now_ms = int(time.time() * 1000)
    elapsed_s = (now_ms - open_time_ms) / 1000
    remaining = interval_s - elapsed_s
    return max(0, int(remaining))

# ═══════════════════════════════════════════════════════════════════════════════
# OPERACIONES DE TRADING (SP TRADING)
# Sistema de seguimiento de operaciones abiertas con SL/TP
# ═══════════════════════════════════════════════════════════════════════════════

def open_trade(
    user_id: int,
    symbol: str,
    timeframe: str,
    direction: str,
    entry_price: float,
    stop_loss: float,
    tp1: float,
    tp2: float,
    tp3: float,
    tp1_pct: int = 50,
    tp2_pct: int = 30,
    tp3_pct: int = 20,
) -> str:
    """Abre una nueva operación de trading. Devuelve el trade_id."""
    import uuid
    trades = _load(SP_TRADES_PATH)
    uid = str(user_id)
    
    if uid not in trades:
        trades[uid] = []
    
    trade_id = str(uuid.uuid4())[:8]
    now = int(time.time())
    
    trade = {
        "trade_id": trade_id,
        "symbol": symbol,
        "timeframe": timeframe,
        "direction": direction,
        "entry_price": entry_price,
        "stop_loss": stop_loss,
        "tp1": tp1,
        "tp2": tp2,
        "tp3": tp3,
        "tp1_pct": tp1_pct,
        "tp2_pct": tp2_pct,
        "tp3_pct": tp3_pct,
        "opened_at": now,
        "opened_ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "status": "OPEN",
        "close_reason": None,
        "closed_at": None,
        "pnl_pct": 0,
        "current_price": entry_price,
        "tp_hit": None,
        "highest_price": entry_price,
        "lowest_price": entry_price,
    }
    
    trades[uid].append(trade)
    _save(SP_TRADES_PATH, trades)
    return trade_id


def get_user_trades(user_id: int, status: str = None) -> list:
    """Devuelve las operaciones del usuario. Si status es None, todas."""
    trades = _load(SP_TRADES_PATH)
    uid = str(user_id)
    if uid not in trades:
        return []
    if status is None:
        return trades[uid]
    return [t for t in trades[uid] if t.get("status") == status]


def get_open_trades(user_id: int) -> list:
    """Devuelve solo operaciones abiertas."""
    return get_user_trades(user_id, "OPEN")


def get_trade_by_id(user_id: int, trade_id: str) -> dict | None:
    """Devuelve una operación específica por su ID."""
    trades = get_user_trades(user_id)
    for t in trades:
        if t.get("trade_id") == trade_id:
            return t
    return None


def update_trade_price(user_id: int, trade_id: str, current_price: float) -> dict | None:
    """Actualiza el precio actual de una operación."""
    trades = _load(SP_TRADES_PATH)
    uid = str(user_id)
    
    if uid not in trades:
        return None
    
    for t in trades[uid]:
        if t.get("trade_id") == trade_id and t.get("status") == "OPEN":
            t["current_price"] = current_price
            if current_price > t.get("highest_price", 0):
                t["highest_price"] = current_price
            if current_price < t.get("lowest_price", float("inf")):
                t["lowest_price"] = current_price
            _save(SP_TRADES_PATH, trades)
            return t
    return None


def close_trade(
    user_id: int,
    trade_id: str,
    reason: str,
    pnl_pct: float = 0,
) -> dict | None:
    """Cierra una operación. reason: SL_HIT, TP_HIT, MANUAL, TP_RETRACE."""
    trades = _load(SP_TRADES_PATH)
    uid = str(user_id)
    now = int(time.time())
    
    if uid not in trades:
        return None
    
    for t in trades[uid]:
        if t.get("trade_id") == trade_id:
            t["status"] = "CLOSED"
            t["close_reason"] = reason
            t["closed_at"] = now
            t["closed_ts"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            t["pnl_pct"] = pnl_pct
            _save(SP_TRADES_PATH, trades)
            return t
    return None


def delete_trade(user_id: int, trade_id: str) -> bool:
    """Elimina una operación (solo si está cerrada)."""
    trades = _load(SP_TRADES_PATH)
    uid = str(user_id)
    if uid not in trades:
        return False
    trades[uid] = [t for t in trades[uid] if t.get("trade_id") != trade_id]
    _save(SP_TRADES_PATH, trades)
    return True


def check_trade_crosses(trade: dict, current_price: float) -> dict:
    """Verifica si el precio actual ha cruzado SL o algún TP."""
    direction = trade.get("direction", "BUY")
    sl = trade.get("stop_loss", 0)
    tp1 = trade.get("tp1", 0)
    tp2 = trade.get("tp2", 0)
    tp3 = trade.get("tp3", 0)
    entry = trade.get("entry_price", 0)
    
    result = {"sl_hit": False, "tp_hit": None, "retrace": False, "all_tp_hit": False}
    
    if direction in ("BUY", "BUY_STRONG"):
        if sl > 0 and current_price <= sl:
            result["sl_hit"] = True
        if tp3 > 0 and current_price >= tp3:
            result["tp_hit"] = "TP3"
            result["all_tp_hit"] = True
        elif tp2 > 0 and current_price >= tp2:
            result["tp_hit"] = "TP2"
        elif tp1 > 0 and current_price >= tp1:
            result["tp_hit"] = "TP1"
        if entry > 0 and current_price <= entry:
            result["retrace"] = True
    else:  # SELL or SELL_STRONG
        if sl > 0 and current_price >= sl:
            result["sl_hit"] = True
        if tp3 > 0 and current_price <= tp3:
            result["tp_hit"] = "TP3"
            result["all_tp_hit"] = True
        elif tp2 > 0 and current_price <= tp2:
            result["tp_hit"] = "TP2"
        elif tp1 > 0 and current_price <= tp1:
            result["tp_hit"] = "TP1"
        if entry > 0 and current_price >= entry:
            result["retrace"] = True
    
    return result


def get_all_open_trades() -> list:
    """Devuelve todas las operaciones abiertas de todos los usuarios."""
    trades = _load(SP_TRADES_PATH)
    result = []
    for uid, user_trades in trades.items():
        for t in user_trades:
            if t.get("status") == "OPEN":
                result.append((int(uid), t))
    return result


def count_user_open_trades(user_id: int) -> int:
    """Cuenta las operaciones abiertas del usuario."""
    return len(get_open_trades(user_id))


def get_trades_stats() -> dict:
    """Devuelve estadísticas de trades."""
    trades = _load(SP_TRADES_PATH)
    open_count = 0
    closed_count = 0

    for uid, user_trades in trades.items():
        for t in user_trades:
            if t.get('status') == 'OPEN':
                open_count += 1
            else:
                closed_count += 1

    return {
        'total_users': len(trades),
        'open_trades': open_count,
        'closed_trades': closed_count,
    }


def cleanup_closed_trades(days_threshold: int = TRADE_CLEANUP_DAYS) -> dict:
    """
    Elimina operaciones cerradas hace más de 'days_threshold' días.
    Devuelve stats: {deleted_count, remaining_count, users_affected}
    """
    trades = _load(SP_TRADES_PATH)

    cutoff_time = int(time.time()) - (days_threshold * 86400)
    deleted_count = 0
    users_affected = set()

    for uid in list(trades.keys()):
        original_count = len(trades[uid])
        trades[uid] = [t for t in trades[uid]
                      if t.get('status') != 'CLOSED'
                      or t.get('closed_at', 0) > cutoff_time]
        deleted = original_count - len(trades[uid])
        if deleted > 0:
            deleted_count += deleted
            users_affected.add(uid)

    if deleted_count > 0:
        for uid in list(trades.keys()):
            if not trades[uid]:
                del trades[uid]
        _save(SP_TRADES_PATH, trades)

    return {
        'deleted_count': deleted_count,
        'remaining_count': sum(len(t) for t in trades.values()),
        'users_affected': len(users_affected)
    }
