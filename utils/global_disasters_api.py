# utils/global_disasters_api.py - CLIENTE PARA ALERTAS GLOBALES

import requests
import feedparser
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from utils.file_manager import add_log_line

class GlobalDisasterMonitor:
    """
    Monitor de desastres naturales globales usando GDACS y USGS.
    
    Características:
    - Consulta RSS feeds de GDACS cada 10 minutos
    - Consulta API USGS de terremotos cada 5 minutos
    - Caché inteligente para evitar duplicados
    - Filtrado por severidad e impacto
    """
    
    def __init__(self):
        self.gdacs_url = "https://www.gdacs.org/xml/rss.xml"
        self.usgs_url = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/significant_week.geojson"
        
        # Caché de eventos ya procesados (event_id: timestamp)
        self.processed_events = {}
        self.cache_ttl = 86400  # 24 horas
        
        # Última actualización
        self.last_gdacs_update = 0
        self.last_usgs_update = 0
        
        # Cooldowns (segundos)
        self.gdacs_cooldown = 600  # 10 minutos
        self.usgs_cooldown = 300   # 5 minutos
    
    def _clean_old_cache(self):
        """Elimina eventos procesados hace más de 24h."""
        now = time.time()
        to_remove = [
            event_id for event_id, timestamp in self.processed_events.items()
            if (now - timestamp) > self.cache_ttl
        ]
        
        for event_id in to_remove:
            del self.processed_events[event_id]
    
    def _is_event_new(self, event_id: str) -> bool:
        """Verifica si el evento no ha sido procesado."""
        return event_id not in self.processed_events
    
    def _mark_event_processed(self, event_id: str):
        """Marca evento como procesado."""
        self.processed_events[event_id] = time.time()
    
    def get_gdacs_alerts(self) -> List[Dict]:
        """
        Obtiene alertas de GDACS (terremotos, tsunamis, ciclones, volcanes, inundaciones).
        
        Returns:
            Lista de eventos con formato estandarizado
        """
        now = time.time()
        
        # Verificar cooldown
        if (now - self.last_gdacs_update) < self.gdacs_cooldown:
            return []
        
        try:
            add_log_line("🌍 Consultando GDACS...")
            
            feed = feedparser.parse(self.gdacs_url)
            
            if not feed.entries:
                add_log_line("⚠️ GDACS feed vacío")
                return []
            
            self.last_gdacs_update = now
            new_alerts = []
            
            for entry in feed.entries:
                try:
                    # Extraer datos del evento
                    event_id = entry.get('id', entry.get('link', ''))
                    
                    # Verificar si ya fue procesado
                    if not self._is_event_new(event_id):
                        continue
                    
                    title = entry.get('title', '')
                    description = entry.get('summary', '')
                    link = entry.get('link', '')
                    pub_date = entry.get('published', '')
                    
                    # Extraer tipo de desastre y severidad del título
                    # Formato típico: "Green earthquake alert (Magnitude 6.2M) in Japan"
                    severity = "Unknown"
                    disaster_type = "Unknown"
                    
                    title_lower = title.lower()
                    
                    if "green" in title_lower:
                        severity = "Green"
                    elif "orange" in title_lower:
                        severity = "Orange"
                    elif "red" in title_lower:
                        severity = "Red"
                    
                    if "earthquake" in title_lower:
                        disaster_type = "Earthquake"
                    elif "tsunami" in title_lower:
                        disaster_type = "Tsunami"
                    elif "cyclone" in title_lower or "hurricane" in title_lower or "typhoon" in title_lower:
                        disaster_type = "Cyclone"
                    elif "flood" in title_lower:
                        disaster_type = "Flood"
                    elif "volcano" in title_lower:
                        disaster_type = "Volcano"
                    elif "drought" in title_lower:
                        disaster_type = "Drought"
                    
                    # Filtrar solo eventos de alta severidad
                    if severity not in ["Orange", "Red"]:
                        continue
                    
                    # Extraer ubicación (generalmente está al final del título)
                    location = "Unknown location"
                    if " in " in title:
                        location = title.split(" in ")[-1].strip()
                    
                    event = {
                        'id': event_id,
                        'type': disaster_type,
                        'severity': severity,
                        'title': title,
                        'location': location,
                        'description': description,
                        'link': link,
                        'published': pub_date,
                        'source': 'GDACS'
                    }
                    
                    new_alerts.append(event)
                    self._mark_event_processed(event_id)
                    
                    add_log_line(f"🚨 Nuevo evento GDACS: {disaster_type} ({severity}) en {location}")
                
                except Exception as e:
                    add_log_line(f"⚠️ Error procesando entrada GDACS: {e}")
                    continue
            
            return new_alerts
        
        except Exception as e:
            add_log_line(f"❌ Error consultando GDACS: {e}")
            return []
    
    def get_usgs_earthquakes(self) -> List[Dict]:
        """
        Obtiene terremotos significativos de USGS (magnitud ≥ 6.0).
        
        Returns:
            Lista de terremotos con formato estandarizado
        """
        now = time.time()
        
        # Verificar cooldown
        if (now - self.last_usgs_update) < self.usgs_cooldown:
            return []
        
        try:
            add_log_line("🌍 Consultando USGS...")
            
            response = requests.get(self.usgs_url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            self.last_usgs_update = now
            new_alerts = []
            
            for feature in data.get('features', []):
                try:
                    props = feature['properties']
                    geom = feature['geometry']
                    
                    event_id = feature['id']
                    
                    # Verificar si ya fue procesado
                    if not self._is_event_new(event_id):
                        continue
                    
                    magnitude = props.get('mag', 0)
                    
                    # Solo terremotos significativos (≥ 6.0)
                    if magnitude < 6.0:
                        continue
                    
                    location = props.get('place', 'Unknown location')
                    depth = geom['coordinates'][2]  # km
                    timestamp = props.get('time')  # milliseconds
                    
                    # Determinar severidad según magnitud
                    if magnitude >= 7.0:
                        severity = "Red"  # Devastador
                    elif magnitude >= 6.5:
                        severity = "Orange"  # Muy fuerte
                    else:
                        severity = "Green"  # Fuerte
                    
                    # Solo alertar eventos Orange o Red
                    if severity not in ["Orange", "Red"]:
                        continue
                    
                    # Convertir timestamp
                    dt = datetime.fromtimestamp(timestamp / 1000)
                    
                    event = {
                        'id': event_id,
                        'type': 'Earthquake',
                        'severity': severity,
                        'title': f"Magnitude {magnitude:.1f} earthquake - {location}",
                        'location': location,
                        'magnitude': magnitude,
                        'depth': depth,
                        'description': f"Magnitude {magnitude:.1f} at depth {depth:.1f}km",
                        'link': props.get('url', ''),
                        'published': dt.strftime('%Y-%m-%d %H:%M:%S UTC'),
                        'source': 'USGS'
                    }
                    
                    new_alerts.append(event)
                    self._mark_event_processed(event_id)
                    
                    add_log_line(f"🚨 Nuevo terremoto USGS: M{magnitude:.1f} en {location}")
                
                except Exception as e:
                    add_log_line(f"⚠️ Error procesando terremoto USGS: {e}")
                    continue
            
            return new_alerts
        
        except Exception as e:
            add_log_line(f"❌ Error consultando USGS: {e}")
            return []
    
    def get_all_alerts(self) -> List[Dict]:
        """
        Obtiene todas las alertas disponibles (GDACS + USGS).
        
        Returns:
            Lista combinada de eventos globales
        """
        self._clean_old_cache()
        
        gdacs_alerts = self.get_gdacs_alerts()
        usgs_alerts = self.get_usgs_earthquakes()
        
        all_alerts = gdacs_alerts + usgs_alerts
        
        if all_alerts:
            add_log_line(f"✅ {len(all_alerts)} nuevas alertas globales detectadas")
        
        return all_alerts

# Instancia global
disaster_monitor = GlobalDisasterMonitor()

def get_global_disaster_alerts():
    """Función alias para compatibilidad."""
    return disaster_monitor.get_all_alerts()
