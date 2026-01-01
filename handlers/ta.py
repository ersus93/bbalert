# handlers/ta.py

import asyncio
import requests
import json
import pytz 
import pandas as pd
import pandas_ta as ta
from io import BytesIO
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from tradingview_ta import TA_Handler, Interval, Exchange
from core.ai_logic import get_groq_crypto_analysis
# Importamos configuraciones y utilidades existentes
from core.config import ADMIN_CHAT_IDS
from utils.file_manager import (
    add_log_line, check_feature_access, registrar_uso_comando
)
from utils.ads_manager import get_random_ad_text
from core.i18n import _
from core.btc_advanced_analysis import BTCAdvancedAnalyzer



# === NUEVO COMANDO /ta MEJORADO ===

def get_binance_klines(symbol, interval, limit=500): 
    """
    Obtiene velas de Binance (Global o US). 
    Limit reducido a 500 por defecto para rapidez, el Analyzer usa internamente lo necesario.
    """
    endpoints = [
        "https://api.binance.com/api/v3/klines", 
        "https://api.binance.us/api/v3/klines"
    ]
    for url in endpoints:
        params = {"symbol": symbol, "interval": interval, "limit": limit}
        try:
            response = requests.get(url, params=params, timeout=5)
            response.raise_for_status()
            data = response.json()
            if not data or not isinstance(data, list): continue
            
            df = pd.DataFrame(data, columns=[
                "open_time", "open", "high", "low", "close", "volume",
                "close_time", "quote_asset_volume", "trades", 
                "taker_base", "taker_quote", "ignore"
            ])
            cols = ["open", "high", "low", "close", "volume"]
            df[cols] = df[cols].apply(pd.to_numeric, errors='coerce')
            
            # Convertir tiempo para el Analyzer
            df['time'] = pd.to_datetime(df['open_time'], unit='ms')
            df.set_index('time', inplace=True)
            
            return df
        except Exception:
            continue
    return None

def calculate_table_indicators(df):
    """
    Calcula SOLO los indicadores necesarios para la TABLA visual (Historial).
    El análisis lógico (Señales) se delegará al BTCAdvancedAnalyzer.
    """
    # Helper seguro
    def safe_ind(name, series):
        try:
            df[name] = series if series is not None else 0.0
        except:
            df[name] = 0.0

    # Indicadores específicos para la tabla
    safe_ind('RSI', df.ta.rsi(length=14))
    safe_ind('MFI', df.ta.mfi(length=14))
    safe_ind('CCI', df.ta.cci(length=20)) # Estándar suele ser 20 para CCI
    safe_ind('ADX', df.ta.adx(length=14)['ADX_14']) # ADX devuelve DF
    safe_ind('WILLR', df.ta.willr(length=14))
    safe_ind('OBV', df.ta.obv())
    
    # Devolvemos las últimas 3 filas para construir la tabla (Actual, Previo, Ante-previo)
    return df.iloc[-3:]

