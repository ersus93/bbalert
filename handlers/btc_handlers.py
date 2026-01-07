
# handlers/btc_handlers.py

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler, CommandHandler
from telegram.constants import ParseMode
import json
import os
import pandas as pd
from core.i18n import _
from utils.btc_manager import (
    is_btc_subscribed, 
    toggle_btc_subscription, 
    load_btc_state, 
    load_btc_subs 
)
from utils.ads_manager import get_random_ad_text
from datetime import datetime
from core.config import DATA_DIR
from core.btc_advanced_analysis import BTCAdvancedAnalyzer
from core.btc_loop import get_btc_klines, get_btc_candle_data
from utils.tv_helper import get_tv_data 

# --- Función Auxiliar para Generar Botones ---
def _get_btc_keyboard(user_id, current_source="BINANCE", current_tf="1d"):
    # 1. Cargar suscripciones
    subs_data = load_btc_subs().get(str(user_id), {}).get('subscriptions', [])
    
    # Función auxiliar para texto del botón
    def get_sub_text(tf):
        is_active = tf in subs_data 
        return f"🔔 {tf.upper()}" if is_active else f"🔕 {tf.upper()}"

    # --- SECCIÓN 1: BOTONES DE SUSCRIPCIÓN (Filas de 3 máximo) ---
    subs_buttons = [
        InlineKeyboardButton(get_sub_text("1h"), callback_data=f"toggle_btc_alerts|1h"),
        InlineKeyboardButton(get_sub_text("2h"), callback_data=f"toggle_btc_alerts|2h"),
        InlineKeyboardButton(get_sub_text("4h"), callback_data=f"toggle_btc_alerts|4h"),
        InlineKeyboardButton(get_sub_text("8h"), callback_data=f"toggle_btc_alerts|8h"),
        InlineKeyboardButton(get_sub_text("12h"), callback_data=f"toggle_btc_alerts|12h"),
        InlineKeyboardButton(get_sub_text("1d"), callback_data=f"toggle_btc_alerts|1d"),
        InlineKeyboardButton(get_sub_text("1w"), callback_data=f"toggle_btc_alerts|1w")
    ]
    
    # Organizar suscripciones en filas de 3 para que no ocupen tanto verticalmente
    keyboard = []
    keyboard.append([
        InlineKeyboardButton(
            "✨ Análisis IA", 
            callback_data=f"ai_analyze|{current_source}|BTC|USDT|{current_tf}"
        )
    ])
    
    row = []
    for btn in subs_buttons:
        row.append(btn)
        if len(row) == 3: # Cambia a 2 si prefieres botones más grandes
            keyboard.append(row)
            row = []
    if row: keyboard.append(row)

    # --- SECCIÓN 2: CAMBIO DE TEMPORALIDAD (Filas de 2) ---
    # Solo mostramos las que NO estamos viendo
    tf_buttons = []
    for tf in ["1h", "2h", "4h", "8h", "12h", "1d", "1w"]: # Asegúrate de usar "12h" no "12"
        if tf != current_tf:
            tf_buttons.append(InlineKeyboardButton(f"⏳ Ver {tf.upper()}", callback_data=f"btc_switch_view|{current_source}|{tf}"))
    
    # Organizar botones de vista en filas de 2
    row = []
    for btn in tf_buttons:
        row.append(btn)
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row: keyboard.append(row)

    # --- SECCIÓN 3: FUENTE Y ACTUALIZAR ---
    other_source = "TV" if current_source == "BINANCE" else "BINANCE"
    source_text = "📊 Ir a TradingView" if current_source == "BINANCE" else "🦁 Ir a Local"
    
    # Botón de fuente y botón de refrescar manual en la misma fila
    control_row = [
        InlineKeyboardButton(source_text, callback_data=f"btc_switch_view|{other_source}|{current_tf}"),
        # Un botón para forzar recarga si el precio no cambió
        InlineKeyboardButton("🔄", callback_data=f"btc_switch_view|{current_source}|{current_tf}")
    ]
    keyboard.append(control_row)
    
    return InlineKeyboardMarkup(keyboard)

