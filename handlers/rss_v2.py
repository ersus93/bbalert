# handlers/rss_v2.py - VERSIÓN CORREGIDA Y ORDENADA

import re
import html
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from telegram.constants import ParseMode
from utils.rss_manager_v2 import RSSManager
from utils.file_manager import add_log_line

rss_manager = RSSManager()

# ============================================================
# 1. ESTADOS DE CONVERSACIÓN (Definición única y completa)
# ============================================================
(
    ADD_CHANNEL_FWD, ADD_FEED_URL, SELECT_CHANNEL, 
    SELECT_FORMAT, EDIT_TEMPLATE, ADD_FILTER_PATTERN,
    ADD_FILTER_MODE, EDIT_REPLACEMENT, EDIT_FREQUENCY, 
    EDIT_TEMPLATE_TEXT
) = range(10)

# ============================================================
# 2. DASHBOARD PRINCIPAL
# ============================================================

async def rss_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Dashboard principal de RSS."""
    user_id = update.effective_user.id
    user_data = rss_manager.get_user_data(user_id)
    
    ch_count = len(user_data.get('channels', []))
    feed_count = len(user_data.get('feeds', []))
    total_sent = sum(f.get('stats', {}).get('total_sent', 0) for f in user_data.get('feeds', []))
    
    txt = (
        "📰 *Centro de Control RSS Pro*\n"
        "—————————————————\n\n"
        f"📊 *Estadísticas:*\n"
        f"  • Canales/Grupos: {ch_count}\n"
        f"  • Feeds Activos: {feed_count}\n"
        f"  • Noticias Enviadas: {total_sent}\n\n"
        "Gestiona tus fuentes con filtros, plantillas personalizadas y más."
    )
    
    kb = [
        [InlineKeyboardButton("📺 Mis Canales", callback_data="rss_channels")],
        [InlineKeyboardButton("🔗 Mis Feeds", callback_data="rss_feeds_list")],
        [InlineKeyboardButton("🛒 Comprar Slots", callback_data="rss_shop")],
    ]
    
    if update.callback_query:
        await update.callback_query.edit_message_text(
            txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN
        )
    else:
        await update.message.reply_text(
            txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN
        )

# ============================================================
# 3. GESTIÓN DE CANALES
# ============================================================

async def menu_channels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menú de canales."""
    query = update.callback_query
    user_id = query.from_user.id
    user_data = rss_manager.get_user_data(user_id)
    
    kb = []
    for ch in user_data.get('channels', []):
        kb.append([InlineKeyboardButton(
            f"🗑 {ch['title']}", 
            callback_data=f"rss_del_ch_{ch['id']}"
        )])
    
    kb.append([InlineKeyboardButton("➕ Nuevo Canal", callback_data="rss_add_channel")])
    kb.append([InlineKeyboardButton("🔙 Volver", callback_data="rss_home")])
    
    await query.edit_message_text(
        "📺 *Mis Canales/Grupos*\n\nPulsa para eliminar.",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode=ParseMode.MARKDOWN
    )

