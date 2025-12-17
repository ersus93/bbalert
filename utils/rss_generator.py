# utils/rss_generator.py

import xml.etree.ElementTree as ET
from datetime import datetime
from typing import List, Dict, Optional
from urllib.parse import urlparse
import hashlib

class RSSGenerator:
    """
    Generador RSS/Atom desde cero siguiendo los estándares oficiales.
    Soporta RSS 2.0 y Atom 1.0
    """
    
    def __init__(self, format_type: str = 'rss'):
        """
        Args:
            format_type: 'rss' para RSS 2.0, 'atom' para Atom 1.0
        """
        self.format_type = format_type
    
    def generate_rss_feed(
        self,
        channel_title: str,
        channel_link: str,
        channel_description: str,
        items: List[Dict],
        language: str = 'es',
        image_url: Optional[str] = None
    ) -> bytes:
        """
        Genera un feed RSS 2.0 completo.
        
        Args:
            channel_title: Título del canal
            channel_link: URL del sitio
            channel_description: Descripción del canal
            items: Lista de items con estructura:
                {
                    'title': str,
                    'link': str,
                    'description': str,
                    'pub_date': datetime,
                    'guid': str,
                    'author': str (opcional),
                    'enclosure': {'url': str, 'type': str, 'length': int} (opcional)
                }
            language: Código de idioma (es, en, etc)
            image_url: URL de imagen del canal
        
        Returns:
            bytes: XML del feed RSS
        """
        
        # Crear elemento raíz
        rss = ET.Element('rss', attrib={
            'version': '2.0',
            'xmlns:atom': 'http://www.w3.org/2005/Atom',
            'xmlns:media': 'http://search.yahoo.com/mrss/',
            'xmlns:dc': 'http://purl.org/dc/elements/1.1/'
        })
        
        channel = ET.SubElement(rss, 'channel')
        
        # Metadatos del canal
        ET.SubElement(channel, 'title').text = channel_title
        ET.SubElement(channel, 'link').text = channel_link
        ET.SubElement(channel, 'description').text = channel_description
        ET.SubElement(channel, 'language').text = language
        ET.SubElement(channel, 'lastBuildDate').text = self._format_rfc822_date(datetime.now())
        ET.SubElement(channel, 'generator').text = 'BitBread RSS Generator v1.0'
        
        # Link auto-descubrimiento (Atom)
        atom_link = ET.SubElement(channel, '{http://www.w3.org/2005/Atom}link', attrib={
            'href': channel_link,
            'rel': 'self',
            'type': 'application/rss+xml'
        })
        
        # Imagen del canal (opcional)
        if image_url:
            image = ET.SubElement(channel, 'image')
            ET.SubElement(image, 'url').text = image_url
            ET.SubElement(image, 'title').text = channel_title
            ET.SubElement(image, 'link').text = channel_link
        
        # Añadir items
        for item_data in items:
            self._add_rss_item(channel, item_data)
        
        # Convertir a bytes con declaración XML
        xml_string = ET.tostring(rss, encoding='utf-8', method='xml')
        return b'<?xml version="1.0" encoding="UTF-8"?>\n' + xml_string
    
    def generate_atom_feed(
        self,
        feed_title: str,
        feed_link: str,
        feed_id: str,
        entries: List[Dict],
        author_name: str = 'BitBread Bot',
        subtitle: Optional[str] = None
    ) -> bytes:
        """
        Genera un feed Atom 1.0 completo.
        
        Args:
            feed_title: Título del feed
            feed_link: URL del feed
            feed_id: ID único del feed (puede ser la URL)
            entries: Lista de entradas
            author_name: Nombre del autor
            subtitle: Subtítulo del feed
        
        Returns:
            bytes: XML del feed Atom
        """
        
        feed = ET.Element('feed', attrib={
            'xmlns': 'http://www.w3.org/2005/Atom',
            'xmlns:media': 'http://search.yahoo.com/mrss/'
        })
        
        # Metadatos del feed
        ET.SubElement(feed, 'title').text = feed_title
        ET.SubElement(feed, 'id').text = feed_id
        ET.SubElement(feed, 'updated').text = self._format_iso8601_date(datetime.now())
        
        link_elem = ET.SubElement(feed, 'link', attrib={
            'href': feed_link,
            'rel': 'alternate'
        })
        
        self_link = ET.SubElement(feed, 'link', attrib={
            'href': feed_link,
            'rel': 'self'
        })
        
        if subtitle:
            ET.SubElement(feed, 'subtitle').text = subtitle
        
        author = ET.SubElement(feed, 'author')
        ET.SubElement(author, 'name').text = author_name
        
        # Añadir entradas
        for entry_data in entries:
            self._add_atom_entry(feed, entry_data)
        
        xml_string = ET.tostring(feed, encoding='utf-8', method='xml')
        return b'<?xml version="1.0" encoding="UTF-8"?>\n' + xml_string
    
    def _add_rss_item(self, channel: ET.Element, item_data: Dict):
        """Añade un item RSS 2.0 al canal."""
        item = ET.SubElement(channel, 'item')
        
        # Campos obligatorios
        ET.SubElement(item, 'title').text = item_data.get('title', 'Sin título')
        ET.SubElement(item, 'link').text = item_data['link']
        ET.SubElement(item, 'description').text = item_data.get('description', '')
        
        # GUID único (importante para deduplicación)
        guid = item_data.get('guid', self._generate_guid(item_data['link']))
        ET.SubElement(item, 'guid', attrib={'isPermaLink': 'false'}).text = guid
        
        # Fecha de publicación
        pub_date = item_data.get('pub_date', datetime.now())
        ET.SubElement(item, 'pubDate').text = self._format_rfc822_date(pub_date)
        
        # Autor (opcional)
        if 'author' in item_data:
            ET.SubElement(item, '{http://purl.org/dc/elements/1.1/}creator').text = item_data['author']
        
        # Enclosure (imagen/video)
        if 'enclosure' in item_data:
            enc = item_data['enclosure']
            ET.SubElement(item, 'enclosure', attrib={
                'url': enc['url'],
                'type': enc.get('type', 'image/jpeg'),
                'length': str(enc.get('length', 0))
            })
        
        # Media RSS (imágenes)
        if 'media_content' in item_data:
            media = item_data['media_content']
            ET.SubElement(item, '{http://search.yahoo.com/mrss/}content', attrib={
                'url': media['url'],
                'type': media.get('type', 'image/jpeg'),
                'medium': 'image'
            })
    
    def _add_atom_entry(self, feed: ET.Element, entry_data: Dict):
        """Añade una entrada Atom 1.0 al feed."""
        entry = ET.SubElement(feed, 'entry')
        
        ET.SubElement(entry, 'title').text = entry_data.get('title', 'Sin título')
        ET.SubElement(entry, 'id').text = entry_data.get('id', self._generate_guid(entry_data['link']))
        ET.SubElement(entry, 'updated').text = self._format_iso8601_date(
            entry_data.get('updated', datetime.now())
        )
        
        ET.SubElement(entry, 'link', attrib={
            'href': entry_data['link'],
            'rel': 'alternate'
        })
        
        # Contenido
        content = ET.SubElement(entry, 'content', attrib={'type': 'html'})
        content.text = entry_data.get('content', entry_data.get('summary', ''))
        
        # Resumen
        if 'summary' in entry_data:
            ET.SubElement(entry, 'summary').text = entry_data['summary']
        
        # Autor
        if 'author' in entry_data:
            author = ET.SubElement(entry, 'author')
            ET.SubElement(author, 'name').text = entry_data['author']
    
    @staticmethod
    def _format_rfc822_date(dt: datetime) -> str:
        """Formatea fecha para RSS 2.0 (RFC 822)."""
        return dt.strftime('%a, %d %b %Y %H:%M:%S +0000')
    
    @staticmethod
    def _format_iso8601_date(dt: datetime) -> str:
        """Formatea fecha para Atom (ISO 8601)."""
        return dt.strftime('%Y-%m-%dT%H:%M:%SZ')
    
    @staticmethod
    def _generate_guid(url: str) -> str:
        """Genera GUID único a partir de URL."""
        return hashlib.sha256(url.encode('utf-8')).hexdigest()[:16]