def get_tradingview_analysis_enhanced(symbol_pair, interval_str):
    """
    Fallback a TradingView mejorado para obtener SCORE y SEÑALES.
    """
    interval_map = {
        "1m": Interval.INTERVAL_1_MINUTE, "5m": Interval.INTERVAL_5_MINUTES,
        "15m": Interval.INTERVAL_15_MINUTES, "1h": Interval.INTERVAL_1_HOUR,
        "4h": Interval.INTERVAL_4_HOURS, "1d": Interval.INTERVAL_1_DAY,
        "1w": Interval.INTERVAL_1_WEEK, "1M": Interval.INTERVAL_1_MONTH
    }
    tv_interval = interval_map.get(interval_str, Interval.INTERVAL_1_HOUR)
    
    try:
        # Intentar Binance primero
        handler = TA_Handler(symbol=symbol_pair, screener="crypto", exchange="BINANCE", interval=tv_interval)
        analysis = handler.get_analysis()
    except:
        try:
            # Fallback a GateIO o genérico
            handler = TA_Handler(symbol=symbol_pair, screener="crypto", exchange="GATEIO", interval=tv_interval)
            analysis = handler.get_analysis()
        except:
            return None

    if not analysis: return None

    ind = analysis.indicators
    summ = analysis.summary # Aquí están los contadores BUY/SELL
    
    return {
        'source': 'TradingView',
        'close': ind.get('close', 0),
        'volume': ind.get('volume', 0),
        # Datos para tabla (TV solo da el actual, rellenaremos ceros en el comando)
        'RSI': ind.get('RSI', 0),
        'MFI': ind.get('MFI', 0) or 0, # TV a veces no da MFI directo en standard
        'CCI': ind.get('CCI20', 0),
        'ADX': ind.get('ADX', 0),
        'WR': ind.get('W.R', 0),
        'OBV': ind.get('OBV', 0) or ind.get('volume', 0), # Fallback to vol
        
        # Datos para Niveles
        'Pivot': ind.get('Pivot.M.Classic.Middle', 0),
        'R1': ind.get('Pivot.M.Classic.R1', 0), 'R2': ind.get('Pivot.M.Classic.R2', 0), 'R3': ind.get('Pivot.M.Classic.R3', 0),
        'S1': ind.get('Pivot.M.Classic.S1', 0), 'S2': ind.get('Pivot.M.Classic.S2', 0), 'S3': ind.get('Pivot.M.Classic.S3', 0),
        
        # Datos para Score/Señal
        'RECOMMENDATION': summ.get('RECOMMENDATION', 'NEUTRAL'),
        'BUY_SCORE': summ.get('BUY', 0),
        'SELL_SCORE': summ.get('SELL', 0),
        'NEUTRAL_SCORE': summ.get('NEUTRAL', 0),
        
        # Extras visuales
        'MACD_hist': ind.get('MACD.hist', 0),
        'SMA_50': ind.get('SMA50', 0),
        'EMA_200': ind.get('EMA200', 0)
    }

def get_binance_klines(symbol, interval, limit=500): 
    """Obtiene velas de Binance (Global o US)."""
    endpoints = [
        "https://api.binance.com/api/v3/klines", 
        "https://api.binance.us/api/v3/klines"
    ]
    for url in endpoints:
        params = {"symbol": symbol, "interval": interval, "limit": limit}
        try:
            response = requests.get(url, params=params, timeout=3) # Timeout rápido para UX
            if response.status_code != 200: continue
            data = response.json()
            if not data or not isinstance(data, list): continue
            
            df = pd.DataFrame(data, columns=[
                "open_time", "open", "high", "low", "close", "volume",
                "close_time", "quote_asset_volume", "trades", 
                "taker_base", "taker_quote", "ignore"
            ])
            cols = ["open", "high", "low", "close", "volume"]
            df[cols] = df[cols].apply(pd.to_numeric, errors='coerce')
            df['time'] = pd.to_datetime(df['open_time'], unit='ms')
            df.set_index('time', inplace=True)
            return df
        except Exception:
            continue
    return None

def calculate_table_indicators(df):
    """Calcula indicadores visuales para la tabla."""
    def safe_ind(name, series):
        try: df[name] = series if series is not None else 0.0
        except: df[name] = 0.0

    safe_ind('RSI', df.ta.rsi(length=14))
    safe_ind('MFI', df.ta.mfi(length=14))
    safe_ind('CCI', df.ta.cci(length=20))
    try: safe_ind('ADX', df.ta.adx(length=14)['ADX_14'])
    except: df['ADX'] = 0.0
    safe_ind('WILLR', df.ta.willr(length=14))
    safe_ind('OBV', df.ta.obv())
    return df.iloc[-3:]

