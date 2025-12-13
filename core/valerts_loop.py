# core/valerts_loop.py

import asyncio
import requests
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

# Variable global para la función de envío (inyectada desde bbalert.py)
VALERTS_SENDER = None

def set_valerts_sender(func):
    global VALERTS_SENDER
    VALERTS_SENDER = func

def fetch_binance_klines(symbol, interval="4h", limit=2):
    """Obtiene las últimas velas de Binance para calcular pivots."""
    endpoints = [
        "https://api.binance.com/api/v3/klines",
        "https://api.binance.us/api/v3/klines",
        "https://api1.binance.com/api/v3/klines"
    ]
    params = {"symbol": symbol.upper(), "interval": interval, "limit": limit}
    
    for url in endpoints:
        try:
            r = requests.get(url, params=params, timeout=5)
            if r.status_code == 200:
                return r.json()
        except Exception as e:
            continue
    
    # print(f"Error fetching {symbol}: No endpoint disponible") 
    return None

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

def get_alert_context(triggered_level, current_price, levels, symbol):
    """
    Genera información contextual inteligente para cada alerta.
    Retorna: diccionario con emoji, titulo, descripcion, etc.
    """
    # Escapamos el símbolo aquí por si contiene guiones bajos (ej: PEPE_USDT)
    clean_symbol = symbol.replace("_", "\\_")
    
    level_value = levels.get(triggered_level, 0)
    p = levels.get('P', 0)
    
    # Mapeo completo de cada nivel con contexto técnico
    alert_context = {
        'R3': {
            'emoji': '🚀',
            'titulo': f'Volatilidad Extrema Alcista en {clean_symbol}',
            'descripcion': 'El precio ha entrado en territorio de extensión máxima por encima de R3.',
            'tecnico': 'Ruptura de máxima volatilidad. Condiciones de sobrecompra severa.',
            'proximo': ('Discovery', 'Máximos históricos o retracción brusca'),
            'recomendacion': 'Zona de máximo riesgo alcista. Considere asegurar ganancias.'
        },
        'R2': {
            'emoji': '🌊',
            'titulo': f'Impulso Alcista Fuerte en {clean_symbol}',
            'descripcion': 'El precio ha superado la segunda resistencia (R2).',
            'tecnico': 'Ruptura confirmada de nivel R2. Presión de compra significativa.',
            'proximo': ('R3', f'${levels.get("R3", 0):,.4f}'),
            'recomendacion': 'Confirmación de fortaleza. Target: R3 o retracción a R1.'
        },
        'R1': {
            'emoji': '📈',
            'titulo': f'Primera Resistencia Superada en {clean_symbol}',
            'descripcion': 'El precio ha perforado el primer nivel de resistencia (R1).',
            'tecnico': 'Ruptura de R1. Sesgo intradía claramente positivo.',
            'proximo': ('R2', f'${levels.get("R2", 0):,.4f}'),
            'recomendacion': 'Consolidación en zona positiva. Próximo target: R2.'
        },
        'P_UP': {
            'emoji': '⚖️',
            'titulo': f'Pivot Point Recuperado en {clean_symbol}',
            'descripcion': 'El precio está por encima del punto de equilibrio (Pivot).',
            'tecnico': 'Recuperación del pivot central. Sesgo intradiario ligeramente alcista.',
            'proximo': ('R1', f'${levels.get("R1", 0):,.4f}'),
            'recomendacion': 'Soporte dinámico. Monitorear para salida o entrada.'
        },
        'S1': {
            'emoji': '⚠️',
            'titulo': f'Soporte Testado en {clean_symbol}',
            'descripcion': 'El precio ha caído por debajo del primer soporte (S1).',
            'tecnico': 'Pérdida de S1. Debilidad técnica considerable.',
            'proximo': ('S2', f'${levels.get("S2", 0):,.4f}'),
            'recomendacion': 'Zona de debilidad. Atención a continuidad bajista.'
        },
        'S2': {
            'emoji': '📉',
            'titulo': f'Presión de Venta Fuerte en {clean_symbol}',
            'descripcion': 'El precio ha penetrado la segunda zona de soporte (S2).',
            'tecnico': 'Ruptura de S2. Estructura técnica deteriorada.',
            'proximo': ('S3', f'${levels.get("S3", 0):,.4f}'),
            'recomendacion': 'Zona de máximo riesgo bajista. Considere cobertura.'
        },
        'S3': {
            'emoji': '🕳️',
            'titulo': f'Caída Extrema en {clean_symbol}',
            'descripcion': 'El precio ha perforado S3, máximo nivel de volatilidad bajista.',
            'tecnico': 'Ruptura de S3. Condiciones de sobreventa severa.',
            'proximo': ('Discovery', 'Mínimos históricos o rebote fuerte'),
            'recomendacion': 'Zona de volatilidad extrema. Posibles retracción o pánico.'
        },
        'P_DOWN': {
            'emoji': '⚖️',
            'titulo': f'Pivot Point Perdido en {clean_symbol}',
            'descripcion': 'El precio ha caído por debajo del punto de equilibrio (Pivot).',
            'tecnico': 'Pérdida del pivot central. Sesgo intradiario negativo.',
            'proximo': ('S1', f'${levels.get("S1", 0):,.4f}'),
            'recomendacion': 'Resistencia dinámica. Vigilar para entrada o salida.'
        }
    }
    
    return alert_context.get(triggered_level, {
        'emoji': '⚡',
        'titulo': f'Alerta de Nivel {triggered_level} en {clean_symbol}',
        'descripcion': f'El precio ha tocado/cruzado el nivel {triggered_level}.',
        'tecnico': 'Revisión de niveles recomendada.',
        'proximo': ('Siguiente', 'Pendiente análisis'),
        'recomendacion': 'Monitorear desarrollo.'
    })

