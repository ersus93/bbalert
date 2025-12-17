# core/rss_loop_v2.py - VERSIÓN CORREGIDA Y COMPLETA

import asyncio
import time
import html
import re
from typing import Dict, List, Tuple, Optional
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.error import TelegramError, Forbidden, BadRequest

from utils.feed_parser_v4 import FeedParserV4
from utils.rss_manager_v2 import RSSManager
from utils.file_manager import add_log_line

class RSSMonitor:
    """Monitor robusto de feeds RSS con soporte avanzado de plantillas."""
    
    def __init__(self, bot: Bot):
        self.bot = bot
        self.parser = FeedParserV4()
        self.manager = RSSManager()
    
    # ============================================================
    # LIMPIEZA DE HTML
    # ============================================================
    @staticmethod
    def clean_html_content(summary: str) -> str:
        """Limpieza robusta de HTML para Telegram."""
        if not summary:
            return ""
        
        text = summary.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
        text = text.replace("</p>", "\n\n")
        
        text = re.sub(r'<(script|style|iframe|embed|object|svg)[^>]*>.*?</\1>', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<img[^>]*>', '', text, flags=re.IGNORECASE)
        text = re.sub(r'<(?!\/?(b|strong|i|em|u|s|a|code|pre)\b)[^>]*>', '', text, flags=re.IGNORECASE)
        
        text = text.replace('<strong>', '<b>').replace('</strong>', '</b>')
        text = text.replace('<em>', '<i>').replace('</em>', '</i>')
        
        text = re.sub(r'\n\s*\n\s*\n', '\n\n', text)
        text = html.unescape(text)
        
        return text.strip()
    
    # ============================================================
    # PROCESAMIENTO DE PLANTILLAS
    # ============================================================
    def process_template(self, template: str, entry: Dict, feed: Dict) -> Tuple[str, List[List[InlineKeyboardButton]], Dict]:
        """
        Procesa la plantilla reemplazando variables y extrayendo botones/flags.
        Retorna: (Texto Final, Botones, Flags detectados)
        """
        text = template
        
        # 1. Detectar Flags
        flags = {
            'only_first_media': '#only_first_media#' in text,
            'ignore_media': '#ignore_media#' in text,
            'ignore_video': '#ignore_video#' in text,
            'telegram_preview': '#telegram_preview#' in text,
            'no_view_original': '#no_view_original_post_link#' in text,
            'format': feed.get('format', 'bitbread')
        }
        
        # Eliminar flags del texto
        for flag_tag in ['#only_first_media#', '#ignore_media#', '#ignore_video#', 
                         '#telegram_preview#', '#no_view_original_post_link#']:
            text = text.replace(flag_tag, '')
        
        # 2. Variables de Datos
        raw_desc = entry.get('description', '') or entry.get('summary', '')
        clean_desc = self.clean_html_content(raw_desc)
        
        replacements = {
            '#media_title#': html.escape(entry.get('title', 'Sin Título')),
            '#media_description#': clean_desc,
            '#media_short_description#': clean_desc[:200] + "..." if len(clean_desc) > 200 else clean_desc,
            '#media_url#': entry.get('link', ''),
            '#source_title#': html.escape(feed.get('source_title', 'Fuente')),
            '#source_url#': feed.get('source_link', entry.get('link', '')),
            '#source_type#': feed.get('detected_type', 'RSS'),
            '#summary#': clean_desc[:400],
        }
        
        for tag, value in replacements.items():
            text = text.replace(tag, str(value))
        
        # 3. Extracción de Botones
        buttons = []
        matches = re.findall(r"\{\{button\|(.*?)\|(.*?)\}\}", text)
        for btn_text, btn_url in matches:
            clean_url = btn_url.strip()
            buttons.append([InlineKeyboardButton(btn_text, url=clean_url)])
            text = text.replace(f"{{{{button|{btn_text}|{btn_url}}}}}", "")
        
        return text.strip(), buttons, flags
    
    # ============================================================
    # ENVÍO DE ENTRADAS
    # ============================================================
    async def _send_entry(self, user_id: int, feed: Dict, entry: Dict) -> bool:
        """Envía una entrada procesada con lógica diferenciada por formato."""
        try:
            # 1. Filtrado de contenido
            content_check = f"{entry.get('title', '')} {entry.get('description', '')}"
            should_block, _ = self.manager.apply_content_filters(content_check, feed.get('filters', []))
            
            if should_block:
                feed['stats']['total_blocked'] += 1
                add_log_line(f"🚫 Entrada bloqueada por filtro: {entry.get('title', 'Sin título')[:50]}")
                return True
            
            # 2. Preparar Plantilla
            current_template = feed.get('template')
            if not current_template:
                fmt = feed.get('format', 'bitbread')
                current_template = RSSManager.DEFAULT_TELEGRAM_TEMPLATE if fmt == 'telegram' else RSSManager.DEFAULT_BITBREAD_TEMPLATE
            
            # 3. Procesar Variables y Botones
            msg_text, buttons, flags = self.process_template(current_template, entry, feed)
            reply_markup = InlineKeyboardMarkup(buttons) if buttons else None
            target_channel = feed['target_channel_id']
            
            # 4. Determinar Imagen
            image_url = entry.get('image')
            format_type = flags.get('format', 'bitbread')
            
            # 5. Bifurcación según formato
            if format_type == 'bitbread':
                return await self._send_bitbread_style(
                    target_channel, 
                    image_url, 
                    msg_text, 
                    reply_markup, 
                    flags
                )
            else:
                return await self._send_telegram_style(
                    target_channel, 
                    image_url, 
                    msg_text, 
                    reply_markup,
                    entry.get('link', '')
                )
        
        except Exception as e:
            add_log_line(f"❌ Error general en _send_entry: {e}")
            return False
    
    # ============================================================
    # ESTILOS DE ENVÍO
    # ============================================================
    async def _send_bitbread_style(
        self, 
        channel_id: int, 
        image_url: str, 
        msg_text: str, 
        reply_markup, 
        flags: Dict
    ) -> bool:
        """Estilo BitBread: Imagen grande con caption HTML."""
        sent = False
        
        # Intento 1: send_photo
        if image_url and not flags.get('ignore_media'):
            try:
                caption_text = msg_text[:997] + "..." if len(msg_text) > 1000 else msg_text
                
                await self.bot.send_photo(
                    chat_id=channel_id,
                    photo=image_url,
                    caption=caption_text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=reply_markup
                )
                sent = True
                add_log_line(f"✅ [BitBread] Enviado como FOTO a {channel_id}")
            
            except Exception as e:
                add_log_line(f"⚠️ [BitBread] Falló send_photo: {str(e)[:100]}. Intentando texto...")
        
        # Intento 2: send_message con preview
        if not sent:
            try:
                final_text = msg_text
                
                if image_url and not flags.get('ignore_media'):
                    final_text = f"<a href='{image_url}'>&#8205;</a>" + msg_text
                
                disable_preview = not bool(image_url)
                
                await self.bot.send_message(
                    chat_id=channel_id,
                    text=final_text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=reply_markup,
                    disable_web_page_preview=disable_preview
                )
                sent = True
                add_log_line(f"✅ [BitBread] Enviado como TEXTO a {channel_id}")
            
            except Exception as e:
                add_log_line(f"❌ [BitBread] Error fatal: {str(e)[:100]}")
        
        return sent
    
    async def _send_telegram_style(
        self, 
        channel_id: int, 
        image_url: str, 
        msg_text: str, 
        reply_markup,
        article_url: str
    ) -> bool:
        """Estilo Telegram: Vista Instantánea (Link Preview) automática."""
        try:
            if article_url and article_url not in msg_text:
                msg_text = f"<a href='{article_url}'>&#8205;</a>{msg_text}"
            
            await self.bot.send_message(
                chat_id=channel_id,
                text=msg_text,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup,
                disable_web_page_preview=False,
                link_preview_options={
                    "is_disabled": False,
                    "prefer_large_media": True,
                    "show_above_text": True
                }
            )
            
            add_log_line(f"✅ [Telegram] Enviado con Vista Instantánea a {channel_id}")
            return True
        
        except Exception as e:
            add_log_line(f"❌ [Telegram] Error enviando: {str(e)[:100]}")
            return False
    
    # ============================================================
    # PROCESAMIENTO DE FEEDS
    # ============================================================
    # En core/rss_loop_v2.py

    async def _process_feed(self, user_id: int, feed: Dict, force: bool = False):
        """
        Procesa el feed usando comparación de listas (Feed vs Historial) 
        y optimiza la URL automáticamente.
        """
        current_url = feed['url']
        
        # 1. Analizar Feed
        res = await self.parser.parse(current_url)
        
        if not res.get('success'):
            add_log_line(f"⚠️ Error leyendo feed {feed.get('source_title', '?')}: {res.get('error')}")
            feed['stats']['errors'] += 1
            return

        # --- AUTO-CORRECCIÓN DE URL (OPTIMIZACIÓN) ---
        # Si estábamos usando .com y encontramos .xml, guardamos el cambio PARA SIEMPRE.
        detected_url = res.get('real_url')
        if detected_url and detected_url != current_url:
            if 'rss' in detected_url or 'xml' in detected_url or 'feed' in detected_url:
                add_log_line(f"🛠️ URL Optimizada detectada: {current_url} -> {detected_url}")
                feed['url'] = detected_url # Actualizamos memoria
                # Guardamos en disco INMEDIATAMENTE para que el próximo ciclo no escanee de nuevo
                data = RSSManager.load_data()
                # Buscamos el feed en la estructura global para actualizarlo
                if str(user_id) in data:
                    for f in data[str(user_id)].get('feeds', []):
                        if f['id'] == feed['id']:
                            f['url'] = detected_url
                            break
                RSSManager.save_data(data)

        entries = res.get('entries', [])
        if not entries:
            return

        # 2. Inicializar Historial (Si no existe)
        if 'sent_history' not in feed:
            feed['sent_history'] = []
            # Si es la primera vez, marcamos todo como "visto" para no spamear 50 noticias de golpe
            # excepto si es FORCE, o dejamos pasar solo la última.
            if not force and 'last_checked' not in feed:
                for entry in entries:
                    feed['sent_history'].append(entry['hash'])
                feed['last_checked'] = time.time()
                return

        # 3. Filtrado: ¿Qué noticias NO están en el historial?
        noticias_nuevas = []
        for entry in entries:
            if entry['hash'] not in feed['sent_history']:
                noticias_nuevas.append(entry)

        # Si no hay nada nuevo
        if not noticias_nuevas:
            if force:
                # En force, si no hay nada nuevo, reenviamos la primera del feed original
                add_log_line(f"⚡ [Force] No hay nuevas. Reenviando la más reciente.")
                noticias_nuevas = [entries[0]]
            else:
                feed['last_checked'] = time.time()
                return

        # 4. Ordenar para envío (De la más vieja a la más nueva)
        # Los feeds suelen venir [Nueva, Vieja, Más Vieja]. Invertimos.
        noticias_nuevas.reverse()

        # 5. Envío y Actualización
        sent_count = 0
        for entry in noticias_nuevas:
            # Protección anti-spam: Máximo 5 noticias por ciclo (salvo que sea manual)
            if sent_count >= 5 and not force:
                break
            
            # Intentar enviar
            if await self._send_entry(user_id, feed, entry):
                # AGREGAR AL HISTORIAL
                feed['sent_history'].append(entry['hash'])
                feed['stats']['total_sent'] += 1
                sent_count += 1
                await asyncio.sleep(2) # Pausa para no saturar Telegram

        # 6. Mantenimiento del Historial (Limpieza)
        # Solo guardamos los últimos 100 hashes para que el JSON no crezca infinito
        if len(feed['sent_history']) > 100:
            feed['sent_history'] = feed['sent_history'][-100:]

        feed['last_checked'] = time.time()
        
        # Guardamos el estado actualizado (historial) en disco
        data = RSSManager.load_data()
        RSSManager.save_data(data) # Guardado global
    
    # ============================================================
    # BUCLE DE MONITOREO
    # ============================================================
    async def monitor_loop(self):
        """Loop principal de monitoreo."""
        add_log_line("📰 RSS Monitor v2 Iniciado...")
        await asyncio.sleep(10)
        
        while True:
            try:
                await self._check_all_feeds()
            except Exception as e:
                add_log_line(f"❌ Error en monitor_loop: {e}")
            
            await asyncio.sleep(60)
    
    async def _check_all_feeds(self):
        """Verifica todos los feeds activos."""
        data = RSSManager.load_data()
        now = time.time()
        
        for uid, udata in data.items():
            for feed in udata.get('feeds', []):
                if not feed.get('active', True):
                    continue
                
                last_checked = feed.get('last_checked', 0)
                frequency = feed.get('frequency_minutes', 60) * 60
                
                if (now - last_checked) >= frequency:
                    await self._process_feed(int(uid), feed, force=False)
                    feed['last_checked'] = now
                    RSSManager.save_data(data)
    
    # ============================================================
    # ENVÍO MANUAL (FORCE SEND)
    # ============================================================
    async def force_send_feed(self, user_id: int, feed_id: str) -> Tuple[bool, str]:
        """Envía noticias de un feed de forma manual."""
        try:
            data = RSSManager.load_data()
            user_data = data.get(str(user_id), {})
            feed = next((f for f in user_data.get('feeds', []) if f['id'] == feed_id), None)
            
            if not feed:
                return False, "Feed no encontrado"
            
            channel_id = feed['target_channel_id']
            
            # Verificar permisos
            try:
                member = await self.bot.get_chat_member(channel_id, self.bot.id)
                if member.status not in ['administrator', 'creator']:
                    return False, "⚠️ El bot no es administrador del canal"
            except Exception as e:
                return False, f"❌ Error de canal: {str(e)[:100]}"
            
            # Procesar feed
            await self._process_feed(user_id, feed, force=True)
            
            return True, f"✅ Feed '{feed['source_title']}' procesado correctamente"
        
        except Exception as e:
            add_log_line(f"❌ Error en force_send_feed: {e}")
            import traceback
            add_log_line(f"Traceback: {traceback.format_exc()[:500]}")
            return False, f"Error: {str(e)[:100]}"


# ============================================================
# VARIABLES GLOBALES
# ============================================================
rss_monitor_instance = None

def set_rss_monitor(monitor):
    global rss_monitor_instance
    rss_monitor_instance = monitor

def get_rss_monitor():
    return rss_monitor_instance
