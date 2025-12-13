# utils/feed_parser.py - VERSIÓN ULTRA-ROBUSTA PARA IMÁGENES

import asyncio
import feedparser
import requests
import re
import html
import json
from typing import Dict, List, Tuple, Optional
from datetime import datetime
from enum import Enum
from utils.file_manager import add_log_line

import warnings
warnings.filterwarnings('ignore', message='Unverified HTTPS request')

class FeedType(Enum):
    RSS = "rss"
    ATOM = "atom"
    JSON_FEED = "json_feed"
    TELEGRAM_CHANNEL = "telegram"
    TWITTER_USER = "twitter"
    INSTAGRAM_USER = "instagram"
    YOUTUBE_CHANNEL = "youtube"
    GENERIC = "generic"

class RobustFeedParser:
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/rss+xml, application/atom+xml, application/json, text/html",
        "Cache-Control": "no-cache",
    }
    
    RSSHUB_MIRRORS = [
        "https://rsshub.app",
        "https://rsshub.feeddd.org",
        "https://rsshub.blue",
    ]
    
    PATTERNS = {
        'twitter': r'(?:twitter\.com|x\.com)/([a-zA-Z0-9_]+)',
        'instagram': r'instagram\.com/([a-zA-Z0-9_.]+)',
        'youtube': r'(?:youtube\.com|youtu\.be).*?(?:/channel/|/c/|/user/|/@)([a-zA-Z0-9_-]+)',
        'telegram': r't\.me/([a-zA-Z0-9_]+)',
    }
    
    def __init__(self, timeout: int = 15):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        self.session.verify = False
    
    @staticmethod
    def detect_feed_type(url: str) -> Tuple[FeedType, Optional[str]]:
        url_lower = url.lower()
        for social, pattern in RobustFeedParser.PATTERNS.items():
            match = re.search(pattern, url)
            if match:
                return FeedType[f"{social.upper()}_{'USER' if social in ['twitter', 'instagram'] else 'CHANNEL'}"], match.group(1)
        if '.json' in url_lower: return FeedType.JSON_FEED, None
        return FeedType.GENERIC, None
    
    async def fetch_with_fallback(self, url: str) -> Optional[bytes]:
        try:
            resp = await asyncio.to_thread(self.session.get, url, timeout=self.timeout)
            if resp.status_code == 200: return resp.content
        except Exception:
            return None
        return None

    async def handle_social_media_feed(self, feed_type: FeedType, username: str) -> Optional[bytes]:
        paths = {
            FeedType.TWITTER_USER: f"/twitter/user/{username}",
            FeedType.INSTAGRAM_USER: f"/instagram/user/{username}",
            FeedType.YOUTUBE_CHANNEL: f"/youtube/channel/{username}",
            FeedType.TELEGRAM_CHANNEL: f"/telegram/channel/{username}",
        }
        path = paths.get(feed_type)
        if not path: return None
        for mirror in self.RSSHUB_MIRRORS:
            try:
                content = await self.fetch_with_fallback(f"{mirror}{path}")
                if content: return content
            except: continue
        return None

    async def parse(self, url: str) -> Dict:
        feed_type, param = self.detect_feed_type(url)
        
        if feed_type in [FeedType.TWITTER_USER, FeedType.INSTAGRAM_USER, FeedType.YOUTUBE_CHANNEL, FeedType.TELEGRAM_CHANNEL]:
            content = await self.handle_social_media_feed(feed_type, param)
        else:
            content = await self.fetch_with_fallback(url)
            
        if not content:
            return {'success': False, 'error': 'No se pudo descargar', 'type': feed_type.value}

        try:
            # Feedparser
            loop = asyncio.get_event_loop()
            parsed = await loop.run_in_executor(None, feedparser.parse, content)
            
            return self._parse_rss_atom(parsed, url, feed_type)
        except Exception as e:
            return {'success': False, 'error': str(e), 'type': feed_type.value}

    def _parse_rss_atom(self, parsed, url: str, feed_type: FeedType) -> Dict:
        if not parsed.entries and not parsed.feed.get('title'):
            return {'success': False, 'error': 'Feed vacío', 'type': feed_type.value}
        
        entries = []
        for entry in parsed.entries[:20]:
            try:
                # Extracción robusta de contenido para buscar imágenes
                content_html = ''
                if 'content' in entry:
                    for c in entry.content:
                        content_html += c.get('value', '')
                
                description = entry.get('summary', entry.get('description', ''))
                full_html_for_search = f"{description} {content_html}"

                entries.append({
                    'id': entry.get('id', entry.get('link', '')),
                    'title': self._clean_html(entry.get('title', 'Sin título')),
                    'link': entry.get('link', ''),
                    'description': description,
                    'image': self._extract_image_from_entry(entry, full_html_for_search),
                    'source': parsed.feed.get('title', 'Feed'),
                    'source_link': parsed.feed.get('link', ''),
                })
            except Exception:
                continue
        
        return {
            'success': True,
            'type': feed_type.value,
            'source_title': parsed.feed.get('title', 'Feed'),
            'entries': entries
        }

    @staticmethod
    def _clean_html(raw_html: str) -> str:
        clean = re.sub(r'<[^>]+>', '', html.unescape(raw_html))
        return clean.strip()
    
    @staticmethod
    def _extract_image_from_entry(entry: dict, full_html: str) -> Optional[str]:
        """Busca imágenes en todos los rincones posibles del RSS."""
        
        # 1. Buscar en 'media_content' (Estándar Media RSS)
        if 'media_content' in entry:
            for m in entry.media_content:
                if 'image' in m.get('type', '') or m.get('medium') == 'image':
                    if 'url' in m: return m['url']

        # 2. Buscar en 'media_thumbnail'
        if 'media_thumbnail' in entry:
            if isinstance(entry.media_thumbnail, list) and len(entry.media_thumbnail) > 0:
                return entry.media_thumbnail[0].get('url')

        # 3. Buscar en 'links' (enclosures) -> CRUCIAL para muchos feeds
        if 'links' in entry:
            for link in entry.links:
                if link.get('rel') == 'enclosure' and 'image' in link.get('type', ''):
                    return link.get('href')

        # 4. Buscar etiqueta <img> en el contenido HTML
        # Buscamos src="..." ignorando mayúsculas/minúsculas
        img_match = re.search(r'<img[^>]+src=["\']\s*([^"\'>]+)["\']', full_html, re.IGNORECASE)
        if img_match:
            url = img_match.group(1)
            # Filtrar iconos pequeños, trackers, pixels
            if not any(x in url.lower() for x in ['pixel', 'tracker', 'icon', 'emoji', 'avatar']):
                return url

        return None