# handlers/valerts_handlers.py

import requests
import pandas as pd
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler, CommandHandler
from telegram.constants import ParseMode
from core.i18n import _
from utils.tv_helper import get_tv_data
from core.btc_advanced_analysis import BTCAdvancedAnalyzer
from utils.valerts_manager import (
    is_valerts_subscribed, 
    toggle_valerts_subscription, 
    get_active_symbols
)
from utils.ads_manager import get_random_ad_text

# --- 1. UTILIDADES DE DATOS ---

def fmt_price(price):
    """Formatea precios dinámicamente de forma segura."""
    try:
        if price is None: return "0.00"
        price = float(price)
        if price < 0.0001: return f"{price:.8f}"
        if price < 1: return f"{price:.6f}"
        if price < 10: return f"{price:.4f}"
        return f"{price:,.2f}"
    except:
        return "0.00"

def get_binance_klines_generic(symbol, interval="4h", limit=10000):
    """
    Obtiene velas históricas de Binance para cualquier par.
    """
    # Intentamos primero con sufijo USDT si no lo tiene y no es BTC
    if not symbol.endswith("USDT") and not symbol.endswith("BTC"):
        symbol += "USDT"
        
    endpoints = [
        "https://api.binance.com/api/v3/klines",
        "https://api.binance.us/api/v3/klines"
    ]
    
    params = {
        "symbol": symbol.upper(),
        "interval": interval,
        "limit": limit
    }
    
    for url in endpoints:
        try:
            r = requests.get(url, params=params, timeout=5)
            if r.status_code != 200:
                continue
                
            data = r.json()
            if not isinstance(data, list) or len(data) < 50:
                continue
                
            # Convertir a DataFrame
            df = pd.DataFrame(data, columns=[
                "open_time", "open", "high", "low", "close", "volume",
                "close_time", "quote_asset_volume", "trades",
                "taker_base", "taker_quote", "ignore"
            ])
            
            # Convertir tipos numéricos
            cols = ["open", "high", "low", "close", "volume"]
            df[cols] = df[cols].apply(pd.to_numeric, errors='coerce')
                
            # Convertir tiempo
            df['time'] = pd.to_datetime(df['open_time'], unit='ms')
            
            return df, symbol.upper()
        except Exception:
            continue
            
    return None, symbol

# --- 2. COMANDO PRINCIPAL ---