def get_tradingview_analysis_enhanced(symbol_pair, interval_str):
    """Fallback a TradingView para obtener Score y Señales."""
    interval_map = {
        "1m": Interval.INTERVAL_1_MINUTE, "5m": Interval.INTERVAL_5_MINUTES,
        "15m": Interval.INTERVAL_15_MINUTES, "1h": Interval.INTERVAL_1_HOUR,
        "4h": Interval.INTERVAL_4_HOURS, "1d": Interval.INTERVAL_1_DAY,
        "1w": Interval.INTERVAL_1_WEEK, "1M": Interval.INTERVAL_1_MONTH
    }
    tv_interval = interval_map.get(interval_str, Interval.INTERVAL_1_HOUR)
    
    try:
        handler = TA_Handler(symbol=symbol_pair, screener="crypto", exchange="BINANCE", interval=tv_interval)
        analysis = handler.get_analysis()
    except:
        try:
            handler = TA_Handler(symbol=symbol_pair, screener="crypto", exchange="GATEIO", interval=tv_interval)
            analysis = handler.get_analysis()
        except:
            return None

    if not analysis: return None
    ind = analysis.indicators
    summ = analysis.summary 
    return {
        'source': 'TradingView',
        'close': ind.get('close', 0),
        'volume': ind.get('volume', 0),
        'RSI': ind.get('RSI', 0),
        'MFI': ind.get('MFI', 0) or 0,
        'CCI': ind.get('CCI20', 0),
        'ADX': ind.get('ADX', 0),
        'WR': ind.get('W.R', 0),
        'OBV': ind.get('OBV', 0) or ind.get('volume', 0),
        'Pivot': ind.get('Pivot.M.Classic.Middle', 0),
        'R1': ind.get('Pivot.M.Classic.R1', 0), 'R2': ind.get('Pivot.M.Classic.R2', 0), 'R3': ind.get('Pivot.M.Classic.R3', 0),
        'S1': ind.get('Pivot.M.Classic.S1', 0), 'S2': ind.get('Pivot.M.Classic.S2', 0), 'S3': ind.get('Pivot.M.Classic.S3', 0),
        'RECOMMENDATION': summ.get('RECOMMENDATION', 'NEUTRAL'),
        'BUY_SCORE': summ.get('BUY', 0),
        'SELL_SCORE': summ.get('SELL', 0),
        'MACD_hist': ind.get('MACD.hist', 0),
        'SMA_50': ind.get('SMA50', 0),
        'ATR': ind.get('ATR', 0)
    }

