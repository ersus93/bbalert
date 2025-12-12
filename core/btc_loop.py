import asyncio
import requests
import pandas as pd
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.constants import ParseMode

from utils.file_manager import add_log_line
from utils.btc_manager import get_btc_subscribers, load_btc_state, save_btc_state
from utils.ads_manager import get_random_ad_text
from core.i18n import _
from core.btc_advanced_analysis import BTCAdvancedAnalyzer

# Variable para la función de envío (inyectada)
_enviar_msg_func = None

def set_btc_sender(func):
    global _enviar_msg_func
    _enviar_msg_func = func

def get_btc_klines(limit=100):
    """Obtiene velas de BTC/USDT de Binance."""
    endpoints = [
        "https://api.binance.com/api/v3/klines",
        "https://api.binance.us/api/v3/klines",
        "https://api1.binance.com/api/v3/klines"
    ]
    params = {"symbol": "BTCUSDT", "interval": "4h", "limit": limit}
    
    for url in endpoints:
        try:
            r = requests.get(url, params=params, timeout=10)
            r.raise_for_status()
            data = r.json()
            
            if not isinstance(data, list) or len(data) < 2:
                continue
            
            # Convertir a DataFrame
            df = pd.DataFrame(data, columns=[
                "open_time", "open", "high", "low", "close", "volume",
                "close_time", "quote_asset_volume", "trades",
                "taker_base", "taker_quote", "ignore"
            ])
            
            # Convertir a números
            for col in ["open", "high", "low", "close", "volume"]:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            return df
        except Exception:
            continue
    
    return None

def get_btc_4h_candle():
    """Obtiene la última vela cerrada de 4H de Binance."""
    df = get_btc_klines(limit=2)
    
    if df is None or len(df) < 2:
        return None
    
    closed_candle = df.iloc[-2]
    current_candle = df.iloc[-1]
    
    return {
        "time": int(closed_candle['open_time']),
        "high": float(closed_candle['high']),
        "low": float(closed_candle['low']),
        "close": float(closed_candle['close']),
        "current_price": float(current_candle['close']),
        "df": df
    }