async def valerts_monitor_loop(bot):
    """
    Bucle principal que monitorea monedas activas, calcula niveles
    y envía alertas si el precio cruza niveles clave con mensajes profundos.
    """
    add_log_line("🦁 Loop de Volatilidad (Valerts) iniciado con mensajes mejorados...")
    
    while True:
        try:
            active_symbols = get_active_symbols()
            
            if not active_symbols:
                await asyncio.sleep(60)
                continue

            for symbol in active_symbols:
                try:
                    # 1. Obtener datos (Vela cerrada anterior y precio actual)
                    klines = fetch_binance_klines(symbol, interval="4h")
                    if not klines or len(klines) < 2:
                        continue

                    prev_candle = klines[-2] 
                    curr_candle = klines[-1]
                    
                    ph, pl, pc = float(prev_candle[2]), float(prev_candle[3]), float(prev_candle[4])
                    current_price = float(curr_candle[4])
                    
                    # 2. Calcular Niveles
                    levels = calculate_pivot_points(ph, pl, pc)
                    levels['current_price'] = current_price
                    
                    zone_name, zone_emoji, intensity, zone_desc = determine_market_zone(current_price, levels)
                    
                    # 3. Obtener estado anterior
                    state = get_symbol_state(symbol)
                    last_alerted_levels = state.get('alerted_levels', [])
                    candle_ts = prev_candle[0]
                    
                    if state.get('last_candle_time') != candle_ts:
                        last_alerted_levels = []
                        state['last_candle_time'] = candle_ts
                    
                    # 4. Chequear Cruces
                    check_list = [
                        ('R3', levels['R3']), ('R2', levels['R2']), ('R1', levels['R1']),
                        ('P_UP', levels['P']), ('P_DOWN', levels['P']),
                        ('S1', levels['S1']), ('S2', levels['S2']), ('S3', levels['S3'])
                    ]
                    
                    alerts_to_send = []
                    
                    for name, value in check_list:
                        if name in last_alerted_levels:
                            continue
                        
                        diff = abs(current_price - value) / value
                        if diff < 0.002: # 0.2% de margen
                            if name == 'P_UP' and current_price > value:
                                alerts_to_send.append((name, value))
                                last_alerted_levels.append(name)
                            elif name == 'P_DOWN' and current_price < value:
                                alerts_to_send.append((name, value))
                                last_alerted_levels.append(name)
                            elif name not in ['P_UP', 'P_DOWN']:
                                alerts_to_send.append((name, value))
                                last_alerted_levels.append(name)

                    # 5. Guardar Estado
                    state['levels'] = levels
                    state['alerted_levels'] = last_alerted_levels
                    state['current_zone'] = zone_name
                    update_symbol_state(symbol, state)
                    
                    # 6. Enviar Alertas
                    if alerts_to_send and VALERTS_SENDER:
                        subscribers = get_valerts_subscribers(symbol)
                        if subscribers:
                            for lname, lval in alerts_to_send:
                                context = get_alert_context(lname, current_price, levels, symbol)
                                
                                decimals = 2 if current_price > 100 else 4
                                fmt = f",.{decimals}f"
                                
                                # --- CORRECCIÓN CRÍTICA DE MARKDOWN ---
                                # "Sanitizamos" el nombre del nivel para que no rompa el Markdown
                                # Si lname es "P_UP", se convierte en "P UP" (sin guion bajo)
                                display_level_name = lname.replace("_", " ") 
                                # O si prefieres mantener el guion bajo visualmente, usa:
                                # display_level_name = lname.replace("_", "\\_")

                                # Construir mensaje
                                msg = (
                                    f"{context['emoji']} *{context['titulo']}*\n"
                                    f"—————————————————\n"
                                    f"{context['descripcion']}\n\n"
                                    f"*Análisis Técnico:*\n"
                                    f"`{context['tecnico']}`\n\n"
                                    f"*Detalles del Cruce:*\n"
                                    # AQUÍ USAMOS LA VARIABLE SANITIZADA display_level_name
                                    f"🏷️ Nivel: {display_level_name} (${lval:{fmt}})\n"
                                    f"💰 Precio: ${current_price:{fmt}}\n"
                                    f"🎯 Próximo: {context['proximo'][0]} ({context['proximo'][1]})\n\n"
                                    f"✍️ *Recomendación:* {context['recomendacion']}\n\n"
                                    f"{zone_emoji} Zona: {zone_name}\n"
                                    f"⏳ Marco: 4H"
                                )
                                
                                msg += get_random_ad_text()
                                
                                kb = [[InlineKeyboardButton("📊 Ver Tabla de Niveles", callback_data=f"valerts_view|{symbol}")]]
                                
                                await VALERTS_SENDER(msg, subscribers, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(kb))
                                await asyncio.sleep(0.05)

                except Exception as e:
                    # print(f"Error procesando {symbol}: {e}")
                    add_log_line(f"❌ Error en Valerts Loop ({symbol}): {e}")
                    
            await asyncio.sleep(60)

        except Exception as e:
            add_log_line(f"❌ Error crítico en Valerts Loop: {e}")
            await asyncio.sleep(60)