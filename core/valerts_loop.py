# core/valerts_loop.py

import asyncio
import requests
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Bot

from utils.file_manager import add_log_line
from utils.valerts_manager import (
    get_active_symbols, 
    get_valerts_subscribers, 
    get_symbol_state, 
    update_symbol_state
)
from utils.ads_manager import get_random_ad_text

# Variable para función de envío inyectada
_enviar_msg_func = None

def set_valerts_sender(func):
    global _enviar_msg_func
    _enviar_msg_func = func

def get_candle_data(symbol):
    """Obtiene vela 4H para un símbolo específico."""
    endpoints = [
        "https://api.binance.us/api/v3/klines",
        "https://api.binance.com/api/v3/klines"
    ]
    params = {"symbol": symbol, "interval": "4h", "limit": 2}
    
    for url in endpoints:
        try:
            r = requests.get(url, params=params, timeout=5)
            if r.status_code != 200: continue
            data = r.json()
            if not isinstance(data, list) or len(data) < 2: continue

            closed = data[-2]
            current = data[-1]
            
            return {
                "time": closed[0],
                "high": float(closed[2]),
                "low": float(closed[3]),
                "close": float(closed[4]),
                "current_price": float(current[4])
            }
        except:
            continue
    return None

async def valerts_monitor_loop(bot: Bot):
    """Bucle que revisa TODAS las monedas activas."""
    add_log_line("🦁 Iniciando Monitor Multi-Moneda (Valerts)...")
    
    while True:
        try:
            # 1. Obtener qué monedas le interesan a la gente
            active_symbols = get_active_symbols()
            
            # Si no hay nadie suscrito a nada, esperamos y seguimos
            if not active_symbols:
                await asyncio.sleep(60)
                continue

            # 2. Iterar sobre cada moneda
            for symbol in active_symbols:
                await process_symbol(symbol)
                await asyncio.sleep(1) # Pequeña pausa para no saturar API

        except Exception as e:
            add_log_line(f"Error en loop Valerts General: {e}")
        
        # Espera antes de la siguiente ronda de revisiones
        await asyncio.sleep(60)

async def process_symbol(symbol):
    """Procesa lógica de niveles para UN solo símbolo."""
    try:
        data = get_candle_data(symbol)
        if not data: return

        # Cargar estado Específico de este símbolo
        state = get_symbol_state(symbol)
        subs = get_valerts_subscribers(symbol) # Solo usuarios de esta moneda

        last_candle_time = state.get('last_candle_time', 0)
        current_candle_time = data['time']
        current_price = data['current_price']
        
        # --- CASO A: Nueva Vela (Recálculo) ---
        if current_candle_time > last_candle_time:
            H, L, C = data['high'], data['low'], data['close']
            P = (H + L + C) / 3
            
            new_levels = {
                "R3": P + 2 * (H - L),
                "R2": P + (H - L),
                "R1": (2 * P) - L,
                "P": P,
                "S1": (2 * P) - H,
                "S2": P - (H - L),
                "S3": P - 2 * (H - L),
                "current_price": current_price
            }
            
            state['levels'] = new_levels
            state['last_candle_time'] = current_candle_time
            state['alerted_levels'] = []
            update_symbol_state(symbol, state)
            
            # Notificación de recálculo
            if subs and _enviar_msg_func:
                msg = (
                    f"🔄 *Nuevos Niveles {symbol} (4H)*\n"
                    "—————————————————\n"
                    f"Vela cerrada. Niveles actualizados.\n"
                    f"⚖️ *Pivot:* ${P:,.4f}\n"
                    f"💰 *Precio:* ${current_price:,.4f}"
                )
                kb = [[InlineKeyboardButton("📊 Ver Niveles", callback_data=f"valerts_view|{symbol}")]]
                await _enviar_msg_func(msg, subs, reply_markup=InlineKeyboardMarkup(kb))

        # --- CASO B: Monitoreo Continuo ---
        else:
            if 'levels' not in state: state['levels'] = {}
            state['levels']['current_price'] = current_price
            update_symbol_state(symbol, state) # Guardamos precio actual

            if subs:
                levels = state.get('levels', {})
                if not levels or 'R1' not in levels: return

                alerted = state.get('alerted_levels', [])
                threshold = 0.001 

                trigger = None
                nxt = None
                emoji = ""
                title = ""

                # Lógica simplificada de triggers (reutilizando la de BTC)
                # RESISTENCIAS
                if current_price > levels['R3'] * (1 + threshold) and "R3" not in alerted:
                    trigger, nxt, emoji, title = "R3", "Discovery", "🚀", "R3 Roto"
                elif current_price > levels['R2'] * (1 + threshold) and "R2" not in alerted:
                    trigger, nxt, emoji, title = "R2", "R3", "🌊", "Fuerza Alcista"
                elif current_price > levels['R1'] * (1 + threshold) and "R1" not in alerted:
                    trigger, nxt, emoji, title = "R1", "R2", "📈", "Resistencia R1"
                
                # SOPORTES
                elif current_price < levels['S3'] * (1 - threshold) and "S3" not in alerted:
                    trigger, nxt, emoji, title = "S3", "Discovery", "🕳️", "S3 Roto"
                elif current_price < levels['S2'] * (1 - threshold) and "S2" not in alerted:
                    trigger, nxt, emoji, title = "S2", "S3", "📉", "Debilidad S2"
                elif current_price < levels['S1'] * (1 - threshold) and "S1" not in alerted:
                    trigger, nxt, emoji, title = "S1", "S2", "⚠️", "Soporte S1"

                if trigger and _enviar_msg_func:
                    lvl_price = levels.get(trigger, 0)
                    msg = (
                        f"{emoji} *{title}: {symbol}*\n"
                        f"—————————————————\n"
                        f"El precio ha cruzado el nivel clave.\n\n"
                        f"🏷️ *Nivel:* {trigger} (${lvl_price:,.4f})\n"
                        f"💰 *Precio:* ${current_price:,.4f}\n"
                    )
                    msg += get_random_ad_text()
                    kb = [[InlineKeyboardButton(f"📊 Ver {symbol}", callback_data=f"valerts_view|{symbol}")]]
                    
                    await _enviar_msg_func(msg, subs, reply_markup=InlineKeyboardMarkup(kb))
                    
                    state['alerted_levels'].append(trigger)
                    update_symbol_state(symbol, state)
                    add_log_line(f"🦁 Alerta {symbol} enviada: {trigger}")

    except Exception as e:
        add_log_line(f"Error procesando {symbol}: {e}")