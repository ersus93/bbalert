# core/btc_loop.py

import asyncio
import requests
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Bot

from utils.file_manager import add_log_line
from utils.btc_manager import get_btc_subscribers, load_btc_state, save_btc_state
from utils.ads_manager import get_random_ad_text

# Variable para la función de envío (inyectada)
_enviar_msg_func = None

def set_btc_sender(func):
    global _enviar_msg_func
    _enviar_msg_func = func

def get_btc_4h_candle():
    """Obtiene la última vela CERRADA de 4H de Binance con manejo de errores robusto."""
    endpoints = [
        "https://api.binance.us/api/v3/klines",
        "https://api.binance.com/api/v3/klines",
        "https://api1.binance.com/api/v3/klines"
    ]
    params = {"symbol": "BTCUSDT", "interval": "4h", "limit": 2}
    
    for url in endpoints:
        try:
            r = requests.get(url, params=params, timeout=10)
            r.raise_for_status()
            data = r.json()
            
            if not isinstance(data, list) or len(data) < 2:
                continue 

            # data[-2] = vela cerrada, data[-1] = vela actual (en vivo)
            closed_candle = data[-2]
            current_candle = data[-1]
            
            return {
                "time": closed_candle[0], # Timestamp de inicio de la vela cerrada
                "high": float(closed_candle[2]),
                "low": float(closed_candle[3]),
                "close": float(closed_candle[4]),
                "current_price": float(current_candle[4])
            }
        except Exception:
            continue

    add_log_line("❌ Error crítico: No se pudo conectar a Binance (BTC Loop).")
    return None

async def btc_monitor_loop(bot: Bot):
    """Bucle principal de monitoreo BTC con persistencia de datos."""
    add_log_line("🦁 Iniciando Monitor BTC Pro (Persistencia JSON Activada)...")
    
    while True:
        try:
            data = get_btc_4h_candle()
            if not data:
                await asyncio.sleep(60)
                continue

            # 1. Cargar estado anterior desde JSON
            state = load_btc_state()
            
            last_candle_time = state.get('last_candle_time', 0)
            current_candle_time = data['time']
            current_price = data['current_price']
            
            # --- LÓGICA DE REINICIO vs NUEVA VELA ---
            
            # CASO A: Nueva vela detectada (el tiempo de Binance es mayor al guardado)
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
                
                # Guardamos nuevos niveles y RESETEAMOS las alertas enviadas
                state['levels'] = new_levels
                state['last_candle_time'] = current_candle_time
                state['alerted_levels'] = [] 
                
                save_btc_state(state)
                add_log_line(f"🦁 Nuevos niveles 4H calculados. Pivot: ${P:.2f}")

            # CASO B: Misma vela (Reinicio del bot o chequeo normal)
            else:
                # Solo actualizamos el precio actual en el JSON para el comando /btcalerts
                if 'levels' not in state: state['levels'] = {} # Seguridad
                state['levels']['current_price'] = current_price
                save_btc_state(state)
                # NOTA: No borramos 'alerted_levels', así recordamos qué alertas ya se enviaron

            # 3. Lógica de Cruce
            subs = get_btc_subscribers()
            if subs:
                levels = state.get('levels', {})
                # Si por alguna razón no hay niveles (primer arranque sin historial), saltamos
                if not levels or 'R1' not in levels:
                    await asyncio.sleep(10)
                    continue

                alerted = state.get('alerted_levels', [])
                alert_data = None
                threshold = 0.001 

                # Verificamos cruces SOLO si no están en la lista 'alerted'
                
                # R1
                if "R1" not in alerted and current_price > levels['R1'] * (1 + threshold):
                    alert_data = ("R1", levels['R1'], "R2", "🚀 BREAKOUT CONFIRMADO")
                # R2
                elif "R2" not in alerted and current_price > levels['R2'] * (1 + threshold):
                    alert_data = ("R2", levels['R2'], "R3", "🚀 MOON MISSION")
                # S1
                elif "S1" not in alerted and current_price < levels['S1'] * (1 - threshold):
                    alert_data = ("S1", levels['S1'], "S2", "🛑 SOPORTE ROTO")
                # S2
                elif "S2" not in alerted and current_price < levels['S2'] * (1 - threshold):
                    alert_data = ("S2", levels['S2'], "S3", "🩸 CAÍDA LIBRE")
                # Pivot
                elif "P" not in alerted:
                    if current_price > levels['P'] * (1+threshold) and "P_UP" not in alerted:
                        alert_data = ("P", levels['P'], "R1", "⚖️ RECUPERANDO PIVOT")
                        state['alerted_levels'].append("P_UP") 
                    elif current_price < levels['P'] * (1-threshold) and "P_DOWN" not in alerted:
                        alert_data = ("P", levels['P'], "S1", "⚖️ PERDIENDO PIVOT")
                        state['alerted_levels'].append("P_DOWN")

                # 4. Enviar Alerta
                if alert_data:
                    lvl_name, lvl_price, next_target, title = alert_data
                    target_price = levels[next_target]
                    
                    msg = (
                        f"{title}\n"
                        f"—————————————————\n"
                        f"BTC rompió con fuerza el nivel *{lvl_name} (${lvl_price:,.2f})*.\n\n"
                        f"👀 *Próximo Objetivo:* {next_target} (${target_price:,.2f})\n"
                        f"💰 *Precio Actual:* ${current_price:,.2f}\n"
                        f"⏳ *Vela:* 4H\n•\n"                        
                        f"💱 _Puedes usar el comando /ta para análisis técnico avanzado._"
                    )
                    
                    msg += get_random_ad_text()
                    kb = [[InlineKeyboardButton("📊 Ver Niveles", callback_data="btcalerts_view")]]
                    
                    if _enviar_msg_func:
                        await _enviar_msg_func(msg, subs, reply_markup=InlineKeyboardMarkup(kb))
                    
                    # IMPORTANTE: Guardar inmediatamente que ya alertamos este nivel
                    state['alerted_levels'].append(lvl_name)
                    save_btc_state(state)
                    add_log_line(f"🦁 Alerta BTC enviada y registrada: {lvl_name}")

        except Exception as e:
            add_log_line(f"Error en loop BTC: {e}")
        
        await asyncio.sleep(60)