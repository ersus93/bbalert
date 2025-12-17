# core/valerts_loop.py

import asyncio
import requests
import pandas as pd
from datetime import datetime
from telegram.constants import ParseMode
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from utils.valerts_manager import (
    get_active_symbols,
    get_valerts_subscribers,
    update_symbol_state,
    get_symbol_state
)
from utils.file_manager import add_log_line
from utils.ads_manager import get_random_ad_text
from utils.tv_helper import get_tv_data
from core.api_client import obtener_datos_moneda
from core.btc_advanced_analysis import BTCAdvancedAnalyzer

# Variable global para la función de envío (inyectada desde bbalert.py)
VALERTS_SENDER = None
_enviar_valerts_msg = None

def set_valerts_sender(func):
    global VALERTS_SENDER
    VALERTS_SENDER = func


def fetch_binance_klines_data(symbol, interval="4h", limit=1000):
    """
    Obtiene datos de velas de Binance de forma robusta.
    Igual que en btc_loop, limitamos a 1000 por llamada para evitar errores de API,
    pero es suficiente para calcular EMA200 y Pivotes.
    """
    # Ajuste de símbolo para asegurar compatibilidad
    if not symbol.endswith("USDT") and "BTC" not in symbol:
        symbol += "USDT"

    # Endpoints de redundancia
    endpoints = [
        "https://api.binance.us/api/v3/klines",
        "https://api.binance.com/api/v3/klines",
        "https://api1.binance.com/api/v3/klines"
    ]
    
    # Binance limita a 1000 por request estándar
    safe_limit = min(limit, 1000)
    
    params = {
        "symbol": symbol,
        "interval": interval,
        "limit": safe_limit
    }

    for url in endpoints:
        try:
            r = requests.get(url, params=params, timeout=10)
            if r.status_code != 200:
                continue
            
            data = r.json()
            
            # Verificar que hay suficientes datos para el análisis técnico
            if not isinstance(data, list) or len(data) < 200:
                continue
                
            # Definir columnas explícitamente
            column_names = [
                "open_time", "open", "high", "low", "close", "volume",
                "close_time", "quote_asset_volume", "trades",
                "taker_base", "taker_quote", "ignore"
            ]
            
            df = pd.DataFrame(data, columns=column_names)
            
            # Convertir a números
            for col in ["open", "high", "low", "close", "volume"]:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # Obtener precio actual (última vela)
            current_price = float(df.iloc[-1]['close'])
            
            return {
                'df': df,
                'current_price': current_price
            }
        except Exception as e:
            continue # Intentar siguiente endpoint

    return None

def get_alert_text_data(level_name, symbol, price, target):
    """Genera los textos y emojis para la alerta."""
    clean_sym = symbol.replace("USDT", "").replace(":TV", "")
    
    # Diccionario de textos
    texts = {
        'R3': {'e': '🚀', 't': 'Volatilidad Extrema (R3)', 'd': 'Precio en zona de extensión máxima.'},
        'R2': {'e': '🌊', 't': 'Impulso Fuerte (R2)', 'd': 'Ruptura alcista con fuerza.'},
        'R1': {'e': '📈', 't': 'Resistencia R1 Rota', 'd': 'Inicio de zona alcista.'},
        'S1': {'e': '⚠️', 't': 'Soporte S1 Perforado', 'd': 'Debilidad en la estructura.'},
        'S2': {'e': '📉', 't': 'Soporte S2 Perdido', 'd': 'Presión de venta acelerada.'},
        'S3': {'e': '🕳️', 't': 'Caída Libre (S3)', 'd': 'Volatilidad extrema bajista.'}
    }
    
    data = texts.get(level_name, {'e': '⚡', 't': f'Nivel {level_name}', 'd': 'Cruce de nivel detectado.'})
    
    return {
        'emoji': data['e'],
        'titulo': f"{data['t']}",
        'descripcion': data['d'],
        'symbol': clean_sym,
        'target': target
    }

