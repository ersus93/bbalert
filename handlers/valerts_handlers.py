# handlers/valerts_handlers.py

import pandas as pd
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler, CommandHandler
from telegram.constants import ParseMode
from telegram.error import BadRequest

from utils.valerts_manager import (
    is_valerts_subscribed, 
    toggle_valerts_subscription, 
    get_active_symbols
)
from utils.tv_helper import get_tv_data
from core.btc_advanced_analysis import BTCAdvancedAnalyzer
from utils.ads_manager import get_random_ad_text

# --- FETCHER DE DATOS ROBUSTO ---
def get_kline_data(symbol, interval="4h", limit=200):
    """Obtiene velas de Binance para cualquier par."""
    if not symbol.endswith("USDT") and "BTC" not in symbol: 
        symbol += "USDT"
    
    # Intentamos endpoints redundantes
    endpoints = [
        "https://api.binance.com/api/v3/klines",
        "https://api.binance.us/api/v3/klines"
    ]
    
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    
    for url in endpoints:
        try:
            r = requests.get(url, params=params, timeout=5)
            if r.status_code == 200:
                data = r.json()
                if isinstance(data, list) and len(data) > 50:
                    df = pd.DataFrame(data, columns=[
                        "open_time", "open", "high", "low", "close", "volume",
                        "c_time", "q_vol", "trades", "tb_base", "tb_quote", "ig"
                    ])
                    cols = ["open", "high", "low", "close", "volume"]
                    df[cols] = df[cols].apply(pd.to_numeric, errors='coerce')
                    # Importante: Convertir tiempo para el Analyzer
                    df['time'] = pd.to_datetime(df['open_time'], unit='ms')
                    return df
        except:
            continue
    return None

# --- TECLADO DINÁMICO (Estilo BTC) ---
def _get_valerts_keyboard(user_id, symbol, current_source="BINANCE", current_tf="4h"):
    keyboard = []
    
    # 1. Botones de Suscripción (Multi-TF)
    tfs_interest = ["1h", "4h", "12h", "1d"]
    row_subs = []
    for tf in tfs_interest:
        is_sub = is_valerts_subscribed(user_id, symbol, timeframe=tf)
        icon = "🔔" if is_sub else "🔕"
        # Callback: toggle_valerts|SYMBOL|TF
        row_subs.append(InlineKeyboardButton(f"{icon} {tf.upper()}", callback_data=f"toggle_valerts|{symbol}|{tf}"))
        if len(row_subs) == 2:
            keyboard.append(row_subs)
            row_subs = []
    if row_subs: keyboard.append(row_subs)

    # 2. Botones de Vista (Switch Timeframe)
    row_view = []
    for tf in tfs_interest:
        if tf != current_tf:
            row_view.append(InlineKeyboardButton(f"👀 Ver {tf.upper()}", callback_data=f"valerts_view|{symbol}|{current_source}|{tf}"))
    
    # Filas de 2 para vistas
    chunks = [row_view[i:i + 2] for i in range(0, len(row_view), 2)]
    for chunk in chunks:
        keyboard.append(chunk)

    # 3. Control y Fuente
    other_source = "TV" if current_source == "BINANCE" else "BINANCE"
    source_lbl = "📊 Ir a TV" if current_source == "BINANCE" else "🦁 Ir a Local"
    
    ctrl_row = [
        InlineKeyboardButton(source_lbl, callback_data=f"valerts_view|{symbol}|{other_source}|{current_tf}"),
        InlineKeyboardButton("🔙 Lista", callback_data="valerts_list_back"),
        InlineKeyboardButton("🔄", callback_data=f"valerts_view|{symbol}|{current_source}|{current_tf}")
    ]
    keyboard.append(ctrl_row)

    return InlineKeyboardMarkup(keyboard)

# --- COMANDO PRINCIPAL (ROUTER) ---

