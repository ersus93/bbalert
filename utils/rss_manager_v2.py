# utils/rss_manager_v2.py - VERSIÓN MEJORADA CON PLANTILLA POR DEFECTO SEGURA

import json
import os
import uuid
import re
from typing import Tuple, Optional, List, Dict
from datetime import datetime
from core.config import DATA_DIR
from utils.feed_parser_v4 import FeedParserV4
from utils.content_filter import ContentFilter, FilterMode
from utils.file_manager import add_log_line

RSS_DATA_PATH = os.path.join(DATA_DIR, "rss_data_v2.json")

class RSSManager:
    """Gestor centralizado robusto de RSS."""
    
    # ============================================================
    # PLANTILLAS PREDEFINIDAS (Actualizadas)
    # ============================================================
    
    # Tu plantilla personalizada por defecto
    DEFAULT_BITBREAD_TEMPLATE = (
        "#only_first_media#\n"
        "<b><a href='#media_url#'>#media_title#</a></b>\n\n"
        "#media_description#\n\n"
        "#no_view_original_post_link#\n"
        "•••\n"
        "<i><b><a href='https://t.me/boost/bbalertchannel'>✨ BitBread</a></b> • <a href='#media_url#'>#source_title#</a></i>"
    )
    
    DEFAULT_TELEGRAM_TEMPLATE = (
        "<b>#media_title#</b>\n\n"
        "#media_description#\n\n"
        "<a href='#media_url#'>🔗 Ver noticia completa</a>"  # ✅ Enlace explícito
    )


    def get_feed(self, user_id: int, feed_id: str) -> Optional[Dict]:
        """
        Obtiene un feed completo por ID.
        Alias de _find_feed para mantener compatibilidad.
        """
        data = self.load_data()
        return self._find_feed(data, user_id, feed_id)
    
    def get_feed_by_id(self, user_id: int, feed_id: str) -> Dict:
        """
        Obtiene un feed por su ID.
        Compatibilidad con código existente.
        """
        data = self.load_data()
        user_feeds = data.get(str(user_id), {}).get('feeds', [])
        for feed in user_feeds:
            if feed['id'] == feed_id:
                return feed
        return None

