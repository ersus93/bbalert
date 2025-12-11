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

# Plantilla por defecto (Estilo BitBread)
DEFAULT_TEMPLATE = (
    "<b><a href='#media_url#'>#media_title#</a></b>\n\n"
    "#media_description#\n\n"
    "<i>Fuente: <a href='#source_url#'>#source_title#</a></i>\n"
    "#only_first_media#"
)

def clean_html_summary(summary):
    """
    Limpia etiquetas HTML complejas y peligrosas.
    """
    if not summary: return ""
    text = summary.replace("<br>", "\n").replace("<br/>", "\n").replace("<p>", "").replace("</p>", "\n")
    # Eliminar imagenes inline del resumen
    text = re.sub(r'<img[^>]+>', '', text) 
    text = re.sub(r'<(script|style|iframe)[^>]*>.*?</\1>', '', text, flags=re.DOTALL)
    return text.strip()

def render_notification(template, entry, feed_title, feed_url):
    """
    Procesa la plantilla y devuelve HTML listo para Telegram.
    """
    if not template:
        template = DEFAULT_TEMPLATE
        
    text = template
    flags = {
        'ignore_media': False,
        'only_first_media': False,
        'telegram_preview': False,
        'no_web_page_preview': True
    }
    
    # 1. Variables Básicas
    replacements = {
        '#media_title#': html.escape(entry.get('title', 'Sin Título')),
        '#media_url#': entry.get('link', ''),
        '#source_title#': html.escape(feed_title),
        '#source_url#': feed_url or entry.get('link', ''),
        '#source_type#': 'RSS',
    }
    
    # Descripción/Resumen (Limpieza básica)
    summary_raw = entry.get('summary', '') or entry.get('description', '')
    summary_clean = clean_html_summary(summary_raw)
    
    # Limitamos longitud
    if len(summary_clean) > 800:
        summary_clean = summary_clean[:800] + "..."
        
    replacements['#media_description#'] = summary_clean
    replacements['#summary#'] = summary_clean # Alias Aximo
    
    # Aplicar reemplazos
    for tag, value in replacements.items():
        text = text.replace(tag, value)
        
    # 2. Banderas de control (Flags)
    if "#ignore_media#" in text:
        flags['ignore_media'] = True
        text = text.replace("#ignore_media#", "")
        
    if "#only_first_media#" in text:
        flags['only_first_media'] = True
        text = text.replace("#only_first_media#", "")
        
    if "#telegram_preview#" in text:
        flags['telegram_preview'] = True
        flags['no_web_page_preview'] = False
        text = text.replace("#telegram_preview#", "")
        
    text = text.replace("#no_view_original_post_link#", "")
    text = text.replace("#ignore_video#", "")

    # 3. Botones
    buttons = []
    matches = re.findall(r"\{\{button\|(.*?)\|(.*?)\}\}", text)
    for btn_text, btn_url in matches:
        buttons.append([InlineKeyboardButton(btn_text, url=btn_url)])
        text = text.replace(f"{{{{button|{btn_text}|{btn_url}}}}}", "")
        
    return text.strip(), buttons, flags

async def rss_monitor_loop(bot: Bot):
    add_log_line("📰 Iniciando Monitor RSS (Avanzado con Persistencia Segura)...")
    
    while True:
        try:
            # Cargar datos al inicio del ciclo
            data = load_rss_data()
            updates_to_save = {} # Diccionario para guardar cambios de estado: {feed_id: {'link': x, 'checked': y}}
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
                            
                            # Si hay noticia nueva
                            if entry_link != feed.get('last_entry_link'):
                                
                                # Verificar Filtros
                                filters_list = feed.get('filters', [])
                                blocked = False
                                if filters_list:
                                    content_check = (latest.get('title', '') + " " + latest.get('summary', '')).lower()
                                    for bad_word in filters_list:
                                        if bad_word.lower() in content_check:
                                            blocked = True
                                            add_log_line(f"🚫 RSS Bloqueado: {feed['title']} (Filtro: {bad_word})")
                                            break
                                
                                if blocked:
                                    # Marcar como leido pero no enviado
                                    updates_to_save[feed['id']] = {'link': entry_link, 'checked': now}
                                    dirty = True
                                    continue

                                # Renderizar notificación
                                tpl = feed.get('template', None)
                                msg_text, buttons, flags = render_notification(
                                    tpl, latest, 
                                    feed.get('title', 'RSS'), 
                                    parsed.feed.get('link', '')
                                )
                                
                                reply_markup = InlineKeyboardMarkup(buttons) if buttons else None
                                target_id = feed['target_channel_id']
                                
                                # Buscar Imagen
                                img_url = None
                                if not flags['ignore_media']:
                                    if 'media_content' in latest:
                                        img_url = latest['media_content'][0]['url']
                                    elif 'links' in latest:
                                        for l in latest['links']:
                                            if 'image' in l.get('type', ''):
                                                img_url = l['href']
                                                break
                                    if not img_url and 'summary' in latest:
                                        img_match = re.search(r'<img .*?src=["\'](.*?)["\']', latest['summary'])
                                        if img_match:
                                            img_url = img_match.group(1)

                                try:
                                    if img_url:
                                        if len(msg_text) > 1024:
                                            await bot.send_message(
                                                chat_id=target_id,
                                                text=f"[​​​​​​​​​​​]({img_url})" + msg_text,
                                                parse_mode=ParseMode.HTML,
                                                reply_markup=reply_markup
                                            )
                                        else:
                                            await bot.send_photo(
                                                chat_id=target_id,
                                                photo=img_url,
                                                caption=msg_text,
                                                parse_mode=ParseMode.HTML,
                                                reply_markup=reply_markup
                                            )
                                    else:
                                        await bot.send_message(
                                            chat_id=target_id,
                                            text=msg_text,
                                            parse_mode=ParseMode.HTML,
                                            reply_markup=reply_markup,
                                            disable_web_page_preview=flags['no_web_page_preview']
                                        )
                                    
                                    add_log_line(f"✅ RSS enviado: {latest.get('title')} -> {target_id}")
                                    
                                except Exception as e:
                                    add_log_line(f"⚠️ Error enviando RSS a {target_id}: {e}")
                                
                                # Guardar actualización pendiente
                                updates_to_save[feed['id']] = {'link': entry_link, 'checked': now}
                                dirty = True
                            else:
                                # Solo actualizar timestamp
                                updates_to_save[feed['id']] = {'link': entry_link, 'checked': now}
                                dirty = True
                                
                        except Exception as e:
                            print(f"Error feed {feed['url']}: {e}")
            
            # === FASE DE GUARDADO SEGURO (Merge) ===
            if dirty:
                # 1. Recargar archivo del disco (para obtener cambios hechos por el usuario durante el loop)
                fresh_data = load_rss_data()
                
                # 2. Aplicar SOLO los cambios de timestamps a la data fresca
                for uid, udata in fresh_data.items():
                    for f in udata['feeds']:
                        if f['id'] in updates_to_save:
                            update_info = updates_to_save[f['id']]
                            f['last_checked'] = update_info['checked']
                            # Solo actualizamos el link si cambió (para no borrar nulls accidentalmente)
                            if update_info['link']:
                                f['last_entry_link'] = update_info['link']
                
                # 3. Guardar la data fusionada
                save_rss_data(fresh_data)
                
        except Exception as e:
            add_log_line(f"❌ Error CRÍTICO RSS Loop: {e}")
            
        await asyncio.sleep(60)