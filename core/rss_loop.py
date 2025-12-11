# core/rss_loop.py

import asyncio
import time
import re
import html
import feedparser
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from utils.file_manager import add_log_line
from utils.rss_manager import load_rss_data, save_rss_data

# === CONFIGURACIÓN DE ESTILOS ===

# Este es el estilo BitBread (Personalizable) que se usará como base.
# Lo renombramos a DEFAULT_TEMPLATE para que handlers/rss.py no de error al importar.
DEFAULT_TEMPLATE = (
    "<b>#media_title#</b>\n\n"
    "#media_description#\n\n"
    "•••\n"
    "<i><b><a href='https://t.me/boost/bbalertchannel'>✨ BitBread</a></b> • <a href='#media_url#'>#source_title#</a></i>"
)

# Estilo Telegram (Fijo)
TELEGRAM_STYLE = (
    "<b>#media_title#</b>\n\n"
    "#media_description#\n\n"
    "<a href='#media_url#'>Leer noticia completa</a>"
)

def render_notification(feed_data, entry, feed_title, feed_url):
    """
    Procesa la notificación según el formato elegido: 'telegram' o 'bitbread'.
    """
    style_mode = feed_data.get('format', 'bitbread')
    
    # Determinar qué plantilla usar
    if style_mode == 'telegram':
        template = TELEGRAM_STYLE
    else:
        # Si es BitBread, usamos la personalizada del usuario o la por defecto
        template = feed_data.get('template') or DEFAULT_TEMPLATE
        
    text = template
    flags = {
        'ignore_media': False,
        'only_first_media': True, # Forzado para ambos estilos como pides
        'telegram_preview': False,
        'no_web_page_preview': False
    }

def clean_html_summary(summary):
    """
    Limpia etiquetas HTML para dejar solo las soportadas por Telegram.
    Elimina DIVs, SPANs, Tablas, etc., pero mantiene el texto.
    """
    if not summary: return ""
    # 1. Convertir saltos de línea comunes a \n
    text = summary.replace("<br>", "\n").replace("<br/>", "\n").replace("</p>", "\n")
    # 2. Eliminar bloques completos de scripts/estilos
    text = re.sub(r'<(script|style|iframe|embed|object)[^>]*>.*?</\1>', '', text, flags=re.DOTALL | re.IGNORECASE)
    
    # 3. Eliminar TODAS las etiquetas EXCEPTO las permitidas por Telegram (b, i, u, s, a, code, pre)
    # Explicación regex: Busca < ... > que NO empiece por /?(b|i|a|...)
    text = re.sub(r'<(?!\/?(b|strong|i|em|u|s|a|code|pre)\b)[^>]*>', '', text, flags=re.IGNORECASE)
    
    # 4. Limpieza de espacios múltiples resultantes
    text = re.sub(r'\n\s*\n', '\n\n', text)
    
    return text.strip()

