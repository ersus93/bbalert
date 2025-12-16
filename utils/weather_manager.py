# utils/weather_manager.py - VERSIÓN v3 CON ANTI-SPAM TOTAL

import json
import os
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
from core.config import DATA_DIR
from utils.file_manager import add_log_line

# Rutas de archivos
WEATHER_SUBS_PATH = os.path.join(DATA_DIR, "weather_subs.json")
WEATHER_ALERTS_HISTORY_PATH = os.path.join(DATA_DIR, "weather_alerts_history.json")

class WeatherAlertManager:
    def __init__(self):
        self._subs_cache: Optional[Dict] = None
        self._alerts_history_cache: Optional[Dict] = None
        self.HISTORY_RETENTION_DAYS = 7  # Aumentado a 7 días para mejor tracking
        
    # ========================================
    # NUEVO: GENERADOR DE ID ÚNICO DE EVENTO
    # ========================================
    
    @staticmethod
    def generate_event_id(
        user_id: int,
        alert_type: str,
        event_time: datetime,
        weather_id: int = None,
        lat: float = None,
        lon: float = None
    ) -> str:
        """
        Genera ID único e inmutable para cada evento climático.
        
        Formato: hash(user_id + tipo + fecha_hora + weather_id + coordenadas)
        """
        # Redondear a la hora más cercana para agrupar eventos similares
        rounded_time = event_time.replace(minute=0, second=0, microsecond=0)
        
        components = [
            str(user_id),
            alert_type,
            rounded_time.strftime('%Y%m%d%H'),
        ]
        
        if weather_id:
            components.append(str(weather_id))
        
        if lat and lon:
            # Coordenadas redondeadas a 2 decimales (precisión ~1km)
            components.append(f"{lat:.2f},{lon:.2f}")
        
        # Generar hash SHA256 corto (primeros 16 caracteres)
        signature = "_".join(components)
        return hashlib.sha256(signature.encode()).hexdigest()[:16]
    
    # ========================================
    # GESTIÓN DE SUSCRIPCIONES (Sin cambios)
    # ========================================
    
    def load_subscriptions(self, force_reload: bool = False) -> Dict:
        """Carga suscripciones desde JSON."""
        if not force_reload and self._subs_cache:
            return self._subs_cache
        
        if not os.path.exists(WEATHER_SUBS_PATH):
            self._subs_cache = {}
            return {}
        
        try:
            with open(WEATHER_SUBS_PATH, 'r', encoding='utf-8') as f:
                self._subs_cache = json.load(f)
                return self._subs_cache
        except Exception as e:
            add_log_line(f"❌ Error cargando suscripciones: {e}")
            return {}
    
    def save_subscriptions(self, subs: Dict):
        """Guarda suscripciones en JSON."""
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            with open(WEATHER_SUBS_PATH, 'w', encoding='utf-8') as f:
                json.dump(subs, f, indent=4, ensure_ascii=False)
            self._subs_cache = subs
        except Exception as e:
            add_log_line(f"❌ Error guardando suscripciones: {e}")
    
    def subscribe_user(
        self, 
        user_id: int, 
        city: str, 
        country: str, 
        timezone: str,
        lat: float,
        lon: float,
        alert_time: str = "07:00"
    ) -> bool:
        """Suscribe usuario CON coordenadas obligatorias."""
        try:
            if not city or not isinstance(city, str):
                add_log_line(f"⚠️ Ciudad inválida para {user_id}")
                return False

            if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
                add_log_line(f"⚠️ Coordenadas inválidas: {lat}, {lon}")
                return False
        
            subs = self.load_subscriptions(force_reload=True)

            subs[str(user_id)] = {
                "city": city,
                "country": country,
                "timezone": timezone,
                "lat": float(lat),
                "lon": float(lon),
                "alert_time": alert_time,
                "subscribed_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "alerts_enabled": True,
                "alert_types": {
                    "rain": True,
                    "uv_high": True,
                    "storm": True,
                    "snow": True,
                    "fog": True,
                    "temp_high": True,
                    "temp_low": True,
                    "global_disasters": True
                }
            }
        
            self.save_subscriptions(subs)
            add_log_line(f"✅ Usuario {user_id} suscrito: {city} ({lat}, {lon})")
            return True

        except Exception as e:
            add_log_line(f"❌ Error en subscribe_user: {e}")
            import traceback
            add_log_line(traceback.format_exc())
            return False
    
    def get_user_subscription(self, user_id: int) -> Optional[Dict]:
        """Obtiene suscripción de usuario."""
        subs = self.load_subscriptions()
        return subs.get(str(user_id))
    
    def get_all_subscribed_users(self) -> list:
        """Obtiene lista de usuarios activos."""
        subs = self.load_subscriptions()
        return [
            int(uid) for uid, data in subs.items() 
            if data.get('alerts_enabled', False)
        ]
    
    def unsubscribe_user(self, user_id: int) -> bool:
        """Elimina suscripción de usuario."""
        subs = self.load_subscriptions(force_reload=True)
        if str(user_id) in subs:
            del subs[str(user_id)]
            self.save_subscriptions(subs)
            return True
        return False
    
    def toggle_alert_type(self, user_id: int, alert_type: str) -> bool:
        """Activa/desactiva tipo de alerta."""
        subs = self.load_subscriptions(force_reload=True)
        if str(user_id) in subs:
            current = subs[str(user_id)]['alert_types'].get(alert_type, True)
            subs[str(user_id)]['alert_types'][alert_type] = not current
            self.save_subscriptions(subs)
            return True
        return False
    
    # ========================================
    # SISTEMA DE HISTORIAL v3 (MEJORADO)
    # ========================================
    
    def _load_history(self) -> Dict:
        """Carga historial completo desde JSON."""
        if self._alerts_history_cache is not None:
            return self._alerts_history_cache
        
        if not os.path.exists(WEATHER_ALERTS_HISTORY_PATH):
            self._alerts_history_cache = {
                "local": {},
                "global": {},
                "events": {}  # NUEVO: Índice de eventos por ID
            }
            return self._alerts_history_cache
        
        try:
            with open(WEATHER_ALERTS_HISTORY_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
                # Migración de versiones antiguas
                if "events" not in data:
                    data["events"] = {}
                
                if "local" not in data:
                    data["local"] = {}
                
                if "global" not in data:
                    data["global"] = {}
                
                self._alerts_history_cache = data
                return data
        
        except Exception as e:
            add_log_line(f"⚠️ Error cargando historial: {e}")
            self._alerts_history_cache = {
                "local": {},
                "global": {},
                "events": {}
            }
            return self._alerts_history_cache
    
    def _save_history(self, history: Dict):
        """Guarda historial con limpieza automática."""
        try:
            cutoff = (datetime.now() - timedelta(days=self.HISTORY_RETENTION_DAYS)).isoformat()
            
            # Limpieza de alertas locales
            clean_local = {}
            if "local" in history and isinstance(history["local"], dict):
                for uid, alerts in history["local"].items():
                    if not isinstance(alerts, list):
                        continue
                    
                    valid_alerts = [
                        a for a in alerts
                        if isinstance(a, dict) 
                        and 'timestamp' in a 
                        and a['timestamp'] > cutoff
                    ]
                    
                    if valid_alerts:
                        clean_local[uid] = valid_alerts
            
            # Limpieza de eventos globales
            clean_global = {
                eid: ts for eid, ts in history.get("global", {}).items()
                if ts > cutoff
            }
            
            # Limpieza de índice de eventos
            clean_events = {
                eid: data for eid, data in history.get("events", {}).items()
                if data.get('timestamp', '') > cutoff
            }
            
            clean_history = {
                "local": clean_local,
                "global": clean_global,
                "events": clean_events
            }
            
            os.makedirs(DATA_DIR, exist_ok=True)
            with open(WEATHER_ALERTS_HISTORY_PATH, 'w', encoding='utf-8') as f:
                json.dump(clean_history, f, indent=4, ensure_ascii=False)
            
            self._alerts_history_cache = clean_history
            
        except Exception as e:
            add_log_line(f"❌ Error guardando historial: {e}")
    
    # ========================================
    # NUEVO: VERIFICACIÓN AVANZADA DE ALERTAS
    # ========================================
    
    def should_send_weather_alert(
        self,
        user_id: int,
        alert_type: str,
        event_time: datetime,
        weather_id: int,
        lat: float,
        lon: float,
        stage: str,  # 'early' o 'imminent'
        cooldown_hours: float
    ) -> Tuple[bool, str]:
        """
        Sistema de decisión inteligente para alertas climáticas.
        
        Returns:
            (puede_enviar: bool, razón: str)
        """
        # 1. Generar ID único del evento
        event_id = self.generate_event_id(
            user_id, alert_type, event_time, weather_id, lat, lon
        )
        
        history = self._load_history()
        events = history.get("events", {})
        
        # 2. Verificar si este evento exacto ya fue enviado
        if event_id in events:
            event_data = events[event_id]
            
            # Verificar si ya se envió esta etapa (early/imminent)
            if stage in event_data.get('stages_sent', []):
                return False, f"Etapa '{stage}' ya enviada para este evento"
            
            # Verificar cooldown entre etapas
            last_sent_str = event_data.get('last_sent')
            if last_sent_str:
                last_sent = datetime.fromisoformat(last_sent_str)
                hours_since = (datetime.now() - last_sent).total_seconds() / 3600
                
                if hours_since < cooldown_hours:
                    return False, f"Cooldown activo ({hours_since:.1f}h < {cooldown_hours}h)"
        
        # 3. Buscar eventos similares recientes (mismo tipo, fecha similar)
        now = datetime.now()
        
        for eid, edata in events.items():
            if edata.get('user_id') != user_id:
                continue
            
            if edata.get('alert_type') != alert_type:
                continue
            
            # Verificar si es un evento muy cercano temporalmente
            event_ts_str = edata.get('event_time')
            if event_ts_str:
                try:
                    event_ts = datetime.fromisoformat(event_ts_str)
                    time_diff_hours = abs((event_time - event_ts).total_seconds() / 3600)
                    
                    # Si hay otro evento del mismo tipo a menos de 2h, podría ser duplicado
                    if time_diff_hours < 2:
                        last_sent_str = edata.get('last_sent')
                        if last_sent_str:
                            last_sent = datetime.fromisoformat(last_sent_str)
                            hours_since_last = (now - last_sent).total_seconds() / 3600
                            
                            if hours_since_last < cooldown_hours:
                                return False, f"Evento similar reciente bloqueado (cooldown)"
                
                except ValueError:
                    continue
        
        # ✅ Todas las verificaciones pasadas
        return True, "OK"
    
    def mark_weather_alert_sent(
        self,
        user_id: int,
        alert_type: str,
        event_time: datetime,
        weather_id: int,
        lat: float,
        lon: float,
        stage: str,
        description: str
    ):
        """Registra una alerta enviada en el índice de eventos."""
        event_id = self.generate_event_id(
            user_id, alert_type, event_time, weather_id, lat, lon
        )
        
        history = self._load_history()
        
        if "events" not in history:
            history["events"] = {}
        
        now_iso = datetime.now().isoformat()
        
        if event_id in history["events"]:
            # Actualizar evento existente
            history["events"][event_id]['stages_sent'].append(stage)
            history["events"][event_id]['last_sent'] = now_iso
        else:
            # Crear nuevo registro
            history["events"][event_id] = {
                "user_id": user_id,
                "alert_type": alert_type,
                "event_time": event_time.isoformat(),
                "weather_id": weather_id,
                "description": description,
                "stages_sent": [stage],
                "first_sent": now_iso,
                "last_sent": now_iso,
                "timestamp": now_iso
            }
        
        # También registrar en historial local (compatibilidad)
        user_key = str(user_id)
        if "local" not in history:
            history["local"] = {}
        
        if user_key not in history["local"]:
            history["local"][user_key] = []
        
        history["local"][user_key].append({
            "type": alert_type,
            "stage": stage,
            "desc": description,
            "event_id": event_id,
            "timestamp": now_iso
        })
        
        self._save_history(history)
        
        add_log_line(
            f"📝 Alerta registrada: {alert_type}/{stage} "
            f"para user {user_id} (ID: {event_id[:8]}...)"
        )
    
    # ========================================
    # ALERTAS GLOBALES (Sin cambios necesarios)
    # ========================================
    
    def is_global_event_sent(self, event_id: str) -> bool:
        """Verifica si evento global ya fue procesado."""
        history = self._load_history()
        return event_id in history.get("global", {})
    
    def mark_global_event_sent(self, event_id: str):
        """Marca evento global como enviado."""
        history = self._load_history()
        
        if "global" not in history:
            history["global"] = {}
        
        history["global"][event_id] = datetime.now().isoformat()
        self._save_history(history)
        
        add_log_line(f"📝 Evento global {event_id} marcado")
    
    # ========================================
    # RESUMEN DIARIO
    # ========================================
    
    def get_last_daily_summary(self, user_id: int) -> Optional[datetime]:
        """Obtiene timestamp del último resumen diario."""
        history = self._load_history()
        user_key = str(user_id)
        
        if user_key in history.get("local", {}):
            for alert in reversed(history["local"][user_key]):
                if alert.get('type') == 'daily_summary':
                    ts_str = alert.get('timestamp')
                    if ts_str:
                        try:
                            return datetime.fromisoformat(ts_str)
                        except ValueError:
                            continue
        
        return None
    
    def mark_daily_summary_sent(self, user_id: int):
        """Marca resumen diario como enviado."""
        history = self._load_history()
        user_key = str(user_id)
        
        if "local" not in history:
            history["local"] = {}
        
        if user_key not in history["local"]:
            history["local"][user_key] = []
        
        history["local"][user_key].append({
            "type": "daily_summary",
            "stage": "sent",
            "desc": "Resumen diario enviado",
            "timestamp": datetime.now().isoformat()
        })
        
        self._save_history(history)

# Instancia Global
weather_manager = WeatherAlertManager()

# === FUNCIONES WRAPPER PARA COMPATIBILIDAD ===

def load_weather_subscriptions():
    return weather_manager.load_subscriptions()

def save_weather_subscriptions(subs):
    weather_manager.save_subscriptions(subs)

def subscribe_user(user_id, city, country, timezone, lat, lon, alert_time="07:00"):
    return weather_manager.subscribe_user(user_id, city, country, timezone, lat, lon, alert_time)

def get_user_subscription(user_id):
    return weather_manager.get_user_subscription(user_id)

def get_all_subscribed_users():
    return weather_manager.get_all_subscribed_users()

def unsubscribe_user(user_id):
    return weather_manager.unsubscribe_user(user_id)

def toggle_alert_type(user_id, alert_type):
    return weather_manager.toggle_alert_type(user_id, alert_type)

def should_send_alert_advanced(user_id, alert_type, event_time, cooldown_hours, **kwargs):
    """NUEVA FUNCIÓN: Wrapper mejorado."""
    weather_id = kwargs.get('weather_id', 0)
    
    # Obtener coordenadas del usuario
    sub = weather_manager.get_user_subscription(user_id)
    if not sub:
        return False, "Usuario no suscrito"
    
    lat = sub.get('lat', 0)
    lon = sub.get('lon', 0)
    
    # Extraer stage del nombre del alert_type
    # Ej: "rain_early" → tipo="rain", stage="early"
    if '_' in alert_type:
        base_type, stage = alert_type.rsplit('_', 1)
    else:
        base_type = alert_type
        stage = "general"
    
    return weather_manager.should_send_weather_alert(
        user_id=user_id,
        alert_type=base_type,
        event_time=event_time,
        weather_id=weather_id,
        lat=lat,
        lon=lon,
        stage=stage,
        cooldown_hours=cooldown_hours
    )

def mark_alert_sent_advanced(user_id, alert_type, event_time, **kwargs):
    """NUEVA FUNCIÓN: Wrapper mejorado."""
    weather_id = kwargs.get('weather_id', 0)
    desc = kwargs.get('event_desc', 'Alerta automática')
    
    # Obtener coordenadas
    sub = weather_manager.get_user_subscription(user_id)
    if not sub:
        return
    
    lat = sub.get('lat', 0)
    lon = sub.get('lon', 0)
    
    # Extraer stage
    if '_' in alert_type:
        base_type, stage = alert_type.rsplit('_', 1)
    else:
        base_type = alert_type
        stage = "general"
    
    weather_manager.mark_weather_alert_sent(
        user_id=user_id,
        alert_type=base_type,
        event_time=event_time,
        weather_id=weather_id,
        lat=lat,
        lon=lon,
        stage=stage,
        description=desc
    )