#    def get_feed_by_id(self, user_id: int, feed_id: str) -> Optional[Dict]:
#        """Obtiene un feed por ID."""
#        data = self.load_data()
#        return self._find_feed(data, user_id, feed_id)

    def __init__(self):
        self.parser = FeedParserV4()  # ✅ USAR V4
        self.filter = ContentFilter()
    
    @staticmethod
    def load_data() -> Dict:
        """Carga datos con fallback."""
        if not os.path.exists(RSS_DATA_PATH):
            return {}
        try:
            with open(RSS_DATA_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            add_log_line(f"❌ Error loading RSS data: {e}")
            return {}
    
    @staticmethod
    def save_data(data: Dict):
        """Guarda datos con backup."""
        try:
            # Crear backup
            if os.path.exists(RSS_DATA_PATH):
                backup_path = RSS_DATA_PATH + ".backup"
                with open(RSS_DATA_PATH, 'r') as src:
                    with open(backup_path, 'w') as dst:
                        dst.write(src.read())
            
            # Guardar nuevos datos
            with open(RSS_DATA_PATH, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            add_log_line(f"❌ Error saving RSS data: {e}")
    
    @staticmethod
    def get_user_data(user_id: int) -> Dict:
        """Obtiene datos del usuario con estructura normalizada."""
        data = RSSManager.load_data()
        uid = str(user_id)
        
        if uid not in data:
            data[uid] = {
                "channels": [],
                "feeds": [],
                "subscriptions": [],
                "extra_slots": {"channels": 0, "feeds": 0},
                "settings": {
                    "default_format": "bitbread",
                    "timezone": "UTC",
                    "language": "es"
                }
            }
            RSSManager.save_data(data)
        
        return data[uid]
    
    async def add_feed_advanced(
        self,
        user_id: int,
        url: str,
        channel_id: int,
        format_type: str = "bitbread"
    ) -> Tuple[bool, Dict]:
        """Añade feed con parser v4."""
        try:
            parse_result = await self.parser.parse(url)
            
            if not parse_result.get('success'):
                return False, {
                    'error': parse_result.get('error', 'Error desconocido'),
                    'type': parse_result.get('type', 'unknown')
                }
            
            entries = parse_result.get('entries', [])
            if not entries:
                return False, {'error': 'Feed vacío'}
            
            # ✅ USAR TÍTULO CORRECTO
            source_title = parse_result.get('source_title', 'Feed')
            
            # ✅ HASH EN VEZ DE ID
            last_hash = entries[0].get('hash', entries[0]['id'])
            
            feed_id = str(uuid.uuid4())[:12]
            
            new_feed = {
                "id": feed_id,
                "url": url,
                "detected_type": parse_result.get('type', 'generic'),
                "source_title": source_title,  # ✅ CORRECTO
                "source_link": parse_result.get('link', ''),
                "description": parse_result.get('description', '')[:200],
                "target_channel_id": channel_id,
                
                "format": format_type,
                "template": (
                    self.DEFAULT_TELEGRAM_TEMPLATE if format_type == 'telegram'
                    else self.DEFAULT_BITBREAD_TEMPLATE
                ),
                
                "frequency_minutes": 60,
                "last_checked": 0,
                "last_entry_hash": last_hash,  # ✅ HASH EN VEZ DE ID
                
                "active": True,
                "created_at": datetime.now().isoformat(),
                "filters": [],
                
                "stats": {
                    "total_sent": 0,
                    "total_blocked": 0,
                    "last_error": None,
                }
            }
            
            data = RSSManager.load_data()
            if str(user_id) not in data:
                data[str(user_id)] = RSSManager.get_user_data(user_id)
            
            data[str(user_id)]['feeds'].append(new_feed)
            RSSManager.save_data(data)
            
            add_log_line(f"✅ Feed '{source_title}' añadido correctamente")
            return True, new_feed
            
        except Exception as e:
            add_log_line(f"❌ Error en add_feed_advanced: {e}")
            import traceback
            add_log_line(f"Traceback: {traceback.format_exc()[:500]}")
            return False, {'error': str(e)[:100]}
    
    def add_filter_to_feed(
        self,
        user_id: int,
        feed_id: str,
        pattern: str,
        mode: str = "block",
        replacement: str = ""
    ) -> Tuple[bool, str]:
        """Añade filtro a feed."""
        try:
            data = RSSManager.load_data()
            feed = self._find_feed(data, user_id, feed_id)
            
            if not feed:
                return False, "Feed no encontrado"
            
            # Validar
            is_valid, msg = ContentFilter.validate_filter_config({
                'pattern': pattern,
                'mode': mode,
                'replacement': replacement
            })
            
            if not is_valid:
                return False, msg
            
            # Añadir
            feed['filters'].append({
                'pattern': pattern,
                'mode': mode,
                'replacement': replacement,
            })
            
            RSSManager.save_data(data)
            add_log_line(f"✅ Filtro '{pattern}' ({mode}) añadido a feed {feed_id}")
            return True, f"Filtro añadido: {pattern}"
            
        except Exception as e:
            add_log_line(f"❌ Error añadiendo filtro: {e}")
            return False, str(e)
    
    def apply_content_filters(
        self,
        content: str,
        filters: List[Dict]
    ) -> Tuple[bool, str]:
        """
        Aplica todos los filtros a un contenido.
        
        Retorna: (debe_bloquearse, contenido_filtrado)
        """
        return self.filter.apply_filters(content, filters)
    
    @staticmethod
    def _find_feed(data: Dict, user_id: int, feed_id: str) -> Optional[Dict]:
        """Busca feed del usuario."""
        user_data = data.get(str(user_id), {})
        for feed in user_data.get('feeds', []):
            if feed['id'] == feed_id:
                return feed
        return None
    
    @staticmethod
    def check_limits(user_id: int, type_check: str) -> Tuple[bool, int, int]:
        """Verifica límites de usuario."""
        data = RSSManager.get_user_data(user_id)
        
        base_limits = {
            "channels": 5,
            "feeds": 20,
        }
        
        current = len(data.get(type_check, []))
        extra = data.get("extra_slots", {}).get(type_check, 0)
        limit = base_limits.get(type_check, 0) + extra
        
        return current < limit, current, limit
    
    def get_feed_template(self, user_id: int, feed_id: str) -> Optional[str]:
        """
        Obtiene la plantilla de un feed.
        Si es None (feeds antiguos), devuelve la plantilla por defecto.
        """
        data = RSSManager.load_data()
        feed = self._find_feed(data, user_id, feed_id)
        
        if not feed:
            return None
        
        template = feed.get('template')
        
        # ✅ CORRECCIÓN: Si el feed no tiene plantilla (legacy), asignar una por defecto
        if not template:
            format_type = feed.get('format', 'bitbread')
            template = (
                self.DEFAULT_TELEGRAM_TEMPLATE if format_type == 'telegram'
                else self.DEFAULT_BITBREAD_TEMPLATE
            )
            
            # Actualizar el feed con la plantilla por defecto
            feed['template'] = template
            RSSManager.save_data(data)
            
            add_log_line(f"🔧 Plantilla por defecto asignada a feed {feed_id} ({format_type})")
        
        return template
    
    def update_feed_template(
        self, 
        user_id: int, 
        feed_id: str, 
        template: str
    ) -> Tuple[bool, str]:
        """
        Actualiza la plantilla de un feed con validación.
        """
        try:
            data = RSSManager.load_data()
            feed = self._find_feed(data, user_id, feed_id)
            
            if not feed:
                return False, "Feed no encontrado"
            
            # Validación básica
            if len(template) < 10:
                return False, "La plantilla es demasiado corta (mínimo 10 caracteres)"
            
            if len(template) > 4000:
                return False, "La plantilla es demasiado larga (máximo 4000 caracteres)"
            
            # Validar que contenga al menos el título o descripción
            if '#media_title#' not in template and '#media_description#' not in template:
                return False, "La plantilla debe incluir al menos #media_title# o #media_description#"
            
            # Actualizar
            feed['template'] = template
            RSSManager.save_data(data)
            
            add_log_line(f"✅ Plantilla actualizada para feed {feed_id}")
            return True, "Plantilla guardada correctamente"
            
        except Exception as e:
            add_log_line(f"❌ Error actualizando plantilla: {e}")
            return False, f"Error: {str(e)[:50]}"
    
    def switch_feed_format(
        self, 
        user_id: int, 
        feed_id: str
    ) -> Tuple[bool, str]:
        """
        Alterna entre formatos 'bitbread' y 'telegram' y actualiza la plantilla.
        """
        try:
            data = RSSManager.load_data()
            feed = self._find_feed(data, user_id, feed_id)
            
            if not feed:
                return False, "Feed no encontrado"
            
            # Alternar formato
            current_format = feed.get('format', 'bitbread')
            new_format = 'telegram' if current_format == 'bitbread' else 'bitbread'
            
            # Asignar nueva plantilla por defecto
            new_template = (
                self.DEFAULT_TELEGRAM_TEMPLATE if new_format == 'telegram'
                else self.DEFAULT_BITBREAD_TEMPLATE
            )
            
            feed['format'] = new_format
            feed['template'] = new_template
            
            RSSManager.save_data(data)
            
            add_log_line(f"✅ Formato cambiado a '{new_format}' para feed {feed_id}")
            return True, f"Formato cambiado a: {new_format}"
            
        except Exception as e:
            add_log_line(f"❌ Error cambiando formato: {e}")
            return False, f"Error: {str(e)[:50]}"

def add_purchased_slot(user_id: int, slot_type: str, quantity: int) -> bool:
    """Añade slots comprados al usuario (para compatibilidad con pay.py)."""
    try:
        data = RSSManager.load_data()
        uid = str(user_id)
        
        if uid not in data:
            data[uid] = RSSManager.get_user_data(user_id)
        
        current = data[uid]['extra_slots'].get(slot_type, 0)
        data[uid]['extra_slots'][slot_type] = current + quantity
        
        RSSManager.save_data(data)
        add_log_line(f"✅ Slots añadidos: {quantity} {slot_type} para usuario {user_id}")
        return True
    except Exception as e:
        add_log_line(f"❌ Error añadiendo slots: {e}")
        return False