async def start_add_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inicia flujo de añadir canal."""
    query = update.callback_query
    user_id = query.from_user.id
    
    can_add, curr, lim = rss_manager.check_limits(user_id, 'channels')
    
    if not can_add:
        await query.answer(f"⚠️ Límite alcanzado ({curr}/{lim})", show_alert=True)
        return ConversationHandler.END
    
    msg = (
        "➕ *Vincular Canal*\n\n"
        "1. Añade @BitBreadBot como admin\n"
        "2. Reenvía un mensaje del canal aquí\n\n"
        "O envía el ID del canal (ej: -1001234567890)"
    )
    
    await query.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
    return ADD_CHANNEL_FWD

async def process_channel_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Procesa entrada de canal."""
    msg = update.message
    user_id = msg.from_user.id
    chat_id = None
    title = None
    
    # Intentar obtener del reenvío
    if msg.forward_origin:
        origin = msg.forward_origin
        if hasattr(origin, 'chat'):
            chat_id = origin.chat.id
            title = origin.chat.title
    
    # Si no hay reenvío, intentar parsear como ID
    if not chat_id:
        try:
            chat_id = int(msg.text.strip())
            try:
                chat_obj = await context.bot.get_chat(chat_id)
                title = chat_obj.title
            except:
                await msg.reply_text("❌ ID inválido o bot no es admin en ese chat.")
                return ADD_CHANNEL_FWD
        except:
            await msg.reply_text("❌ Formato inválido. Usa: reenvío del chat o ID numérico.")
            return ADD_CHANNEL_FWD
    
    # Verificar permisos del bot
    try:
        member = await context.bot.get_chat_member(chat_id, context.bot.id)
        if member.status not in ['administrator', 'creator']:
            await msg.reply_text("⚠️ El bot no es admin en ese chat.")
            return ConversationHandler.END
    except Exception as e:
        await msg.reply_text(f"❌ Error: {str(e)[:100]}")
        return ConversationHandler.END
    
    # Guardar canal
    data = RSSManager.load_data()
    if str(user_id) not in data:
        data[str(user_id)] = rss_manager.get_user_data(user_id)
    
    # Evitar duplicados
    for ch in data[str(user_id)].get('channels', []):
        if ch['id'] == chat_id:
            await msg.reply_text("✅ Este canal ya está vinculado.")
            return ConversationHandler.END
    
    data[str(user_id)]['channels'].append({
        'id': chat_id,
        'title': title or f'Chat {chat_id}'
    })
    
    RSSManager.save_data(data)
    # MENÚ DE NAVEGACIÓN MEJORADO
    kb = [
        [InlineKeyboardButton("➕ Añadir Otro Canal", callback_data="rss_add_channel")],
        [InlineKeyboardButton("🔗 Ir a Mis Feeds", callback_data="rss_feeds_list")],
        [InlineKeyboardButton("🏠 Menú Principal", callback_data="rss_home")]
    ]
    
    await msg.reply_text(
        f"✅ *¡Éxito!*\nCanal '{title}' vinculado correctamente.",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode=ParseMode.MARKDOWN
    )
    return ConversationHandler.END

# ============================================================
# 4. AGREGAR FEED
# ============================================================

async def start_add_feed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inicio del proceso de añadir feed."""
    query = update.callback_query
    user_id = query.from_user.id
    
    can_add, curr, lim = rss_manager.check_limits(user_id, 'feeds')
    
    if not can_add:
        await query.answer(f"⚠️ Límite alcanzado ({curr}/{lim})", show_alert=True)
        return ConversationHandler.END
    
    msg = (
        "🔗 *Añadir Feed RSS*\n\n"
        "Soporta:\n"
        "  • RSS/Atom estándar\n\n"
        "  • *Proximamente*\n "
        "  • Canales Telegram\n"
        "  • Perfiles Twitter/X\n"
        "  • Cuentas Instagram\n"
        "  • Canales YouTube\n\n"
        "Envía la **URL**:"
    )
    
    await query.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
    return ADD_FEED_URL

async def process_feed_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Procesa URL del feed."""
    url = update.message.text.strip()
    context.user_data['new_feed_url'] = url
    
    user_id = update.effective_user.id
    user_data = rss_manager.get_user_data(user_id)
    
    if not user_data.get('channels', []):
        await update.message.reply_text(
            "⚠️ Primero debes añadir un **Canal/Grupo** de destino.\n\n"
            "Usa: /rss → Mis Canales → Nuevo Canal"
        )
        return ConversationHandler.END
    
    kb = []
    for ch in user_data['channels']:
        kb.append([InlineKeyboardButton(
            f"📺 {ch['title']}", 
            callback_data=f"rss_select_ch_{ch['id']}"
        )])
    
    await update.message.reply_text(
        "📡 ¿A qué canal enviarás el feed?",
        reply_markup=InlineKeyboardMarkup(kb)
    )
    
    return SELECT_CHANNEL