async def valerts_check_command(update: Update, context: ContextTypes.DEFAULT_TYPE, source=None, symbol_override=None):
    """
    Controlador maestro para alertas de volatilidad (Estilo PRO).
    """
    is_callback = update.callback_query is not None
    user_id = update.effective_user.id
    msg = ""
    switch_btn = []
    
    # --- A. PARSEO DE ARGUMENTOS ---
    if is_callback:
        # data format: "valerts_view|SYMBOL|SOURCE"
        data_parts = update.callback_query.data.split("|")
        symbol_raw = data_parts[1]
        # Si el callback trae la fuente, la usamos, sino default a BINANCE
        source = data_parts[2] if len(data_parts) > 2 else (source or "BINANCE")
    else:
        # Comando normal: /valert ETH TV
        if symbol_override:
            symbol_raw = symbol_override
        elif context.args:
            symbol_raw = context.args[0].upper()
            if len(context.args) > 1 and "TV" in context.args[1].upper():
                source = "TV"
            elif not source:
                source = "BINANCE"
        else:
            await valerts_list_view(update, context)
            return

    # Limpieza del símbolo para mostrar (ej: ETH)
    symbol_display = symbol_raw.upper().replace("USDT", "")

    # Gestión de Key para suscripción (Siempre con USDT para consistencia interna)
    sub_key = symbol_raw.upper()
    if not sub_key.endswith("USDT") and "BTC" not in sub_key:
        sub_key += "USDT"
        
    is_sub = is_valerts_subscribed(user_id, sub_key)
    sub_icon = "✅ ACTIVADAS" if is_sub else "☑️ DESACTIVADAS"

    # ==================================================================
    # CASO 1: VISTA TRADINGVIEW (API Externa)
    # ==================================================================
    if source == "TV":
        try:
            # Llamada segura con 2 argumentos
            tv_data = get_tv_data(sub_key, "4h")
            
            if not tv_data:
                raise Exception("Sin datos TV")

            curr = tv_data.get('current_price', 0)
            rec = tv_data.get('recommendation', 'NEUTRAL')
            
            # Emojis de Señal
            if "STRONG_BUY" in rec: sig_icon, sig_txt = "🚀", "COMPRA FUERTE"
            elif "BUY" in rec: sig_icon, sig_txt = "🐂", "COMPRA"
            elif "STRONG_SELL" in rec: sig_icon, sig_txt = "🩸", "VENTA FUERTE"
            elif "SELL" in rec: sig_icon, sig_txt = "🐻", "VENTA"
            else: sig_icon, sig_txt = "⚖️", "NEUTRAL"

            # Indicadores Visuales
            rsi_val = tv_data.get('RSI', 50)
            if rsi_val > 70: rsi_str = "SOBRECOMPRA 🔴"
            elif rsi_val < 30: rsi_str = "SOBREVENTA 🟢"
            else: rsi_str = "NEUTRAL"

            macd_hist = tv_data.get('MACD_hist', 0)
            macd_str = "Positivo (Alcista) ✅" if macd_hist > 0 else "Negativo (Bajista) ❌"
            
            sma50 = tv_data.get('SMA50', 0)
            sma_str = "Sobre SMA50 📈" if curr > sma50 else "Bajo SMA50 📉"

            msg = (
                f"🦁 *Monitor {symbol_display} (TradingView)*\n"
                f"—————————————————\n"
                f"📊 *Estructura (4H)*\n"
                f"📡 Fuente: _TradingView API_\n"
                f"{sig_icon} *Señal:* `{sig_txt}`\n"
                f"⚖️ *Score:* {tv_data.get('buy_count',0)} Compra | {tv_data.get('sell_count',0)} Venta\n\n"
                
                f"*Indicadores:*\n"
                f"🔵 *RSI:* `{rsi_val:.1f}` _{rsi_str}_\n"
                f"❌ *MACD:* _{macd_str}_\n"
                f"📉 *SMA:* _{sma_str}_\n\n"
                
                f"*💹 Niveles Clave:*\n"
                f"🧗 R3: `${fmt_price(tv_data.get('R3', 0))}`\n"
                f"🟥 R2: `${fmt_price(tv_data.get('R2', 0))}`\n"
                f"🟧 R1: `${fmt_price(tv_data.get('R1', 0))}`\n"
                f"⚖️ *PIVOT: ${fmt_price(tv_data.get('P', 0))}*\n"
                f"🟦 S1: `${fmt_price(tv_data.get('S1', 0))}`\n"
                f"🟩 S2: `${fmt_price(tv_data.get('S2', 0))}`\n"
                f"🕳️ S3: `${fmt_price(tv_data.get('S3', 0))}`\n\n"
                
                f"💰 *Precio:* `${fmt_price(curr)}`\n"
                f"—————————————————\n"
                f"🔔 *Suscripción:* {sub_icon}"
            )
            switch_btn = [InlineKeyboardButton("🦁 Ver Local (Binance)", callback_data=f"valerts_view|{symbol_raw}|BINANCE")]

        except Exception:
            msg = f"⚠️ *No encontrado en TradingView* ({symbol_display}).\nPrueba el modo local."
            switch_btn = [InlineKeyboardButton("🦁 Probar Binance", callback_data=f"valerts_view|{symbol_raw}|BINANCE")]

    # ==================================================================
    # CASO 2: VISTA BINANCE PRO (Análisis Local con Pandas TA)
    # ==================================================================
    else:
        try:
            # 1. Obtener Velas (Igual límite seguro)
            df, full_symbol = get_binance_klines_generic(symbol_raw, limit=1000)
            
            if df is None:
                msg = (
                    f"❌ *{symbol_display} no encontrado en Binance.*\n"
                    "¿Quieres probar en TradingView?"
                )
                switch_btn = [InlineKeyboardButton("📊 Buscar en TradingView", callback_data=f"valerts_view|{symbol_raw}|TV")]
            else:
                # 2. Análisis PRO (Misma clase que BTC)
                analyzer = BTCAdvancedAnalyzer(df)
                
                # Obtener valores actuales (Indicadores)
                curr_vals = analyzer.get_current_values()
                
                # --- EXTRACCIÓN DE DATOS (Alineado con BTC) ---
                price = curr_vals.get('close', 0)
                
                # RSI
                rsi = curr_vals.get('RSI', 50)
                
                # ADX
                adx = curr_vals.get('ADX', 0)
                if adx >= 50: adx_txt = "🔥 Tendencia Muy Fuerte"
                elif adx >= 25: adx_txt = "💪 Tendencia Fuerte"
                else: adx_txt = "💤 Rango / Sin Tendencia"
                
                # Stochastic
                stoch_k = curr_vals.get('STOCH_K', 50) # Clave corregida del Analyzer
                if stoch_k >= 80: stoch_txt = "🔴 Sobrecompra"
                elif stoch_k <= 20: stoch_txt = "🟢 Sobrevendido"
                else: stoch_txt = "⚖️ Neutro"
                
                # MACD & Medias
                macd_hist = curr_vals.get('MACD_HIST', 0)
                ema50 = curr_vals.get('EMA_50', 0)
                ema200 = curr_vals.get('EMA_200', 0)

                # Señales y Pivotes (Claves en Mayúscula R1, S1...)
                mom_sig, mom_emoji, (b, s), reasons = analyzer.get_momentum_signal()
                sr = analyzer.get_support_resistance_dynamic()
                
                # Divergencias
                divergence = analyzer.detect_rsi_divergence(lookback=5)
                div_text = ""
                if divergence:
                    d_type, d_desc = divergence
                    d_emoji = "🐂" if d_type == "BULLISH" else "🐻"
                    div_text = f"\n{d_emoji} *Divergencia Detectada:* _{d_desc}_\n"

                # Textos Visuales
                if rsi > 70: rsi_state = "SOBRECOMPRA 🔴"
                elif rsi < 30: rsi_state = "SOBREVENTA 🟢"
                elif rsi > 50: rsi_state = "ALCISTA ↗️"
                else: rsi_state = "BAJISTA ↘️"
                
                macd_txt = "Positivo 🟢" if macd_hist > 0 else "Negativo 🔴"
                trend_state = "ALCISTA (Sobre EMA50)" if price > ema50 else "BAJISTA (Bajo EMA50)"
                
                # Zona Fibonacci (Usamos las claves MAYÚSCULAS correctas)
                if price > sr.get('R2',0): zone = "🚀 EXTENSIÓN"
                elif price > sr.get('R1',0): zone = "🐂 ALCISTA"
                elif price < sr.get('S2',0): zone = "🩸 EXTENSIÓN"
                elif price < sr.get('S1',0): zone = "🐻 BAJISTA"
                else: zone = "⚖️ NEUTRAL"

                # Construcción del Mensaje (Formato Idéntico a BTC)
                msg = (
                    f"🦁 *Monitor {symbol_display} PRO (Local)*\n"
                    f"—————————————————\n"
                    f"{mom_emoji} *Señal:* {mom_sig}\n"
                    f"⚖️ *Score:* {b} Compra vs {s} Venta\n"
                    f"{div_text}\n\n"
                    
                    f"*Osciladores & Momentum:*\n"
                    f"🔵 *RSI (14):* `{rsi:.1f}` _{rsi_state}_\n"
                    f"🌊 *Stoch K:* `{stoch_k:.1f}` _{stoch_txt}_\n"
                    f"🔋 *ADX Force:* `{adx:.1f}` _{adx_txt}_\n"
                    f"❌ *MACD:* {macd_txt}\n\n"
                    
                    f"*Tendencia (Medias Móviles):*\n"
                    f"📉 *Estructura:* _{trend_state}_\n"
                    f"EMA 200: `${fmt_price(ema200)}` _(Tendencia LP)_\n\n"
                    
                    f"—————————————————\n"
                    f"💹 *Niveles Fibonacci (4H)*\n"
                    f"Estado: {zone}\n"
                    # NOTA: Usamos sr.get('R3') en lugar de 'r3'
                    f"🧗 R3: `${fmt_price(sr.get('R3',0))}`\n"
                    f"🟥 R2: `${fmt_price(sr.get('R2',0))}`\n"
                    f"🟧 R1: `${fmt_price(sr.get('R1',0))}`\n"
                    f"⚖️ *PIVOT: ${fmt_price(sr.get('P',0))}*\n"
                    f"🟦 S1: `${fmt_price(sr.get('S1',0))}`\n"
                    f"🟩 S2: `${fmt_price(sr.get('S2',0))}`\n"
                    f"🕳️ S3: `${fmt_price(sr.get('S3',0))}`\n\n"
                    
                    f"💰 *Precio Actual:* `${fmt_price(price)}`\n"
                    f"—————————————————\n"
                    f"🔔 *Suscripción:* {sub_icon}"
                )
                
                if reasons:
                   msg += f"\n\n*Factores Clave:*\n"
                   for r in reasons[:2]:
                       msg += f"• {r}\n"
                
                switch_btn = [InlineKeyboardButton("📊 Ver en TradingView", callback_data=f"valerts_view|{symbol_raw}|TV")]

        except Exception as e:
            msg = f"❌ *Error de Análisis Local.*\n_{str(e)}_"
            switch_btn = [InlineKeyboardButton("📊 Ir a TradingView", callback_data=f"valerts_view|{symbol_raw}|TV")]

    # ==================================================================
    # ENVIAR / EDITAR
    # ==================================================================
    msg += get_random_ad_text()
    
    kb = []
    # Botón Suscribir
    sub_txt = f"🔕 Desactivar {symbol_display}" if is_sub else f"🔔 Activar {symbol_display}"
    kb.append([InlineKeyboardButton(sub_txt, callback_data=f"toggle_valerts|{sub_key}")])
    
    # Botón Switch
    if switch_btn:
        kb.append(switch_btn)
        
    # Botón Volver
    if is_callback:
        kb.append([InlineKeyboardButton("🔙 Volver a Lista", callback_data="valerts_list_back")])

    reply_markup = InlineKeyboardMarkup(kb)

    if is_callback:
        try:
            await update.callback_query.answer()
            await update.callback_query.edit_message_text(
                text=msg, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN
            )
        except Exception: 
            pass
    else:
        await update.message.reply_text(
            msg, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN
        )

