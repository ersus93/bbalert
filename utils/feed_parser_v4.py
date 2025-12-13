# utils/feed_parser_v4.py - SISTEMA RSS DEFINITIVO

import asyncio
import aiohttp
import feedparser
import hashlib
import json
from bs4 import BeautifulSoup
import re
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from urllib.parse import urljoin, urlparse
from utils.file_manager import add_log_line

class FeedParserV4:
    """
    Parser RSS Ultra-Robusto con:
    - Hash único por entrada (evita duplicados)
    - Detección automática de feeds en páginas web
    - Soporte para RSS Bridge y RSSHub con fallbacks
    - Extracción inteligente de imágenes
    """
    
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/rss+xml, application/atom+xml, application/xml, text/html, */*",
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    }
    
    # ========================================
    # SERVICIOS DE CONVERSIÓN (Prioridad)
    # ========================================
    RSSHUB_MIRRORS = [
        "https://rsshub.app",
        "https://rss.nixnet.services",
        "https://rsshub.rssforever.com",
    ]
    
    RSS_BRIDGE_MIRRORS = [
        "https://rss-bridge.org/bridge01",
        "https://wtf.roflcopter.fr/rss-bridge",
    ]
    
    NITTER_INSTANCES = [
        "https://nitter.net",
        "https://nitter.poast.org",
        "https://nitter.privacydev.net",
    ]
    
    def __init__(self, timeout: int = 25):
        self.timeout = timeout
        self._session = None
    
    async def _get_session(self):
        """Crea sesión HTTP persistente."""
        if not self._session:
            self._session = aiohttp.ClientSession(
                headers=self.HEADERS,
                timeout=aiohttp.ClientTimeout(total=self.timeout),
                connector=aiohttp.TCPConnector(ssl=False, limit=10)
            )
        return self._session
    
    async def close(self):
        """Cierra la sesión."""
        if self._session:
            await self._session.close()
            self._session = None
    
    # ========================================
    # DETECCIÓN DE TIPO DE FEED
    # ========================================
    def detect_source_type(self, url: str) -> Tuple[str, Optional[str]]:
        """
        Detecta el tipo de fuente.
        Retorna: (tipo, identificador)
        """
        url_lower = url.lower()
        
        # Twitter/X
        if 'twitter.com' in url_lower or 'x.com' in url_lower:
            match = re.search(r'(?:twitter\.com|x\.com)/([a-zA-Z0-9_]{1,15})', url)
            return ('twitter', match.group(1) if match else None)
        
        # Instagram
        if 'instagram.com' in url_lower:
            match = re.search(r'instagram\.com/([a-zA-Z0-9_.]{1,30})', url)
            return ('instagram', match.group(1) if match else None)
        
        # YouTube
        if 'youtube.com' in url_lower or 'youtu.be' in url_lower:
            # Channel ID
            match = re.search(r'youtube\.com/channel/(UC[a-zA-Z0-9_-]{22})', url)
            if match:
                return ('youtube', match.group(1))
            
            # @username
            match = re.search(r'youtube\.com/@([a-zA-Z0-9_-]+)', url)
            if match:
                return ('youtube', f"@{match.group(1)}")
            
            # /c/ o /user/
            match = re.search(r'youtube\.com/(?:c|user)/([a-zA-Z0-9_-]+)', url)
            return ('youtube', match.group(1) if match else None)
        
        # Telegram
        if 't.me' in url_lower or 'telegram.me' in url_lower:
            match = re.search(r't(?:elegram)?\.me/([a-zA-Z0-9_]{5,32})', url)
            return ('telegram', match.group(1) if match else None)
        
        # Reddit
        if 'reddit.com' in url_lower:
            match = re.search(r'reddit\.com/r/([a-zA-Z0-9_]{3,21})', url)
            return ('reddit', match.group(1) if match else None)
        
        # RSS/Atom genérico
        return ('generic', None)
    
    # ========================================
    # CONVERSIÓN DE REDES SOCIALES
    # ========================================
    async def convert_social_to_rss(self, source_type: str, identifier: str) -> Optional[bytes]:
        """
        Convierte redes sociales a RSS usando múltiples servicios.
        """
        services = []
        
        # --- TWITTER/X ---
        if source_type == 'twitter':
            # Nitter (más rápido)
            for instance in self.NITTER_INSTANCES:
                services.append(f"{instance}/{identifier}/rss")
            
            # RSSHub
            for mirror in self.RSSHUB_MIRRORS:
                services.append(f"{mirror}/twitter/user/{identifier}")
            
            # RSS Bridge
            for mirror in self.RSS_BRIDGE_MIRRORS:
                services.append(
                    f"{mirror}/?action=display&bridge=Twitter&context=By+username"
                    f"&u={identifier}&format=Atom"
                )
        
        # --- INSTAGRAM ---
        elif source_type == 'instagram':
            # RSSHub
            for mirror in self.RSSHUB_MIRRORS:
                services.append(f"{mirror}/instagram/user/{identifier}")
            
            # Bibliogram
            services.append(f"https://bibliogram.art/u/{identifier}/rss.xml")
        
        # --- YOUTUBE ---
        elif source_type == 'youtube':
            # Feed nativo (mejor opción)
            if identifier.startswith('UC'):
                services.append(f"https://www.youtube.com/feeds/videos.xml?channel_id={identifier}")
            else:
                services.append(f"https://www.youtube.com/feeds/videos.xml?user={identifier}")
            
            # RSSHub (backup)
            for mirror in self.RSSHUB_MIRRORS:
                services.append(f"{mirror}/youtube/user/{identifier}")
        
        # --- TELEGRAM ---
        elif source_type == 'telegram':
            # RSSHub
            for mirror in self.RSSHUB_MIRRORS:
                services.append(f"{mirror}/telegram/channel/{identifier}")
        
        # --- REDDIT ---
        elif source_type == 'reddit':
            # Reddit nativo (mejor)
            services.append(f"https://www.reddit.com/r/{identifier}.rss")
            services.append(f"https://www.reddit.com/r/{identifier}/new.rss")
        
        # --- INTENTAR TODOS LOS SERVICIOS ---
        session = await self._get_session()
        
        for service_url in services:
            try:
                add_log_line(f"🔄 Intentando: {service_url[:70]}...")
                
                async with session.get(service_url) as response:
                    if response.status == 200:
                        content = await response.read()
                        
                        # Verificar que es XML válido
                        if self._is_valid_feed(content):
                            add_log_line(f"✅ Éxito con: {service_url[:70]}")
                            return content
                
                await asyncio.sleep(0.5)  # Rate limiting
            
            except Exception as e:
                add_log_line(f"⚠️ Falló {service_url[:50]}: {str(e)[:50]}")
                continue
        
        return None
    
    # ========================================
    # DESCARGA CON REINTENTOS
    # ========================================
    async def fetch(self, url: str, max_retries: int = 3) -> Optional[bytes]:
        """Descarga con reintentos exponenciales."""
        session = await self._get_session()
        
        for attempt in range(max_retries):
            try:
                async with session.get(url) as response:
                    if response.status == 200:
                        content = await response.read()
                        add_log_line(f"✅ Descargado: {url[:60]} ({len(content)} bytes)")
                        return content
                    else:
                        add_log_line(f"⚠️ HTTP {response.status} en {url[:60]}")
            
            except asyncio.TimeoutError:
                add_log_line(f"⏱️ Timeout en {url[:60]} (Intento {attempt + 1})")
            
            except Exception as e:
                add_log_line(f"❌ Error: {str(e)[:100]} (Intento {attempt + 1})")
            
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)  # Espera exponencial
        
        return None
    
    # ========================================
    # DESCUBRIMIENTO DE FEEDS EN PÁGINAS WEB
    # ========================================
    async def discover_feed(self, url: str) -> Optional[str]:
        """
        Busca feeds RSS/Atom en una página web.
        """
        try:
            content = await self.fetch(url)
            if not content:
                return None
            
            soup = BeautifulSoup(content, 'html.parser')
            
            # 1. Buscar en <link> tags
            for link in soup.find_all('link', type=['application/rss+xml', 'application/atom+xml']):
                href = link.get('href')
                if href:
                    feed_url = urljoin(url, href)
                    add_log_line(f"🔍 Feed encontrado en <link>: {feed_url}")
                    return feed_url
            
            # 2. Rutas comunes
            domain = urlparse(url).netloc
            common_paths = [
                '/feed', '/rss', '/atom.xml', '/rss.xml', '/feed.xml',
                '/index.xml', '/feeds/posts/default',  # Blogger
                '?feed=rss2', '?feed=atom',  # WordPress
            ]
            
            for path in common_paths:
                candidate = f"https://{domain}{path}"
                test_content = await self.fetch(candidate)
                
                if test_content and self._is_valid_feed(test_content):
                    add_log_line(f"🔍 Feed en ruta común: {candidate}")
                    return candidate
            
            # 3. Buscar enlaces con keywords
            for a in soup.find_all('a', href=True):
                href = a['href'].lower()
                if any(kw in href for kw in ['rss', 'feed', 'atom', '.xml']):
                    feed_url = urljoin(url, a['href'])
                    test_content = await self.fetch(feed_url)
                    
                    if test_content and self._is_valid_feed(test_content):
                        add_log_line(f"🔍 Feed en enlace: {feed_url}")
                        return feed_url
            
            return None
        
        except Exception as e:
            add_log_line(f"❌ Error en discover_feed: {e}")
            return None
    
    @staticmethod
    def _is_valid_feed(content: bytes) -> bool:
        """Verifica si es un feed válido."""
        if not content:
            return False
        
        try:
            text = content.decode('utf-8', errors='ignore')[:2000].lower()
            return any(tag in text for tag in ['<rss', '<feed', '<atom', '<channel', '<entry', '<item'])
        except:
            return False
    
    # ========================================
    # GENERACIÓN DE HASH ÚNICO
    # ========================================
    @staticmethod
    def generate_entry_hash(entry: Dict) -> str:
        """
        Genera un hash único para una entrada.
        Basado en: título + enlace + fecha publicación
        """
        components = [
            entry.get('title', ''),
            entry.get('link', ''),
            entry.get('id', ''),
            str(entry.get('published_parsed', '')),
        ]
        
        unique_string = '|'.join(filter(None, components))
        return hashlib.sha256(unique_string.encode('utf-8')).hexdigest()[:16]
    
    # ========================================
    # EXTRACCIÓN DE IMÁGENES
    # ========================================
    def extract_image(self, entry: dict, full_html: str = '') -> Optional[str]:
        """Extrae imagen de una entrada con múltiples métodos."""
        
        # 1. Media RSS
        if hasattr(entry, 'media_content'):
            for m in entry.media_content:
                if 'image' in m.get('type', '') or m.get('medium') == 'image':
                    return m.get('url')
        
        # 2. Media Thumbnail
        if hasattr(entry, 'media_thumbnail'):
            if isinstance(entry.media_thumbnail, list) and entry.media_thumbnail:
                return entry.media_thumbnail[0].get('url')
        
        # 3. Enclosure
        if hasattr(entry, 'links'):
            for link in entry.links:
                if link.get('rel') == 'enclosure' and 'image' in link.get('type', ''):
                    return link.get('href')
        
        # 4. Buscar en HTML (evitando trackers)
        img_match = re.search(r'<img[^>]+src=["\']\s*([^"\'>]+)["\']', full_html, re.IGNORECASE)
        if img_match:
            url = img_match.group(1)
            # Filtrar trackers conocidos
            if not any(x in url.lower() for x in ['pixel', 'tracker', 'icon', 'emoji', '1x1', 'avatar']):
                return url
        
        # 5. Open Graph
        if hasattr(entry, 'summary'):
            og_match = re.search(r'og:image["\s]+content=["\']\s*([^"\'>]+)["\']', entry.summary, re.IGNORECASE)
            if og_match:
                return og_match.group(1)
        
        return None
    
    # ========================================
    # LIMPIEZA DE HTML
    # ========================================
    @staticmethod
    def clean_html(raw_html: str) -> str:
        """Limpia HTML para Telegram."""
        if not raw_html:
            return ""
        
        # Normalización
        text = raw_html.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
        text = text.replace("</p>", "\n\n")
        
        # Eliminar elementos no deseados
        text = re.sub(r'<(script|style|iframe|embed|object|svg)[^>]*>.*?</\1>', '', text, flags=re.DOTALL | re.IGNORECASE)
        
        # Eliminar imágenes
        text = re.sub(r'<img[^>]*>', '', text, flags=re.IGNORECASE)
        
        # Mantener solo etiquetas permitidas por Telegram
        text = re.sub(r'<(?!\/?(b|strong|i|em|u|s|a|code|pre)\b)[^>]*>', '', text, flags=re.IGNORECASE)
        
        # Normalizar
        text = text.replace('<strong>', '<b>').replace('</strong>', '</b>')
        text = text.replace('<em>', '<i>').replace('</em>', '</i>')
        
        # Limpiar espacios
        text = re.sub(r'\n\s*\n\s*\n', '\n\n', text)
        
        import html as html_module
        text = html_module.unescape(text)
        
        return text.strip()
    
    # ========================================
    # PARSE PRINCIPAL
    # ========================================
    async def parse(self, url: str) -> Dict:
        """
        Parse principal ultra-robusto.
        """
        try:
            source_type, identifier = self.detect_source_type(url)
            add_log_line(f"🔍 Tipo detectado: {source_type} | ID: {identifier}")
            
            content = None
            original_url = url
            
            # --- REDES SOCIALES ---
            if source_type in ['twitter', 'instagram', 'youtube', 'telegram', 'reddit'] and identifier:
                content = await self.convert_social_to_rss(source_type, identifier)
                
                if not content:
                    return {
                        'success': False,
                        'error': f'No se pudo convertir {source_type} a RSS',
                        'type': source_type
                    }
            
            # --- RSS/ATOM GENÉRICO ---
            else:
                content = await self.fetch(url)
                
                # Si no es feed válido, intentar descubrir
                if not content or not self._is_valid_feed(content):
                    add_log_line(f"⚠️ No es feed válido. Buscando en la página...")
                    discovered_url = await self.discover_feed(url)
                    
                    if discovered_url:
                        content = await self.fetch(discovered_url)
                        original_url = discovered_url
            
            # --- VALIDAR CONTENIDO ---
            if not content:
                return {
                    'success': False,
                    'error': 'No se pudo descargar ningún feed',
                    'type': source_type
                }
            
            # --- PARSE CON FEEDPARSER ---
            parsed = await asyncio.get_event_loop().run_in_executor(
                None, feedparser.parse, content
            )
            
            if not parsed.entries:
                return {
                    'success': False,
                    'error': 'Feed sin entradas',
                    'type': source_type
                }
            
            # --- PROCESAR ENTRADAS ---
            entries = []
            for entry in parsed.entries[:20]:
                try:
                    # Contenido completo
                    content_html = ''
                    if hasattr(entry, 'content'):
                        for c in entry.content:
                            content_html += c.get('value', '')
                    
                    description = entry.get('summary', entry.get('description', ''))
                    full_html = f"{description} {content_html}"
                    
                    clean_desc = self.clean_html(description)
                    
                    processed_entry = {
                        'id': entry.get('id', entry.get('link', '')),
                        'hash': self.generate_entry_hash(entry),  # ✅ HASH ÚNICO
                        'title': self.clean_html(entry.get('title', 'Sin título')),
                        'link': entry.get('link', ''),
                        'description': clean_desc,
                        'image': self.extract_image(entry, full_html),
                        'published': entry.get('published', ''),
                        'source': parsed.feed.get('title', 'Feed'),
                        'source_link': parsed.feed.get('link', original_url),
                    }
                    
                    entries.append(processed_entry)
                
                except Exception as e:
                    add_log_line(f"⚠️ Error procesando entrada: {e}")
                    continue
            
            if not entries:
                return {
                    'success': False,
                    'error': 'No se pudieron procesar entradas',
                    'type': source_type
                }
            
            # --- EXTRAER METADATOS ---
            source_title = parsed.feed.get('title', 'Feed')
            
            # Añadir emoji según tipo
            emoji_map = {
                'twitter': '🐦',
                'instagram': '📸',
                'youtube': '📺',
                'telegram': '💬',
                'reddit': '🗨️',
            }
            
            if source_type in emoji_map:
                source_title = f"{emoji_map[source_type]} {source_title}"
            
            return {
                'success': True,
                'type': source_type,
                'source_title': source_title,  # ✅ TÍTULO CORRECTO
                'link': parsed.feed.get('link', original_url),
                'description': parsed.feed.get('description', ''),
                'entries': entries
            }
        
        except Exception as e:
            add_log_line(f"❌ Error crítico en parse: {e}")
            import traceback
            add_log_line(f"Traceback: {traceback.format_exc()[:500]}")
            
            return {
                'success': False,
                'error': f'Error: {str(e)[:100]}',
                'type': 'unknown'
            }