async def ta_command(update: Update, context: ContextTypes.DEFAULT_TYPE, override_source=None, override_args=None):
    """
    Controlador maestro de Análisis Técnico con soporte para Switch de Fuente.
    """
    user_id = update.effective_user.id
    is_callback = update.callback_query is not None
    message = update.effective_message

    # === ARGUMENT PARSING ===
    if is_callback and override_args:
        # Formato args: [SYMBOL, PAIR, TIME]
        symbol_base, pair, timeframe = override_args
        full_symbol = f"{symbol_base}{pair}"
        target_source = override_source # BINANCE o TV
    else:
        # Comando normal: /ta BTC USDT 4h TV
        if not context.args:
            await message.reply_text(_("⚠️ Uso: `/ta <SYMBOL> [PAR] [TIME] [TV]`", user_id), parse_mode=ParseMode.MARKDOWN)
            return
        
        raw_args = [arg.upper() for arg in context.args]
        target_source = "TV" if "TV" in raw_args else "BINANCE"
        if "TV" in raw_args: raw_args.remove("TV")
        
        symbol_base = raw_args[0]
        pair = "USDT"
        timeframe = "1h"
        
        if len(raw_args) > 1:
            for arg in raw_args[1:]:
                if arg[-1].lower() in ['m', 'h', 'd', 'w']:
                    timeframe = arg.lower()
                else:
                    pair = arg
        full_symbol = f"{symbol_base}{pair}"

    # === MENSAJE DE ESPERA ===
    if is_callback:
        # Si es callback, no mandamos mensaje nuevo, editaremos el existente.
        # Pero primero validamos disponibilidad si se pide LOCAL
        if target_source == "BINANCE":
            # Chequeo rápido de existencia
            # NOTA: Hacemos esto antes de borrar nada para poder cancelar si falla
            loop = asyncio.get_running_loop()
            check_df = await loop.run_in_executor(None, get_binance_klines, full_symbol, timeframe, 50)
            if check_df is None or check_df.empty:
                await update.callback_query.answer("❌ No disponible en Binance Local", show_alert=True)
                return # IMPORTANTE: Detenemos ejecución aquí, el mensaje anterior se mantiene intacto
    else:
        msg_wait = await message.reply_text(f"⏳ _Analizando {full_symbol} ({timeframe})..._", parse_mode=ParseMode.MARKDOWN)

    # === LÓGICA DE OBTENCIÓN DE DATOS ===
    loop = asyncio.get_running_loop()
    final_data = {}
    data_source_display = ""
    reasons_list = []
    
    # Valores por defecto
    signal_emoji, signal_text = "⚖️", "NEUTRAL"
    score_buy, score_sell = 0, 0
    
    df_result = None

    # 1. INTENTO BINANCE (Si se solicitó)
    if target_source == "BINANCE":
        df_result = await loop.run_in_executor(None, get_binance_klines, full_symbol, timeframe)
        
        if df_result is not None:
            data_source_display = "Binance (Local PRO)"
            # A) TABLA
            last_3 = await loop.run_in_executor(None, calculate_table_indicators, df_result.copy())
            
            # B) ANÁLISIS
            analyzer = BTCAdvancedAnalyzer(df_result)
            sig, emo, (sb, ss), reasons = analyzer.get_momentum_signal()
            curr_vals = analyzer.get_current_values()
            
            signal_emoji, signal_text = emo, sig
            score_buy, score_sell = sb, ss
            reasons_list = reasons
            
            curr = last_3.iloc[-1]
            prev = last_3.iloc[-2]
            pprev = last_3.iloc[-3]

            # === CAMBIO: CÁLCULO DE NIVELES CON 10 VELAS ===
            # 1. Tomamos las últimas 10 velas del dataframe original
            last_10 = df_result.tail(10)
            
            # 2. Obtenemos el Máximo y Mínimo de ese rango de 10 velas
            period_high = last_10['high'].max()
            period_low = last_10['low'].min()
            period_close = last_10['close'].iloc[-1] # El cierre sigue siendo el actual
            
            # 3. Calculamos el Pivote y el Rango basados en esas 10 velas
            pivot_val = (period_high + period_low + period_close) / 3
            rango_val = period_high - period_low

            final_data = {
                'close': curr['close'], 'volume': curr['volume'], 'ATR': curr_vals.get('ATR', 0),
                'RSI_list': [curr.get('RSI', 0), prev.get('RSI', 0), pprev.get('RSI', 0)],
                'MFI_list': [curr.get('MFI', 0), prev.get('MFI', 0), pprev.get('MFI', 0)],
                'CCI_list': [curr.get('CCI', 0), prev.get('CCI', 0), pprev.get('CCI', 0)],
                'ADX_list': [curr.get('ADX', 0), prev.get('ADX', 0), pprev.get('ADX', 0)],
                'WR_list':  [curr.get('WILLR', 0), prev.get('WILLR', 0), pprev.get('WILLR', 0)],
                'OBV_list': [curr.get('OBV', 0), prev.get('OBV', 0), pprev.get('OBV', 0)],
                'MACD_hist': curr_vals.get('MACD_HIST', 0),
                'SMA_50': curr_vals.get('EMA_50', 0),
                
                # Guardamos los valores calculados con las 10 velas
                'Pivot': pivot_val,
                'Rango': rango_val
            }
            
            # 4. Actualizamos los niveles R y S usando Fibonacci sobre el rango de 10 velas
            p = final_data['Pivot']
            r = final_data['Rango']
            
            final_data.update({
                'R1': p + (r * 0.382), 
                'R2': p + (r * 0.618),
                'R3': p + (r * 1.272),
                'S1': p - (r * 0.382),
                'S2': p - (r * 0.618),
                'S3': p - (r * 1.272)
            })

    # 2. INTENTO TRADINGVIEW (Fallback o Solicitud Directa)
    used_tv = False
    if df_result is None:
        # Si falló Binance (o se pidió TV), vamos a TV
        used_tv = True
        tv_data = await loop.run_in_executor(None, get_tradingview_analysis_enhanced, full_symbol, timeframe)
        
        if tv_data:
            data_source_display = "TradingView API"
            final_data = tv_data
            
            # Interpretar señales TV
            rec = final_data.get('RECOMMENDATION', '')
            if "STRONG_BUY" in rec: signal_emoji, signal_text = "🚀", "COMPRA FUERTE"
            elif "BUY" in rec: signal_emoji, signal_text = "🐂", "COMPRA"
            elif "STRONG_SELL" in rec: signal_emoji, signal_text = "🐻", "VENTA FUERTE"
            elif "SELL" in rec: signal_emoji, signal_text = "📉", "VENTA"
            
            score_buy = final_data.get('BUY_SCORE', 0)
            score_sell = final_data.get('SELL_SCORE', 0)
            
            # Rellenar listas con ceros
            for k in ['RSI', 'MFI', 'CCI', 'ADX', 'WR', 'OBV']:
                val = final_data.get(k, 0) or 0
                final_data[f'{k}_list'] = [val, 0, 0]
        else:
            err_txt = _("❌ No se encontraron datos para *{s}* ni en Binance ni en TV.", user_id).format(s=full_symbol)
            if is_callback:
                await update.callback_query.answer("❌ Datos no encontrados", show_alert=True)
            else:
                await msg_wait.edit_text(err_txt, parse_mode=ParseMode.MARKDOWN)
            return
    
    

    # === CONSTRUCCIÓN DEL MENSAJE ===
    def fmt_cell(val, width=7):
        if val is None or pd.isna(val) or val == 0: return "   --  ".center(width)
        try:
            f = float(val)
            if abs(f) > 10000: return f"{f/1000:.1f}k".rjust(width)
            elif abs(f) > 999: return f"{f:.0f}".rjust(width)
            else: return f"{f:.2f}".rjust(width)
        except: return "   --  ".center(width)

    table_msg = "```text\nIND     ACTUAL   PREVIO     ANT.\n──────  ───────  ───────  ───────\n"
    rows = [("RSI", 'RSI_list'), ("MFI", 'MFI_list'), ("CCI", 'CCI_list'), ("WR%", 'WR_list'), ("ADX", 'ADX_list'), ("OBV", 'OBV_list')]
    for l, k in rows:
        v = final_data.get(k, [0,0,0])
        table_msg += f"{l:<6} {fmt_cell(v[0])}  {fmt_cell(v[1])}  {fmt_cell(v[2])}\n"
    table_msg += "```"

    # 1. Definimos el precio ANTES de usarlo en los if
    price = final_data.get('close', 0)

    # 2. Inicializamos valores por defecto (para evitar errores si usamos TV)
    sr = {}
    kijun_val = 0
    fib_val = 0
    zone = "⚖️ NEUTRAL (TV)"
    kijun_icon = "➖"
    kijun_label = "N/A"
    fib_label = "N/A"

    # 3. Solo calculamos lógica avanzada si 'analyzer' existe (Modo Binance Local)
    if 'analyzer' in locals():
        sr = analyzer.get_support_resistance_dynamic()
        
        # Ichimoku Kijun
        kijun_val = sr.get('KIJUN', 0)
        if price > kijun_val:
            kijun_label = "Soporte Dinámico" 
            kijun_icon = "🛡️"
        else:
            kijun_label = "Resistencia Dinámica"
            kijun_icon = "🚧"

        # Fibonacci 0.618
        fib_val = sr.get('FIB_618', 0)
        if price > fib_val:
            fib_label = "Zona de Rebote (Bullish)"
        else:
            fib_label = "Techo de Tendencia (Bearish)"

        # Zona General
        zone = sr.get('status_zone', "⚖️ NEUTRAL")


    price = final_data.get('close', 0)
    macd_s = "Bullish 🟢" if final_data.get('MACD_hist', 0) > 0 else "Bearish 🔴"
    trend_s = "Alcista" if price > final_data.get('SMA_50', 0) else "Bajista"

    msg = (
        f"📊 *Análisis Técnico: {full_symbol}*\n"
        f"—————————————————\n"
        f"⏱ *{timeframe}* | 📡 *{data_source_display}*\n\n"
        f"{signal_emoji} *SEÑAL:* `{signal_text}`\n"
        f"⚖️ *Score:* {score_buy} Compra 🆚 {score_sell} Venta\n\n"
        f"💰 *Precio:* `${price:,.4f}`\n"
        f"📉 *ATR:* `{final_data.get('ATR', 0) or 0:.4f}`\n"
        f"•\n{table_msg}•\n"
        f"🧐 *Diagnóstico de Momentum*\n"
        f"🌊 *Tendencia:* {trend_s}\n"
        f"❌ *MACD:* {macd_s}\n"
        f"*Confluencia y Estado:*\n"
        f"📍 *Zona:* `{zone}`\n"
        f"☁️ *Ichimoku:* `${kijun_val:,.0f}`\n"
        f"   ↳ _{kijun_icon} {kijun_label}_\n"
        f"🟡 *FIB 0.618:* `${fib_val:,.0f}`\n"
        f"   ↳ _📐 {fib_label}_\n\n"
    )
    if reasons_list: msg += f"💡 *Nota:* _{reasons_list[0]}_\n"
    
    msg += (
        f"\n🛡 *Niveles (Pivotes)*\n"
        f"R3: `${final_data.get('R3', 0):,.4f}`\n"
        f"R2: `${final_data.get('R2', 0):,.4f}`\n"
        f"R1: `${final_data.get('R1', 0):,.4f}`\n"
        f"🎯 *Pivot: ${final_data.get('Pivot', 0):,.4f}*\n"
        f"S1: `${final_data.get('S1', 0):,.4f}`\n"
        f"S2: `${final_data.get('S2', 0):,.4f}`\n"
        f"S3: `${final_data.get('S3', 0):,.4f}`\n"
    )
    msg += f"\n_v2.1 Experimental_{get_random_ad_text()}"

    # === CONSTRUCCIÓN DEL BOTÓN SWITCH ===
    kb = []
    
    # 1. Definimos la fuente actual para la IA antes del IF
    current_source = "TV" if used_tv else "BINANCE"

    # 2. Botón de Cambio de Vista (Alternar entre TV y Binance)
    if used_tv:
        # Estamos en TV -> Ofrecer botón para volver a Binance
        btn_data = f"ta_switch|BINANCE|{symbol_base}|{pair}|{timeframe}"
        kb.append([InlineKeyboardButton("🦁 Ver Local (Binance)", callback_data=btn_data)])
    else:
        # Estamos en Local -> Ofrecer botón para ir a TV
        btn_data = f"ta_switch|TV|{symbol_base}|{pair}|{timeframe}"
        kb.append([InlineKeyboardButton("📊 Ver en TradingView", callback_data=btn_data)])

    # 3. Botón de Análisis IA (FUERA DEL IF para que salga SIEMPRE)
    # Lo ponemos en una fila nueva
    kb.append([
        InlineKeyboardButton(
            "🤖 Análisis IA Profesional", 
            callback_data=f"ai_analyze|{current_source}|{symbol_base}|{pair}|{timeframe}"
        )
    ])

    reply_markup = InlineKeyboardMarkup(kb)

    # === ENVÍO / EDICIÓN ===
    if is_callback:
        try:
            # Editamos el mensaje original con el nuevo contenido y teclado
            await update.callback_query.edit_message_text(
                text=msg, 
                parse_mode=ParseMode.MARKDOWN, 
                reply_markup=reply_markup
            )
        except Exception as e:
            # Si el mensaje es idéntico, Telegram lanza error, lo ignoramos
            pass
    else:
        await msg_wait.edit_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)