async def valerts_list_view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra la lista de símbolos activos."""
    if update.callback_query:
        chat_id = update.callback_query.message.chat_id
        await update.callback_query.answer()
    else:
        chat_id = update.effective_chat.id

    active_symbols = get_active_symbols()
    
    msg = (
        "🦁 *Monitor de Volatilidad Multi-Moneda*\n"
        "—————————————————\n"
        "Recibe alertas técnicas inteligentes (RSI, Soportes, Resistencias).\n\n"
        "✍️ *Uso manual:* `/valerts ETH` o `/valerts PEPE`\n\n"
    )
    
    kb_rows = []
    if active_symbols:
        msg += "*📍 Símbolos Activos en la Comunidad:*\n"
        temp_row = []
        for i, sym in enumerate(active_symbols):
            display_sym = sym.replace("USDT", "")
            temp_row.append(InlineKeyboardButton(display_sym, callback_data=f"valerts_view|{sym}|BINANCE"))
            if (i + 1) % 3 == 0:
                kb_rows.append(temp_row)
                temp_row = []
        if temp_row:
            kb_rows.append(temp_row)
        reply_markup = InlineKeyboardMarkup(kb_rows)
    else:
        msg += "_No hay alertas activas. ¡Sé el primero en crear una!_"
        reply_markup = None

    if update.callback_query:
        await update.callback_query.edit_message_text(msg, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
    else:
        await context.bot.send_message(chat_id=chat_id, text=msg, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)

# === HANDLERS DE CALLBACK ===

async def valerts_view_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await valerts_check_command(update, context)

async def valerts_toggle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data_parts = query.data.split("|")
    if len(data_parts) < 2: return
    symbol = data_parts[1]
    symbol_display = symbol.replace("USDT", "")
    
    new_status = toggle_valerts_subscription(query.from_user.id, symbol)
    
    # Actualizar solo botón
    current_kb = query.message.reply_markup.inline_keyboard
    new_kb = []
    btn_text = f"🔕 Desactivar {symbol_display}" if new_status else f"🔔 Activar {symbol_display}"
    
    for row in current_kb:
        new_row = []
        for btn in row:
            if btn.callback_data.startswith("toggle_valerts"):
                new_row.append(InlineKeyboardButton(btn_text, callback_data=f"toggle_valerts|{symbol}"))
            else:
                new_row.append(btn)
        new_kb.append(new_row)
    
    try:
        await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(new_kb))
        status_text = f"✅ {symbol_display} activadas" if new_status else f"🔕 {symbol_display} desactivadas"
        await query.answer(status_text, show_alert=False)
    except:
        pass

async def valerts_list_back_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await valerts_list_view(update, context)

# Lista para main
valerts_handlers_list = [
    CommandHandler("valerts", valerts_check_command),
    CallbackQueryHandler(valerts_toggle_callback, pattern="^toggle_valerts\\|"),
    CallbackQueryHandler(valerts_list_back_callback, pattern="^valerts_list_back$"),
    CallbackQueryHandler(valerts_view_callback, pattern="^valerts_view\\|")
]