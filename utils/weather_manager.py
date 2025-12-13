# utils/weather_manager.py - VERSIÓN UNIFICADA Y CORREGIDA

import json
import os
from datetime import datetime
from typing import Optional, Dict
from core.config import DATA_DIR
from utils.file_manager import add_log_line

# Rutas
WEATHER_SUBS_PATH = os.path.join(DATA_DIR, "weather_subs.json")
WEATHER_ALERTS_LOG_PATH = os.path.join(DATA_DIR, "weather_alerts_log.json")

class WeatherAlertManager:
    def __init__(self):
        self._subs_cache: Optional[Dict] = None
        self._alerts_log_cache: Optional[Dict] = None
        self._last_cache_update = 0
        self.CACHE_TTL = 60
    
    def load_subscriptions(self, force_reload: bool = False) -> Dict:
        now = datetime.now().timestamp()
        
        if not force_reload and self._subs_cache and (now - self._last_cache_update < self.CACHE_TTL):
            return self._subs_cache
        
        if not os.path.exists(WEATHER_SUBS_PATH):
            self._subs_cache = {}
            self._last_cache_update = now
            return {}
        
        try:
            with open(WEATHER_SUBS_PATH, 'r', encoding='utf-8') as f:
                self._subs_cache = json.load(f)
                self._last_cache_update = now
                return self._subs_cache
        except Exception as e:
            add_log_line(f"⚠️ Error cargando suscripciones: {e}")
            self._subs_cache = {}
            return {}
    
    def save_subscriptions(self, subs: Dict):
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            
            with open(WEATHER_SUBS_PATH, 'w', encoding='utf-8') as f:
                json.dump(subs, f, indent=4, ensure_ascii=False)
            
            self._subs_cache = subs
            self._last_cache_update = datetime.now().timestamp()
            
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
        """✅ Suscribe usuario CON coordenadas obligatorias."""
        try:
            # Validaciones
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
                "lat": float(lat),  # ✅ Guardar coordenadas
                "lon": float(lon),  # ✅ Guardar coordenadas
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
                    "temp_low": True
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
        subs = self.load_subscriptions()
        return subs.get(str(user_id))
    
    def get_all_subscribed_users(self) -> list:
        subs = self.load_subscriptions()
        return [
            int(uid) for uid, data in subs.items() 
            if data.get('alerts_enabled', False)
        ]
    
    def unsubscribe_user(self, user_id: int) -> bool:
        subs = self.load_subscriptions(force_reload=True)
        if str(user_id) in subs:
            del subs[str(user_id)]
            self.save_subscriptions(subs)
            return True
        return False
    
    def toggle_alert_type(self, user_id: int, alert_type: str) -> bool:
        subs = self.load_subscriptions(force_reload=True)
        if str(user_id) in subs:
            current = subs[str(user_id)]['alert_types'].get(alert_type, True)
            subs[str(user_id)]['alert_types'][alert_type] = not current
            self.save_subscriptions(subs)
            return True
        return False
    
    def _load_alerts_log(self) -> Dict:
        if self._alerts_log_cache:
            return self._alerts_log_cache
        
        if not os.path.exists(WEATHER_ALERTS_LOG_PATH):
            self._alerts_log_cache = {}
            return {}
        
        try:
            with open(WEATHER_ALERTS_LOG_PATH, 'r') as f:
                self._alerts_log_cache = json.load(f)
                return self._alerts_log_cache
        except:
            self._alerts_log_cache = {}
            return {}
    
    def _save_alerts_log(self, log: Dict):
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            with open(WEATHER_ALERTS_LOG_PATH, 'w') as f:
                json.dump(log, f, indent=4)
            self._alerts_log_cache = log
        except Exception as e:
            add_log_line(f"❌ Error guardando log: {e}")
    
    def should_send_alert(self, user_id: int, alert_type: str, cooldown_hours: int = 3) -> bool:
        try:
            log = self._load_alerts_log()
            user_key = str(user_id)
            
            if user_key not in log or alert_type not in log[user_key]:
                return True
            
            last_time = datetime.fromisoformat(log[user_key][alert_type])
            hours_passed = (datetime.now() - last_time).total_seconds() / 3600
            
            return hours_passed >= cooldown_hours
            
        except Exception as e:
            add_log_line(f"⚠️ Error en should_send_alert: {e}")
            return True
    
    def mark_alert_sent(self, user_id: int, alert_type: str):
        try:
            log = self._load_alerts_log()
            user_key = str(user_id)
            
            if user_key not in log:
                log[user_key] = {}
            
            log[user_key][alert_type] = datetime.now().isoformat()
            self._save_alerts_log(log)
            
        except Exception as e:
            add_log_line(f"❌ Error en mark_alert_sent: {e}")
    
    def get_last_daily_summary(self, user_id: int) -> Optional[datetime]:
        try:
            log = self._load_alerts_log()
            user_key = str(user_id)
            
            if user_key in log and 'daily_summary' in log[user_key]:
                return datetime.fromisoformat(log[user_key]['daily_summary'])
            return None
        except:
            return None

# Instancia global
weather_manager = WeatherAlertManager()

# Funciones compatibles
def load_weather_subscriptions():
    return weather_manager.load_subscriptions()

def save_weather_subscriptions(subs):
    weather_manager.save_subscriptions(subs)

def subscribe_user(user_id, city, country, timezone, lat, lon, alert_time="07:00"):
    """✅ Ahora REQUIERE lat y lon."""
    return weather_manager.subscribe_user(user_id, city, country, timezone, lat, lon, alert_time)

def get_user_subscription(user_id):
    return weather_manager.get_user_subscription(user_id)

def get_all_subscribed_users():
    return weather_manager.get_all_subscribed_users()

def unsubscribe_user(user_id):
    return weather_manager.unsubscribe_user(user_id)

def toggle_alert_type(user_id, alert_type):
    return weather_manager.toggle_alert_type(user_id, alert_type)

def should_send_alert(user_id, alert_type, cooldown_hours=3):
    return weather_manager.should_send_alert(user_id, alert_type, cooldown_hours)

def update_last_alert_time(user_id, alert_type):
    weather_manager.mark_alert_sent(user_id, alert_type)