async def ai_analysis_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Callback del botón IA. 
    Funciona tanto para reportes de BINANCE (Local) como de TRADINGVIEW (TV).
    """
    query = update.callback_query
    await query.answer("🧠 Analizando datos...") 
    
    try:
        # 1. Extraer todos los datos del botón
        # Estructura: ['ai_analyze', SOURCE, SYMBOL, PAIR, TIMEFRAME]
        data = query.data.split("|")
        
        source = data[1]      # "BINANCE" o "TV"
        symbol = data[2]
        pair = data[3]
        timeframe = data[4]
        full_symbol = f"{symbol}{pair}"
        
        await query.message.reply_chat_action("typing")
        
        # 2. Capturar el TEXTO visible del mensaje (sea Binace o TV)
        # Si es foto (TV suele serlo), usa caption. Si es texto, usa text.
        original_report_text = query.message.caption if query.message.caption else query.message.text
        
        if not original_report_text:
             await query.message.reply_text("❌ Error: No se pudo leer el reporte en pantalla.", parse_mode=ParseMode.MARKDOWN)
             return

        # 3. Preparar el texto enriquecido para la IA
        # Le decimos explícitamente de dónde viene la data para que ajuste su análisis
        if source == "TV":
            source_context = "FUENTE: TradingView (Consenso de indicadores y medias móviles)."
        else:
            source_context = "FUENTE: Binance Local (Cálculo matemático directo del Bot)."

        final_text_for_ai = f"{source_context}\n\n{original_report_text}"

        loop = asyncio.get_running_loop()

        # 4. Llamar a la IA (usando la función que ya arreglamos antes)
        ai_response = await loop.run_in_executor(
            None, 
            get_groq_crypto_analysis, 
            full_symbol, 
            timeframe, 
            final_text_for_ai  # <--- Enviamos el texto con la etiqueta de la fuente
        )

        # 5. Enviar respuesta con encabezado dinámico
        # Usamos un icono diferente según la fuente
        icon = "📡" if source == "TV" else "📊"
        header = f"🤖 *BitBread IA* (_Experimental_)\n {icon} *{source}* | Moneda: *{full_symbol}* ({timeframe})\n—————————————————\n"
        
        await query.message.reply_text(
            header + ai_response, 
            parse_mode=ParseMode.MARKDOWN,
            reply_to_message_id=query.message.message_id
        )

    except Exception as e:
        print(f"Error en callback IA: {e}")
        try:
            await query.message.reply_text("⚠️ La IA está ocupada, intenta de nuevo.", parse_mode=ParseMode.MARKDOWN)
        except:
            pass


# === HANDLER DEL BOTÓN ===

async def ta_switch_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Maneja el clic en el botón de cambio de vista.
    Formato data: ta_switch|TARGET|SYMBOL|PAIR|TIMEFRAME
    """
    query = update.callback_query
    # No hacemos answer() aquí todavía, lo hacemos dentro de ta_command o si fallamos
    
    data = query.data.split("|")
    if len(data) < 5:
        await query.answer("❌ Datos corruptos", show_alert=True)
        return

    target = data[1]    # BINANCE o TV
    symbol = data[2]
    pair = data[3]
    timeframe = data[4]
    
    # Llamamos a la función principal pasándole los datos override
    # Esto permite reutilizar toda la lógica
    await ta_command(
        update, 
        context, 
        override_source=target, 
        override_args=[symbol, pair, timeframe]
    )