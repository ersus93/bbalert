from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler, CommandHandler
from telegram.constants import ParseMode
import json
import os
import pandas as pd
from core.i18n import _
from utils.btc_manager import is_btc_subscribed, toggle_btc_subscription, load_btc_state
from utils.ads_manager import get_random_ad_text
from datetime import datetime
from core.config import DATA_DIR
from core.btc_advanced_analysis import BTCAdvancedAnalyzer
from core.btc_loop import get_btc_klines

BTC_SUBS_PATH = os.path.join(DATA_DIR, "btc_subs.json")
BTC_STATE_PATH = os.path.join(DATA_DIR, "btc_alert_state.json")

def load_btc_subs():
    if not os.path.exists(BTC_SUBS_PATH):
        return {}
    try:
        with open(BTC_SUBS_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

def save_btc_subs(subs):
    try:
        temp_path = f"{BTC_SUBS_PATH}.tmp"
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(subs, f, indent=4)
        os.replace(temp_path, BTC_SUBS_PATH)
    except Exception as e:
        print(f"Error guardando subs BTC: {e}")

def toggle_btc_subscription(user_id):
    """Activa o desactiva la suscripción de un usuario."""
    subs = load_btc_subs()
    uid = str(user_id)
    
    if uid in subs:
        current = subs[uid].get('active', False)
        subs[uid]['active'] = not current
    else:
        subs[uid] = {'active': True, 'joined_at': datetime.now().isoformat()}
    
    save_btc_subs(subs)
    return subs[uid]['active']

def is_btc_subscribed(user_id):
    subs = load_btc_subs()
    return subs.get(str(user_id), {}).get('active', False)

def get_btc_subscribers():
    subs = load_btc_subs()
    return [uid for uid, data in subs.items() if data.get('active')]

def load_btc_state():
    """Carga el estado de niveles y alertas enviadas."""
    if not os.path.exists(BTC_STATE_PATH):
        return {"last_candle_time": 0, "levels": {}, "alerted_levels": []}
    try:
        with open(BTC_STATE_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠️ Error cargando estado BTC ({e}). Iniciando limpio.")
        return {"last_candle_time": 0, "levels": {}, "alerted_levels": []}

def save_btc_state(data):
    """Guarda el estado actual en JSON de forma segura."""
    try:
        temp_path = f"{BTC_STATE_PATH}.tmp"
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
        os.replace(temp_path, BTC_STATE_PATH)
    except Exception as e:
        print(f"❌ Error crítico guardando estado BTC: {e}")

async def btc_alerts_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra análisis técnico completo de BTC con indicadores PRO."""
    
    if update.callback_query:
        user_id = update.callback_query.from_user.id
        chat_id = update.callback_query.message.chat_id
        is_callback = True
    else:
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        is_callback = False

    subscribed = is_btc_subscribed(user_id)
    state = load_btc_state()
    levels = state.get('levels', {})

    status_icon = "✅ ACTIVADAS" if subscribed else "☑️ DESACTIVADAS"
    
    # --- ANÁLISIS TÉCNICO EN VIVO ---
    analysis_text = "⏳ _Cargando análisis..._"
    
    try:
        df = get_btc_klines(limit=100)
        if df is not None and len(df) > 0:
            analyzer = BTCAdvancedAnalyzer(df)
            curr_values = analyzer.get_current_values()
            momentum_signal, emoji_mom, score, reasons = analyzer.get_momentum_signal()
            support_res = analyzer.get_support_resistance_dynamic()
            divergence = analyzer.detect_rsi_divergence()
            
            # Emoji de RSI
            rsi_val = curr_values['rsi']
            if rsi_val > 70:
                rsi_emoji = "🔴"
                rsi_state = "SOBRECOMPRADO"
            elif rsi_val > 60:
                rsi_emoji = "🟢"
                rsi_state = "ALCISTA"
            elif rsi_val > 40:
                rsi_emoji = "🟡"
                rsi_state = "NEUTRAL"
            else:
                rsi_emoji = "🔵"
                rsi_state = "BAJISTA/SOBREVENTA"
            
            # Emoji de MACD
            macd_emoji = "✅" if (curr_values['macd_hist'] > 0) else "❌"
            macd_state = "Alcista" if (curr_values['macd_hist'] > 0) else "Bajista"
            
            # Emoji de Volumen
            vol_ratio = curr_values['volume_ratio']
            if vol_ratio > 1.5:
                vol_emoji = "📈"
                vol_state = "MUY ALTO (Fuerte)"
            elif vol_ratio > 1.2:
                vol_emoji = "📊"
                vol_state = "ALTO (Confirmación)"
            elif vol_ratio > 0.8:
                vol_emoji = "📉"
                vol_state = "NORMAL"
            else:
                vol_emoji = "⚠️"
                vol_state = "BAJO (Débil)"
            
            # Emoji de SMA
            price = curr_values['price']
            sma_50 = curr_values['sma_50']
            sma_200 = curr_values['sma_200']
            
            if price > sma_50 > sma_200:
                sma_emoji = "🚀"
                sma_state = "ALCISTA (Todos UP)"
            elif price > sma_50:
                sma_emoji = "📈"
                sma_state = "POSITIVO"
            elif price > sma_200:
                sma_emoji = "⚖️"
                sma_state = "NEUTRAL"
            else:
                sma_emoji = "📉"
                sma_state = "BAJISTA"
            
            analysis_text = (
                f"*📊 Análisis Técnico Actual (4H)*\n"
                f"—————————————————\n"
                f"{emoji_mom} *Momentum:* {momentum_signal}\n"
                f"📈 _Score: {score}/10_\n\n"
                f"*Indicadores Clave:*\n"
                f"{rsi_emoji} *RSI:* `{rsi_val:.1f}` _{rsi_state}_\n"
                f"{macd_emoji} *MACD:* _{macd_state}_\n"
                f"{vol_emoji} *Volumen:* `{vol_ratio:.2f}x` _{vol_state}_\n"
                f"{sma_emoji} *SMA:* _{sma_state}_\n"
            )
            
            # Divergencia con emoji destacado
            if divergence:
                div_type, div_desc = divergence
                div_emoji = "🐂" if div_type == "BULLISH" else "🐻"
                analysis_text += (
                    f"\n{div_emoji} *Divergencia Detectada:* {div_type}\n"
                    f"💡 _{div_desc}_\n"
                )
            
            # Factores clave
            analysis_text += f"\n*Factores Principales:*\n"
            for i, reason in enumerate(reasons[:3], 1):
                analysis_text += f"{i}️⃣ {reason}\n"
    
    except Exception as e:
        print(f"Error en análisis: {e}")
        analysis_text = "⚠️ _Análisis técnico no disponible en este momento._"
    
    # --- TABLA DE NIVELES CON EMOJIS ---
    if levels:
        price_now = levels.get('current_price', 0)
        p = levels.get('P', 0)
        
        # Emoji de zona
        if price_now > levels.get('R2', 0):
            zone = "🚀 EXTENSIÓN"
            zone_color = "🟠"
        elif price_now > levels.get('R1', 0):
            zone = "🐂 ALCISTA"
            zone_color = "🟢"
        elif price_now < levels.get('S2', 0):
            zone = "🩸 EXTENSIÓN"
            zone_color = "🔴"
        elif price_now < levels.get('S1', 0):
            zone = "🐻 BAJISTA"
            zone_color = "🔴"
        else:
            zone = "⚖️ NEUTRAL"
            zone_color = "🟡"
        
        levels_msg = (
            f"*💹 Estructura de Mercado (4H)*\n"
            f"Estado: {zone_color} {zone}\n\n"
            f"🧗 *R3:* `${levels.get('R3',0):,.0f}` _(Máximo)_\n"
            f"🔺 *R2:* `${levels.get('R2',0):,.0f}` _(Extensión)_\n"
            f"📍 *R1:* `${levels.get('R1',0):,.0f}` _(Resistencia)_\n"
            f"⚖️ *PIVOT:* `${p:,.0f}` _(Equilibrio)_\n"
            f"📍 *S1:* `${levels.get('S1',0):,.0f}` _(Soporte)_\n"
            f"🔻 *S2:* `${levels.get('S2',0):,.0f}` _(Extensión)_\n"
            f"🕳️ *S3:* `${levels.get('S3',0):,.0f}` _(Mínimo)_"
        )
    else:
        levels_msg = "⏳ _Calculando niveles..._"

    msg = (
        f"🦁 *Monitor BTC PRO*\n"
        f"—————————————————\n"
        f"{analysis_text}\n\n"
        f"—————————————————\n"
        f"{levels_msg}\n"
        f"—————————————————\n"
        f"🔔 *Suscripción:* {status_icon}\n\n"
        f"🎯 Alertas inteligentes con análisis técnico avanzado"
    )

    btn_text = "🔕 Desactivar" if subscribed else "🔔 Activar Alertas"
    kb = [[InlineKeyboardButton(btn_text, callback_data="toggle_btc_alerts")]]
    
    if is_callback:
        await update.callback_query.answer()
        await context.bot.send_message(chat_id=chat_id, text=msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)

async def btc_toggle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    new_status = toggle_btc_subscription(query.from_user.id)
    
    user_id = query.from_user.id
    btn_text = "🔕 Desactivar" if new_status else "🔔 Activar Alertas"
    kb = [[InlineKeyboardButton(btn_text, callback_data="toggle_btc_alerts")]]
    
    try:
        await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(kb))
        status_text = "✅ Alertas ACTIVADAS" if new_status else "🔕 Alertas DESACTIVADAS"
        await query.answer(status_text, show_alert=False)
    except:
        pass

async def btc_view_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback para el botón 'Ver Análisis'."""
    await btc_alerts_command(update, context)

btc_handlers_list = [
    CommandHandler("btcalerts", btc_alerts_command),
    CallbackQueryHandler(btc_toggle_callback, pattern="^toggle_btc_alerts$"),
    CallbackQueryHandler(btc_view_callback, pattern="^btcalerts_view$") 
]
