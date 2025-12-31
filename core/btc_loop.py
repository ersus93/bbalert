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

def get_btc_klines(interval="1d", limit=1000): 
    """
    Obtiene velas de BTC/USDT con intervalo dinámico.
    CORREGIDO: Mantiene 'open_time' (int) y crea 'time' (datetime).
    """
    endpoints = [
        "https://api.binance.us/api/v3/klines",
        "https://api.binance.com/api/v3/klines",
        "https://api1.binance.com/api/v3/klines"
    ]
    
    try:
        safe_limit = int(limit)
    except:
        safe_limit = 1000

    params = {"symbol": "BTCUSDT", "interval": interval, "limit": safe_limit}
    
    for url in endpoints:
        try:
            r = requests.get(url, params=params, timeout=5)
            if r.status_code != 200:
                continue
            
            data = r.json()
            if not data or not isinstance(data, list):
                continue
                
            # 1. DEFINICIÓN DE COLUMNAS (Usamos nombres estándar de Binance)
            # Antes tenías 'time' aquí, ahora ponemos 'open_time' para evitar el KeyError
            df = pd.DataFrame(data, columns=[
                'open_time', 'open', 'high', 'low', 'close', 'volume', 
                'close_time', 'quote_asset_volume', 'number_of_trades', 
                'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
            ])
            
            # 2. CONVERSIÓN DE TIPOS
            df['open_time'] = df['open_time'].astype(int) # Mantenemos el int original
            df['close'] = df['close'].astype(float)
            df['high'] = df['high'].astype(float)
            df['low'] = df['low'].astype(float)
            df['open'] = df['open'].astype(float)
            df['volume'] = df['volume'].astype(float)
            
            # 3. CREAR COLUMNA 'time' (DATETIME)
            # Necesaria para el BTCAdvancedAnalyzer y para gráficos
            df['time'] = pd.to_datetime(df['open_time'], unit='ms')
            
            return df
            
        except Exception as e:
            print(f"⚠️ Error conectando con {url}: {e}")
            continue

    print("❌ Error crítico: No se pudo obtener datos de ningún endpoint de Binance.")
    return None

def get_btc_candle_data(interval="1d"):
    """
    Obtiene la última vela cerrada del intervalo especificado.
    """
    df = get_btc_klines(interval=interval, limit=1000)
    
    if df is None or len(df) < 2:
        return None

    # Obtenemos las velas
    closed_candle = df.iloc[-2]
    current_candle = df.iloc[-1]

    # CORREGIDO: Ahora 'open_time' existe en el DataFrame, así que esto no fallará
    return {
        "time": int(closed_candle['open_time']), 
        "high": float(closed_candle['high']),
        "low": float(closed_candle['low']),
        "close": float(closed_candle['close']),
        "current_price": float(current_candle['close']),
        "df": df
    }

