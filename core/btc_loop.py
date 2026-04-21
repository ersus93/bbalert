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
from utils.year_manager import get_simple_year_string

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
    except Exception:
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
    """
    Bucle principal Multi-Timeframe (4h, 1d, 1w).
    Versión OPTIMIZADA: Reducción de carga del sistema.
    """
    add_log_line("🦁 Iniciando Monitor BTC PRO (Optimizado)...")
    
    # Definimos las temporalidades a monitorear
    TIMEFRAMES = ["1h", "2h", "4h", "8h", "12h", "1d", "1w"]
    
    # Cache para DataFrames y resultados de análisis
    df_cache = {}
    analysis_cache = {}
    
    while True:
        try:
            # Cargamos estado GLOBAL
            global_state = load_btc_state()
            state_changed = False

            for interval in TIMEFRAMES:
                # 1. Validación de Suscriptores
                subs = get_btc_subscribers(interval)
                if not subs:
                    if interval in df_cache:
                        del df_cache[interval]
                    if interval in analysis_cache:
                        del analysis_cache[interval]
                    continue 

                # 2. Obtención de Datos: Solo 2 velas para comprobar cierre
                df_check = get_btc_klines(interval=interval, limit=2)
                if df_check is None or len(df_check) < 2:
                    continue

                last_closed_candle = df_check.iloc[-2]
                current_candle_time = int(last_closed_candle['open_time'])
                current_price = float(df_check.iloc[-1]['close'])

                # Cargar estado del intervalo
                current_state = global_state[interval]
                last_saved_time = current_state.get('last_candle_time', 0)
                loaded_levels = current_state.get('levels', {})
                
                # Detectar si es una vela nueva
                is_new_candle = current_candle_time > last_saved_time

                # Solo cargar datos completos y ejecutar análisis cuando haya vela nueva
                if is_new_candle or interval not in df_cache:
                    df = get_btc_klines(interval=interval, limit=1000)
                    if df is None or len(df) < 200:
                        continue
                    
                    df_cache[interval] = df
                    
                    # Ejecutar análisis solo una vez por vela nueva
                    analyzer = BTCAdvancedAnalyzer(df)
                    levels_fib = analyzer.get_support_resistance_dynamic(interval=interval)
                    momentum_signal, mom_emoji, (buy, sell), reasons = analyzer.get_momentum_signal()
                    divergence = analyzer.detect_rsi_divergence(lookback=5)
                    
                    if 'atr' in levels_fib: 
                        levels_fib['atr'] = float(levels_fib['atr'])
                    
                    analysis_cache[interval] = {
                        'levels': levels_fib,
                        'momentum': (momentum_signal, mom_emoji, buy, sell, reasons),
                        'divergence': divergence
                    }
                else:
                    # Usar cache
                    df = df_cache[interval]
                    cache_data = analysis_cache[interval]
                    levels_fib = cache_data['levels']
                    momentum_signal, mom_emoji, buy, sell, reasons = cache_data['momentum']
                    divergence = cache_data['divergence']

                # ==============================================================================
                # FASE 1: GESTIÓN DE NUEVA VELA (Contexto de Sesión)
                # ==============================================================================
                if is_new_candle or not loaded_levels:
                    
                    # Guardamos los nuevos niveles y tiempo
                    current_state['levels'] = levels_fib
                    current_state['last_candle_time'] = current_candle_time
                    
                    # --- LÓGICA INTELIGENTE DE POSICIONAMIENTO ---
                    pre_filled_alerts = []
                    status_msg = ""
                    status_icon = "⚖️"
                    
                    # A) ANÁLISIS ALCISTA
                    if current_price >= levels_fib['R3']:
                        pre_filled_alerts.extend(['P_UP', 'R1', 'R2', 'R3'])
                        status_msg = f"Extrema euforia. BTC inicia sesión sobre R3."
                        status_icon = "🚀"
                    elif current_price >= levels_fib['R2']:
                        pre_filled_alerts.extend(['P_UP', 'R1', 'R2'])
                        status_msg = f"Momentum muy fuerte. BTC consolidando sobre R2."
                        status_icon = "🌊"
                    elif current_price >= levels_fib['R1']:
                        pre_filled_alerts.extend(['P_UP', 'R1'])
                        status_msg = f"Tendencia alcista sana. BTC sosteniendo soporte en R1."
                        status_icon = "📈"
                    elif current_price >= levels_fib['P']:
                        pre_filled_alerts.append('P_UP')
                        status_msg = f"Sesgo positivo. BTC sobre Pivot central."
                        status_icon = "✅"
                        
                    # B) ANÁLISIS BAJISTA
                    elif current_price <= levels_fib['S3']:
                        pre_filled_alerts.extend(['P_DOWN', 'S1', 'S2', 'S3'])
                        status_msg = f"Pánico extremo. BTC bajo S3."
                        status_icon = "🕳️"
                    elif current_price <= levels_fib['S2']:
                        pre_filled_alerts.extend(['P_DOWN', 'S1', 'S2'])
                        status_msg = f"Debilidad fuerte. BTC atrapado bajo S2."
                        status_icon = "🩸"
                    elif current_price <= levels_fib['S1']:
                        pre_filled_alerts.extend(['P_DOWN', 'S1'])
                        status_msg = f"Tendencia bajista. BTC inicia sesión bajo S1."
                        status_icon = "📉"
                    elif current_price < levels_fib['P']: 
                        pre_filled_alerts.append('P_DOWN')
                        status_msg = f"Sesgo negativo. BTC bajo Pivot central."
                        status_icon = "⚠️"

                    # C) LÓGICA GOLDEN POCKET (Independiente)
                    if current_price >= levels_fib['FIB_618']:
                        if 'FIB_618_UP' not in pre_filled_alerts: pre_filled_alerts.append('FIB_618_UP')
                    else:
                        if 'FIB_618_DOWN' not in pre_filled_alerts: pre_filled_alerts.append('FIB_618_DOWN')

                    current_state['alerted_levels'] = pre_filled_alerts
                    state_changed = True
                    ytext = get_simple_year_string() 

                    add_log_line(f"🦁 [{interval.upper()}] Nueva Vela. Estado: {status_msg}")

                    # --- REPORTE DE SESIÓN (Visualización Inicial) ---
                    if _enviar_msg_func:
                        msg_session = (
                            f"🔄 *Actualización de Estructura BTC ({interval.upper()})*\n"
                            f"—————————————————\n"
                            f"{status_icon} *Estado:* _{status_msg}_\n\n"
                            f"📊 *Nuevos Niveles Calculados:*\n"
                            f"🛡️ R3: `${levels_fib['R3']:,.0f}`\n"
                            f"🛡️ R2: `${levels_fib['R2']:,.0f}`\n"
                            f"🛡️ R1: `${levels_fib['R1']:,.0f}`\n"
                            f"🟡 G. Pocket (0.618): `${levels_fib['FIB_618']:,.0f}`\n" 
                            f"⚖️ Pivot: `${levels_fib['P']:,.0f}`\n"
                            f"🛡️ S1: `${levels_fib['S1']:,.0f}`\n"
                            f"🛡️ S2: `${levels_fib['S2']:,.0f}`\n"
                            f"🛡️ S3: `${levels_fib['S3']:,.0f}`\n\n"
                            f"💰 *Precio Actual:* `${current_price:,.0f}`\n"
                            f"🌊 *Tendencia:* {mom_emoji} {momentum_signal}\n\n"
                            f"{ytext}"
                        )
                        
                        msg_session += get_random_ad_text()
                        kb = [[InlineKeyboardButton(f"📊 Ver Análisis Completo", callback_data=f"btc_switch_view|BINANCE|{interval}")]]
                        await _enviar_msg_func(msg_session, subs, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)

                else:
                    if 'levels' in current_state and current_state['levels']:
                        current_state['levels']['current_price'] = current_price
                        state_changed = True

                # ==============================================================================
                # FASE 2: MONITOREO DE CRUCES EN VIVO (Mensajes Enriquecidos)
                # ==============================================================================
                
                levels = current_state.get('levels', {})
                alerted = current_state.get('alerted_levels', [])
                
                if not levels: continue 
                
                threshold = 0.001 
                trigger_level = None
                alert_data = {} # Aquí cargaremos la info rica del legacy

                # --- RUPTURAS ALCISTAS ---
                if current_price > levels['R3'] * (1 + threshold) and "R3" not in alerted:
                    trigger_level = "R3"
                    alert_data = {
                        'emoji': '🚀', 'titulo': f'Ruptura R3 ({interval.upper()})',
                        'descripcion': 'Precio en zona de extensión máxima. Posible agotamiento o "parada de tren".',
                        'icon_nivel': '🧗', 'icon_precio': '💰', 'icon_target': '🌌', 'icon_rec': '⚡',
                        'target_siguiente': levels['R3'] * 1.05,
                        'recomendacion': 'Zona de toma de ganancias. Precaución extrema.'
                    }
                
                elif current_price > levels['R2'] * (1 + threshold) and "R2" not in alerted:
                    trigger_level = "R2"
                    alert_data = {
                        'emoji': '🌊', 'titulo': f'R2 Superado ({interval.upper()})',
                        'descripcion': 'Ruptura de nivel clave Fibonacci (161.8% o expansión). Momentum sólido.',
                        'icon_nivel': '🔺', 'icon_precio': '💰', 'icon_target': '🎯', 'icon_rec': '✅',
                        'target_siguiente': levels['R3'],
                        'recomendacion': 'Buscar continuación hacia R3.'
                    }
                
                elif current_price > levels['R1'] * (1 + threshold) and "R1" not in alerted:
                    trigger_level = "R1"
                    alert_data = {
                        'emoji': '📈', 'titulo': f'R1 Superado ({interval.upper()})',
                        'descripcion': 'El precio entra en zona de fortaleza alcista.',
                        'icon_nivel': '📍', 'icon_precio': '💹', 'icon_target': '🎯', 'icon_rec': '🔝',
                        'target_siguiente': levels['R2'],
                        'recomendacion': 'Mantener largos con stop bajo Pivot.'
                    }

                elif current_price > levels['FIB_618'] * (1 + threshold) and "FIB_618_UP" not in alerted:
                    trigger_level = "FIB_618_UP"
                    alert_data = {
                        'emoji': '🟡', 'titulo': f'BTC Golden Pocket Recuperado ({interval.upper()})',
                        'descripcion': 'El precio supera el nivel crítico 61.8% Fibonacci. Señal de reversión alcista.',
                        'icon_nivel': '🔱', 'icon_precio': '💰', 'icon_target': '🎯', 'icon_rec': '💎',
                        'target_siguiente': levels['R1'],
                        'recomendacion': 'Soporte institucional detectado. Sesgo alcista reforzado.'
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

                # --- RUPTURAS BAJISTAS ---
                elif current_price < levels['S3'] * (1 - threshold) and "S3" not in alerted:
                    trigger_level = "S3"
                    alert_data = {
                        'emoji': '🕳️', 'titulo': f'S3 Perforado ({interval.upper()})',
                        'descripcion': 'Extensión bajista máxima alcanzada. Caída libre.',
                        'icon_nivel': '🧗', 'icon_precio': '💸', 'icon_target': '⬇️', 'icon_rec': '⚠️',
                        'target_siguiente': levels['S3'] * 0.95,
                        'recomendacion': 'Esperar rebote por sobreventa extrema.'
                    }

                elif current_price < levels['S2'] * (1 - threshold) and "S2" not in alerted:
                    trigger_level = "S2"
                    alert_data = {
                        'emoji': '🩸', 'titulo': f'BTC S2 Perforado ({interval.upper()})',
                        'descripcion': 'Pérdida de soporte estructural mayor.',
                        'icon_nivel': '🔻', 'icon_precio': '💸', 'icon_target': '🔴', 'icon_rec': '🛑',
                        'target_siguiente': levels['S3'],
                        'recomendacion': 'No buscar compras todavía. Debilidad.'
                    }

                elif current_price < levels['S1'] * (1 - threshold) and "S1" not in alerted:
                    trigger_level = "S1"
                    alert_data = {
                        'emoji': '📉', 'titulo': f'BTC S1 Perdido ({interval.upper()})',
                        'descripcion': 'Caída bajo el primer soporte clave.',
                        'icon_nivel': '📍', 'icon_precio': '📉', 'icon_target': '🔽', 'icon_rec': '⚠️',
                        'target_siguiente': levels['S2'],
                        'recomendacion': 'Precaución con largos.'
                    }

                elif current_price < levels['FIB_618'] * (1 - threshold) and "FIB_618_DOWN" not in alerted:
                    trigger_level = "FIB_618_DOWN"
                    alert_data = {
                        'emoji': '💀', 'titulo': f'BTC Pérdida Golden Pocket ({interval.upper()})',
                        'descripcion': 'El precio pierde el 61.8% Fibonacci. Compradores perdiendo control.',
                        'icon_nivel': '🔱', 'icon_precio': '💸', 'icon_target': '🔽', 'icon_rec': '🆘',
                        'target_siguiente': levels['S2'],
                        'recomendacion': 'Riesgo de capitulación. G. Pocket actuará como resistencia.'
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


                # --- CONSTRUCCIÓN Y ENVÍO DEL MENSAJE RICO ---
                if trigger_level and _enviar_msg_func and alert_data:
                    # Recuperamos el precio del nivel limpio (sin _UP/_DOWN)
                    clean_code = trigger_level.replace('_UP', '').replace('_DOWN', '')
                    level_price = levels.get(clean_code, 0)

                    # 1. Cabecera y Descripción
                    msg = (
                        f"{alert_data['emoji']} *{alert_data['titulo']}*\n"
                        f"—————————————————\n"
                        f"📊 {alert_data['descripcion']}\n\n"
                    )
                    
                    # 2. Contexto Técnico (Momentum)
                    msg += (
                        f"*Contexto Técnico:*\n"
                        f"{mom_emoji} Momentum: {momentum_signal}\n"
                        f"⚖️ Score: {buy} Compra | {sell} Venta\n"
                    )
                    
                    # Razones y Divergencias
                    if reasons:
                        msg += f"• _Clave: {reasons[0]}_\n"
                    if divergence:
                        d_type, d_text = divergence
                        d_icon = "🐂" if d_type == "BULLISH" else "🐻"
                        msg += f"{d_icon} *Divergencia:* {d_text}\n"
                    msg += "\n"

                    # 3. Bloque de Detalles (Iconos y Datos)
                    msg += (
                        f"*Detalles del Cruce:*\n"
                        f"{alert_data['icon_nivel']} Nivel: `{clean_code}` (${level_price:,.0f})\n"
                        f"{alert_data['icon_precio']} Precio: `${current_price:,.0f}`\n"
                        f"{alert_data['icon_target']} Objetivo: `${alert_data['target_siguiente']:,.0f}`\n\n"
                        f"{alert_data['icon_rec']} *Recomendación:*\n"
                        f"_{alert_data['recomendacion']}_\n\n"
                        f"⏳ *Marco Temporal:* {interval.upper()}"
                    )

                    msg += get_random_ad_text()
                    kb = [[InlineKeyboardButton(f"📊 Ver Análisis PRO", callback_data=f"btc_switch_view|BINANCE|{interval}")]]
                    
                    await _enviar_msg_func(msg, subs, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)
                    
                    # Actualizar estado para no repetir
                    current_state['alerted_levels'].append(trigger_level)
                    global_state[interval] = current_state
                    state_changed = True
                    add_log_line(f"🚨 Alerta BTC Enviada: {trigger_level} ({interval})")

                # Pequeña pausa entre intervalos para no bloquear el event loop
                await asyncio.sleep(0.1)

            if state_changed:
                save_btc_state(global_state)

        except Exception as e:
            add_log_line(f"❌ Error en BTC Monitor Loop: {e}")
            import traceback
            traceback.print_exc()
        
        # Espera principal del bucle: 10 segundos entre ciclos
        # Balance perfecto: no consumir CPU, pero responder rápido a cruces de niveles
        await asyncio.sleep(10)