async def valerts_handler_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Router maestro: Decide si mostrar lista o análisis."""
    query = update.callback_query
    
    # Defaults
    symbol = None
    source = "BINANCE"
    tf = "4h"

    # A. CALLBACK
    if query:
        parts = query.data.split("|")
        # valerts_view|SYMBOL|SOURCE|TF
        if len(parts) >= 2: symbol = parts[1]
        if len(parts) >= 3: source = parts[2]
        if len(parts) >= 4: tf = parts[3]
    
    # B. COMANDO /valerts [ETH] [1d]
    else:
        if context.args:
            symbol = context.args[0].upper()
            if not symbol.endswith("USDT") and "BTC" not in symbol: 
                symbol += "USDT"
            
            # Segundo argumento opcional para TF
            if len(context.args) > 1:
                arg2 = context.args[1].lower()
                if arg2 in ["1h", "4h", "12h", "1d"]: tf = arg2
        else:
            await valerts_show_list(update, context)
            return

    # Si hay símbolo, mostramos análisis
    await valerts_show_analysis(update, context, symbol, source, tf)

# --- VISTA 1: LISTA ---
async def valerts_show_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    active = get_active_symbols()
    msg = (
        "🦁 *Monitor de Volatilidad Multi-Moneda*\n"
        "—————————————————\n"
        "Sistema PRO de alertas técnicas (Soportes, Resistencias, RSI).\n\n"
        "✍️ *Manual:* `/valerts ETH` o `/valerts SOL 1d`\n"
    )
    
    kb = []
    if active:
        msg += "\n*📍 Monedas activas en la comunidad:*"
        row = []
        for sym in active:
            display = sym.replace("USDT", "")
            # Default a 4h BINANCE
            row.append(InlineKeyboardButton(display, callback_data=f"valerts_view|{sym}|BINANCE|4h"))
            if len(row) == 3:
                kb.append(row)
                row = []
        if row: kb.append(row)
    else:
        msg += "\n_No hay alertas activas. ¡Crea la primera!_"
    
    reply_markup = InlineKeyboardMarkup(kb)
    
    if update.callback_query:
        await update.callback_query.edit_message_text(msg, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(msg, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)

# --- VISTA 2: ANÁLISIS PRO (REMASTERIZADO) ---
async def valerts_show_analysis(update: Update, context: ContextTypes.DEFAULT_TYPE, symbol, source, tf):
    user_id = update.effective_user.id
    display_sym = symbol.replace("USDT", "")
    
    is_sub = is_valerts_subscribed(user_id, symbol, tf)
    sub_txt = "✅ ACTIVADA" if is_sub else "☑️ DESACTIVADA"
    
    msg = ""

    # --- FUNCIÓN DE FORMATEO DINÁMICO (CRÍTICA PARA ALTS) ---
    def fmt(p): 
        """Formatea precios adaptándose a PEPE (0.0000x) o SOL (140.00)"""
        if not isinstance(p, (int, float)): return "0.00"
        if p < 0.001: return f"{p:.8f}" # Para SHIB, PEPE
        if p < 1: return f"{p:.6f}"     # Para XRP, ADA
        if p < 100: return f"{p:.4f}"   # Para SOL, LTC
        return f"{p:,.2f}"              # Para ETH, BTC (o tokens grandes)

    # ==================================================================
    # MODO LOCAL (BINANCE PRO) - Lógica Idéntica a BTC Handler
    # ==================================================================
    if source == "BINANCE":
        df = get_kline_data(symbol, tf)
        if df is None:
            msg = f"⚠️ No hay datos para {display_sym}. Prueba TradingView."
        else:
            try:
                analyzer = BTCAdvancedAnalyzer(df) # Funciona perfecto para ALTS
                curr = analyzer.get_current_values()
                sr = analyzer.get_support_resistance_dynamic(interval=tf)
                mom_sig, mom_emoji, (b, s), reasons = analyzer.get_momentum_signal()
                
                # Extracción de Datos
                price = curr['close']
                rsi_val = curr['RSI']
                
                # ADX y Tendencia
                adx = curr.get('ADX_14', curr.get('ADX', 0))
                if adx >= 50: adx_txt = "🔥 Muy Fuerte"
                elif adx >= 25: adx_txt = "💪 Fuerte"
                else: adx_txt = "💤 Rango"

                # Estocástico
                stoch_k = curr.get('stoch_k', 50) # Ojo con la mayúscula/minúscula de tu analyzer
                if stoch_k >= 80: stoch_txt = "🔴 Sobrecompra"
                elif stoch_k <= 20: stoch_txt = "🟢 Sobreventa"
                else: stoch_txt = "⚖️ Neutro"

                # MACD y EMAs
                macd_hist = curr.get('MACD_HIST', 0)
                ema_50 = curr.get('EMA_50', 0)
                ema_200 = curr.get('EMA_200', 0)

                # Etiquetas Lógicas
                if rsi_val > 70: rsi_str = "SOBRECOMPRA 🔴"
                elif rsi_val < 30: rsi_str = "SOBREVENTA 🟢"
                elif rsi_val > 50: rsi_str = "ALCISTA ↗️"
                else: rsi_str = "BAJISTA ↘️"

                trend_str = "ALCISTA (Sobre EMA50)" if price > ema_50 else "BAJISTA (Bajo EMA50)"

                # --- ETIQUETAS DINÁMICAS (Ichimoku & Fib) ---
                kijun_val = sr.get('KIJUN', 0)
                kijun_label = "Soporte Dinámico" if price > kijun_val else "Resistencia Dinámica"
                kijun_icon = "🛡️" if price > kijun_val else "🚧"

                fib_val = sr.get('FIB_618', 0)
                fib_label = "Zona Rebote (Bullish)" if price > fib_val else "Techo Tendencia (Bearish)"

                # CONSTRUCCIÓN DEL MENSAJE "PRO"
                msg = (
                    f"🦁 *ANÁLISIS {display_sym} PRO ({tf.upper()})*\n"
                    f"—————————————————\n"
                    f"{mom_emoji} *Señal:* {mom_sig}\n"
                    f"⚖️ *Score:* {b} Compra vs {s} Venta\n\n"
                    
                    f"*Osciladores & Momentum:*\n"
                    f"🔵 *RSI (14):* `{rsi_val:.1f}` _{rsi_str}_\n"
                    f"🌊 *Stoch K:* `{stoch_k:.1f}` _{stoch_txt}_\n"
                    f"🔋 *ADX:* `{adx:.1f}` _{adx_txt}_\n"
                    f"❌ *MACD:* {'Positivo 🟢' if macd_hist > 0 else 'Negativo 🔴'}\n\n"
                    
                    f"*Tendencia (Medias Móviles):*\n"
                    f"📉 *Estructura:* _{trend_str}_\n"
                    f"EMA 200: `${fmt(ema_200)}` _(Tendencia LP)_\n\n"
                    
                    f"*Confluencia y Estado:*\n"
                    f"📍 *Zona:* `{sr.get('status_zone', 'N/A')}`\n"
                    f"☁️ *Ichimoku:* `${fmt(kijun_val)}`\n"
                    f"   ↳ _{kijun_icon} {kijun_label}_\n"
                    f"🟡 *FIB 0.618:* `${fmt(fib_val)}`\n"
                    f"   ↳ _📐 {fib_label}_\n\n"
                    
                    f"—————————————————\n"
                    f"💹 *Niveles Claves ({tf.upper()})*\n"
                    f"🧗 R3 (Ext): `${fmt(sr.get('R3',0))}`\n"
                    f"🟥 R2 (Res): `${fmt(sr.get('R2',0))}`\n"
                    f"🟧 R1 (Res): `${fmt(sr.get('R1',0))}`\n"
                    f"⚖️ *PIVOT: ${fmt(sr.get('P',0))}*\n"
                    f"🟦 S1 (Sup): `${fmt(sr.get('S1',0))}`\n"
                    f"🟩 S2 (Sup): `${fmt(sr.get('S2',0))}`\n"
                    f"🕳️ S3 (Pánico): `${fmt(sr.get('S3',0))}`\n\n"
                    
                    f"💰 *Precio:* `${fmt(price)}`\n"
                    f"💸 *ATR:* `${fmt(sr.get('atr', 0))}`\n"
                    f"—————————————————\n"
                    f"🔔 *Suscripción {tf.upper()}:* {sub_txt}"
                )
                
                # Factores Clave (Reasons)
                if reasons:
                    msg += f"\n\n*Factores Clave:*\n"
                    for r in reasons[:2]:
                        msg += f"• {r}\n"
            
            except Exception as e:
                msg = f"❌ Error Análisis Local: {e}"

    # ==================================================================
    # MODO TRADINGVIEW (FALLBACK PRO)
    # ==================================================================
    else:
        tv = get_tv_data(symbol, tf)
        if tv:
            # Extraer variables TV
            curr = tv.get('current_price', 0)
            rec = tv.get('recommendation', 'NEUTRAL')
            b_count, s_count = tv.get('buy_count', 0), tv.get('sell_count', 0)
            rsi = tv.get('RSI', 50)
            
            # Iconos Señal
            if "BUY" in rec: sig_icon = "🐂"
            elif "SELL" in rec: sig_icon = "🐻"
            else: sig_icon = "⚖️"
            
            # Etiquetas TV
            rsi_state = "🔴 SOBRECOMPRA" if rsi > 70 else "🟢 SOBREVENTA" if rsi < 30 else "⚖️ NEUTRAL"
            sma_state = "📈 Sobre SMA50" if curr > tv.get('SMA50', 0) else "📉 Bajo SMA50"

            msg = (
                f"🦁 *Monitor {display_sym} (TradingView {tf.upper()})*\n"
                f"—————————————————\n"
                f"📊 *Estructura General*\n"
                f"📡 Fuente: _TradingView API_\n"
                f"{sig_icon} *Señal:* `{rec}`\n"
                f"⚖️ *Score:* {b_count} Compra | {s_count} Venta\n\n"
                
                f"*Indicadores:*\n"
                f"🔵 *RSI:* `{rsi:.1f}` _{rsi_state}_\n"
                f"❌ *MACD:* {'Alcista' if tv.get('MACD_hist', 0) > 0 else 'Bajista'}\n"
                f"📉 *SMA:* _{sma_state}_\n\n"
                
                f"*💹 Niveles Clave:*\n"
                f"🧗 R3: `${fmt(tv.get('R3',0))}`\n"
                f"🟥 R2: `${fmt(tv.get('R2',0))}`\n"
                f"🟧 R1: `${fmt(tv.get('R1',0))}`\n"
                f"⚖️ *PIVOT: ${fmt(tv.get('P',0))}*\n"
                f"🟦 S1: `${fmt(tv.get('S1',0))}`\n"
                f"🟩 S2: `${fmt(tv.get('S2',0))}`\n"
                f"🕳️ S3: `${fmt(tv.get('S3',0))}`\n\n"

                f"💰 *Precio:* `${fmt(curr)}`\n"
                f"💸 *ATR:* `${fmt(tv.get('ATR', 0))}`\n"
                f"—————————————————\n"
                f"🔔 *Suscripción {tf.upper()}:* {sub_txt}"
            )
        else:
            msg = "⚠️ Error conectando con TradingView."

    # --- ENVÍO Y MANEJO DE ERRORES ---
    msg += get_random_ad_text()
    kb = _get_valerts_keyboard(user_id, symbol, source, tf)
    
    if update.callback_query:
        # Truco: Responder para quitar el relojito
        try: await update.callback_query.answer()
        except: pass
        
        try:
            await update.callback_query.edit_message_text(msg, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
        except BadRequest as e:
            # Ignorar si el mensaje es idéntico (usuario pulsó el botón pero no ha cambiado el precio)
            if "Message is not modified" in str(e):
                pass
            else:
                print(f"Error editando mensaje Valerts: {e}")
    else:
        await update.message.reply_text(msg, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)

# --- CALLBACKS AUXILIARES ---

async def valerts_toggle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    parts = query.data.split("|")
    sym = parts[1]
    tf = parts[2]
    
    new_status = toggle_valerts_subscription(query.from_user.id, sym, tf)
    
    # Intentamos mantener la vista actual
    # Truco: Miramos el botón "Ir a TV/Local" para saber en qué fuente estamos
    current_source = "BINANCE"
    try:
        for row in query.message.reply_markup.inline_keyboard:
            for btn in row:
                if "valerts_view" in btn.callback_data and ("TV" in btn.text or "Local" in btn.text):
                    # Si el botón dice "Ir a TV", estamos en BINANCE
                    if "TV" in btn.text: current_source = "BINANCE"
                    else: current_source = "TV"
    except: pass

    kb = _get_valerts_keyboard(query.from_user.id, sym, current_source, tf) # Recargamos el teclado con el TF actual
    
    txt = f"✅ Alerta {tf.upper()} Activada" if new_status else f"🔕 Alerta {tf.upper()} Desactivada"
    await query.answer(txt)
    try:
        await query.edit_message_reply_markup(kb)
    except: pass

async def valerts_list_back_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await valerts_show_list(update, context)

valerts_handlers_list = [
    CommandHandler("valerts", valerts_handler_main),
    CallbackQueryHandler(valerts_handler_main, pattern="^valerts_view\\|"),
    CallbackQueryHandler(valerts_toggle_callback, pattern="^toggle_valerts\\|"),
    CallbackQueryHandler(valerts_list_back_callback, pattern="^valerts_list_back$")
]