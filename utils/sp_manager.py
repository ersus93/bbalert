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