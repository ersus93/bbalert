# core/btc_loop.py

import asyncio
import requests
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Bot

from utils.file_manager import add_log_line
from utils.btc_manager import get_btc_subscribers, load_btc_state, save_btc_state
from utils.ads_manager import get_random_ad_text
from core.i18n import _

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

            # 1. Cargar estado anterior
            state = load_btc_state()
            subs = get_btc_subscribers()
            
            last_candle_time = state.get('last_candle_time', 0)
            current_candle_time = data['time']
            current_price = data['current_price']
            
            # --- CASO A: Nueva vela detectada (CIERRE DE VELA) ---
            if current_candle_time > last_candle_time:
                H, L, C = data['high'], data['low'], data['close']
                P = (H + L + C) / 3
                
                # Cálculo extendido hasta R3/S3
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
                
                # Guardamos estado y reseteamos alertas
                state['levels'] = new_levels
                state['last_candle_time'] = current_candle_time
                state['alerted_levels'] = [] 
                save_btc_state(state)
                
                add_log_line(f"🦁 Niveles recalculados (Nueva Vela 4H). Pivot: ${P:,.0f}")

                # --- NOTIFICACIÓN DE RECÁLCULO (Tu nueva solicitud) ---
                if subs and _enviar_msg_func:
                    msg_recalc = (
                        "🔄 *Actualización de Niveles (4H)*\n"
                        "—————————————————\n"
                        "La vela de 4 horas ha cerrado. El sistema ha *recalculado* los soportes y resistencias basándose en la volatilidad reciente.\n\n"
                        f"⚖️ *Nuevo Pivot:* ${P:,.2f}\n"
                        f"💰 *Precio Actual:* ${current_price:,.2f}\n\n"
                        "_Las alertas anteriores han sido reseteadas._"
                    )
                    msg_recalc += get_random_ad_text()
                    
                    kb_recalc = [[InlineKeyboardButton("📊 Ver Nuevos Niveles", callback_data="btcalerts_view")]]
                    await _enviar_msg_func(msg_recalc, subs, reply_markup=InlineKeyboardMarkup(kb_recalc))

            # --- CASO B: Misma vela (Monitoreo continuo) ---
            else:
                # Actualizamos precio actual en JSON para cuando consulten /btcalerts
                if 'levels' not in state: state['levels'] = {}
                state['levels']['current_price'] = current_price
                save_btc_state(state)

                # --- LÓGICA DE ALERTAS ---
                if subs:
                    levels = state.get('levels', {})
                    if not levels or 'R1' not in levels:
                        await asyncio.sleep(10)
                        continue

                    alerted = state.get('alerted_levels', [])
                    threshold = 0.001 # 0.1% tolerancia ruido

                    trigger_level = None
                    next_level = None
                    msg_emoji = ""
                    msg_title = ""
                    msg_body = ""

                    # --- RESISTENCIAS (Alcista) ---
                    if current_price > levels['R3'] * (1 + threshold) and "R3" not in alerted:
                        trigger_level = "R3"
                        next_level = "Discovery"
                        msg_emoji = "🚀"
                        msg_title = "Máxima Volatilidad Alcista"
                        msg_body = "El precio ha entrado en zona de extensión extrema, superando la resistencia R3."
                    
                    elif current_price > levels['R2'] * (1 + threshold) and "R2" not in alerted:
                        trigger_level = "R2"
                        next_level = "R3"
                        msg_emoji = "🌊"
                        msg_title = "Impulso Alcista Fuerte"
                        msg_body = "Ruptura confirmada del segundo nivel de resistencia (R2). Presión de compra significativa."

                    elif current_price > levels['R1'] * (1 + threshold) and "R1" not in alerted:
                        trigger_level = "R1"
                        next_level = "R2"
                        msg_emoji = "📈"
                        msg_title = "Resistencia Superada"
                        msg_body = "BTC ha logrado perforar la primera resistencia (R1). El mercado busca consolidar niveles superiores."

                    elif current_price > levels['P'] * (1 + threshold) and "P_UP" not in alerted:
                        trigger_level = "P_UP"
                        next_level = "R1"
                        msg_emoji = "⚖️"
                        msg_title = "Recuperación de Pivot"
                        msg_body = "El precio se sitúa por encima del Punto de Equilibrio (Pivot). Sesgo intradía ligeramente positivo."

                    # --- SOPORTES (Bajista) ---
                    elif current_price < levels['S3'] * (1 - threshold) and "S3" not in alerted:
                        trigger_level = "S3"
                        next_level = "Discovery"
                        msg_emoji = "🕳️"
                        msg_title = "Caída Extrema"
                        msg_body = "Soporte crítico S3 perforado. Condiciones de sobreventa o volatilidad bajista muy alta."

                    elif current_price < levels['S2'] * (1 - threshold) and "S2" not in alerted:
                        trigger_level = "S2"
                        next_level = "S3"
                        msg_emoji = "📉"
                        msg_title = "Presión de Venta"
                        msg_body = "El precio pierde el nivel S2. La estructura técnica muestra debilidad considerable."

                    elif current_price < levels['S1'] * (1 - threshold) and "S1" not in alerted:
                        trigger_level = "S1"
                        next_level = "S2"
                        msg_emoji = "⚠️"
                        msg_title = "Testeo de Soporte"
                        msg_body = "BTC ha perdido el primer nivel de soporte (S1). Atención a posible continuidad bajista."

                    elif current_price < levels['P'] * (1 - threshold) and "P_DOWN" not in alerted:
                        trigger_level = "P_DOWN"
                        next_level = "S1"
                        msg_emoji = "⚖️"
                        msg_title = "Pivot Perdido"
                        msg_body = "El precio cae por debajo del Punto de Equilibrio (Pivot). El sesgo intradía se torna negativo."

                    # --- ENVIAR ALERTA ---
                    if trigger_level and _enviar_msg_func:
                        # Preparar datos visuales
                        lvl_key = trigger_level.replace('_UP','').replace('_DOWN','')
                        lvl_price = levels['P'] if 'P' in trigger_level else levels.get(lvl_key, 0)
                        
                        target_price_str = f"${levels[next_level]:,.2f}" if next_level in levels else "---"

                        msg = (
                            f"{msg_emoji} *{msg_title}*\n"
                            f"—————————————————\n"
                            f"{msg_body}\n\n"
                            f"🏷️ *Nivel:* {lvl_key} (${lvl_price:,.2f})\n"
                            f"🎯 *Siguiente Obj:* {next_level} ({target_price_str})\n"
                            f"💰 *Precio:* ${current_price:,.2f}\n"
                            f"⏳ *Vela:* 4H"
                        )
                        msg += get_random_ad_text()
                        
                        # IMPORTANTE: Botón para ver niveles (enviará mensaje NUEVO gracias al cambio en handlers)
                        kb = [[InlineKeyboardButton("📊 Ver Tabla de Niveles", callback_data="btcalerts_view")]]
                        
                        await _enviar_msg_func(msg, subs, reply_markup=InlineKeyboardMarkup(kb))
                        
                        # Registrar
                        state['alerted_levels'].append(trigger_level)
                        save_btc_state(state)
                        add_log_line(f"🦁 Alerta BTC enviada: {trigger_level}")

        except Exception as e:
            add_log_line(f"Error en loop BTC: {e}")
        
        await asyncio.sleep(60)