async def btc_monitor_loop(bot: Bot):
    """Bucle principal Multi-Timeframe (4h, 1d, 1w)."""
    add_log_line("🦁 Iniciando Monitor BTC PRO (Multi-Timeframe)...")
    
    # Definimos las temporalidades a monitorear
    TIMEFRAMES = ["1h", "2h", "4h", "8h", "12h", "1d", "1w"]
    
    while True:
        try:
            # Cargamos estado GLOBAL (contiene todas las temporalidades)
            global_state = load_btc_state()
            state_changed = False

            # --- ITERAMOS POR CADA TEMPORALIDAD ---
            for interval in TIMEFRAMES:
                
                # 1. Obtener suscriptores de ESTE intervalo
                subs = get_btc_subscribers(interval)
                if not subs:
                    continue # Si nadie sigue 1W, saltamos análisis para ahorrar recursos

                # 2. Obtener datos
                df = get_btc_klines(interval=interval, limit=1000)
                if df is None or len(df) < 200:
                    continue

                # Datos de tiempo y precio
                last_closed_candle = df.iloc[-2]
                current_candle = df.iloc[-1]
                current_candle_time = int(last_closed_candle['open_time'])
                current_price = float(current_candle['close'])

                # 3. Análisis Técnico
                analyzer = BTCAdvancedAnalyzer(df)
                #levels_fib = analyzer.get_support_resistance_dynamic()
                levels_fib = analyzer.get_support_resistance_dynamic(interval=interval)
                momentum_signal, emoji, (buy, sell), reasons = analyzer.get_momentum_signal()
                if 'atr' in levels_fib:
                    levels_fib['atr'] = float(levels_fib['atr'])
                divergence = analyzer.detect_rsi_divergence(lookback=5)

                # Accedemos al sub-estado correspondiente al intervalo
                # load_btc_state garantiza que las claves existan
                current_state = global_state[interval]
                last_saved_time = current_state.get('last_candle_time', 0)
                loaded_levels = current_state.get('levels', {})
                is_legacy_state = 'FIB_618' not in loaded_levels

                # 4. GESTIÓN DE VELA NUEVA VS ACTUALIZACIÓN
                if current_candle_time > last_saved_time or not loaded_levels or is_legacy_state:
                    
                    # --- CASO A: NUEVA VELA (Recalcular Niveles) ---
                    #levels_fib = analyzer.get_support_resistance_dynamic()
                    levels_fib = analyzer.get_support_resistance_dynamic(interval=interval)
                    if 'atr' in levels_fib:
                        levels_fib['atr'] = float(levels_fib['atr'])

                    current_state['levels'] = levels_fib
                    current_state['last_candle_time'] = current_candle_time 
                    current_state['alerted_levels'] = []                   
                    pre_filled_alerts = []
                    c_price = current_price
                    
                    # 1. Verificar Zona Alcista (Si estamos arriba, silenciamos los de abajo)
                    if c_price > levels_fib['R3']:
                        pre_filled_alerts.extend(['R3', 'R2', 'R1', 'P_UP'])
                    elif c_price > levels_fib['R2']:
                        pre_filled_alerts.extend(['R2', 'R1', 'P_UP'])
                    elif c_price > levels_fib['R1']:
                        pre_filled_alerts.extend(['R1', 'P_UP'])
                    elif c_price > levels_fib['P']:
                        pre_filled_alerts.append('P_UP')
                        
                    # 2. Verificar Zona Bajista (Si estamos abajo, silenciamos los de arriba)
                    if c_price < levels_fib['S3']:
                        pre_filled_alerts.extend(['S3', 'S2', 'S1', 'P_DOWN'])
                    elif c_price < levels_fib['S2']:
                        pre_filled_alerts.extend(['S2', 'S1', 'P_DOWN'])
                    elif c_price < levels_fib['S1']:
                        pre_filled_alerts.extend(['S1', 'P_DOWN'])
                    elif c_price < levels_fib['P']:
                        pre_filled_alerts.append('P_DOWN')

                    current_state['alerted_levels'] = pre_filled_alerts
                    
                    state_changed = True
                    add_log_line(f"🦁 [{interval.upper()}] Nuevos niveles. Pivot: ${levels_fib['P']:,.2f}. Alertas silenciadas: {pre_filled_alerts}")
                    
                    # Notificación de Recálculo (Opcional, reducida para no saturar)
                    if _enviar_msg_func and interval in ["1h", "2h", "4h", "8h", "12h", "1d", "1w"]:
                        msg_recalc = (
                            f"🔄 *Niveles BTC Actualizados ({interval.upper()})*\n"
                            f"—————————————————\n"
                            f"📊 La vela ha cerrado. Niveles Fibonacci actualizados.\n\n"
                            f"⚖️ *Nuevo Pivot:* `${levels_fib['P']:,.0f}`\n"
                            f"💰 *Precio Actual:* `${current_price:,.0f}`\n\n"
                            f"🔁 _Alertas listas para la nueva sesión._"
                        )
                        msg_recalc += get_random_ad_text()
                        kb = [[InlineKeyboardButton(f"📊 Ver Análisis {interval.upper()}", callback_data=f"btc_switch_view|BINANCE|{interval}")]]
                        await _enviar_msg_func(msg_recalc, subs, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)
                        # (He comentado el envío para no hacer spam cada 4h, descomenta si lo quieres)

                else:
                    # --- CASO B: MISMA VELA (Solo actualizamos precio) ---
                    # Esto es lo que te faltaba para que sea dinámico
                    if 'levels' in current_state and current_state['levels']:
                        current_state['levels']['current_price'] = current_price
                        # NO recalcula S1, R1, P... esos se quedan fijos hasta la siguiente vela.
                        state_changed = True

                # ========================================================
                # 5. INICIALIZACIÓN DE VARIABLES (CORRECCIÓN DEL ERROR)
                # ========================================================
                # Esto debe estar FUERA del if/else para que 'levels' siempre exista
                
                # Actualizamos el objeto en el estado global
                global_state[interval] = current_state
                
                # Definimos las variables LOCALES para la lógica de abajo
                levels = current_state.get('levels', {})
                alerted = current_state.get('alerted_levels', [])
                check_price = current_price
                # Variables de control
                threshold = 0.001 
                trigger_level = None
                alert_data = {}

                # --- DEBUG --- 
                # add_log_line(f"[{interval}] Precio: ${check_price} vs Nivel-S1: ${levels['S1']}")
                # add_log_line(f"[{interval}] Precio: ${check_price} vs Nivel-S2: ${levels['S2']}")
                # add_log_line(f"[{interval}] Precio: ${check_price} vs Nivel-S3: ${levels['S3']}")
                # add_log_line(f"[{interval}] Precio: ${check_price} vs Pivot: ${levels['P']}")
                # add_log_line(f"[{interval}] Precio: ${check_price} vs Nivel-R1: ${levels['R1']}")
                # add_log_line(f"[{interval}] Precio: ${check_price} vs Nivel-R2: ${levels['R2']}")
                # add_log_line(f"[{interval}] Precio: ${check_price} vs Nivel-R3: ${levels['R3']}")


                # Si por error levels está vacío, saltamos esta iteración para no crashear
                if not levels:
                    continue

                # --- Lógica de Cruces (Usando los niveles Fibonacci cargados) ---
                
                # RUPTURAS ALCISTAS
                if check_price > levels['R3'] * (1 + threshold) and "R3" not in alerted:
                    trigger_level = "R3"
                    alert_data = {
                        'emoji': '🚀', 'titulo': f'Ruptura R3 ({interval.upper()})',
                        'descripcion': 'Precio en zona de extensión máxima. Posible agotamiento o "parada de tren".',
                        'icon_nivel': '🧗', 'icon_precio': '💰', 'icon_target': '🌌', 'icon_rec': '⚡',
                        'target_siguiente': levels['R3'] * 1.05,
                        'recomendacion': 'Zona de toma de ganancias. Precaución extrema.'
                    }
                
                elif check_price > levels['R2'] * (1 + threshold) and "R2" not in alerted:
                    trigger_level = "R2"
                    alert_data = {
                        'emoji': '🌊', 'titulo': f'R2 Superado ({interval.upper()}) - Impulso Fuerte',
                        'descripcion': 'Ruptura de nivel clave Fibonacci (61.8%). Momentum sólido.',
                        'icon_nivel': '🔺', 'icon_precio': '💰', 'icon_target': '🎯', 'icon_rec': '✅',
                        'target_siguiente': levels['R3'],
                        'recomendacion': 'Buscar continuación hacia R3.'
                    }

                elif check_price > levels['R1'] * (1 + threshold) and "R1" not in alerted:
                    trigger_level = "R1"
                    alert_data = {
                        'emoji': '📈', 'titulo': f'R1 Superado ({interval.upper()}) Superada',
                        'descripcion': 'El precio entra en zona alcista (38.2% Fib).',
                        'icon_nivel': '📍', 'icon_precio': '💹', 'icon_target': '🎯', 'icon_rec': '🔝',
                        'target_siguiente': levels['R2'],
                        'recomendacion': 'Mantener largos con stop en Pivot.'
                    }

                elif check_price > levels['P'] * (1 + threshold) and "P_UP" not in alerted:
                    trigger_level = "P_UP"                        
                    alert_data = {
                        'emoji': '⚖️', 'titulo': 'BTC Recupera el Pivot',
                        'descripcion': 'El precio cruza el equilibrio hacia arriba.',
                        'icon_nivel': '⚖️', 'icon_precio': '↗️', 'icon_target': '➡️', 'icon_rec': '👀',
                        'target_siguiente': levels['R1'],
                        'recomendacion': 'Sesgo intradía positivo.'
                    }

                # --- ALERTA GOLDEN POCKET (FIB 0.618) ---
                elif check_price > levels['FIB_618'] * (1 + threshold) and "FIB_618_UP" not in alerted:
                    trigger_level = "FIB_618_UP"
                    alert_data = {
                        'emoji': '🟡', 'titulo': f'Golden Pocket Recuperado ({interval.upper()})',
                        'descripcion': 'El precio ha superado el nivel crítico 61.8% de Fibonacci. Señal de reversión alcista importante.',
                        'icon_nivel': '🔱', 'icon_precio': '💰', 'icon_target': '🎯', 'icon_rec': '💎',
                        'target_siguiente': levels['R1'], # Apuntamos al siguiente nivel técnico
                        'recomendacion': 'Soporte institucional detectado. Sesgo alcista reforzado.'
                    }

                # RUPTURAS BAJISTAS
                elif check_price < levels['S3'] * (1 - threshold) and "S3" not in alerted:
                    trigger_level = "S3"
                    alert_data = {
                        'emoji': '🕳️', 'titulo': f'S3 Perforado ({interval.upper()})',
                        'descripcion': 'Extensión bajista máxima alcanzada.',
                        'icon_nivel': '🧗', 'icon_precio': '💸', 'icon_target': '⬇️', 'icon_rec': '⚠️',
                        'target_siguiente': levels['S3'] * 0.95,
                        'recomendacion': 'Esperar rebote por sobreventa extrema.'
                    }

                elif check_price < levels['S2'] * (1 - threshold) and "S2" not in alerted:
                        trigger_level = "S2"
                        alert_data = {
                            'emoji': '📉', 'titulo': f'BTC S2 Perforado ({interval.upper()})',
                        'descripcion': 'Pérdida del nivel clave Fibonacci (61.8%). Debilidad seria.',
                        'icon_nivel': '🔻', 'icon_precio': '💸', 'icon_target': '🔴', 'icon_rec': '🛑',
                        'target_siguiente': levels['S3'],
                        'recomendacion': 'No buscar compras todavía.'
                    }

                elif check_price < levels['S1'] * (1 - threshold) and "S1" not in alerted:
                        trigger_level = "S1"
                        alert_data = {
                            'emoji': '⚠️', 'titulo': f'BTC S1 Perdido ({interval.upper()})',
                        'descripcion': 'Entrada en zona bajista (38.2% Fib).',
                        'icon_nivel': '📍', 'icon_precio': '📉', 'icon_target': '🔽', 'icon_rec': '⚠️',
                        'target_siguiente': levels['S2'],
                        'recomendacion': 'Precaución con largos.'
                    }

                elif check_price < levels['P'] * (1 - threshold) and "P_DOWN" not in alerted:
                    trigger_level = "P_DOWN"
                    alert_data = {
                        'emoji': '⚖️', 'titulo': 'BTC Pierde el Pivot',
                        'descripcion': 'El precio cruza el equilibrio hacia abajo.',
                        'icon_nivel': '⚖️', 'icon_precio': '↘️', 'icon_target': '⬅️', 'icon_rec': '👁️',
                        'target_siguiente': levels['S1'],
                        'recomendacion': 'Sesgo intradía negativo.'
                    }

                elif check_price < levels['FIB_618'] * (1 - threshold) and "FIB_618_DOWN" not in alerted:
                    trigger_level = "FIB_618_DOWN"
                    alert_data = {
                        'emoji': '💀', 'titulo': f'Pérdida del Golden Pocket ({interval.upper()})',
                        'descripcion': 'El precio ha caído por debajo del 61.8% de Fibonacci. Los compradores han perdido el control de la estructura.',
                        'icon_nivel': '🔱', 'icon_precio': '💸', 'icon_target': '🔽', 'icon_rec': '🆘',
                        'target_siguiente': levels['S2'],
                        'recomendacion': 'Riesgo de capitulación. El Golden Pocket ahora actuará como resistencia.'
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
                        f"⏳ *Marco Temporal:* {interval.upper()}"
                    )
                    
                    msg += get_random_ad_text()
                    kb = [[InlineKeyboardButton(f"📊 Ver Análisis PRO {interval.upper()}", callback_data=f"btc_switch_view|BINANCE|{interval}")]]
                    
                    await _enviar_msg_func(msg, subs, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)
                    
                    # Actualizar estado local y global
                    current_state['alerted_levels'].append(trigger_level)
                    global_state[interval] = current_state
                    state_changed = True
                    add_log_line(f"🦁 Alerta BTC Enviada: {trigger_level} ({interval})")

                # Pausa pequeña entre iteraciones de intervalos para no saturar CPU/API
                await asyncio.sleep(2) 

            # Guardamos estado global si hubo cambios
            if state_changed:
                save_btc_state(global_state)

        except Exception as e:
            add_log_line(f"Error Loop BTC ({interval}): {e}") # Agregamos el intervalo para saber cual falla
            if "int64" in str(e) or "float64" in str(e) or "serializable" in str(e):
                print("❌ ERROR CRÍTICO JSON: Datos de Numpy detectados. Usa float() o int().")
            import traceback
            traceback.print_exc()# Esto ayuda a ver errores en consola
        
        await asyncio.sleep(60)