async def btc_monitor_loop(bot: Bot):
    """Bucle principal de monitoreo BTC con análisis avanzado."""
    add_log_line("🦁 Iniciando Monitor BTC PRO (Análisis Avanzado Activado)...")
    
    while True:
        try:
            data = get_btc_4h_candle()
            if not data:
                await asyncio.sleep(60)
                continue

            state = load_btc_state()
            subs = get_btc_subscribers()
            
            if not subs:
                await asyncio.sleep(60)
                continue
            
            last_candle_time = state.get('last_candle_time', 0)
            current_candle_time = data['time']
            current_price = data['current_price']
            df = data['df']
            
            # --- CASO A: Nueva vela detectada ---
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
                save_btc_state(state)
                
                add_log_line(f"🦁 Nuevos niveles BTC. Pivot: ${P:,.2f}")
                
                if _enviar_msg_func:
                    msg_recalc = (
                        "🔄 *Actualización de Niveles BTCUSDT (4H)*\n"
                        "—————————————————\n"
                        "📊 La vela ha cerrado. Niveles recalculados.\n\n"
                        f"⚖️ *Nuevo Pivot:* `${P:,.0f}`\n"
                        f"💰 *Precio Actual:* `${current_price:,.0f}`\n\n"
                        "🔁 _Alertas reseteadas para nueva sesión._"
                    )
                    msg_recalc += get_random_ad_text()
                    
                    kb = [[InlineKeyboardButton("📊 Ver Análisis PRO", callback_data="btcalerts_view")]]
                    await _enviar_msg_func(msg_recalc, subs, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)

            # --- CASO B: Misma vela (Monitoreo + Alertas) ---
            else:
                if 'levels' not in state:
                    state['levels'] = {}
                state['levels']['current_price'] = current_price
                save_btc_state(state)

                # --- ANÁLISIS TÉCNICO AVANZADO ---
                analyzer = None
                momentum_signal = "NEUTRAL"
                divergence = None
                
                try:
                    analyzer = BTCAdvancedAnalyzer(df)
                    curr_values = analyzer.get_current_values()
                    momentum_signal, emoji, score, reasons = analyzer.get_momentum_signal()
                    support_res = analyzer.get_support_resistance_dynamic()
                    divergence = analyzer.detect_rsi_divergence(lookback=5)
                    
                    state['analysis'] = {
                        'momentum': momentum_signal,
                        'rsi': curr_values['rsi'],
                        'macd_hist': curr_values['macd_hist'],
                        'divergence': divergence[0] if divergence else None
                    }
                    save_btc_state(state)
                    
                except Exception as e:
                    print(f"Error en análisis: {e}")

                if subs:
                    levels = state.get('levels', {})
                    if not levels or 'R1' not in levels:
                        await asyncio.sleep(10)
                        continue

                    alerted = state.get('alerted_levels', [])
                    threshold = 0.001

                    trigger_level = None
                    alert_data = {}

                    # --- RESISTENCIAS (Alcista) ---
                    if current_price > levels['R3'] * (1 + threshold) and "R3" not in alerted:
                        trigger_level = "R3"
                        alert_data = {
                            'emoji': '🚀',
                            'titulo': 'Ruptura de R3 - Volatilidad Extrema Alcista',
                            'descripcion': 'El precio ha perforado R3, máxima volatilidad alcista alcanzada.',
                            'icon_nivel': '🧗',
                            'icon_precio': '💰',
                            'icon_target': '🎯',
                            'icon_rec': '⚡',
                            'target_siguiente': levels.get('R3', 0) * 1.05,
                            'recomendacion': 'Zona de máximo riesgo. Asegura ganancias.'
                        }
                    
                    elif current_price > levels['R2'] * (1 + threshold) and "R2" not in alerted:
                        trigger_level = "R2"
                        momentum = analyzer.get_momentum_signal()[0] if analyzer else "NEUTRAL"
                        alert_data = {
                            'emoji': '🌊',
                            'titulo': 'R2 Perforado - Impulso Alcista Fuerte',
                            'descripcion': f'Ruptura de R2 confirmada. Momentum fuerte detectado.',
                            'icon_nivel': '🔺',
                            'icon_precio': '💰',
                            'icon_target': '🎯',
                            'icon_rec': '✅',
                            'target_siguiente': levels.get('R3', 0),
                            'recomendacion': f'Confirma fortaleza. Target: R3'
                        }

                    elif current_price > levels['R1'] * (1 + threshold) and "R1" not in alerted:
                        trigger_level = "R1"
                        alert_data = {
                            'emoji': '📈',
                            'titulo': 'Resistencia R1 Superada',
                            'descripcion': 'Primera resistencia perforada. Sesgo fuertemente alcista.',
                            'icon_nivel': '📍',
                            'icon_precio': '💹',
                            'icon_target': '🎯',
                            'icon_rec': '🔝',
                            'target_siguiente': levels.get('R2', 0),
                            'recomendacion': f'Consolidación en zona positiva'
                        }

                    elif current_price > levels['P'] * (1 + threshold) and "P_UP" not in alerted:
                        trigger_level = "P_UP"
                        rsi = analyzer.get_current_values()['rsi'] if analyzer else 50
                        alert_data = {
                            'emoji': '⚖️',
                            'titulo': 'Pivot Recuperado',
                            'descripcion': f'Precio por encima del Pivot. RSI: {rsi:.1f}',
                            'icon_nivel': '⚖️',
                            'icon_precio': '↗️',
                            'icon_target': '➡️',
                            'icon_rec': '👀',
                            'target_siguiente': levels.get('R1', 0),
                            'recomendacion': f'Sesgo positivo intradía'
                        }

                    # --- SOPORTES (Bajista) ---
                    elif current_price < levels['S3'] * (1 - threshold) and "S3" not in alerted:
                        trigger_level = "S3"
                        alert_data = {
                            'emoji': '🕳️',
                            'titulo': 'Caída Extrema - S3 Perforado',
                            'descripcion': 'Máximo nivel de volatilidad bajista alcanzado.',
                            'icon_nivel': '🧗',
                            'icon_precio': '💸',
                            'icon_target': '⬇️',
                            'icon_rec': '⚠️',
                            'target_siguiente': levels.get('S3', 0) * 0.95,
                            'recomendacion': 'Volatilidad extrema. Posible pánico.'
                        }

                    elif current_price < levels['S2'] * (1 - threshold) and "S2" not in alerted:
                        trigger_level = "S2"
                        alert_data = {
                            'emoji': '📉',
                            'titulo': 'Presión de Venta - S2 Perforado',
                            'descripcion': 'Segundo nivel de soporte roto. Estructura deteriorada.',
                            'icon_nivel': '🔻',
                            'icon_precio': '💸',
                            'icon_target': '🔴',
                            'icon_rec': '🛑',
                            'target_siguiente': levels.get('S3', 0),
                            'recomendacion': f'Zona crítica de riesgo'
                        }

                    elif current_price < levels['S1'] * (1 - threshold) and "S1" not in alerted:
                        trigger_level = "S1"
                        alert_data = {
                            'emoji': '⚠️',
                            'titulo': 'Soporte S1 Testado',
                            'descripcion': 'Primer soporte roto. Sesgo fuertemente bajista.',
                            'icon_nivel': '📍',
                            'icon_precio': '📉',
                            'icon_target': '🔽',
                            'icon_rec': '⚠️',
                            'target_siguiente': levels.get('S2', 0),
                            'recomendacion': f'Debilidad confirmada'
                        }

                    elif current_price < levels['P'] * (1 - threshold) and "P_DOWN" not in alerted:
                        trigger_level = "P_DOWN"
                        rsi = analyzer.get_current_values()['rsi'] if analyzer else 50
                        alert_data = {
                            'emoji': '⚖️',
                            'titulo': 'Pivot Perdido',
                            'descripcion': f'Precio por debajo del Pivot. RSI: {rsi:.1f}',
                            'icon_nivel': '⚖️',
                            'icon_precio': '↘️',
                            'icon_target': '⬅️',
                            'icon_rec': '👁️',
                            'target_siguiente': levels.get('S1', 0),
                            'recomendacion': 'Sesgo negativo intradía'
                        }

                    # --- ENVIAR ALERTA CON ANÁLISIS Y EMOJIS ---
                    if trigger_level and _enviar_msg_func and alert_data:
                        lvl_key = trigger_level.replace('_UP', '').replace('_DOWN', '')
                        lvl_price = levels['P'] if 'P' in trigger_level else levels.get(lvl_key, 0)
                        
                        msg = (
                            f"{alert_data['emoji']} *{alert_data['titulo']}*\n"
                            f"—————————————————\n"
                            f"📊 {alert_data['descripcion']}\n\n"
                        )
                        
                        # Análisis técnico con emojis
                        if analyzer:
                            signal, sig_emoji, score, reasons = analyzer.get_momentum_signal()
                            msg += (
                                f"*Momentum Actual:* {sig_emoji} {signal}\n"
                                f"📊 _Score: {score}/10_\n"
                                f"✓ {reasons[0]}\n"
                                f"✓ {reasons[1]}\n\n"
                            )
                        
                        # Divergencia con emojis
                        if divergence:
                            div_type, div_desc = divergence
                            div_emoji = "🐂" if div_type == "BULLISH" else "🐻"
                            msg += (
                                f"{div_emoji} *Divergencia {div_type}*\n"
                                f"💡 _{div_desc}_\n\n"
                            )
                        
                        # Datos de nivel con emojis
                        msg += (
                            f"*Detalles del Cruce:*\n"
                            f"{alert_data['icon_nivel']} Nivel: `{lvl_key}` "
                            f"(${lvl_price:,.0f})\n"
                            f"{alert_data['icon_precio']} Precio: `${current_price:,.0f}`\n"
                            f"{alert_data['icon_target']} Objetivo: "
                            f"`${alert_data['target_siguiente']:,.0f}`\n\n"
                            f"{alert_data['icon_rec']} *Recomendación:*\n"
                            f"_{alert_data['recomendacion']}_\n\n"
                            f"⏳ *Marco Temporal:* 4H"
                        )
                        
                        msg += get_random_ad_text()
                        
                        kb = [[InlineKeyboardButton("📊 Ver Análisis Completo", callback_data="btcalerts_view")]]
                        
                        await _enviar_msg_func(msg, subs, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)
                        
                        state['alerted_levels'].append(trigger_level)
                        save_btc_state(state)
                        add_log_line(f"🦁 Alerta BTC: {trigger_level} ({momentum_signal})")

        except Exception as e:
            add_log_line(f"Error en loop BTC: {e}")
        
        await asyncio.sleep(60)
