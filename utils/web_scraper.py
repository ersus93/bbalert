# utils/web_scraper.py

import asyncio
import aiohttp
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
from datetime import datetime
from urllib.parse import urljoin, urlparse
import re
from utils.file_manager import add_log_line

class WebContentScraper:
    """
    Scraper universal que puede detectar y extraer contenido
    de páginas web para convertir a RSS.
    """
    
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    }
    
    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self._session = None
    
    async def _get_session(self):
        """Crea sesión HTTP persistente."""
        if not self._session:
            self._session = aiohttp.ClientSession(
                headers=self.HEADERS,
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            )
        return self._session
    
    async def close(self):
        """Cierra la sesión."""
        if self._session:
            await self._session.close()
            self._session = None
    
    async def scrape_webpage(self, url: str) -> Dict:
        """
        Extrae contenido estructurado de una página web.
        
        Returns:
            {
                'success': bool,
                'title': str,
                'items': List[Dict],
                'type': str  # 'blog', 'news', 'generic'
            }
        """
        try:
            session = await self._get_session()
            
            async with session.get(url) as response:
                if response.status != 200:
                    return {'success': False, 'error': f'HTTP {response.status}'}
                
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                # Detectar tipo de sitio
                site_type = self._detect_site_type(soup, url)
                
                # Extraer metadatos del sitio
                site_title = self._extract_site_title(soup, url)
                site_description = self._extract_site_description(soup)
                
                # Extraer artículos/posts según el tipo
                items = []
                
                if site_type == 'blog':
                    items = self._extract_blog_posts(soup, url)
                elif site_type == 'news':
                    items = self._extract_news_articles(soup, url)
                else:
                    items = self._extract_generic_content(soup, url)
                
                return {
                    'success': True,
                    'site_title': site_title,
                    'site_description': site_description,
                    'site_url': url,
                    'items': items,
                    'type': site_type
                }
        
        except Exception as e:
            add_log_line(f"❌ Error scrapeando {url}: {e}")
            return {'success': False, 'error': str(e)}
    
    def _detect_site_type(self, soup: BeautifulSoup, url: str) -> str:
        """Detecta el tipo de sitio web."""
        
        # Detectar WordPress
        if soup.find('meta', {'name': 'generator', 'content': re.compile('WordPress')}):
            return 'blog'
        
        # Detectar Blogger
        if 'blogspot.com' in url or soup.find('meta', {'content': re.compile('Blogger')}):
            return 'blog'
        
        # Detectar Medium
        if 'medium.com' in url:
            return 'blog'
        
        # Detectar sitios de noticias por estructura
        if soup.find_all('article', class_=re.compile('post|article|entry|news')):
            return 'news'
        
        return 'generic'
    
    def _extract_site_title(self, soup: BeautifulSoup, url: str) -> str:
        """Extrae el título del sitio."""
        
        # Open Graph
        og_title = soup.find('meta', property='og:site_name')
        if og_title and og_title.get('content'):
            return og_title['content']
        
        # Title tag
        title_tag = soup.find('title')
        if title_tag:
            return title_tag.get_text().strip()
        
        # Fallback al dominio
        domain = urlparse(url).netloc
        return domain
    
    def _extract_site_description(self, soup: BeautifulSoup) -> str:
        """Extrae la descripción del sitio."""
        
        # Meta description
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc and meta_desc.get('content'):
            return meta_desc['content']
        
        # Open Graph description
        og_desc = soup.find('meta', property='og:description')
        if og_desc and og_desc.get('content'):
            return og_desc['content']
        
        return "Contenido web convertido a RSS"
    
    def _extract_blog_posts(self, soup: BeautifulSoup, base_url: str) -> List[Dict]:
        """Extrae posts de blogs (WordPress, Blogger, etc)."""
        items = []
        
        # Selectores comunes de blogs
        selectors = [
            'article',
            '.post',
            '.entry',
            '.blog-post',
            '[class*="post"]',
            '[class*="article"]'
        ]
        
        for selector in selectors:
            posts = soup.select(selector)
            if posts:
                for post in posts[:10]:  # Límite de 10
                    item = self._extract_post_data(post, base_url)
                    if item:
                        items.append(item)
                break  # Ya encontramos posts
        
        return items
    
    def _extract_news_articles(self, soup: BeautifulSoup, base_url: str) -> List[Dict]:
        """Extrae artículos de sitios de noticias."""
        items = []
        
        # Buscar por schema.org (NewsArticle)
        articles = soup.find_all(attrs={'itemtype': re.compile('NewsArticle|Article')})
        
        if not articles:
            # Fallback a selectores comunes
            articles = soup.select('article, .article, .news-item, [class*="article"]')
        
        for article in articles[:10]:
            item = self._extract_article_data(article, base_url)
            if item:
                items.append(item)
        
        return items
    
    def _extract_generic_content(self, soup: BeautifulSoup, base_url: str) -> List[Dict]:
        """Extracción genérica para cualquier sitio."""
        items = []
        
        # Buscar todos los enlaces con cierta estructura
        links = soup.find_all('a', href=True)
        
        for link in links[:15]:
            # Filtrar enlaces internos relevantes
            href = link.get('href')
            if not href or href.startswith('#') or href.startswith('javascript:'):
                continue
            
            full_url = urljoin(base_url, href)
            
            # Debe ser del mismo dominio
            if urlparse(full_url).netloc != urlparse(base_url).netloc:
                continue
            
            title = link.get_text().strip()
            if len(title) < 10:  # Filtrar títulos muy cortos
                continue
            
            items.append({
                'title': title,
                'link': full_url,
                'description': '',
                'pub_date': datetime.now(),
                'guid': full_url
            })
        
        return items
    
    def _extract_post_data(self, post_elem, base_url: str) -> Optional[Dict]:
        """Extrae datos de un post individual."""
        try:
            # Título
            title_elem = (
                post_elem.find('h1') or 
                post_elem.find('h2') or 
                post_elem.find('h3') or
                post_elem.find(class_=re.compile('title|heading'))
            )
            
            if not title_elem:
                return None
            
            title = title_elem.get_text().strip()
            
            # Enlace
            link_elem = title_elem.find('a') or post_elem.find('a', class_=re.compile('permalink|link'))
            link = urljoin(base_url, link_elem['href']) if link_elem and link_elem.get('href') else base_url
            
            # Descripción/Excerpt
            desc_elem = (
                post_elem.find(class_=re.compile('excerpt|summary|description|content')) or
                post_elem.find('p')
            )
            description = desc_elem.get_text().strip()[:300] if desc_elem else ''
            
            # Fecha
            date_elem = post_elem.find('time') or post_elem.find(class_=re.compile('date|published'))
            pub_date = self._parse_date(date_elem) if date_elem else datetime.now()
            
            # Imagen
            img_elem = post_elem.find('img')
            image_url = urljoin(base_url, img_elem['src']) if img_elem and img_elem.get('src') else None
            
            return {
                'title': title,
                'link': link,
                'description': description,
                'pub_date': pub_date,
                'guid': link,
                'enclosure': {
                    'url': image_url,
                    'type': 'image/jpeg',
                    'length': 0
                } if image_url else None
            }
        
        except Exception as e:
            add_log_line(f"⚠️ Error extrayendo post: {e}")
            return None
    
    def _extract_article_data(self, article_elem, base_url: str) -> Optional[Dict]:
        """Extrae datos de un artículo de noticias."""
        # Similar a _extract_post_data pero con selectores específicos de noticias
        return self._extract_post_data(article_elem, base_url)
    
    def _parse_date(self, date_elem) -> datetime:
        """Intenta parsear una fecha de un elemento."""
        try:
            # Atributo datetime
            if date_elem.get('datetime'):
                return datetime.fromisoformat(date_elem['datetime'].replace('Z', '+00:00'))
            
            # Texto del elemento
            date_text = date_elem.get_text().strip()
            # Aquí podrías usar dateutil.parser o parseo manual
            # Por simplicidad, retornamos fecha actual
            return datetime.now()
        except:
            return datetime.now()
