# handlers/rss.py

import re
import asyncio
import feedparser
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from telegram.constants import ParseMode

from core.rss_loop import render_notification, DEFAULT_TEMPLATE, TELEGRAM_STYLE
from utils.rss_manager import (
    check_rss_limits, add_rss_channel, get_user_rss, add_rss_feed, 
    delete_rss_item, load_rss_data, save_rss_data, update_feed_template, 
    get_feed_details, toggle_feed_active, manage_feed_filter
)

# Estados Conversación
ADD_CHANNEL_FWD, ADD_FEED_URL, ADD_FEED_SELECT_CH, EDIT_TEMPLATE_WAIT, FILTER_ADD_WORD = range(5)

async def rss_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_rss = get_user_rss(user_id)
    
    ch_count = len(user_rss['channels'])
    feed_count = len(user_rss['feeds'])
    
    txt = (
        "📰 *Centro de Control RSS*\n—————————————————\n"
        f"📊 *Estadísticas:*\n"
        f"• Canales/Grupos: {ch_count}\n"
        f"• Feeds Activos: {feed_count}\n\n"
        "Configura tus fuentes de noticias y destinos."
    )
    
    kb = [
        [InlineKeyboardButton("📺 Mis Canales/Grupos", callback_data="rss_menu_channels")],
        [InlineKeyboardButton("🔗 Mis Feeds RSS", callback_data="rss_menu_feeds")],
        [InlineKeyboardButton("🛒 Comprar Slots RSS", callback_data="rss_shop")]
    ]
    
    if update.callback_query:
        await update.callback_query.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
    else:
        await update.message.reply_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

# === GESTIÓN DE CANALES ===
async def menu_channels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_rss = get_user_rss(user_id)
    kb = []
    for ch in user_rss['channels']:
        kb.append([InlineKeyboardButton(f"🗑 {ch['title']}", callback_data=f"rss_del_ch_{ch['id']}")])
    kb.append([InlineKeyboardButton("➕ Añadir Nuevo Canal/Grupo", callback_data="rss_add_channel")])
    kb.append([InlineKeyboardButton("🔙 Volver", callback_data="rss_home")])
    await update.callback_query.edit_message_text(
        "📺 *Gestión de Destinos*\n\nAquí ves tus grupos/canales vinculados. Pulsa para eliminar.",
        reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown"
    )

async def start_add_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    can_add, curr, lim = check_rss_limits(query.from_user.id, 'channels')
    if not can_add:
        await query.answer(f"⚠️ Límite alcanzado ({curr}/{lim}).", show_alert=True)
        return ConversationHandler.END
    await query.message.reply_text(
        "➕ *Vincular Canal o Grupo*\n\n1. Añade a @BitBreadBot como admin.\n2. Reenvía un mensaje aquí o escribe el ID.",
        parse_mode="Markdown"
    )
    return ADD_CHANNEL_FWD

async def process_channel_fwd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    user_id = msg.from_user.id
    chat_id, title = None, None
    if getattr(msg, 'forward_origin', None):
        origin = msg.forward_origin
        if origin.type == 'channel':
            chat_id, title = origin.chat.id, origin.chat.title
        elif origin.type == 'chat':
            chat_id, title = origin.sender_chat.id, origin.sender_chat.title
    if not chat_id:
        try:
            chat_id = int(msg.text)
            chat_obj = await context.bot.get_chat(chat_id)
            title = chat_obj.title
        except:
            await msg.reply_text("❌ ID inválido o no es reenvío.")
            return ADD_CHANNEL_FWD
    try:
        member = await context.bot.get_chat_member(chat_id, context.bot.id)
        if member.status not in ['administrator', 'creator']:
            await msg.reply_text("⚠️ El bot no es admin en ese chat.")
            return ConversationHandler.END
    except Exception:
        await msg.reply_text("❌ Error acceso: añade al bot como admin.")
        return ConversationHandler.END
    success, text = add_rss_channel(user_id, chat_id, title)
    await msg.reply_text(f"{'✅' if success else '⚠️'} {text}")
    return ConversationHandler.END

