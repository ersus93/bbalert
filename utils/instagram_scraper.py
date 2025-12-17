# utils/instagram_scraper.py

import os
import asyncio
import aiohttp
import json
import re
from typing import Dict, List, Optional
from datetime import datetime
from utils.file_manager import add_log_line

# ===== NUEVAS IMPORTACIONES =====
from utils.rss_generator import RSSGenerator
from utils.web_scraper import WebContentScraper
from aiohttp import ClientTimeout  # <-- Necesario para el timeout
from aiohttp.client_exceptions import ClientConnectorError

class InstagramScraper:
    """
    Scraper de Instagram que extrae posts públicos sin API.
    Utiliza técnicas de scraping web legal de contenido público.
    """
    
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
        "Viewport-Width": "1920", 
    }
    
    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self._session = None
        self.session_id = os.environ.get("INSTAGRAM_SESSION_ID")

    async def _get_session(self):
        if not self._session:
            # Copiamos los headers base
            headers = self.HEADERS.copy()
            
            # === MODIFICACIÓN: Inyección de Cookie ===
            if self.session_id:
                # La cookie debe ir en el formato exacto
                headers["Cookie"] = f"sessionid={self.session_id}"
                # Añadimos headers extra que Instagram suele pedir a usuarios logueados
                headers["X-IG-App-ID"] = "936619743392459" 
                headers["X-ASBD-ID"] = "198387"
                headers["X-IG-WWW-Claim"] = "0"
                add_log_line("🍪 Cookie de sesión inyectada correctamente")
            # =========================================

            self._session = aiohttp.ClientSession(
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=self.timeout),
                connector=aiohttp.TCPConnector(ssl=False) 
            )
        return self._session
    
    async def close(self):
        if self._session:
            await self._session.close()
            self._session = None
    
    async def scrape_profile(self, identifier: str) -> Dict:
        """Extrae el perfil y posts de un usuario de Instagram usando una sesión temporal segura."""
        url = f"https://www.instagram.com/{identifier}/"
        
        # 1. Timeout estricto y Sesión de uso único (CRÍTICO)
        # 30 segundos es un tiempo razonable para evitar cuelgues indefinidos.
        timeout_setting = ClientTimeout(total=30) 
        
        try:
            # Reemplazamos self._get_session() por una sesión NUEVA y temporal
            # Esto evita que una sesión previa o bloqueada congele el loop
            async with aiohttp.ClientSession(headers=self.HEADERS, timeout=timeout_setting) as session:
                
                # NOTA: La inyección de la cookie DEBE ocurrir antes de esta llamada, 
                # o el código que inyecta la cookie debe usar este objeto 'session'.
                
                # 2. Realizamos la solicitud
                # Quitamos el timeout aquí ya que lo definimos en el ClientSession.
                async with session.get(url, allow_redirects=True) as response:
                    
                    # 3. Manejo de Bloqueos y Status
                    if '/accounts/login/' in str(response.url):
                        add_log_line(f"⚠️ Redirección a login detectada para @{identifier}. La cookie expiró o es inválida.")
                        return {'success': False, 'error': 'Redirección a login (Cookie o Bloqueo)'}
                        
                    if response.status == 429: # Demasiadas Solicitudes (Bloqueo Duro)
                        add_log_line(f"❌ Instagram devolvió 429 (Bloqueo) para @{identifier}. Intento fallido.")
                        return {'success': False, 'error': 'Bloqueo HTTP 429'}
                        
                    if response.status != 200:
                        add_log_line(f"⚠️ Instagram devolvió HTTP {response.status} para @{identifier}")
                        return {'success': False, 'error': f'HTTP {response.status}'}
                        
                    # 4. Lectura y Extracción
                    html = await response.text()
                    data = self._extract_json_data(html)
                    
                    if data:
                        return self._parse_profile_data(data)
                    
                    add_log_line(f"⚠️ JSON no encontrado para @{identifier}, intentando fallback OpenGraph.")
                    return self._extract_from_html_fallback(html)
            
        except asyncio.TimeoutError:
            # Captura el error de cuelgue/timeout (CRÍTICO para evitar el bloqueo)
            add_log_line(f"❌ Timeout (30s) alcanzado para @{identifier}. El bot no se colgará.")
            return {'success': False, 'error': 'Timeout de red alcanzado'}
        except ClientConnectorError as e:
            add_log_line(f"❌ Error de conexión (DNS/TCP) para @{identifier}: {e}")
            return {'success': False, 'error': f'Error de conexión: {str(e)}'}
        except Exception as e:
            # Captura cualquier otro error no manejado
            add_log_line(f"❌ Error crítico en scrape_profile para @{identifier}: {e}")
            return {'success': False, 'error': f'Error desconocido: {str(e)}'}
    
    def _extract_json_data(self, html: str) -> Optional[Dict]:
        """
        Intenta extraer datos JSON incrustados en el HTML de Instagram
        usando múltiples patrones de búsqueda modernos (GraphQL y Items).
        """
        try:
            # PATRÓN 1: Busca la estructura moderna de GraphQL (Timeline)
            # Buscamos la clave 'edge_owner_to_timeline_media' en el HTML.
            timeline_match = re.search(r'"edge_owner_to_timeline_media"\s*:\s*({.*?})\s*,\s*"', html)
            if timeline_match:
                try:
                    data_str = timeline_match.group(1)
                    edges_data = json.loads(data_str)
                    # Construimos un objeto simulado compatible con tu parser existente
                    return {
                        "entry_data": {
                            "ProfilePage": [{
                                "graphql": {
                                    "user": {
                                        "edge_owner_to_timeline_media": edges_data
                                    }
                                }
                            }]
                        }
                    }
                except:
                    # Falló al parsear el JSON encontrado, continuamos con el siguiente patrón
                    pass

            # PATRÓN 2: Busca "items" (Estructura API interna v1)
            # A veces aparece el array de posts directamente bajo la clave "items"
            items_match = re.search(r'"items"\s*:\s*(\[{.*?}\])', html)
            if items_match:
                try:
                    items_str = items_match.group(1)
                    items_list = json.loads(items_str)
                    # Convertimos el formato 'items' al que espera tu parser principal
                    return self._convert_items_to_graphql(items_list)
                except:
                    # Falló al parsear el JSON encontrado, continuamos con el siguiente patrón
                    pass

            # PATRÓN 3 (FALLBACK ANTIGUO): window._sharedData (Si aún existe)
            script_pattern = re.compile(r'window\._sharedData\s*=\s*({.*?});', re.DOTALL)
            match = script_pattern.search(html)
            if match:
                return json.loads(match.group(1))

            add_log_line("⚠️ No se encontraron patrones JSON conocidos en el HTML de Instagram")
            return None

        except Exception as e:
            add_log_line(f"⚠️ Error parseando JSON de Instagram: {e}")
            return None

    def _convert_items_to_graphql(self, items: list) -> Dict:
        """Helper para convertir formato API v1 a formato GraphQL"""
        edges = []
        for item in items:
            node = {
                "node": {
                    "shortcode": item.get("code"),
                    "display_url": item.get("image_versions2", {}).get("candidates", [{}])[0].get("url"),
                    "edge_media_to_caption": {"edges": [{"node": {"text": item.get("caption", {}).get("text", "")}}]},
                    "taken_at_timestamp": item.get("taken_at"),
                    "is_video": item.get("media_type") == 2, # 2 es video
                    "video_url": item.get("video_versions", [{}])[0].get("url") if item.get("media_type") == 2 else None
                }
            }
            edges.append(node)
        
        return {
            "entry_data": {
                "ProfilePage": [{
                    "graphql": {
                        "user": {
                            "edge_owner_to_timeline_media": {"edges": edges}
                        }
                    }
                }]
            }
        }
    

    def _extract_from_html_fallback(self, html: str) -> List[Dict]:
        """
        Último recurso: Busca enlaces a posts directamente en el HTML usando Regex simple.
        Útil cuando Instagram ofusca el JSON pero renderiza el HTML (SSR).
        """
        posts = []
        try:
            # Busca enlaces tipo /p/CÓDIGO/
            # Grupo 1: Shortcode
            link_pattern = re.compile(r'<a href="/p/([^/]+)/"', re.IGNORECASE)
            matches = link_pattern.findall(html)
            
            # Eliminamos duplicados manteniendo el orden
            unique_codes = list(dict.fromkeys(matches))

            if not unique_codes:
                # Intento extra: buscar en meta tags og:url
                # A veces el perfil redirecciona al último post
                return []

            add_log_line(f"🔍 Método HTML crudo: Encontrados {len(unique_codes)} posibles posts.")

            for code in unique_codes[:12]: # Limitamos a 12
                # Como no tenemos imagen ni texto en este modo básico,
                # creamos un post "placeholder". El bot luego intentará resolverlo.
                # O mejor, intentamos buscar la imagen asociada cercana en el HTML (avanzado),
                # pero por estabilidad, devolvemos lo básico para que el sistema detecte el post nuevo.
                
                posts.append({
                    'id': code,
                    'shortcode': code,
                    'url': f"https://www.instagram.com/p/{code}/",
                    'image': None, # El parser principal intentará sacar info OpenGraph de la URL del post
                    'caption': "Ver en Instagram (Modo HTML Básico)",
                    'date': int(datetime.now().timestamp()), # Fecha aproximada
                    'is_video': False
                })
                
            return posts

        except Exception as e:
            add_log_line(f"⚠️ Error en fallback HTML: {e}")
            return []
        
        
    def _find_key_recursive(self, obj, key):
        """Busca una clave recursivamente en un diccionario anidado."""
        if isinstance(obj, dict):
            if key in obj:
                return obj[key]
            for k, v in obj.items():
                item = self._find_key_recursive(v, key)
                if item is not None:
                    return item
        elif isinstance(obj, list):
            for v in obj:
                item = self._find_key_recursive(v, key)
                if item is not None:
                    return item
        return None
    
    def _convert_items_to_graphql(self, items: list) -> Dict:
        """Helper para convertir formato API v1 ('items') a formato GraphQL ('entry_data') compatible."""
        edges = []
        for item in items:
            node = {
                "node": {
                    "id": str(item.get("pk", item.get("id"))), # Usar 'pk' o 'id'
                    "shortcode": item.get("code"),
                    "display_url": item.get("image_versions2", {}).get("candidates", [{}])[0].get("url"),
                    "edge_media_to_caption": {"edges": [{"node": {"text": item.get("caption", {}).get("text", "")}}]},
                    "taken_at_timestamp": item.get("taken_at"),
                    "is_video": item.get("media_type") == 2, # 2 es video
                    "video_url": item.get("video_versions", [{}])[0].get("url") if item.get("media_type") == 2 else None
                }
            }
            edges.append(node)
        
        # Construimos el objeto simulado compatible con tu lógica de parseo existente
        return {
            "entry_data": {
                "ProfilePage": [{
                    "graphql": {
                        "user": {
                            "edge_owner_to_timeline_media": {"edges": edges}
                        }
                    }
                }]
            }
        }

    def _parse_profile_data(self, data: Dict, username: str) -> Dict:
        """
        Parsea los datos JSON buscando las claves críticas recursivamente.
        """
        try:
            # Si es el fallback de meta tags, retornar directo
            if data.get('_meta_fallback'):
                return {
                    'profile_name': username,
                    'profile_bio': data.get('description', ''),
                    'profile_pic': data.get('image', ''),
                    'posts': []
                }

            # 1. Buscar objeto de usuario (suele estar bajo la clave 'user' o 'user_info')
            user_data = self._find_key_recursive(data, 'user')
            
            # Si no hay objeto 'user', usamos el root data (común en ld+json)
            if not user_data and ('name' in data or 'description' in data):
                user_data = data

            if not user_data:
                 return self._extract_from_meta_tags("") or {} 

            # 2. Extraer datos básicos
            profile_name = user_data.get('full_name', user_data.get('name', username))
            biography = user_data.get('biography', user_data.get('description', ''))
            profile_pic = user_data.get('profile_pic_url_hd', user_data.get('image', ''))
            
            # 3. Buscar posts (timeline) recursivamente
            timeline = self._find_key_recursive(data, 'edge_owner_to_timeline_media')
            posts = []
            
            if timeline and 'edges' in timeline:
                posts = self._extract_posts_from_timeline(timeline)
            
            return {
                'profile_name': profile_name,
                'profile_bio': biography,
                'profile_pic': profile_pic,
                'posts': posts
            }
        
        except Exception as e:
            add_log_line(f"⚠️ Error parseando datos de perfil: {e}")
            return {
                'profile_name': username,
                'profile_bio': '',
                'profile_pic': '',
                'posts': []
            }

    def _extract_posts_from_timeline(self, timeline: Dict) -> List[Dict]:
        """Extrae lista de posts limpias desde el objeto timeline encontrado."""
        posts = []
        try:
            edges = timeline.get('edges', [])
            for edge in edges[:12]: # Últimos 12
                node = edge.get('node', {})
                if not node: continue
                
                shortcode = node.get('shortcode', '')
                post_url = f"https://www.instagram.com/p/{shortcode}/"
                
                # Caption
                caption = ""
                edge_caption = node.get('edge_media_to_caption', {})
                if edge_caption and 'edges' in edge_caption:
                    edges_cap = edge_caption['edges']
                    if edges_cap:
                        caption = edges_cap[0].get('node', {}).get('text', '')
                
                # Timestamp
                timestamp = node.get('taken_at_timestamp', 0)
                pub_date = datetime.fromtimestamp(timestamp) if timestamp else datetime.now()
                
                # Media URL (Imagen o Video)
                media_url = node.get('display_url', '')
                media_type = 'image/jpeg'
                
                if node.get('is_video'):
                    # A veces el video_url no está disponible en la vista de lista pública
                    # Usamos display_url (la portada del video) como fallback visual
                    if node.get('video_url'):
                        media_url = node['video_url']
                        media_type = 'video/mp4'
                
                posts.append({
                    'title': caption[:100] + '...' if len(caption) > 100 else (caption or 'Instagram Post'),
                    'link': post_url,
                    'description': caption,
                    'pub_date': pub_date,
                    'guid': shortcode, # El shortcode es mejor GUID que la URL completa
                    'media_url': media_url,
                    'media_type': media_type,
                    'likes': node.get('edge_liked_by', {}).get('count', 0),
                    'comments': node.get('edge_media_to_comment', {}).get('count', 0)
                })
            return posts
        except Exception as e:
            add_log_line(f"⚠️ Error extrayendo timeline: {e}")
            return []
    
    def _extract_from_meta_tags(self, html: str) -> Optional[Dict]:
        """Extrae datos básicos de meta tags como fallback."""
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')
        
        title = soup.find('meta', property='og:title')
        description = soup.find('meta', property='og:description')
        image = soup.find('meta', property='og:image')
        
        if title:
            return {
                '_meta_fallback': True,
                'title': title.get('content', ''),
                'description': description.get('content', '') if description else '',
                'image': image.get('content', '') if image else ''
            }
        
        return None
    
    def _parse_profile_data(self, data: Dict, username: str) -> Dict:
        """
        Parsea los datos JSON de Instagram y extrae posts.
        """
        try:
            # Si es fallback de meta tags
            if data.get('_meta_fallback'):
                return {
                    'profile_name': username,
                    'profile_bio': data.get('description', ''),
                    'profile_pic': data.get('image', ''),
                    'posts': []  # No podemos extraer posts del meta tag
                }
            
            # Estructura normal de datos
            posts = []
            
            # Navegar la estructura de JSON de Instagram
            # (La estructura exacta varía según la versión)
            
            if 'entry_data' in data:
                # Método antiguo
                profile_page = data.get('entry_data', {}).get('ProfilePage', [])
                if profile_page:
                    user_data = profile_page[0].get('graphql', {}).get('user', {})
                    posts = self._extract_posts_from_user_data(user_data)
                    
                    return {
                        'profile_name': user_data.get('full_name', username),
                        'profile_bio': user_data.get('biography', ''),
                        'profile_pic': user_data.get('profile_pic_url_hd', ''),
                        'follower_count': user_data.get('edge_followed_by', {}).get('count', 0),
                        'posts': posts
                    }
            
            # Si no encontramos posts, retornar estructura vacía
            return {
                'profile_name': username,
                'profile_bio': '',
                'profile_pic': '',
                'posts': []
            }
        
        except Exception as e:
            add_log_line(f"⚠️ Error parseando datos de perfil: {e}")
            return {
                'profile_name': username,
                'profile_bio': '',
                'profile_pic': '',
                'posts': []
            }
    
    def _extract_posts_from_user_data(self, user_data: Dict) -> List[Dict]:
        """Extrae lista de posts del objeto user de Instagram."""
        posts = []
        
        try:
            edges = user_data.get('edge_owner_to_timeline_media', {}).get('edges', [])
            
            for edge in edges[:12]:  # Últimos 12 posts
                node = edge.get('node', {})
                
                post_url = f"https://www.instagram.com/p/{node.get('shortcode', '')}/"
                
                # Extraer texto del caption
                caption_edges = node.get('edge_media_to_caption', {}).get('edges', [])
                caption = caption_edges[0].get('node', {}).get('text', '') if caption_edges else ''
                
                # Timestamp a datetime
                timestamp = node.get('taken_at_timestamp', 0)
                pub_date = datetime.fromtimestamp(timestamp) if timestamp else datetime.now()
                
                # Extraer URL de imagen
                if node.get('is_video'):
                    media_url = node.get('video_url', '')
                    media_type = 'video/mp4'
                else:
                    media_url = node.get('display_url', '')
                    media_type = 'image/jpeg'
                
                posts.append({
                    'title': caption[:100] + '...' if len(caption) > 100 else caption,
                    'link': post_url,
                    'description': caption,
                    'pub_date': pub_date,
                    'guid': post_url,
                    'media_url': media_url,
                    'media_type': media_type,
                    'likes': node.get('edge_liked_by', {}).get('count', 0),
                    'comments': node.get('edge_media_to_comment', {}).get('count', 0)
                })
            
            return posts
        
        except Exception as e:
            add_log_line(f"⚠️ Error extrayendo posts: {e}")
            return []
    
    async def scrape_hashtag(self, hashtag: str, limit: int = 20) -> Dict:
        """
        Extrae posts públicos de un hashtag.
        
        Args:
            hashtag: Hashtag sin el símbolo # (ejemplo: 'travel')
            limit: Número máximo de posts a extraer
        
        Returns:
            Dict con posts del hashtag
        """
        try:
            url = f"https://www.instagram.com/explore/tags/{hashtag}/"
            session = await self._get_session()
            
            async with session.get(url) as response:
                if response.status != 200:
                    return {'success': False, 'error': f'HTTP {response.status}'}
                
                html = await response.text()
                data = self._extract_json_data(html)
                
                if not data:
                    return {'success': False, 'error': 'No se pudo extraer datos'}
                
                # Extraer posts del hashtag
                # (Similar a profile pero con estructura diferente)
                
                return {
                    'success': True,
                    'hashtag': hashtag,
                    'posts': []  # Implementación similar a profile
                }
        
        except Exception as e:
            return {'success': False, 'error': str(e)}