# === COMANDO PRINCIPAL CON LÓGICA DE SWITCH ===

async def btc_alerts_command(update: Update, context: ContextTypes.DEFAULT_TYPE, source="BINANCE"):
    # 1. Variables iniciales
    is_callback = update.callback_query is not None
    user_id = update.effective_user.id
    user_id_str = str(user_id)
    target_tf = "1d" # Valor por defecto

    # 2. DETERMINAR TEMPORALIDAD (target_tf) PRIMERO
    if is_callback:
        query = update.callback_query
        data_parts = query.data.split("|")
        # data_parts ejemplo: ["btc_switch_view", "BINANCE", "4h"]
        if len(data_parts) >= 3:
            source = data_parts[1]
            target_tf = data_parts[2] # Aquí capturamos "4h" u "8h"
        elif len(data_parts) == 2:
            source = data_parts[1]

    if not is_callback and context.args:
        args_upper = [a.upper() for a in context.args]
        if "TV" in args_upper: source = "TV"
        # Detectar si el usuario escribió una temporalidad manualmente
        for tf in ["1h", "2h", "4h", "8h", "12h", "1d", "1w"]:
            if tf.upper() in args_upper: 
                target_tf = tf.lower()

    # 3. AHORA VERIFICAR SUSCRIPCIÓN (Con el target_tf ya correcto)
    subs_data = load_btc_subs()
    user_subs = subs_data.get(user_id_str, {}).get('subscriptions', [])
    
    # La lógica que pediste:
    is_active = target_tf in user_subs
    status_text = "✅ ACTIVADAS" if is_active else "☑️ DESACTIVADAS"

    # --- FIN DE LA CORRECCIÓN DE LÓGICA ---

    msg = ""
    switch_btn = []
    
    
    # --- CAMBIO: Pasar interval explícito ---
    df = get_btc_klines(interval=target_tf, limit=150)
    
    if df is None or df.empty:
        await update.message.reply_text("⚠️ Error obteniendo datos de Binance.")
        return
    
    

    # ==================================================================
    # CASO A: VISTA TRADINGVIEW (ESTILO PRO / VALERTS)
    # ==================================================================
    if source == "TV":
        try:
            # 1. Obtener datos de TradingView
            tv_data = get_tv_data("BTCUSDT", interval_str=target_tf)
            
            if not tv_data:
                raise Exception("Sin datos de TV")
            
            # 2. Extraer variables clave
            curr = tv_data.get('current_price', 0)
            rec = tv_data.get('recommendation', 'NEUTRAL')
            buy_score = tv_data.get('buy_count', 0)
            sell_score = tv_data.get('sell_count', 0)
            atr_val = tv_data.get('ATR', 0)
            
            rsi_val = tv_data.get('RSI', 50)
            macd_hist = tv_data.get('MACD_hist', 0)
            sma50 = tv_data.get('SMA50', 0)
            
            # 3. Lógica de Emojis y Textos (Igual que en Valerts)
            # --- Señal General ---
            if "STRONG_BUY" in rec:
                sig_icon, sig_txt = "🚀", "COMPRA FUERTE"
            elif "BUY" in rec:
                sig_icon, sig_txt = "🐂", "COMPRA"
            elif "STRONG_SELL" in rec:
                sig_icon, sig_txt = "🩸", "VENTA FUERTE"
            elif "SELL" in rec:
                sig_icon, sig_txt = "🐻", "VENTA"
            else:
                sig_icon, sig_txt = "⚖️", "NEUTRAL"

            # --- RSI ---
            if rsi_val > 70:
                rsi_icon, rsi_state = "🔴", "SOBRECOMPRA"
            elif rsi_val < 30:
                rsi_icon, rsi_state = "🟢", "SOBREVENTA"
            elif rsi_val > 50:
                rsi_icon, rsi_state = "🔵", "ALCISTA"
            else:
                rsi_icon, rsi_state = "🟠", "BAJISTA"

            # --- MACD ---
            if macd_hist > 0:
                macd_icon, macd_state = "✅", "Positivo (Alcista)"
            else:
                macd_icon, macd_state = "❌", "Negativo (Bajista)"

            # --- SMA 50 ---
            if curr > sma50:
                sma_icon, sma_state = "📈", "Sobre SMA50"
            else:
                sma_icon, sma_state = "📉", "Bajo SMA50"

            # 4. Construcción del Mensaje PRO
            msg = (
                f"🦁 *Monitor BTC (TradingView) [{target_tf.upper()}]*\n"
                f"—————————————————\n"
                f"📊 *Estructura BTC*\n"
                f"📡 Fuente: _TradingView API_\n"
                f"{sig_icon} *Señal:* `{sig_txt}`\n"
                f"⚖️ *Score:* {buy_score} Compra | {sell_score} Venta\n\n"
                
                f"*Indicadores:*\n"
                f"{rsi_icon} *RSI:* `{rsi_val:.1f}` _{rsi_state}_\n"
                f"{macd_icon} *MACD:* _{macd_state}_\n"
                f"{sma_icon} *SMA:* _{sma_state}_\n\n"
                
                f"*💹 Niveles Clave:*\n"
                f"🧗 R3: `${tv_data.get('R3', 0):,.0f}`\n"
                f"🟥 R2: `${tv_data.get('R2', 0):,.0f}`\n"
                f"🟧 R1: `${tv_data.get('R1', 0):,.0f}`\n"
                f"⚖️ *PIVOT: ${tv_data.get('P', 0):,.0f}*\n"
                f"🟦 S1: `${tv_data.get('S1', 0):,.0f}`\n"
                f"🟩 S2: `${tv_data.get('S2', 0):,.0f}`\n"
                f"🕳️ S3: `${tv_data.get('S3', 0):,.0f}`\n\n"
                
                f"💰 *Precio:* `${curr:,.2f}`\n"
                f"💸 *ATR*: `${atr_val:,.0f}`\n"
                f"—————————————————\n"
                f"🔔 Suscripción {target_tf.upper()}: {status_text}"
            )
            
            # El botón switch llevará a la vista LOCAL (Binance)
            switch_btn = [InlineKeyboardButton("🦁 Ver Local (Binance)", callback_data="btc_switch_view|BINANCE")]
            
        except Exception as e:
            msg = f"⚠️ *Error conectando con TradingView.*\nUse la vista local por ahora.\nError: _{e}_"
            # Botón de emergencia para volver a local
            switch_btn = [InlineKeyboardButton("🦁 Volver a Local", callback_data="btc_switch_view|BINANCE")]

    # ==================================================================
    # CASO B: VISTA BINANCE PRO (Cálculo Local Avanzado)
    # ==================================================================
    else:
        try:
            # 1. Obtener Velas (Limit 10000 para precisión en EMA200)
            df = get_btc_klines(interval=target_tf, limit=1000)
            
            if df is None or len(df) < 200:
                msg = "⚠️ *Datos insuficientes de Binance.*\nIntenta de nuevo en unos segundos."
            else:
                # 2. Instanciar Analizador
                analyzer = BTCAdvancedAnalyzer(df)
                
                # 3. Obtener Datos
                curr_values = analyzer.get_current_values()
                momentum_signal, emoji_mom, (buy, sell), reasons = analyzer.get_momentum_signal()
                sr = analyzer.get_support_resistance_dynamic(interval=target_tf)
                #sr = analyzer.get_support_resistance_dynamic()
                
                # 4. Formatear Valores
                price = curr_values.get('close', 0)
                rsi_val = curr_values.get('RSI', 50)
                 # Intentamos buscar ADX_14 o ADX
                adx = curr_values.get('ADX_14', curr_values.get('ADX', 0))
                if adx >= 50:
                    adx_txt = "🔥 Tendencia Muy Fuerte"
                elif adx >= 20:
                    adx_txt = "💪 Tendencia Fuerte"
                else:
                    adx_txt = "💤 Rango / Sin Tendencia"
                # Intentamos buscar STOCHk_14... o similar
                stoch_k = curr_values.get('stoch_k', 50)
                if stoch_k >= 80:
                    stoch_txt = "🔴 Tope, Sobrecompra (Posible Caída)"
                elif stoch_k <= 20:
                    stoch_txt = "🟢 Suelo, Sobrevendido (Posible Rebote)"
                else:
                    stoch_txt = "⚖️ Neutro"
                macd_hist = curr_values.get('MACD_HIST', 0)
                ema_50 = curr_values.get('EMA_50', 0)
                ema_200 = curr_values.get('EMA_200', 0)
                
                # Etiquetas lógicas
                if rsi_val > 70: rsi_str = "SOBRECOMPRA 🔴"
                elif rsi_val < 30: rsi_str = "SOBREVENTA 🟢"
                elif rsi_val > 50: rsi_str = "ALCISTA ↗️"
                else: rsi_str = "BAJISTA ↘️"
                
                trend_str = "ALCISTA (Sobre EMA50)" if price > ema_50 else "BAJISTA (Bajo EMA50)"
                
                # --- ETIQUETAS DINÁMICAS (NUEVO) ---
                # Definimos qué significan los niveles según donde esté el precio hoy
                
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

                # 5. Construir Mensaje PRO
                msg = (
                    f"🦁 *ANÁLISIS BTC PRO ({target_tf.upper()}) (Local)*\n"
                    f"—————————————————\n"
                    f"{emoji_mom} *Señal:* {momentum_signal}\n"
                    f"⚖️ *Score:* {buy} Compra vs {sell} Venta\n\n"
                    
                    f"*Osciladores & Momentum:*\n"
                    f"🔵 *RSI (14):* `{rsi_val:.1f}` _{rsi_str}_\n"
                    f"🌊 *Stoch K:* `{stoch_k:.1f}` _{stoch_txt}_\n"
                    f"🔋 *ADX Force:* `{adx:.1f}` _{adx_txt}_\n"
                    f"❌ *MACD:* {'Positivo 🟢' if macd_hist > 0 else 'Negativo 🔴'}\n\n"
                    
                    f"*Tendencia (Medias Móviles):*\n"
                    f"📉 *Estructura:* _{trend_str}_\n"
                    f"EMA 200: `${ema_200:,.0f}` _(Tendencia LP)_\n\n"
                    
                    f"*Confluencia y Estado:*\n"
                    f"📍 *Zona:* `{zone}`\n"
                    f"☁️ *Ichimoku:* `${kijun_val:,.0f}`\n"
                    f"   ↳ _{kijun_icon} {kijun_label}_\n"
                    f"🟡 *FIB 0.618:* `${fib_val:,.0f}`\n"
                    f"   ↳ _📐 {fib_label}_\n\n"

                    f"—————————————————\n"
                    f"💹 *Niveles Claves ({target_tf.upper()})*\n"  
                    
                   
                    f"🧗 R3 (Ext): `${sr.get('R3',0):,.0f}`\n"
                    f"🟥 R2 (Res): `${sr.get('R2',0):,.0f}`\n"
                    f"🟧 R1 (Res): `${sr.get('R1',0):,.0f}`\n"                    
                    f"⚖️ *PIVOT: ${sr.get('P',0):,.0f}*\n"
                    f"🟦 S1 (Sup): `${sr.get('S1',0):,.0f}`\n"
                    f"🟩 S2 (Sup): `${sr.get('S2',0):,.0f}`\n"
                    f"🕳️ S3 (Pánico): `${sr.get('S3',0):,.0f}`\n\n"
                    
                    f"💰 *Precio Actual:* `${price:,.0f}`\n"
                    f"💸 *ATR*: `${sr.get('atr' ,0):,.0f}`\n"
                    f"—————————————————\n"
                    f"🔔 Suscripción {target_tf.upper()}: {status_text}"
                )
                
                # Agregar razones si existen
                if reasons:
                   msg += f"\n\n*Factores Clave:*\n"
                   for r in reasons[:2]:
                       msg += f"• {r}\n"

        except Exception as e:
            msg = f"❌ *Error crítico en análisis local.*\n_{str(e)}_"
            # En caso de error, permitir ir a TV
            switch_btn = [InlineKeyboardButton("📺 Probar TradingView", callback_data="btc_switch_view|TV")]

        # Si todo salió bien en bloque Binance, definimos el botón a TV
        if not switch_btn:
            switch_btn = [InlineKeyboardButton("📊 Ver en TradingView", callback_data="btc_switch_view|TV")]

    # ==================================================================
    # ARMADO FINAL DEL MENSAJE Y TECLADO
    # ==================================================================
    
    # Agregar publicidad
    msg += get_random_ad_text()

    # --- RESPUESTA ---
    kb = _get_btc_keyboard(user_id, current_source=source, current_tf=target_tf)
    
    if is_callback:
        # Importante: Responder al callback primero para quitar el relojito de carga
        # Si el mensaje no cambia, al menos el usuario ve una notificación flotante
        try:
            await update.callback_query.answer("Analizando...") 
        except:
            pass

        try:
            from telegram.error import BadRequest # Asegúrate de importar esto arriba o usarlo así
            await update.callback_query.edit_message_text(msg, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
        except BadRequest as e:
            error_str = str(e)
            # Si el error es "Message is not modified", lo ignoramos porque significa
            # que el usuario clicó, pero el precio/análisis es idéntico al anterior.
            if "not modified" in error_str:
                pass 
            else:
                print(f"Error editando mensaje BTC: {e}")
                # Opcional: Reintentar sin Markdown si falló por formato
    else:
        await update.message.reply_text(msg, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
    

# === HANDLERS DE CALLBACK ===

async def btc_switch_view_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Simplemente redirige la llamada a la función principal btc_alerts_command.
    La función principal ahora es inteligente y sabrá leer la temporalidad del botón.
    """
    # Llamamos a tu función PRO directamente
    await btc_alerts_command(update, context)


async def btc_toggle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Activa o desactiva alertas para una temporalidad específica."""
    query = update.callback_query
    await query.answer()
    
    # 1. Extraer la temporalidad del callback (ej: toggle_btc_alerts|1d)
    data = query.data.split("|")
    target_tf = data[1] if len(data) > 1 else "1d"
    
    # 2. Ejecutar el cambio en la base de datos (Manager)
    new_state = toggle_btc_subscription(query.from_user.id, timeframe=target_tf)
    
    # 3. Detectar qué vista (tf) y fuente tenía el usuario en ese momento
    current_source = "BINANCE" 
    current_tf_view = "1d" 
    
    try:
        for row in query.message.reply_markup.inline_keyboard:
            for btn in row:
                if "btc_switch_view" in btn.callback_data:
                    # El botón es "Ver X", así que la vista actual es la contraria
                    # O el botón de fuente: "btc_switch_view|TV|4h"
                    parts = btn.callback_data.split("|")
                    if len(parts) > 2:
                        current_tf_view = parts[2]
                        # Si el botón dice "ir a TV", es que estamos en BINANCE
                        current_source = "BINANCE" if "TV" in parts[1] else "TV"
                    break
    except:
        pass

    # 4. Regenerar el teclado completo con el nuevo estado
    new_kb = _get_btc_keyboard(query.from_user.id, current_source, current_tf_view)
    
    # 5. Actualizar el mensaje
    try:
        await query.edit_message_reply_markup(reply_markup=new_kb)
        
        status_msg = f"✅ Alertas {target_tf.upper()} ACTIVADAS" if new_state else f"🔕 Alertas {target_tf.upper()} DESACTIVADAS"
        await query.answer(status_msg, show_alert=False)
    except Exception as e:
        print(f"Error actualizando teclado BTC: {e}")

# === LISTA DE HANDLERS PARA MAIN.PY ===

btc_handlers_list = [
    CommandHandler("btcalerts", btc_alerts_command),
    # Ahora el toggle también acepta parámetros
    CallbackQueryHandler(btc_toggle_callback, pattern="^toggle_btc_alerts"), 
    CallbackQueryHandler(btc_switch_view_callback, pattern="^btc_switch_view"),
    CallbackQueryHandler(btc_switch_view_callback, pattern="^btcalerts_view"),
]