class RSSValidator:
    """Valida feeds RSS/Atom generados."""
    
    @staticmethod
    def validate_rss(xml_content: bytes) -> tuple[bool, str]:
        """
        Valida un feed RSS 2.0.
        
        Returns:
            (es_valido, mensaje_error)
        """
        try:
            root = ET.fromstring(xml_content)
            
            # Verificar estructura básica
            if root.tag != 'rss':
                return False, "El elemento raíz debe ser <rss>"
            
            if root.get('version') != '2.0':
                return False, "La versión debe ser 2.0"
            
            channel = root.find('channel')
            if channel is None:
                return False, "Falta el elemento <channel>"
            
            # Verificar elementos requeridos del canal
            required = ['title', 'link', 'description']
            for elem in required:
                if channel.find(elem) is None:
                    return False, f"Falta el elemento <{elem}> en el canal"
            
            # Verificar items
            items = channel.findall('item')
            for i, item in enumerate(items):
                if item.find('title') is None and item.find('description') is None:
                    return False, f"Item {i}: debe tener <title> o <description>"
            
            return True, "Feed RSS válido"
        
        except ET.ParseError as e:
            return False, f"Error de parseo XML: {str(e)}"
        except Exception as e:
            return False, f"Error de validación: {str(e)}"
    
    @staticmethod
    def validate_atom(xml_content: bytes) -> tuple[bool, str]:
        """Valida un feed Atom 1.0."""
        try:
            root = ET.fromstring(xml_content)
            
            if root.tag != '{http://www.w3.org/2005/Atom}feed':
                return False, "El elemento raíz debe ser <feed> con namespace Atom"
            
            # Elementos requeridos
            required = ['id', 'title', 'updated']
            for elem in required:
                if root.find(f'{{http://www.w3.org/2005/Atom}}{elem}') is None:
                    return False, f"Falta el elemento <{elem}>"
            
            return True, "Feed Atom válido"
        
        except Exception as e:
            return False, f"Error: {str(e)}"