def render_notification(feed_data, entry, feed_title, feed_url):
    """
    Procesa la plantilla según el formato guardado en el feed.
    """
    # Obtenemos el formato: 'bitbread' (por defecto) o 'telegram'
    style_mode = feed_data.get('format', 'bitbread')
    
    if style_mode == 'telegram':
        template = TELEGRAM_STYLE
    else:
        # Usamos la plantilla personalizada si existe, sino la DEFAULT_TEMPLATE
        template = feed_data.get('template') or DEFAULT_TEMPLATE
        
    text = template
    
    # Flags de control
    flags = {
        'ignore_media': False,
        'only_first_media': "#only_first_media#" in text or style_mode == 'telegram',
        'telegram_preview': "#telegram_preview#" in text,
        'no_web_page_preview': False
    }

    # Limpiar etiquetas de control del texto
    for f_tag in ["#only_first_media#", "#ignore_media#", "#telegram_preview#"]:
        text = text.replace(f_tag, "")

    # Variables Básicas
    replacements = {
        '#media_title#': html.escape(entry.get('title', 'Sin Título')),
        '#media_url#': entry.get('link', ''),
        '#source_title#': html.escape(feed_title),
        '#source_url#': feed_url or entry.get('link', ''),
    }
    
    summary_raw = entry.get('summary', '') or entry.get('description', '')
    summary_clean = clean_html_summary(summary_raw)
    
    if len(summary_clean) > 800:
        summary_clean = summary_clean[:800] + "..."
        
    replacements['#media_description#'] = summary_clean
    replacements['#summary#'] = summary_clean
    
    for tag, value in replacements.items():
        text = text.replace(tag, value)
        
    # Botones
    buttons = []
    matches = re.findall(r"\{\{button\|(.*?)\|(.*?)\}\}", text)
    for btn_text, btn_url in matches:
        buttons.append([InlineKeyboardButton(btn_text, url=btn_url)])
        text = text.replace(f"{{{{button|{btn_text}|{btn_url}}}}}", "")
        
    return text.strip(), buttons, flags