# === GESTIÓN DE FEEDS ===
async def menu_feeds(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_rss = get_user_rss(user_id)
    kb = []
    for f in user_rss['feeds']:
        status = "🟢" if f.get('active', True) else "🔴"
        t = f['title'][:20] + "..." if len(f['title']) > 20 else f['title']
        kb.append([InlineKeyboardButton(f"{status} {t}", callback_data=f"rss_edit_{f['id']}")])
    kb.append([InlineKeyboardButton("➕ Añadir Feed", callback_data="rss_add_feed")])
    kb.append([InlineKeyboardButton("🔙 Volver", callback_data="rss_home")])
    await update.callback_query.edit_message_text(
        "🔗 *Gestión de Feeds RSS*\n\nPulsa para configurar:",
        reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown"
    )

async def start_add_feed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    can_add, curr, lim = check_rss_limits(query.from_user.id, 'feeds')
    if not can_add:
        await query.answer(f"⚠️ Límite alcanzado ({curr}/{lim}).", show_alert=True)
        return ConversationHandler.END
    await query.message.reply_text("🔗 Envía la **URL** del Feed RSS.")
    return ADD_FEED_URL

async def process_feed_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    context.user_data['new_rss_url'] = url
    user_rss = get_user_rss(update.effective_user.id)
    if not user_rss['channels']:
        await update.message.reply_text("⚠️ Añade un Canal primero.")
        return ConversationHandler.END
    kb = []
    for ch in user_rss['channels']:
        kb.append([InlineKeyboardButton(ch['title'], callback_data=f"rss_sel_ch_{ch['id']}")])
    await update.message.reply_text("📡 ¿A qué canal enviarás las noticias?", reply_markup=InlineKeyboardMarkup(kb))
    return ADD_FEED_SELECT_CH

async def process_feed_channel_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    ch_id = int(query.data.split('_')[-1])
    url = context.user_data.get('new_rss_url')
    
    await query.edit_message_text("⏳ Verificando Feed...")
    
    # Llamamos a la función (que ahora devuelve el objeto feed si es exitoso)
    success, result = add_rss_feed(query.from_user.id, url, ch_id)
    
    if success:
        feed_data = result # Aquí tenemos el dict con 'id', 'title', etc.
        feed_title = feed_data['title']
        feed_id = feed_data['id']
        
        # Creamos el botón reutilizando tu lógica existente de forzar envío
        kb = [[InlineKeyboardButton("⚡ Enviar Últimas Noticias", callback_data=f"rss_force_{feed_id}")]]
        
        await query.message.reply_text(
            f"✅ Feed *{feed_title}* añadido correctamente.",
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="Markdown"
        )
    else:
        error_msg = result
        await query.message.reply_text(f"❌ Error: {error_msg}")
        
    return ConversationHandler.END

# === EDICIÓN DE FEED ===
async def edit_feed_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, feed_id_override=None):
    query = update.callback_query
    feed_id = feed_id_override or query.data.split('_')[-1]
    feed = get_feed_details(query.from_user.id, feed_id)
    
    # Determinar estilo actual
    current_style = feed.get('format', 'bitbread')
    style_icon = "📱" if current_style == 'telegram' else "🍞"
    style_name = "Estilo: Telegram" if current_style == 'telegram' else "Estilo: BitBread"

    kb = [
        [
            InlineKeyboardButton(f"{'🟢' if feed.get('active', True) else '🔴'} Estado", callback_data=f"rss_toggle_{feed_id}"),
            InlineKeyboardButton(f"⚡ Probar", callback_data=f"rss_force_{feed_id}")
        ],
        [InlineKeyboardButton(f"{style_icon} {style_name}", callback_data=f"rss_switch_style_{feed_id}")],
        [InlineKeyboardButton(f"🚫 Filtros", callback_data=f"rss_filters_menu_{feed_id}")],
    ]

    # Solo mostrar botón de "Personalizar" si el estilo es BitBread
    if current_style == 'bitbread':
        has_tpl = "✅" if feed.get('template') else "📝"
        kb.append([InlineKeyboardButton(f"{has_tpl} Personalizar Plantilla", callback_data=f"rss_template_{feed_id}")])

    kb.append([InlineKeyboardButton(f"⏰ {feed.get('frequency', 60)}min", callback_data=f"rss_set_freq_{feed_id}")])
    kb.append([InlineKeyboardButton(f"🗑 ELIMINAR", callback_data=f"rss_delete_feed_{feed_id}")])
    kb.append([InlineKeyboardButton("🔙 Volver", callback_data="rss_menu_feeds")])

    await query.edit_message_text(f"⚙️ *Ajustes de Feed*\n📌 *{feed['title']}*", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

# === PLANTILLA EXPLICATIVA CON GUÍA HTML ===
# handlers/rss.py

async def ask_for_template(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    feed_id = query.data.split('_')[-1]
    context.user_data['editing_feed_id'] = feed_id
    
    # Obtener plantilla actual
    feed = get_feed_details(query.from_user.id, feed_id)
    current_tpl = feed.get('template', DEFAULT_TEMPLATE)
    if not current_tpl: current_tpl = DEFAULT_TEMPLATE

    # Texto explicativo detallado (TU VERSIÓN ORIGINAL)
    msg = (
        "📝 *Editor de Plantilla Avanzado*\n\n"
        "Configura cómo se ven tus noticias. Copia, edita y reenvía la plantilla de abajo.\n\n"
        "🔹 *Variables Automáticas:*\n"
        "`#media_title#` - Título\n"
        "`#media_url#` - Link de la noticia\n"
        "`#media_description#` - Resumen completo\n"
        "`#source_title#` - Nombre de la Fuente\n\n"
        "🎨 *Formato HTML (Telegram):*\n"
        "• Negrita: `<b>Texto</b>` → <b>Texto</b>\n"
        "• Cursiva: `<i>Texto</i>` → <i>Texto</i>\n"
        "• Enlace: `<a href='URL'>Texto</a>`\n"
        "• Código: `<code>Texto</code>`\n\n"
        "⚙️ *Opciones Especiales (Flags):*\n"
        "`#only_first_media#` (Solo 1ra foto)\n"
        "`#ignore_media#` (Sin fotos, solo texto)\n"
        "`#telegram_preview#` (Vista previa pequeña)\n\n"
        "🔘 *Botones:* `{{button|Texto|URL}}`\n\n"
        "👇 *TU PLANTILLA ACTUAL (Copia y edita):*"
    )
    
    # Enviamos la instrucción
    await query.message.reply_text(msg, parse_mode="Markdown")
    
    # Preparar el botón de Volver
    kb = [[InlineKeyboardButton("🔙 Cancelar / Volver", callback_data=f"rss_back_edit_{feed_id}")]]
    
    # Enviamos la plantilla con el botón adjunto
    import html
    safe_tpl = html.escape(current_tpl)
    await query.message.reply_text(f"<code>{safe_tpl}</code>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb))
    
    return EDIT_TEMPLATE_WAIT

async def cancel_template_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancela la edición de plantilla y vuelve al menú."""
    query = update.callback_query
    feed_id = query.data.split('_')[-1]
    
    await query.answer("Edición cancelada")
    # Volvemos al menú de edición del feed
    await edit_feed_menu(update, context, feed_id_override=feed_id)
    
    return ConversationHandler.END


async def save_template(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tpl = update.message.text
    feed_id = context.user_data.get('editing_feed_id')
    
    if update_feed_template(update.effective_user.id, feed_id, tpl):
        await update.message.reply_text("✅ Plantilla guardada exitosamente.")
    else:
        await update.message.reply_text("❌ Error guardando plantilla.")
        
    # Botón para volver
    kb = [[InlineKeyboardButton("🔙 Volver a Ajustes", callback_data=f"rss_edit_{feed_id}")]]
    await update.message.reply_text("Pulsa para continuar:", reply_markup=InlineKeyboardMarkup(kb))
    return ConversationHandler.END

# === FILTROS ===
async def menu_filters(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    feed_id = context.user_data.get('editing_feed_id')
    feed = get_feed_details(query.from_user.id, feed_id)
    if not feed: return await menu_feeds(update, context)
    
    kb = []
    for word in feed.get('filters', []):
        kb.append([InlineKeyboardButton(f"❌ {word}", callback_data=f"rss_del_filter_{word}")])
    kb.append([InlineKeyboardButton("➕ Añadir Palabra Prohibida", callback_data="rss_add_filter_prompt")])
    kb.append([InlineKeyboardButton("🔙 Volver", callback_data=f"rss_edit_{feed_id}")])
    
    await query.edit_message_text(
        "🚫 *Filtros de Palabras*\n\nSi una noticia contiene estas palabras, **NO** se enviará.",
        reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown"
    )

async def prompt_add_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.message.reply_text("🚫 Envía la **palabra o frase** a bloquear:")
    return FILTER_ADD_WORD

async def save_filter_word(update: Update, context: ContextTypes.DEFAULT_TYPE):
    word = update.message.text.strip()
    feed_id = context.user_data.get('editing_feed_id')
    manage_feed_filter(update.effective_user.id, feed_id, word, 'add')
    await update.message.reply_text(f"✅ Filtro añadido: '{word}'")
    kb = [[InlineKeyboardButton("🔙 Volver a Filtros", callback_data=f"rss_filters_menu_{feed_id}")]]
    await update.message.reply_text("Continuar:", reply_markup=InlineKeyboardMarkup(kb))
    return ConversationHandler.END

# === LOGICA DE ACCIONES ===
async def rss_action_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id
    
    # Navegación
    if data == "rss_home": return await rss_dashboard(update, context)
    if data == "rss_menu_channels": return await menu_channels(update, context)
    if data == "rss_menu_feeds": return await menu_feeds(update, context)
    if data.startswith("rss_edit_"): return await edit_feed_menu(update, context)

    # Eliminar
    if data.startswith("rss_del_ch_"):
        delete_rss_item(user_id, 'channels', data.split("_")[-1])
        await query.answer("Canal eliminado")
        return await menu_channels(update, context)
    if data.startswith("rss_delete_feed_"):
        delete_rss_item(user_id, 'feeds', data.split("_")[-1])
        await query.answer("Feed eliminado")
        return await menu_feeds(update, context)

    # Toggle Active
    if data.startswith("rss_toggle_"):
        f_id = data.split("_")[-1]
        new_status = toggle_feed_active(user_id, f_id)
        await query.answer(f"Feed {'Activado' if new_status else 'Pausado'}")
        return await edit_feed_menu(update, context, feed_id_override=f_id)

    # Filtros
    if data.startswith("rss_filters_menu_"):
        context.user_data['editing_feed_id'] = data.split("_")[-1]
        return await menu_filters(update, context)
    if data.startswith("rss_del_filter_"):
        manage_feed_filter(user_id, context.user_data.get('editing_feed_id'), data.replace("rss_del_filter_", ""), 'del')
        await query.answer("Filtro eliminado")
        return await menu_filters(update, context)

    # Force Send
    if data.startswith("rss_force_"):
        f_id = data.split("_")[-1]
        await query.answer("⚡ Enviando última noticia...")
        await force_send_implementation(update, context, user_id, f_id)
        return

    # Frecuencia
    if data.startswith("rss_set_freq_"):
        f_id = data.split("_")[-1]
        rss_data = load_rss_data()
        uid = str(user_id)
        for f in rss_data[uid]['feeds']:
            if f['id'] == f_id:
                freqs = [15, 30, 60, 120, 360]
                try: f['frequency'] = freqs[(freqs.index(f.get('frequency', 60)) + 1) % len(freqs)]
                except: f['frequency'] = 60
                break
        save_rss_data(rss_data)
        return await edit_feed_menu(update, context, feed_id_override=f_id)
    
    # Switch Style (BitBread <-> Telegram)
    if data.startswith("rss_switch_style_"):
        f_id = data.split("_")[-1]
        rss_data = load_rss_data()
        uid = str(user_id)
        for f in rss_data[uid]['feeds']:
            if f['id'] == f_id:
                # Cambiamos entre estilos
                f['format'] = 'telegram' if f.get('format', 'bitbread') == 'bitbread' else 'bitbread'
                break
        save_rss_data(rss_data)
        await query.answer(f"Cambiado a {f['format']}")
        return await edit_feed_menu(update, context, feed_id_override=f_id)

async def force_send_implementation(update, context, user_id, feed_id):
    """Fuerza el envío de las últimas noticias (CORREGIDO)."""
    feed = get_feed_details(user_id, feed_id)
    if not feed: return

    try:
        parsed = feedparser.parse(feed['url'])
        if not parsed.entries:
            await update.callback_query.message.reply_text("⚠️ El feed está vacío o inaccesible.")
            return

        entries_to_send = parsed.entries[:3] # Enviamos hasta 3
        
        await update.callback_query.message.reply_text(f"⚡ Enviando {len(entries_to_send)} noticias...")

        for latest in entries_to_send:
            # 1. CORRECCIÓN DEL ERROR .GET: Pasamos 'feed' completo
            msg_text, buttons, flags = render_notification(
                feed, latest, 
                feed.get('title', 'RSS'), parsed.feed.get('link', '')
            )
            
            reply_markup = InlineKeyboardMarkup(buttons) if buttons else None
            target_id = feed['target_channel_id']
            
            # === EXTRACCIÓN DE IMAGEN (RESUMIDA) ===
            img_url = None
            if not flags['ignore_media']:
                if 'media_content' in latest:
                     for m in latest['media_content']:
                        if 'image' in m.get('type', '') or any(x in m.get('url', '').lower() for x in ['.jpg', '.png', '.webp']):
                            img_url = m['url']; break
                if not img_url and 'links' in latest:
                    for l in latest['links']:
                        if 'image' in l.get('type', '') and 'href' in l: img_url = l['href']; break
                if not img_url and 'media_thumbnail' in latest:
                        if latest['media_thumbnail']: img_url = latest['media_thumbnail'][0]['url']
                if not img_url:
                    full_html = latest.get('summary', '') + latest.get('description', '')
                    if 'content' in latest:
                        for c in latest['content']: full_html += c.get('value', '')
                    img_tags = re.findall(r'<img[^>]+src=["\']\s*([^"\'>]+)["\']', full_html, re.IGNORECASE)
                    for possible_url in img_tags:
                        bad_keywords = ['emoji', 'icon', 'pixel', 'avatar', 'gravatar', 'share', 'button', 'gif']
                        if any(k in possible_url.lower() for k in bad_keywords): continue
                        img_url = possible_url; break 

            # === ENVÍO CORREGIDO (SendPhoto Priority) ===
            try:
                sent = False
                if img_url:
                    try:
                        # Control de longitud para caption (max 1024)
                        caption_txt = msg_text
                        if len(caption_txt) > 1024: caption_txt = caption_txt[:1000] + "..."
                        
                        await context.bot.send_photo(
                            chat_id=target_id, 
                            photo=img_url,
                            caption=caption_txt,
                            parse_mode=ParseMode.HTML, 
                            reply_markup=reply_markup
                        )
                        sent = True
                    except Exception as e:
                        # Si falla la foto, no pasa nada, intentamos send_message abajo
                        pass

                if not sent:
                    if img_url:
                        header = f"<a href='{img_url}'>\u200b</a>"
                        msg_text = header + msg_text
                    
                    await context.bot.send_message(
                        chat_id=target_id, text=msg_text, parse_mode=ParseMode.HTML,
                        reply_markup=reply_markup, disable_web_page_preview=False
                    )
                
                await asyncio.sleep(1)
                
            except Exception as e:
                await update.callback_query.message.reply_text(f"❌ Error envío: {e}")

        await update.callback_query.message.reply_text(f"✅ Proceso finalizado.")

    except Exception as e:
        await update.callback_query.message.reply_text(f"❌ Error feed: {e}")

# === CONVERSATION HANDLER ===
rss_conv_handler = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(start_add_channel, pattern="^rss_add_channel$"),
        CallbackQueryHandler(start_add_feed, pattern="^rss_add_feed$"),
        CallbackQueryHandler(ask_for_template, pattern="^rss_template_"),
        CallbackQueryHandler(prompt_add_filter, pattern="^rss_add_filter_prompt$")
    ],
    states={
        ADD_CHANNEL_FWD: [MessageHandler(filters.ALL & ~filters.COMMAND, process_channel_fwd)],
        ADD_FEED_URL: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_feed_url)],
        ADD_FEED_SELECT_CH: [CallbackQueryHandler(process_feed_channel_select, pattern="^rss_sel_ch_")],
        EDIT_TEMPLATE_WAIT: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, save_template),
            CallbackQueryHandler(cancel_template_edit, pattern="^rss_back_edit_")
        ],
        FILTER_ADD_WORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_filter_word)]
    },
    fallbacks=[CommandHandler("cancel", rss_dashboard)]
)