# core/btc_loop.py

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

def get_btc_klines(limit=1000): # <--- CAMBIO AQUÍ: 1000 es el máximo seguro
    """Obtiene velas de BTC/USDT de Binance (Max 1000 para estabilidad)."""
    endpoints = [
        "https://api.binance.us/api/v3/klines",
        "https://api.binance.com/api/v3/klines",
        "https://api1.binance.com/api/v3/klines"
    ]
    # Aseguramos que el limit no exceda 1000 para evitar error de API
    safe_limit = min(limit, 1000) 
    
    params = {"symbol": "BTCUSDT", "interval": "4h", "limit": safe_limit}
    
    for url in endpoints:
        try:
            r = requests.get(url, params=params, timeout=10)
            r.raise_for_status()
            data = r.json()
            
            # Comprobación mejorada
            if not isinstance(data, list) or len(data) < 200: # Necesitamos mínimo 200 para EMA200
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
        except Exception as e:
            print(f"Error en endpoint {url}: {e}")
            continue

    return None

def get_btc_4h_candle():
    """Obtiene la última vela cerrada de 4H de Binance."""
    # AUMENTADO A 10000: Necesitamos historial para que EMA200 y RSI se calculen bien
    df = get_btc_klines(limit=20000)
    
    # COMPROBACIÓN MEJORADA - Aseguramos que hay al menos 2 velas
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
    """Bucle principal de monitoreo BTC usando lógica Fibonacci unificada."""
    add_log_line("🦁 Iniciando Monitor BTC PRO (Modo Fibonacci)...")
    
    while True:
        try:
            # 1. Obtener datos (Limit 1000 es suficiente y seguro)
            # Usamos get_btc_klines directamente para tener el DF fresco
            df = get_btc_klines(limit=1000)
            
            if df is None or len(df) < 200:
                await asyncio.sleep(60)
                continue

            # Datos de tiempo
            last_closed_candle = df.iloc[-2]
            current_candle = df.iloc[-1]
            current_candle_time = int(last_closed_candle['open_time']) # Usamos open_time para identificar la vela
            current_price = float(current_candle['close'])

            # 2. Cargar estado y suscriptores
            state = load_btc_state()
            subs = get_btc_subscribers()
            
            if not subs:
                await asyncio.sleep(60)
                continue
            
            # 3. ANÁLISIS TÉCNICO CENTRALIZADO
            # Calculamos todo AQUÍ para que alertas y mensaje 'Ver' sean idénticos
            analyzer = BTCAdvancedAnalyzer(df)
            levels_fib = analyzer.get_support_resistance_dynamic() # Trae P, R1-R3, S1-S3 (Fibonacci)
            momentum_signal, emoji, (buy, sell), reasons = analyzer.get_momentum_signal()
            divergence = analyzer.detect_rsi_divergence(lookback=5)
            
            # Guardamos análisis en estado para que el comando /btcalerts lo use rápido
            state['analysis'] = {
                'momentum': momentum_signal,
                'rsi': analyzer.get_current_values().get('RSI', 50),
                'macd_hist': analyzer.get_current_values().get('MACD_HIST', 0),
                'divergence': divergence[0] if divergence else None
            }

            # 4. GESTIÓN DE NIVELES (Recálculo por Nueva Vela)
            last_saved_time = state.get('last_candle_time', 0)
            
            # Si detectamos nueva vela cerrada O si el estado está vacío
            if current_candle_time > last_saved_time or 'levels' not in state or not state['levels']:
                
                # Actualizamos niveles en el estado con los de Fibonacci calculados
                state['levels'] = levels_fib
                state['last_candle_time'] = current_candle_time
                state['alerted_levels'] = [] # Reseteamos alertas para la nueva sesión
                save_btc_state(state)
                
                add_log_line(f"🦁 Nuevos niveles Fib BTC. Pivot: ${levels_fib['P']:,.2f}")
                
                # Notificación de Recálculo (Opcional, mantiene tu formato)
                if _enviar_msg_func:
                    msg_recalc = (
                        "🔄 *Actualización de Niveles BTCUSDT (4H)*\n"
                        "—————————————————\n"
                        "📊 La vela ha cerrado. Niveles Fibonacci actualizados.\n\n"
                        f"⚖️ *Nuevo Pivot:* `${levels_fib['P']:,.0f}`\n"
                        f"💰 *Precio Actual:* `${current_price:,.0f}`\n\n"
                        "🔁 _Alertas listas para la nueva sesión._"
                    )
                    msg_recalc += get_random_ad_text()
                    kb = [[InlineKeyboardButton("📊 Ver Análisis PRO", callback_data="btc_switch_view|BINANCE")]]
                    await _enviar_msg_func(msg_recalc, subs, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)

            # 5. VERIFICACIÓN DE ALERTAS (Dentro de la vela actual)
            else:
                # Actualizamos precio actual en estado
                state['levels']['current_price'] = current_price
                save_btc_state(state)
                
                levels = state.get('levels', {})
                alerted = state.get('alerted_levels', [])
                threshold = 0.001 # 0.1% de filtro para evitar ruido
                
                trigger_level = None
                alert_data = {}

                # --- Lógica de Cruces (Usando los niveles Fibonacci cargados) ---
                
                # RUPTURAS ALCISTAS
                if current_price > levels['R3'] * (1 + threshold) and "R3" not in alerted:
                    trigger_level = "R3"
                    alert_data = {
                        'emoji': '🚀', 'titulo': 'Ruptura de BTC R3 - Extensión Fibonacci',
                        'descripcion': 'Precio en zona de extensión máxima. Posible agotamiento o "parada de tren".',
                        'icon_nivel': '🧗', 'icon_precio': '💰', 'icon_target': '🌌', 'icon_rec': '⚡',
                        'target_siguiente': levels['R3'] * 1.05,
                        'recomendacion': 'Zona de toma de ganancias. Precaución extrema.'
                    }
                
                elif current_price > levels['R2'] * (1 + threshold) and "R2" not in alerted:
                    trigger_level = "R2"
                    alert_data = {
                        'emoji': '🌊', 'titulo': 'BTC R2 Superado - Impulso Fuerte',
                        'descripcion': 'Ruptura de nivel clave Fibonacci (61.8%). Momentum sólido.',
                        'icon_nivel': '🔺', 'icon_precio': '💰', 'icon_target': '🎯', 'icon_rec': '✅',
                        'target_siguiente': levels['R3'],
                        'recomendacion': 'Buscar continuación hacia R3.'
                    }

                elif current_price > levels['R1'] * (1 + threshold) and "R1" not in alerted:
                    trigger_level = "R1"
                    alert_data = {
                        'emoji': '📈', 'titulo': 'Resistencia BTC R1 Superada',
                        'descripcion': 'El precio entra en zona alcista (38.2% Fib).',
                        'icon_nivel': '📍', 'icon_precio': '💹', 'icon_target': '🎯', 'icon_rec': '🔝',
                        'target_siguiente': levels['R2'],
                        'recomendacion': 'Mantener largos con stop en Pivot.'
                    }

                elif current_price > levels['P'] * (1 + threshold) and "P_UP" not in alerted:
                    trigger_level = "P_UP"                        
                    alert_data = {
                        'emoji': '⚖️', 'titulo': 'BTC Recupera el Pivot',
                        'descripcion': 'El precio cruza el equilibrio hacia arriba.',
                        'icon_nivel': '⚖️', 'icon_precio': '↗️', 'icon_target': '➡️', 'icon_rec': '👀',
                        'target_siguiente': levels['R1'],
                        'recomendacion': 'Sesgo intradía positivo.'
                    }

                # RUPTURAS BAJISTAS
                elif current_price < levels['S3'] * (1 - threshold) and "S3" not in alerted:
                    trigger_level = "S3"
                    alert_data = {
                        'emoji': '🕳️', 'titulo': 'Caída Extrema - BTC S3 Perforado',
                        'descripcion': 'Extensión bajista máxima alcanzada.',
                        'icon_nivel': '🧗', 'icon_precio': '💸', 'icon_target': '⬇️', 'icon_rec': '⚠️',
                        'target_siguiente': levels['S3'] * 0.95,
                        'recomendacion': 'Esperar rebote por sobreventa extrema.'
                    }

                elif current_price < levels['S2'] * (1 - threshold) and "S2" not in alerted:
                    trigger_level = "S2"
                    alert_data = {
                        'emoji': '📉', 'titulo': 'Soporte BTC S2 Perforado',
                        'descripcion': 'Pérdida del nivel clave Fibonacci (61.8%). Debilidad seria.',
                        'icon_nivel': '🔻', 'icon_precio': '💸', 'icon_target': '🔴', 'icon_rec': '🛑',
                        'target_siguiente': levels['S3'],
                        'recomendacion': 'No buscar compras todavía.'
                    }

                elif current_price < levels['S1'] * (1 - threshold) and "S1" not in alerted:
                    trigger_level = "S1"
                    alert_data = {
                        'emoji': '⚠️', 'titulo': 'BTC Pierde Soporte S1',
                        'descripcion': 'Entrada en zona bajista (38.2% Fib).',
                        'icon_nivel': '📍', 'icon_precio': '📉', 'icon_target': '🔽', 'icon_rec': '⚠️',
                        'target_siguiente': levels['S2'],
                        'recomendacion': 'Precaución con largos.'
                    }

                elif current_price < levels['P'] * (1 - threshold) and "P_DOWN" not in alerted:
                    trigger_level = "P_DOWN"
                    alert_data = {
                        'emoji': '⚖️', 'titulo': 'BTC Pierde el Pivot',
                        'descripcion': 'El precio cruza el equilibrio hacia abajo.',
                        'icon_nivel': '⚖️', 'icon_precio': '↘️', 'icon_target': '⬅️', 'icon_rec': '👁️',
                        'target_siguiente': levels['S1'],
                        'recomendacion': 'Sesgo intradía negativo.'
                    }

                # --- ENVIO DE ALERTA ---
                if trigger_level and _enviar_msg_func and alert_data:
                    # Preparamos el mensaje manteniendo tu formato exacto
                    lvl_key = trigger_level.replace('_UP', '').replace('_DOWN', '')
                    lvl_price = levels.get(lvl_key, levels['P'])
                    
                    msg = (
                        f"{alert_data['emoji']} *{alert_data['titulo']}*\n"
                        f"—————————————————\n"
                        f"📊 {alert_data['descripcion']}\n\n"
                    )
                    
                    # Añadimos Momentum del Analyzer
                    msg += (
                        f"*Momentum Actual:* {emoji} {momentum_signal}\n"
                        f"⚖️ _Score: {buy} Compra | {sell} Venta_\n"
                    )
                    if reasons:
                        if len(reasons) > 0: msg += f"✓ {reasons[0]}\n"
                        if len(reasons) > 1: msg += f"✓ {reasons[1]}\n"
                    msg += "\n"

                    # Añadimos Divergencia si existe
                    if divergence:
                        div_type, div_desc = divergence
                        div_emoji = "🐂" if div_type == "BULLISH" else "🐻"
                        msg += f"{div_emoji} *Divergencia {div_type}*\n💡 _{div_desc}_\n\n"

                    # Detalles numéricos
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
                    kb = [[InlineKeyboardButton("📊 Ver Análisis PRO", callback_data="btc_switch_view|BINANCE")]]
                    
                    await _enviar_msg_func(msg, subs, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)
                    
                    # Guardamos que ya alertamos este nivel
                    state['alerted_levels'].append(trigger_level)
                    save_btc_state(state)
                    add_log_line(f"🦁 Alerta BTC Enviada: {trigger_level}")

        except Exception as e:
            add_log_line(f"Error en loop BTC: {e}")
            import traceback
            traceback.print_exc() # Esto ayuda a ver errores en consola
        
        await asyncio.sleep(60)