async def select_channel_for_feed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Selecciona canal destino."""
    query = update.callback_query
    ch_id = int(query.data.split('_')[-1])
    url = context.user_data.get('new_feed_url')
    
    await query.edit_message_text("⏳ Validando feed... (puede tardar 30s)")
    
    # Validar feed
    success, result = await rss_manager.add_feed_advanced(
        query.from_user.id,
        url,
        ch_id,
        format_type="bitbread"
    )
    
    if success:
        feed = result
        kb = [
            [InlineKeyboardButton("⚡ Probar Envío", callback_data=f"rss_force_send_{feed['id']}")],
            [InlineKeyboardButton("📝 Personalizar Plantilla", callback_data=f"rss_template_{feed['id']}")],
            [InlineKeyboardButton("➕ Añadir Otro Feed", callback_data="rss_add_feed")],  # <-- NUEVO
            [InlineKeyboardButton("🏠 Menú Principal", callback_data="rss_home")]          # <-- NUEVO
        ]
        
        await query.message.reply_text(
            f"✅ *Feed Configurado*\n\n"
            f"📰 Fuente: {feed['source_title']}\n"
            f"🎯 Destino: (Canal ID {ch_id})",
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode=ParseMode.MARKDOWN
        )

# ============================================================
# 5. LISTA Y EDICIÓN DE FEEDS
# ============================================================

async def menu_feeds(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menú de feeds."""
    query = update.callback_query
    user_id = query.from_user.id
    user_data = rss_manager.get_user_data(user_id)
    
    kb = []
    for f in user_data.get('feeds', []):
        status = "🟢" if f.get('active', True) else "🔴"
        t = f['source_title'][:25] + "..." if len(f['source_title']) > 25 else f['source_title']
        kb.append([InlineKeyboardButton(
            f"{status} {t}", 
            callback_data=f"rss_edit_{f['id']}"
        )])
    
    kb.append([InlineKeyboardButton("➕ Nuevo Feed", callback_data="rss_add_feed")])
    kb.append([InlineKeyboardButton("🔙 Volver", callback_data="rss_home")])
    
    await query.edit_message_text(
        f"🔗 *Mis Feeds ({len(user_data.get('feeds', []))})*\n\nPulsa para editar:",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode=ParseMode.MARKDOWN
    )