def calculate_pivot_points(high, low, close):
    """Calcula Puntos Pivote Standard con precisión."""
    p = (high + low + close) / 3
    r1 = (2 * p) - low
    s1 = (2 * p) - high
    r2 = p + (high - low)
    s2 = p - (high - low)
    r3 = high + 2 * (p - low)
    s3 = low - 2 * (high - p)
    return {"P": p, "R1": r1, "R2": r2, "R3": r3, "S1": s1, "S2": s2, "S3": s3}

def determine_market_zone(current_price, levels):
    """
    Determina la zona de mercado actual y retorna:
    (zone_name, emoji, intensity, color_description)
    """
    p = levels.get('P', 0)
    r1 = levels.get('R1', 0)
    r2 = levels.get('R2', 0)
    r3 = levels.get('R3', 0)
    s1 = levels.get('S1', 0)
    s2 = levels.get('S2', 0)
    s3 = levels.get('S3', 0)
    
    if current_price > r2:
        return ("EXTENSIÓN ALCISTA", "🚀", "Máxima", "Territorio de volatilidad extrema alcista")
    elif current_price > r1:
        return ("IMPULSO ALCISTA", "📈", "Alta", "Momentum positivo fuerte")
    elif current_price > p:
        return ("PRESIÓN COMPRADORA", "📊", "Moderada", "Sesgo intradía positivo")
    elif current_price > s1:
        return ("NEUTRAL", "⚖️", "Baja", "Equilibrio de fuerzas")
    elif current_price > s2:
        return ("PRESIÓN VENDEDORA", "📉", "Moderada", "Sesgo intradía negativo")
    elif current_price > s3:
        return ("IMPULSO BAJISTA", "⬇️", "Alta", "Momentum negativo fuerte")
    else:
        return ("EXTENSIÓN BAJISTA", "🕳️", "Máxima", "Territorio de volatilidad extrema bajista")


