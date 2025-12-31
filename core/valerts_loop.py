# core/valerts_loop.py

import asyncio
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
from core.btc_advanced_analysis import BTCAdvancedAnalyzer
from handlers.valerts_handlers import get_kline_data 

# Variable global para la función de envío
_sender_func = None

def set_valerts_sender(func):
    global _sender_func
    _sender_func = func

def fmt_price(p):
    """Formatea precios dinámicamente (para manejar desde PEPE a BTC)."""
    if not isinstance(p, (int, float)): return "0.00"
    if p < 0.01: return f"{p:.8f}" 
    if p < 100: return f"{p:.4f}"
    return f"{p:,.2f}"

async def valerts_monitor_loop(bot):
    """
    Monitor Multi-Moneda PRO (Estilo BTC Alert).
    Incluye lógica de Sesión, Niveles Dinámicos y Alertas Ricas.
    """
    add_log_line("🦁 Iniciando Monitor Valerts PRO (Smart Logic Multi-Coin)...")
    
    # Definimos las temporalidades a monitorear
    TIMEFRAMES = ["1h", "4h", "12h", "1d"]
    
    while True:
        try:
            active_symbols = get_active_symbols()
            
            # Si no hay nadie suscrito a nada, esperamos y reintentamos
            if not active_symbols:
                await asyncio.sleep(30)
                continue
            
            for symbol in active_symbols:
                display_sym = symbol.replace("USDT", "") # Ej: ETH
                
                for interval in TIMEFRAMES:
                    
                    # 1. Validación de Suscriptores
                    subs = get_valerts_subscribers(symbol, interval)
                    if not subs: 
                        continue
                    
                    # 2. Obtención de Datos
                    # Usamos limit=300 para asegurar cálculos correctos de EMAs
                    df = get_kline_data(symbol, interval, limit=300)
                    if df is None or len(df) < 100: 
                        continue
                    
                    # Datos básicos de velas
                    last_closed = df.iloc[-2]
                    curr_candle = df.iloc[-1]
                    candle_time = int(last_closed['open_time'])
                    current_price = float(curr_candle['close'])
                    
                    # 3. Análisis Técnico Avanzado
                    analyzer = BTCAdvancedAnalyzer(df)
                    levels_fib = analyzer.get_support_resistance_dynamic(interval=interval)
                    momentum_signal, mom_emoji, (buy_score, sell_score), reasons = analyzer.get_momentum_signal()
                    divergence = analyzer.detect_rsi_divergence(lookback=5)
                    
                    # 4. Gestión de Estado (Persistencia)
                    current_state = get_symbol_state(symbol, interval)
                    last_saved_time = current_state.get('last_candle_time', 0)
                    loaded_levels = current_state.get('levels', {})
                    
                    # Detectar cambio de vela
                    is_new_candle = candle_time > last_saved_time
                    state_changed = False
                    
                    # ==============================================================================
                    # FASE 1: GESTIÓN DE NUEVA VELA (Reporte de Sesión)
                    # ==============================================================================
                    if is_new_candle or not loaded_levels:
                        
                        # Actualizamos estado en memoria
                        current_state['levels'] = levels_fib
                        current_state['last_candle_time'] = candle_time
                        
                        # --- LÓGICA INTELIGENTE DE POSICIONAMIENTO ---
                        pre_filled_alerts = []
                        status_msg = ""
                        status_icon = "⚖️"
                        
                        # A) ANÁLISIS ALCISTA
                        if current_price >= levels_fib['R3']:
                            pre_filled_alerts.extend(['P_UP', 'R1', 'R2', 'R3'])
                            status_msg = f"Euforia en {display_sym}. Sesión sobre R3."
                            status_icon = "🚀"
                        elif current_price >= levels_fib['R2']:
                            pre_filled_alerts.extend(['P_UP', 'R1', 'R2'])
                            status_msg = f"Momentum fuerte. {display_sym} sobre R2."
                            status_icon = "🌊"
                        elif current_price >= levels_fib['R1']:
                            pre_filled_alerts.extend(['P_UP', 'R1'])
                            status_msg = f"Tendencia alcista. Soporte en R1."
                            status_icon = "📈"
                        elif current_price >= levels_fib['P']:
                            pre_filled_alerts.append('P_UP')
                            status_msg = f"Sesgo Positivo. Sobre Pivot."
                            status_icon = "✅"
                            
                        # B) ANÁLISIS BAJISTA
                        elif current_price <= levels_fib['S3']:
                            pre_filled_alerts.extend(['P_DOWN', 'S1', 'S2', 'S3'])
                            status_msg = f"Pánico extremo. {display_sym} bajo S3."
                            status_icon = "🕳️"
                        elif current_price <= levels_fib['S2']:
                            pre_filled_alerts.extend(['P_DOWN', 'S1', 'S2'])
                            status_msg = f"Debilidad fuerte. Atrapado bajo S2."
                            status_icon = "🩸"
                        elif current_price <= levels_fib['S1']:
                            pre_filled_alerts.extend(['P_DOWN', 'S1'])
                            status_msg = f"Tendencia bajista. Bajo soporte S1."
                            status_icon = "📉"
                        elif current_price < levels_fib['P']: 
                            pre_filled_alerts.append('P_DOWN')
                            status_msg = f"Sesgo Negativo. Bajo Pivot."
                            status_icon = "⚠️"

                        # C) GOLDEN POCKET
                        if current_price >= levels_fib['FIB_618']:
                            if 'FIB_618_UP' not in pre_filled_alerts: pre_filled_alerts.append('FIB_618_UP')
                        else:
                            if 'FIB_618_DOWN' not in pre_filled_alerts: pre_filled_alerts.append('FIB_618_DOWN')

                        current_state['alerted_levels'] = pre_filled_alerts
                        state_changed = True
                        
                        # --- ENVÍO DEL REPORTE DE SESIÓN (NUEVO EN VALERTS) ---
                        if _sender_func:
                            msg_session = (
                                f"🔄 *Actualización {display_sym} ({interval.upper()})*\n"
                                f"—————————————————\n"
                                f"{status_icon} *Estado:* _{status_msg}_\n\n"
                                f"📊 *Nuevos Niveles Calculados:*\n"
                                f"🛡️ R3: `${fmt_price(levels_fib['R3'])}`\n"
                                f"🛡️ R2: `${fmt_price(levels_fib['R2'])}`\n"
                                f"🛡️ R1: `${fmt_price(levels_fib['R1'])}`\n"
                                f"🟡 G. Pocket: `${fmt_price(levels_fib['FIB_618'])}`\n" 
                                f"⚖️ Pivot: `${fmt_price(levels_fib['P'])}`\n"
                                f"🛡️ S1: `${fmt_price(levels_fib['S1'])}`\n"
                                f"🛡️ S2: `${fmt_price(levels_fib['S2'])}`\n"
                                f"🛡️ S3: `${fmt_price(levels_fib['S3'])}`\n\n"
                                f"💰 *Precio Actual:* `${fmt_price(current_price)}`\n"
                                f"🌊 *Tendencia:* {mom_emoji} {momentum_signal}\n"
                            )
                            msg_session += get_random_ad_text()
                            
                            # Botón para ver análisis completo
                            kb = [[InlineKeyboardButton(f"📊 Ver Análisis {display_sym}", callback_data=f"valerts_view|{symbol}|BINANCE|{interval}")]]
                            
                            await _sender_func(msg_session, subs, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)

                    else:
                        # Si no es nueva vela, actualizamos precio para referencias futuras
                        if 'levels' in current_state and current_state['levels']:
                            current_state['levels']['current_price'] = current_price
                            state_changed = True

                    # ==============================================================================
                    # FASE 2: MONITOREO DE CRUCES EN VIVO (Alertas Ricas)
                    # ==============================================================================
                    
                    levels = current_state.get('levels', {})
                    alerted = current_state.get('alerted_levels', [])
                    
                    if not levels: continue 
                    
                    threshold = 0.001 
                    trigger_level = None
                    alert_data = {} 

                    # --- RUPTURAS ALCISTAS ---
                    if current_price > levels['R3'] * (1 + threshold) and "R3" not in alerted:
                        trigger_level = "R3"
                        alert_data = {
                            'emoji': '🚀', 'titulo': f'Ruptura R3 {display_sym} ({interval.upper()})',
                            'descripcion': f'{display_sym} en zona de extensión máxima. Posible agotamiento.',
                            'icon_nivel': '🧗', 'icon_precio': '💰', 'icon_target': '🌌', 'icon_rec': '⚡',
                            'target_siguiente': levels['R3'] * 1.05,
                            'recomendacion': 'Zona de toma de ganancias.'
                        }
                    
                    elif current_price > levels['R2'] * (1 + threshold) and "R2" not in alerted:
                        trigger_level = "R2"
                        alert_data = {
                            'emoji': '🌊', 'titulo': f'R2 Superado {display_sym} ({interval.upper()})',
                            'descripcion': 'Ruptura de expansión Fibonacci. Momentum sólido.',
                            'icon_nivel': '🔺', 'icon_precio': '💰', 'icon_target': '🎯', 'icon_rec': '✅',
                            'target_siguiente': levels['R3'],
                            'recomendacion': 'Buscar continuación hacia R3.'
                        }
                    
                    elif current_price > levels['R1'] * (1 + threshold) and "R1" not in alerted:
                        trigger_level = "R1"
                        alert_data = {
                            'emoji': '📈', 'titulo': f'R1 Superado {display_sym} ({interval.upper()})',
                            'descripcion': 'El precio entra en zona de fortaleza alcista.',
                            'icon_nivel': '📍', 'icon_precio': '💹', 'icon_target': '🎯', 'icon_rec': '🔝',
                            'target_siguiente': levels['R2'],
                            'recomendacion': 'Mantener largos con stop bajo Pivot.'
                        }

                    elif current_price > levels['FIB_618'] * (1 + threshold) and "FIB_618_UP" not in alerted:
                        trigger_level = "FIB_618_UP"
                        alert_data = {
                            'emoji': '🟡', 'titulo': f'Golden Pocket {display_sym} ({interval.upper()})',
                            'descripcion': 'Supera el 61.8% Fibonacci. Señal de reversión.',
                            'icon_nivel': '🔱', 'icon_precio': '💰', 'icon_target': '🎯', 'icon_rec': '💎',
                            'target_siguiente': levels['R1'],
                            'recomendacion': 'Soporte institucional detectado.'
                        }

                    elif current_price > levels['P'] * (1 + threshold) and "P_UP" not in alerted:
                        trigger_level = "P_UP"
                        alert_data = {
                            'emoji': '⚖️', 'titulo': f'{display_sym} Recupera Pivot',
                            'descripcion': 'Cruce del equilibrio hacia arriba.',
                            'icon_nivel': '⚖️', 'icon_precio': '↗️', 'icon_target': '➡️', 'icon_rec': '👀',
                            'target_siguiente': levels['R1'],
                            'recomendacion': 'Sesgo intradía positivo.'
                        }

                    # --- RUPTURAS BAJISTAS ---
                    elif current_price < levels['S3'] * (1 - threshold) and "S3" not in alerted:
                        trigger_level = "S3"
                        alert_data = {
                            'emoji': '🕳️', 'titulo': f'S3 Perforado {display_sym} ({interval.upper()})',
                            'descripcion': 'Caída libre extendida. Precaución.',
                            'icon_nivel': '🧗', 'icon_precio': '💸', 'icon_target': '⬇️', 'icon_rec': '⚠️',
                            'target_siguiente': levels['S3'] * 0.95,
                            'recomendacion': 'Esperar rebote por sobreventa extrema.'
                        }

                    elif current_price < levels['S2'] * (1 - threshold) and "S2" not in alerted:
                        trigger_level = "S2"
                        alert_data = {
                            'emoji': '🩸', 'titulo': f'S2 Perforado {display_sym} ({interval.upper()})',
                            'descripcion': 'Pérdida de soporte estructural mayor.',
                            'icon_nivel': '🔻', 'icon_precio': '💸', 'icon_target': '🔴', 'icon_rec': '🛑',
                            'target_siguiente': levels['S3'],
                            'recomendacion': 'Debilidad fuerte. No comprar aún.'
                        }

                    elif current_price < levels['S1'] * (1 - threshold) and "S1" not in alerted:
                        trigger_level = "S1"
                        alert_data = {
                            'emoji': '📉', 'titulo': f'S1 Perdido {display_sym} ({interval.upper()})',
                            'descripcion': 'Caída bajo el primer soporte clave.',
                            'icon_nivel': '📍', 'icon_precio': '📉', 'icon_target': '🔽', 'icon_rec': '⚠️',
                            'target_siguiente': levels['S2'],
                            'recomendacion': 'Precaución con largos.'
                        }

                    elif current_price < levels['FIB_618'] * (1 - threshold) and "FIB_618_DOWN" not in alerted:
                        trigger_level = "FIB_618_DOWN"
                        alert_data = {
                            'emoji': '💀', 'titulo': f'Pierde G. Pocket {display_sym} ({interval.upper()})',
                            'descripcion': 'Pierde el 61.8% Fibonacci. Compradores ceden.',
                            'icon_nivel': '🔱', 'icon_precio': '💸', 'icon_target': '🔽', 'icon_rec': '🆘',
                            'target_siguiente': levels['S2'],
                            'recomendacion': 'Riesgo de capitulación.'
                        }

                    elif current_price < levels['P'] * (1 - threshold) and "P_DOWN" not in alerted:
                        trigger_level = "P_DOWN"
                        alert_data = {
                            'emoji': '⚖️', 'titulo': f'{display_sym} Pierde Pivot',
                            'descripcion': 'Cruce del equilibrio hacia abajo.',
                            'icon_nivel': '⚖️', 'icon_precio': '↘️', 'icon_target': '⬅️', 'icon_rec': '👁️',
                            'target_siguiente': levels['S1'],
                            'recomendacion': 'Sesgo intradía negativo.'
                        }

                    # --- CONSTRUCCIÓN Y ENVÍO DEL MENSAJE (RICH ALERT) ---
                    if trigger_level and _sender_func and alert_data:
                        # Recuperamos el precio del nivel limpio (sin _UP/_DOWN)
                        clean_code = trigger_level.replace('_UP', '').replace('_DOWN', '')
                        level_price = levels.get(clean_code, 0)

                        msg = (
                            f"{alert_data['emoji']} *{alert_data['titulo']}*\n"
                            f"—————————————————\n"
                            f"📊 {alert_data['descripcion']}\n\n"
                            f"*Contexto Técnico:*\n"
                            f"{mom_emoji} Momentum: {momentum_signal}\n"
                            f"⚖️ Score: {buy_score} Compra | {sell_score} Venta\n"
                        )
                        
                        # Razones clave y Divergencias
                        if reasons:
                            msg += f"• _Clave: {reasons[0]}_\n"
                        if divergence:
                            d_type, d_text = divergence
                            d_icon = "🐂" if d_type == "BULLISH" else "🐻"
                            msg += f"{d_icon} *Divergencia:* {d_text}\n"
                        msg += "\n"

                        msg += (
                            f"*Detalles del Cruce:*\n"
                            f"{alert_data['icon_nivel']} Nivel: `{clean_code}` (${fmt_price(level_price)})\n"
                            f"{alert_data['icon_precio']} Precio: `${fmt_price(current_price)}`\n"
                            f"{alert_data['icon_target']} Objetivo: `${fmt_price(alert_data['target_siguiente'])}`\n\n"
                            f"{alert_data['icon_rec']} *Recomendación:*\n"
                            f"_{alert_data['recomendacion']}_\n\n"
                            f"⏳ *Marco Temporal:* {interval.upper()}"
                        )
                        
                        msg += get_random_ad_text()
                        
                        # Botón para ir al análisis
                        kb = [[InlineKeyboardButton(f"📊 Ver Análisis {display_sym}", callback_data=f"valerts_view|{symbol}|BINANCE|{interval}")]]
                        
                        await _sender_func(msg, subs, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)
                        
                        # Actualizar estado para no repetir
                        current_state['alerted_levels'].append(trigger_level)
                        state_changed = True
                        add_log_line(f"🚨 Alerta Valerts Enviada: {symbol} {trigger_level} ({interval})")

                    # Si hubo cambios, guardamos en disco (un guardado por ciclo para eficiencia)
                    if state_changed:
                        update_symbol_state(symbol, interval, current_state)
                        
                    await asyncio.sleep(0.1) # Pequeña pausa entre TFs del mismo symbol
                
                await asyncio.sleep(0.5) # Pausa entre símbolos
            
            await asyncio.sleep(30) # Espera antes del siguiente ciclo general
            
        except Exception as e:
            add_log_line(f"❌ Error en Valerts Monitor Loop: {e}")
            import traceback
            traceback.print_exc()
            await asyncio.sleep(60)