async def edit_feed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menú de edición de feed."""
    query = update.callback_query
    
    # Obtener feed_id del callback o del contexto temporal
    if query and query.data:
        feed_id = query.data.split('_')[-1]
    else:
        feed_id = context.user_data.get('temp_feed_id')
        context.user_data.pop('temp_feed_id', None)  # Limpiar
    
    if not feed_id:
        await query.answer("Feed no encontrado", show_alert=True)
        return
    
    user_id = query.from_user.id
    feed = rss_manager.get_feed(user_id, feed_id)
    
    if not feed:
        await query.answer("Feed no encontrado", show_alert=True)
        return
    
    # ... resto del código

    
    current_format = feed.get('format', 'telegram') # 'telegram' o 'bitbread'

    # === CÁLCULO DE btn_style_text ===
    if current_format == 'bitbread':
        # Opción para cambiar a formato Telegram
        btn_style_text = "🔄 Cambiar a formato Telegram"
    else:
        # Opción para cambiar a formato BitBread
        btn_style_text = "🔄 Cambiar a formato BitBread"   
    
    status_icon = "🟢" if feed.get('active') else "🔴"
    
    kb = [
        [
            InlineKeyboardButton(f"{status_icon} Estado", callback_data=f"rss_toggle_{feed_id}"),
            InlineKeyboardButton("⚡ Probar", callback_data=f"rss_force_send_{feed_id}")
        ],
        [InlineKeyboardButton("📝 Personalizar", callback_data=f"rss_template_{feed_id}")],
        [InlineKeyboardButton(btn_style_text, callback_data=f"rss_switch_style_{feed_id}")],
        [InlineKeyboardButton("🚫 Filtros", callback_data=f"rss_filters_{feed_id}")],
        [InlineKeyboardButton(f"⏰ {feed.get('frequency_minutes', 60)}min", callback_data=f"rss_freq_{feed_id}")],
        [InlineKeyboardButton("📊 Estadísticas", callback_data=f"rss_stats_{feed_id}")],
        [InlineKeyboardButton("🗑 Eliminar", callback_data=f"rss_delete_{feed_id}")],
        [InlineKeyboardButton("🔙 Volver", callback_data="rss_feeds_list")],
    ]

    await query.edit_message_text(
        f"⚙️ *{feed['source_title']}*\n"
        f"Tipo: {feed['detected_type']}\n"
        f"Estado: {'Activo' if feed.get('active') else 'Pausado'}\n"
        f"Enviados: {feed.get('stats', {}).get('total_sent', 0)}\n"
        f"Bloqueados: {feed.get('stats', {}).get('total_blocked', 0)}",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode=ParseMode.MARKDOWN
    )

# ============================================================
# 6. FILTROS
# ============================================================

async def manage_filters_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menú de gestión de filtros."""
    query = update.callback_query
    feed_id = query.data.split('_')[-1]
    context.user_data['editing_feed_id'] = feed_id
    
    user_id = query.from_user.id
    data = RSSManager.load_data()
    user_data = data.get(str(user_id), {})
    
    feed = next((f for f in user_data.get('feeds', []) if f['id'] == feed_id), None)
    if not feed:
        await query.answer("Feed no encontrado")
        return
    
    kb = []
    
    for i, filt in enumerate(feed.get('filters', [])):
        mode_icon = "🚫" if filt['mode'] == 'block' else "✏️"
        pattern = filt['pattern'][:20]
        kb.append([InlineKeyboardButton(
            f"{mode_icon} {pattern}",
            callback_data=f"rss_del_filter_{feed_id}_{i}"
        )])
    
    kb.append([InlineKeyboardButton("➕ Nuevo", callback_data=f"rss_add_filt_{feed_id}")])
    kb.append([InlineKeyboardButton("🔙 Volver", callback_data=f"rss_edit_{feed_id}")])
    
    await query.edit_message_text(
        "🚫 *Filtros de Contenido*\n\n"
        "🚫 Bloquear | ✏️ Reemplazar",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode=ParseMode.MARKDOWN
    )

async def add_filter_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Flujo de añadir filtro."""
    query = update.callback_query
    feed_id = query.data.split('_')[-1]
    context.user_data['filter_feed_id'] = feed_id
    
    await query.message.reply_text(
        "🚫 *Nuevo Filtro*\n\n"
        "¿Qué palabra deseas filtrar?\n\n"
        "Ejemplos: `covid`, `política`, `spam`",
        parse_mode=ParseMode.MARKDOWN
    )
    return ADD_FILTER_PATTERN

async def filter_pattern_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Recibe patrón."""
    pattern = update.message.text.strip()
    context.user_data['filter_pattern'] = pattern
    
    kb = [
        [InlineKeyboardButton("🚫 Bloquear", callback_data="filt_mode_block")],
        [InlineKeyboardButton("✏️ Reemplazar", callback_data="filt_mode_replace")],
    ]
    
    await update.message.reply_text(
        f"¿Qué hacer con '{pattern}'?",
        reply_markup=InlineKeyboardMarkup(kb)
    )
    
    return ADD_FILTER_MODE

async def filter_mode_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Selecciona modo."""
    query = update.callback_query
    mode = query.data.split('_')[-1]
    context.user_data['filter_mode'] = mode
    
    feed_id = context.user_data.get('filter_feed_id')
    pattern = context.user_data.get('filter_pattern')
    
    if mode == 'block':
        success, msg = rss_manager.add_filter_to_feed(
            query.from_user.id,
            feed_id,
            pattern,
            mode="block"
        )
        await query.answer(msg, show_alert=not success)
        return ConversationHandler.END
    else:
        await query.message.reply_text(
            f"¿Por qué reemplazar '{pattern}'?\n\n"
            "(Vacío = ocultar completamente)"
        )
        return EDIT_REPLACEMENT

async def replacement_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Recibe reemplazo."""
    replacement = update.message.text.strip()
    
    feed_id = context.user_data.get('filter_feed_id')
    
    kb = [
        [InlineKeyboardButton("➕ Añadir Otro Filtro", callback_data=f"rss_add_filt_{feed_id}")],
        [InlineKeyboardButton("🔙 Volver al Feed", callback_data=f"rss_edit_{feed_id}")]
    ]
    
    await update.message.reply_text(
        f"✅ Filtro guardado.\n¿Qué deseas hacer ahora?",
        reply_markup=InlineKeyboardMarkup(kb)
    )
    return ConversationHandler.END