async def send_valerts_alert(symbol_key, subs, clean_symbol, level_name, level_value, 
                           current_price, levels, threshold, state, analyzer=None, divergence=None):
    """
    Envía una alerta idéntica a BTC Alerts, incluyendo análisis técnico avanzado.
    """
    # 1. Definir datos base de la alerta (Copiados de BTC para consistencia)
    alert_definitions = {
        'R3': {
            'emoji': '🚀', 'titulo': f'Ruptura de R3 - Volatilidad Extrema',
            'desc': 'El precio ha perforado R3, máxima volatilidad alcista alcanzada.',
            'icon_rec': '⚡', 'rec': 'Zona de máximo riesgo. Asegura ganancias.',
            'next': ('Unknown', 0) 
        },
        'R2': {
            'emoji': '🌊', 'titulo': f'R2 Perforado - Impulso Fuerte',
            'desc': 'Ruptura de R2 confirmada. Momentum fuerte detectado.',
            'icon_rec': '✅', 'rec': 'Confirma fortaleza. Target: R3',
            'next': ('R3', levels.get('R3', 0))
        },
        'R1': {
            'emoji': '📈', 'titulo': f'Resistencia R1 Superada',
            'desc': 'Primera resistencia perforada. Sesgo fuertemente alcista.',
            'icon_rec': '🔝', 'rec': 'Consolidación en zona positiva.',
            'next': ('R2', levels.get('R2', 0))
        },
        'S1': {
            'emoji': '⚠️', 'titulo': f'Soporte S1 Testado',
            'desc': 'Primer soporte roto. Sesgo fuertemente bajista.',
            'icon_rec': '⚠️', 'rec': 'Debilidad confirmada.',
            'next': ('S2', levels.get('S2', 0))
        },
        'S2': {
            'emoji': '📉', 'titulo': f'Presión de Venta - S2 Perforado',
            'desc': 'Segundo nivel de soporte roto. Estructura deteriorada.',
            'icon_rec': '🛑', 'rec': 'Zona crítica de riesgo.',
            'next': ('S3', levels.get('S3', 0))
        },
        'S3': {
            'emoji': '🕳️', 'titulo': f'Caída Extrema - S3 Perforado',
            'desc': 'Máximo nivel de volatilidad bajista alcanzado.',
            'icon_rec': '⚠️', 'rec': 'Volatilidad extrema. Posible pánico.',
            'next': ('Unknown', 0)
        }
    }

    # Datos por defecto (Pivot o casos raros)
    data = alert_definitions.get(level_name, {
        'emoji': '⚡', 'titulo': f'Cruce de Nivel {level_name}',
        'desc': f'El precio cruzó {level_name}',
        'icon_rec': '👀', 'rec': 'Monitorear desarrollo',
        'next': ('-', 0)
    })

    # 2. Construcción del Mensaje Base
    msg = (
        f"{data['emoji']} *{data['titulo']} en {clean_symbol}*\n"
        f"—————————————————\n"
        f"📊 {data['desc']}\n\n"
    )

    # 3. Inyección de Análisis Avanzado (Igual que BTC)
    if analyzer:
        # Obtenemos señales del analyzer pasado como argumento
        signal, sig_emoji, (buy, sell), reasons = analyzer.get_momentum_signal()
        msg += (
            f"*Momentum Actual:* {sig_emoji} {signal}\n"
            f"⚖️ _Score: {buy} Compra | {sell} Venta_\n"
        )
        # Añadir razones clave (si existen)
        if len(reasons) > 0: msg += f"✓ {reasons[0]}\n"
        if len(reasons) > 1: msg += f"✓ {reasons[1]}\n"
        msg += "\n"

    # 4. Inyección de Divergencias
    if divergence:
        div_type, div_desc = divergence
        div_emoji = "🐂" if div_type == "BULLISH" else "🐻"
        msg += (
            f"{div_emoji} *Divergencia {div_type}*\n"
            f"💡 _{div_desc}_\n\n"
        )

    # 5. Detalles Técnicos Finales
    target_name, target_val = data.get('next', ('-', 0))
    msg += (
        f"*Detalles del Cruce:*\n"
        f"📍 Nivel: `{level_name}` (${level_value:,.4f})\n"
        f"💰 Precio: `${current_price:,.4f}`\n"
    )
    
    if target_val > 0:
        msg += f"🎯 Objetivo: `{target_name}` (${target_val:,.4f})\n"
        
    msg += (
        f"\n{data['icon_rec']} *Recomendación:*\n"
        f"_{data['rec']}_\n\n"
        f"⏳ *Marco Temporal:* 4H"
    )
    
    msg += get_random_ad_text()
    
    # 6. Botón de acción (Link al comando de vista PRO)
    # Callback data incluye BINANCE para forzar modo local
    kb = [[InlineKeyboardButton(f"📊 Ver Análisis {clean_symbol}", 
                             callback_data=f"valerts_view|{symbol_key}|BINANCE")]]
    
    # Enviar usando la función global inyectada
    if _enviar_valerts_msg:
        await _enviar_valerts_msg(msg, subs, 
                                reply_markup=InlineKeyboardMarkup(kb),
                                parse_mode=ParseMode.MARKDOWN)
    
    # Log y actualización de estado
    state['alerted_levels'].append(level_name)
    update_symbol_state(symbol_key, state)
    add_log_line(f"🦁 Alerta Valerts enviada {clean_symbol}: {level_name}")