#  === LOOP PRINCIPAL DE MONITOREO RSS ===
async def rss_monitor_loop(bot: Bot):
    add_log_line("📰 Iniciando Monitor RSS (Avanzado)...")
    
    while True:
        try:
            data = load_rss_data()
            updates_to_save = {}
            dirty = False
            now = time.time()
            
            for user_id, user_data in data.items():
                for feed in user_data['feeds']:
                    if not feed.get('active', True):
                        continue
                        
                    freq_sec = feed.get('frequency', 60) * 60
                    last_check = feed.get('last_checked', 0)
                    
                    if (now - last_check) >= freq_sec:
                        try:
                            parsed = feedparser.parse(feed['url'])
                            if not parsed.entries:
                                continue
                                
                            latest = parsed.entries[0]
                            entry_link = latest.get('link')
                            
                            if entry_link != feed.get('last_entry_link'):
                                
                                # --- FILTROS ---
                                filters_list = feed.get('filters', [])
                                blocked = False
                                if filters_list:
                                    content_check = (latest.get('title', '') + " " + latest.get('summary', '')).lower()
                                    for bad_word in filters_list:
                                        if bad_word.lower() in content_check:
                                            blocked = True
                                            break
                                if blocked:
                                    updates_to_save[feed['id']] = {'link': entry_link, 'checked': now}
                                    dirty = True
                                    continue

                                # --- RENDERIZADO ---
                                msg_text, buttons, flags = render_notification(
                                    feed, latest, 
                                    feed.get('title', 'RSS'), 
                                    parsed.feed.get('link', '')
                                )
                                
                                reply_markup = InlineKeyboardMarkup(buttons) if buttons else None
                                target_id = feed['target_channel_id']
                                
                               # === ESTRATEGIA DEFINITIVA DE EXTRACCIÓN DE IMAGEN ===
                                img_url = None
                                
                                if not flags['ignore_media']:
                                    # 1. Búsqueda en metadatos estándar (Media Content / Enclosures / Thumbnails)
                                    # Priorizamos metadatos porque suelen tener mayor calidad que el scrapeo
                                    if 'media_content' in latest:
                                        for m in latest['media_content']:
                                            if 'image' in m.get('type', '') or any(x in m.get('url', '').lower() for x in ['.jpg', '.png', '.jpeg', '.webp']):
                                                img_url = m['url']; break
                                    
                                    if not img_url and 'links' in latest:
                                        for l in latest['links']:
                                            if 'image' in l.get('type', '') and 'href' in l:
                                                img_url = l['href']; break
                                                
                                    if not img_url and 'media_thumbnail' in latest:
                                         if latest['media_thumbnail']: img_url = latest['media_thumbnail'][0]['url']

                                    # 2. Si no hay metadatos, Scrapeo del HTML (Mejorado)
                                    if not img_url:
                                        full_html = latest.get('summary', '') + latest.get('description', '')
                                        if 'content' in latest:
                                            for c in latest['content']: full_html += c.get('value', '')
                                        
                                        # Regex mejorada para capturar srcs con espacios o sin comillas claras
                                        img_tags = re.findall(r'<img[^>]+src=["\']\s*([^"\'>]+)["\']', full_html, re.IGNORECASE)
                                        
                                        for possible_url in img_tags:
                                            # Filtro de basura
                                            bad_keywords = ['emoji', 'icon', 'pixel', 'avatar', 'gravatar', 'share', 'button', 'gif', 'doubleclick', 'adserver']
                                            if any(k in possible_url.lower() for k in bad_keywords):
                                                continue
                                            
                                            img_url = possible_url
                                            break 

                                # =======================================================
                                # LÓGICA DE ENVÍO CORREGIDA (Prioridad SendPhoto)
                                # =======================================================
                                try:
                                    sent_success = False
                                    
                                    # INTENTO 1: Enviar como FOTO (Imagen arriba, Texto abajo)
                                    if img_url:
                                        try:
                                            # Las captions tienen límite de 1024 caracteres. Recortamos si es necesario.
                                            caption_text = msg_text
                                            if len(caption_text) > 1024:
                                                caption_text = caption_text[:1000] + "..."
                                            
                                            await bot.send_photo(
                                                chat_id=target_id,
                                                photo=img_url,
                                                caption=caption_text,
                                                parse_mode=ParseMode.HTML,
                                                reply_markup=reply_markup
                                            )
                                            sent_success = True
                                            add_log_line(f"✅ RSS enviado (FOTO): {latest.get('title')}")
                                        except Exception as e_photo:
                                            # Si falla la foto (ej. formato webp no soportado, url rota), pasamos al plan B
                                            print(f"⚠️ Falló send_photo ({e_photo}), intentando send_message...")
                                            sent_success = False

                                    # INTENTO 2: Enviar como TEXTO (Si no hay img o falló la foto)
                                    if not sent_success:
                                        # Si teníamos imagen pero falló send_photo, usamos el truco del link invisible
                                        # para intentar que salga al menos la vista previa (aunque salga abajo)
                                        if img_url:
                                            header_img = f"<a href='{img_url}'>\u200b</a>"
                                            final_text = header_img + msg_text
                                        else:
                                            final_text = msg_text
                                        
                                        await bot.send_message(
                                            chat_id=target_id,
                                            text=final_text,
                                            parse_mode=ParseMode.HTML,
                                            reply_markup=reply_markup,
                                            disable_web_page_preview=False 
                                        )
                                        add_log_line(f"✅ RSS enviado (TEXTO): {latest.get('title')}")
                                    
                                except Exception as e:
                                    # Fallback extremo: Texto plano
                                    add_log_line(f"⚠️ Fallo envío RSS CRÍTICO ({e}). Reintentando sin formato...")
                                    try:
                                        await bot.send_message(chat_id=target_id, text=latest.get('title') + "\n" + latest.get('link'))
                                    except:
                                        pass
                                
                                updates_to_save[feed['id']] = {'link': entry_link, 'checked': now}
                                dirty = True
                            else:
                                updates_to_save[feed['id']] = {'link': entry_link, 'checked': now}
                                dirty = True
                                
                        except Exception as e:
                            print(f"E: {e}")
            
            if dirty:
                fresh_data = load_rss_data()
                for uid, udata in fresh_data.items():
                    for f in udata['feeds']:
                        if f['id'] in updates_to_save:
                            update_info = updates_to_save[f['id']]
                            f['last_checked'] = update_info['checked']
                            if update_info['link']:
                                f['last_entry_link'] = update_info['link']
                save_rss_data(fresh_data)
                
        except Exception as e:
            add_log_line(f"❌ Error RSS Loop: {e}")
            
        await asyncio.sleep(60)