# ============================================================
# 7. EDITOR DE PLANTILLAS Y FORCE SEND (NUEVAS FUNCIONES)
# ============================================================

async def start_template_editor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inicia el editor de plantillas manteniendo los botones."""
    query = update.callback_query
    feed_id = query.data.split('_')[-1]
    context.user_data['editing_feed_id'] = feed_id
    
    user_id = query.from_user.id
    
    # Obtener feed y plantilla actual
    data = RSSManager.load_data()
    user_data = data.get(str(user_id), {})
    feed = next((f for f in user_data.get('feeds', []) if f['id'] == feed_id), None)
    
    current = feed.get('template', '')
    
    msg = (
        "📝 *Editor de Plantilla Avanzado*\n\n"
        "Copia, edita y reenvía el bloque de código de abajo.\n\n"
        "*🔹 Variables Disponibles:*\n"
        "• `#media_title#` - Título\n"
        "• `#media_description#` - Descripción completa\n"
        "• `#media_short_description#` - Descripción corta\n"
        "• `#media_url#` - Enlace noticia\n"
        "• `#source_title#` - Nombre fuente\n"
        "• `#summary#` - Resumen\n\n"
        "*⚙️ Flags de Control (Ponlos donde sea):*\n"
        "• `#only_first_media#` (Solo 1ra foto)\n"
        "• `#ignore_media#` (Solo texto, sin fotos)\n"
        "• `#telegram_preview#` (Forzar vista previa)\n"
        "• `#no_view_original_post_link#` (Sin enlace)\n\n"
        "*🔘 Botones:*\n"
        "`{{button|Texto del Botón|URL}}`\n\n"
        "*👇 TU PLANTILLA ACTUAL:*"
    )
    
    # Botón de cancelar visible
    kb = [[InlineKeyboardButton("🔙 Cancelar", callback_data=f"rss_edit_{feed_id}")]]
    
    await query.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
    await query.message.reply_text(
        f"`{current}`", 
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(kb)
    )
    return EDIT_TEMPLATE_TEXT

async def save_template(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Guarda la plantilla personalizada."""
    try:
        user_id = update.effective_user.id
        template_text = update.message.text.strip()
        feed_id = context.user_data.get('editing_feed_id')
        
        if not feed_id:
            await update.message.reply_text(
                "❌ Sesión expirada. Inicia el editor de nuevo con /rss",
                parse_mode=ParseMode.MARKDOWN
            )
            return ConversationHandler.END
        
        success, msg = rss_manager.update_feed_template(user_id, feed_id, template_text)
        
        if success:
            kb = [
                [InlineKeyboardButton("⚡ Probar", callback_data=f"rss_force_send_{feed_id}")],
                [InlineKeyboardButton("🔙 Volver", callback_data=f"rss_edit_{feed_id}")]
            ]
            
            await update.message.reply_text(
                f"✅ *Plantilla Guardada*\n\nLa próxima noticia usará este formato.",
                reply_markup=InlineKeyboardMarkup(kb),
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await update.message.reply_text(
                f"❌ *Error:* {msg}\n\nEnvía la plantilla corregida o /cancel para salir.",
                parse_mode=ParseMode.MARKDOWN
            )
            return EDIT_TEMPLATE_TEXT
        
    except Exception as e:
        add_log_line(f"❌ Error en save_template: {e}")
        await update.message.reply_text(
            f"❌ Error interno. Usa /cancel para salir.",
            parse_mode=ParseMode.MARKDOWN
        )
    
    return ConversationHandler.END


# handlers/rss_v2.py - ACTUALIZACIÓN DEL FORCE SEND

async def force_send_feed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Envía noticias manualmente con mejor feedback."""
    query = update.callback_query
    feed_id = query.data.split('_')[-1]
    user_id = query.from_user.id
    
    await query.answer("⏳ Verificando feed...", show_alert=False)
    
    try:
        from core.rss_loop_v2 import get_rss_monitor
        monitor = get_rss_monitor()
        
        if not monitor:
            await query.message.reply_text("❌ Monitor RSS no disponible")
            return
        
        # Mensaje de progreso
        progress_msg = await query.message.reply_text(
            "⏳ *Procesando feed...*\n\n"
            "• Descargando noticias\n"
            "• Verificando permisos\n"
            "• Enviando al canal...",
            parse_mode=ParseMode.MARKDOWN
        )
        
        success, message = await monitor.force_send_feed(user_id, feed_id)
        
        # Actualizar mensaje
        if success:
            await progress_msg.edit_text(
                f"✅ *Éxito*\n\n{message}",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await progress_msg.edit_text(
                f"❌ *Error*\n\n{message}\n\n"
                "*Posibles causas:*\n"
                "• El bot no es admin del canal\n"
                "• El bot fue expulsado\n"
                "• Feed sin entradas nuevas\n"
                "• URL del feed inválida",
                parse_mode=ParseMode.MARKDOWN
            )
    
    except Exception as e:
        add_log_line(f"❌ Error en force_send: {e}")
        import traceback
        add_log_line(f"Traceback: {traceback.format_exc()[:500]}")
        
        await query.message.reply_text(
            f"❌ *Error Técnico*\n\n"
            f"`{str(e)[:200]}`\n\n"
            "Revisa los logs del servidor.",
            parse_mode=ParseMode.MARKDOWN
        )



# ============================================================
# 8. HANDLER DE ACCIONES RÁPIDAS
# ============================================================

async def rss_action_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """✅ MANEJADOR CENTRAL de todas las acciones RSS."""
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id

    # ✅ RESPONDER INMEDIATAMENTE para evitar timeouts
    try:
        await query.answer()
    except Exception:
        pass  # Si ya expiró, continuar de todas formas
    
    # Ignorar callbacks de conversación
    conversation_patterns = ["rss_template_", "rss_add_filt_", "rss_select_ch_", "filt_mode_"]
    if any(data.startswith(p) for p in conversation_patterns):
        return

    # ✅ NUEVA VALIDACIÓN: Ignorar callbacks manejados por ConversationHandler
    conversation_patterns = [
        "rss_template_",      # Editor de plantillas
        "rss_add_filt_",      # Añadir filtros
        "rss_select_ch_",     # Seleccionar canal
        "filt_mode_",         # Modo de filtro
    ]
    
    for pattern in conversation_patterns:
        if data.startswith(pattern):
            return
    
    try:
        # Navegación principal
        if data == "rss_home":
            await rss_dashboard(update, context)
        
        elif data == "rss_channels":
            await menu_channels(update, context)
        
        elif data == "rss_feeds_list":
            await menu_feeds(update, context)
        
        elif data == "rss_add_feed":
            await start_add_feed(update, context)
        
        elif data == "rss_add_channel":
            await start_add_channel(update, context)
        
        # ============ EDITAR FEED ============
        elif data.startswith("rss_edit_"):
            # Esta función DEBE existir arriba en el archivo como 'async def edit_feed(...)'
            await edit_feed(update, context)

        # ============ CAMBIAR ESTILO (BitBread <-> Telegram) ============
        elif data.startswith("rss_switch_style_"):
            feed_id = data.split('_')[-1]
    
            # Ejecutamos el cambio en el manager
            success, message = rss_manager.switch_feed_format(user_id, feed_id)
    
            if success:
                await query.answer(f"🔄 {message}")
        
                # ✅ CORRECCIÓN: Llamar directamente sin modificar query.data
                # Crear un contexto simulado con el feed_id
                context.user_data['temp_feed_id'] = feed_id
        
                # Recargar el menú de edición
                await edit_feed(update, context)
            else:
                await query.answer(f"❌ {message}", show_alert=True)

        # ============ TOGGLE ACTIVO/INACTIVO ============
        elif data.startswith("rss_toggle_"):
            feed_id = data.split('_')[-1]
            rss_data = RSSManager.load_data()
            for feed in rss_data.get(str(user_id), {}).get('feeds', []):
                if feed['id'] == feed_id:
                    feed['active'] = not feed.get('active', True)
                    RSSManager.save_data(rss_data)
                    status = "✅ Activado" if feed['active'] else "⏸ Pausado"
                    await query.answer(status)
                    await edit_feed(update, context)
                    break
        
        # ============ ELIMINAR FEED ============
        elif data.startswith("rss_delete_"):
            feed_id = data.split('_')[-1]
            rss_data = RSSManager.load_data()
            user_data = rss_data.get(str(user_id), {})
            user_data['feeds'] = [f for f in user_data['feeds'] if f['id'] != feed_id]
            RSSManager.save_data(rss_data)
            await query.answer("✅ Feed eliminado")
            await menu_feeds(update, context)
        
        # ============ ELIMINAR CANAL ============
        elif data.startswith("rss_del_ch_"):
            ch_id = int(data.split('_')[-1])
            rss_data = RSSManager.load_data()
            user_data = rss_data.get(str(user_id), {})
            user_data['channels'] = [ch for ch in user_data['channels'] if ch['id'] != ch_id]
            RSSManager.save_data(rss_data)
            await query.answer("✅ Canal eliminado")
            await menu_channels(update, context)
        
        # ============ ELIMINAR FILTRO ============
        elif data.startswith("rss_del_filter_"):
            parts = data.split('_')
            feed_id = parts[3]
            filter_idx = int(parts[4])
            
            rss_data = RSSManager.load_data()
            feed = next((f for f in rss_data.get(str(user_id), {}).get('feeds', []) if f['id'] == feed_id), None)
            
            if feed and 0 <= filter_idx < len(feed.get('filters', [])):
                filt = feed['filters'][filter_idx]
                feed['filters'].pop(filter_idx)
                RSSManager.save_data(rss_data)
                await query.answer(f"✅ Filtro '{filt['pattern']}' eliminado")
                await manage_filters_menu(update, context)
        
        # ============ CAMBIAR FRECUENCIA ============
        elif data.startswith("rss_freq_"):
            feed_id = data.split('_')[-1]
            rss_data = RSSManager.load_data()
            feed = next((f for f in rss_data.get(str(user_id), {}).get('feeds', []) if f['id'] == feed_id), None)
            
            if feed:
                freqs = [15, 30, 60, 120, 360]
                current = feed.get('frequency_minutes', 60)
                try:
                    idx = freqs.index(current)
                    feed['frequency_minutes'] = freqs[(idx + 1) % len(freqs)]
                except:
                    feed['frequency_minutes'] = 60
                
                RSSManager.save_data(rss_data)
                await query.answer(f"✅ Frecuencia: {feed['frequency_minutes']}min")
                await edit_feed(update, context)
        
        
        # ============ ESTADÍSTICAS ============
        elif data.startswith("rss_stats_"):
            feed_id = data.split('_')[-1]
            rss_data = RSSManager.load_data()
            feed = next((f for f in rss_data.get(str(user_id), {}).get('feeds', []) if f['id'] == feed_id), None)
            
            if feed and feed.get('stats'):
                stats = feed['stats']
                msg = (
                    f"📊 *Estadísticas*\n\n"
                    f"📤 Enviados: {stats.get('total_sent', 0)}\n"
                    f"🚫 Bloqueados: {stats.get('total_blocked', 0)}\n"
                    f"⚠️ Último error: {stats.get('last_error', 'Ninguno')}"
                )
                await query.answer(msg, show_alert=True)

        # ============ TIENDA ============    
        elif data == "rss_shop":
            # Llamamos a la función shop_command que importaremos o enviamos mensaje
            await query.answer()
            await query.message.reply_text(
                "🛒 *Tienda BitBread*\n\n"
                "Para comprar slots extra para feeds o canales, usa el comando:\n"
                "👉 /shop",
                parse_mode=ParseMode.MARKDOWN
            )

        
        
        elif data == "rss_feeds_list":
            await menu_feeds(update, context)    
        # ============ PROBAR ENVÍO (FORCE SEND) ============
        elif data.startswith("rss_force_send_"):
            await force_send_feed(update, context)
        
        # ============ FILTROS ============
        elif data.startswith("rss_filters_"):
            await manage_filters_menu(update, context)
        
        elif data.startswith("rss_add_filt_"):
            await add_filter_flow(update, context)
        
        else:
            add_log_line(f"⚠️ Callback no reconocido: {data}")
            await query.answer("❌ Acción no reconocida")
    
    except Exception as e:
        add_log_line(f"❌ Error en rss_action_handler: {e}")
        # ❌ NO INTENTAR query.answer() aquí si ya expiró
        try:
            await query.message.reply_text(
                f"❌ Error: {str(e)[:100]}",
                parse_mode=ParseMode.MARKDOWN
            )
        except:
            pass

async def cancel_template_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancela la edición de plantilla y vuelve al menú del feed."""
    user_id = update.effective_user.id
    feed_id = context.user_data.get('editing_feed_id')
    
    add_log_line(f"DEBUG: Cancelando edición de plantilla para feed {feed_id}")
    
    # Limpiar datos
    context.user_data.pop('editing_feed_id', None)
    
    if feed_id:
        # Volver al menú de edición del feed
        await update.message.reply_text(
            "❌ Edición de plantilla cancelada.",
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Simular callback para volver al menú
        from telegram import CallbackQuery
        query = CallbackQuery(
            id="temp",
            from_user=update.effective_user,
            chat_instance="temp",
            data=f"rss_edit_{feed_id}"
        )
        temp_update = Update(update.update_id, callback_query=query)
        
        # Llamar a edit_feed para restaurar el menú
        await edit_feed(temp_update, context)
    else:
        await update.message.reply_text(
            "❌ Edición cancelada.",
            parse_mode=ParseMode.MARKDOWN
        )
    
    return ConversationHandler.END

# ============================================================
# 9. CONVERSATION HANDLER (Al final, para que encuentre todo)
# ============================================================

rss_conv_handler_v2 = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(start_add_feed, pattern="^rss_add_feed$"),
        CallbackQueryHandler(start_add_channel, pattern="^rss_add_channel$"),
        CallbackQueryHandler(manage_filters_menu, pattern="^rss_filters_"),
        CallbackQueryHandler(add_filter_flow, pattern="^rss_add_filt_"),
        CallbackQueryHandler(start_template_editor, pattern="^rss_template_"),  # ✅ CRÍTICO
    ],
    states={
        ADD_CHANNEL_FWD: [MessageHandler(filters.ALL & ~filters.COMMAND, process_channel_input)],
        ADD_FEED_URL: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_feed_url)],
        SELECT_CHANNEL: [CallbackQueryHandler(select_channel_for_feed, pattern="^rss_select_ch_")],
        ADD_FILTER_PATTERN: [MessageHandler(filters.TEXT & ~filters.COMMAND, filter_pattern_received)],
        ADD_FILTER_MODE: [CallbackQueryHandler(filter_mode_selected, pattern="^filt_mode_")],
        EDIT_REPLACEMENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, replacement_received)],
        EDIT_TEMPLATE_TEXT: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, save_template),
            CommandHandler("cancel", cancel_template_edit),
        ],
    },
    fallbacks=[
        CommandHandler("cancel", cancel_template_edit),
        CallbackQueryHandler(rss_dashboard, pattern="^rss_home$"),
    ],
    per_message=False,
    allow_reentry=True  # ✅ AÑADIR ESTO
)