async def valerts_monitor_loop(bot):
    add_log_line("🦁 Iniciando Monitor Valerts (Modo Fibonacci Multi-Moneda)...")
    global _enviar_valerts_msg
    if VALERTS_SENDER:
        _enviar_valerts_msg = VALERTS_SENDER
    
    while True:
        try:
            active_symbols = get_active_symbols()
            if not active_symbols:
                await asyncio.sleep(30)
                continue
                
            for symbol_key in active_symbols:
                subs = get_valerts_subscribers(symbol_key)
                if not subs: 
                    continue
                
                # 1. Cargar Estado Actual
                state = get_symbol_state(symbol_key)
                last_saved_time = state.get('last_candle_time', 0)
                
                # 2. Obtener datos (Usamos el fetch robusto)
                data_pack = fetch_binance_klines_data(symbol_key, "4h", 1000)
                if not data_pack or data_pack['df'] is None:
                    continue
                    
                df = data_pack['df']
                current_price = data_pack['current_price']
                
                # Tiempos de vela
                # Penúltima fila es la vela cerrada (la base del cálculo)
                # Última fila es la vela actual
                last_closed_candle = df.iloc[-2]
                current_candle_time = int(last_closed_candle['open_time'])
                
                # 3. ANÁLISIS CENTRALIZADO (Igual que BTC)
                analyzer = BTCAdvancedAnalyzer(df)
                
                # Calculamos Niveles Fibonacci (P, R1-R3, S1-S3)
                # Esto usa internamente la vela cerrada anterior
                levels = analyzer.get_support_resistance_dynamic()
                
                # Análisis extra para el mensaje
                momentum_signal, emoji_mom, (buy, sell), reasons = analyzer.get_momentum_signal()
                divergence = analyzer.detect_rsi_divergence(lookback=5)
                
                # 4. GESTIÓN DE ESTADO Y NUEVA VELA
                # Si la vela cerrada actual es más nueva que la guardada, recalculamos
                is_new_candle = current_candle_time > last_saved_time
                
                if is_new_candle or not state.get('levels'):
                    # Guardamos los nuevos niveles calculados
                    state['levels'] = levels
                    state['last_candle_time'] = current_candle_time
                    state['alerted_levels'] = [] # Reseteamos alertas para la nueva sesión
                    update_symbol_state(symbol_key, state)
                    
                    # Opcional: Notificar recálculo (si se desea)
                    # Aquí lo omitimos para no spammear en Valerts, 
                    # pero la lógica ya está lista.
                
                # 5. VERIFICACIÓN DE ALERTAS (Dentro de la vela actual)
                if not state.get('levels'): continue
                
                saved_levels = state['levels']
                alerted_list = state.get('alerted_levels', [])
                clean_symbol = symbol_key.replace("USDT", "").upper()
                threshold = 0.001 # 0.1% margen
                
                # Lista de chequeos (Nombre Nivel, Clave en Dict)
                # NOTA: BTCAdvancedAnalyzer devuelve claves en Mayúsculas (R1, S1...)
                checks = [
                    ('R3', 'R3'), ('R2', 'R2'), ('R1', 'R1'), 
                    ('S1', 'S1'), ('S2', 'S2'), ('S3', 'S3')
                ]

                for lvl_name, dict_key in checks:
                    val = saved_levels.get(dict_key, 0)
                    if val == 0: continue

                    triggered = False
                    
                    # Lógica de Trigger (Precio cruza el nivel)
                    if lvl_name.startswith('R'): # Resistencias (Precio sube)
                        if current_price > val * (1 + threshold): triggered = True
                    elif lvl_name.startswith('S'): # Soportes (Precio baja)
                        if current_price < val * (1 - threshold): triggered = True
                    
                    if triggered and lvl_name not in alerted_list:
                        # ENVIAR ALERTA
                        # Pasamos analyzer y divergence para que send_valerts_alert 
                        # construya el mensaje idéntico a BTC
                        await send_valerts_alert(
                            symbol_key, subs, clean_symbol, 
                            lvl_name, val, current_price, 
                            saved_levels, threshold, state,
                            analyzer=analyzer,       
                            divergence=divergence
                        )
                        # El estado se actualiza dentro de send_valerts_alert 
                        # (añade el nivel a alerted_levels)
                        
            await asyncio.sleep(60) # Espera entre ciclos de todas las monedas
            
        except Exception as e:
            add_log_line(f"Error Valerts Loop: {e}")
            await asyncio.sleep(60)