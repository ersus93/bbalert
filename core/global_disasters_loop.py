# core/global_disasters_loop.py - VERSIÓN MEJORADA (DISTANCIA + PERSISTENCIA)

import asyncio
import math
from telegram import Bot
from telegram.constants import ParseMode
from utils.file_manager import add_log_line
from utils.weather_manager import weather_manager
from utils.global_disasters_api import disaster_monitor

# ========================================
# FUNCIÓN HAVERSINE PARA DISTANCIA
# ========================================

def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calcula distancia entre dos puntos en km usando fórmula de Haversine.
    
    Args:
        lat1, lon1: Coordenadas del punto 1
        lat2, lon2: Coordenadas del punto 2
    
    Returns:
        Distancia en kilómetros
    """
    R = 6371  # Radio de la Tierra en km
    
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    
    a = (math.sin(dlat/2) * math.sin(dlat/2) + 
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon/2) * math.sin(dlon/2))
    
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    
    return R * c

# ========================================
# FORMATEO DE MENSAJES
# ========================================

DISASTER_EMOJIS = {
    "Earthquake": "🌍",
    "Tsunami": "🌊",
    "Cyclone": "🌀",
    "Volcano": "🌋",
    "Flood": "💧",
    "Drought": "🏜️",
    "Unknown": "⚠️"
}

def format_disaster_message(event: dict, distance_km: float = None) -> str:
    """Formatea mensaje de desastre con datos opcionales de distancia."""
    
    emoji = DISASTER_EMOJIS.get(event['type'], "⚠️")
    
    # Color según severidad
    if event['severity'] == "Red":
        sev_icon = "🔴 *CRÍTICO*"
    elif event['severity'] == "Orange":
        sev_icon = "🟠 *ALTO*"
    else:
        sev_icon = "🟢 *MODERADO*"
    
    # Traducción de tipos
    type_names = {
        "Earthquake": "Terremoto",
        "Tsunami": "Tsunami",
        "Cyclone": "Ciclón/Huracán",
        "Volcano": "Erupción Volcánica",
        "Flood": "Inundación",
        "Drought": "Sequía"
    }
    
    type_spanish = type_names.get(event['type'], event['type'])
    
    msg = (
        f"{emoji} {sev_icon}\n"
        f"—————————————————\n"
        f"🌐 *Tipo:* {type_spanish}\n"
        f"📍 *Ubicación:* {event['location']}\n"
    )
    
    # Datos específicos según tipo
    if event['type'] == "Earthquake" and 'magnitude' in event:
        msg += f"📊 *Magnitud:* {event['magnitude']:.1f}\n"
        msg += f"📏 *Profundidad:* {event['depth']:.1f} km\n"
    
    # Distancia al usuario (si aplica)
    if distance_km is not None:
        if distance_km < 500:
            msg += f"📏 *Distancia:* ⚠️ **{int(distance_km)} km de ti**\n"
        else:
            msg += f"📏 *Distancia:* {int(distance_km)} km de ti\n"
    
    msg += (
        f"📅 *Fecha:* {event['published']}\n\n"
        f"ℹ️ {event['description'][:150]}...\n\n"
        f"🔗 [Más información]({event['link']})\n\n"
        f"_Fuente: {event['source']}_"
    )
    
    return msg

# ========================================
# LOOP PRINCIPAL
# ========================================

async def global_disasters_loop(bot: Bot):
    """
    Loop de monitoreo de desastres globales con:
    - Persistencia en disco (evita repeticiones tras reinicios)
    - Filtrado por distancia (prioritiza eventos cercanos)
    - Sistema anti-spam integrado
    """
    add_log_line("🌍 Iniciando Monitor de Desastres Globales v2 (Geolocalizado + Persistente)...")
    
    await asyncio.sleep(45)  # Espera inicial para estabilizar bot
    
    loop_count = 0
    
    while True:
        try:
            loop_count += 1
            add_log_line(f"🔄 Global Disasters Loop Ciclo #{loop_count}")
            
            # 1. Obtener alertas crudas de la API
            raw_alerts = disaster_monitor.get_all_alerts()
            
            if not raw_alerts:
                add_log_line("✅ No hay nuevas alertas globales (API)")
                await asyncio.sleep(3600)  # 60 minutos
                continue
            
            # 2. ✅ FILTRAR EVENTOS YA PROCESADOS (PERSISTENCIA EN DISCO)
            new_events = []
            for event in raw_alerts:
                event_id = event.get('id')
                
                if not event_id:
                    add_log_line(f"⚠️ Evento sin ID: {event.get('title', 'Sin título')}")
                    continue
                
                if not weather_manager.is_global_event_sent(event_id):
                    new_events.append(event)
                else:
                    add_log_line(f"👍 Evento {event_id} ya procesado (en historial JSON)")
            
            if not new_events:
                add_log_line("✅ Todas las alertas ya fueron procesadas anteriormente")
                await asyncio.sleep(300)
                continue
            
            add_log_line(f"🚨 {len(new_events)} eventos globales NUEVOS detectados")
            
            # 3. Obtener usuarios suscritos a alertas globales
            all_users = weather_manager.get_all_subscribed_users()
            
            users_with_global = []
            for uid in all_users:
                sub = weather_manager.get_user_subscription(uid)
                if sub and sub.get('alert_types', {}).get('global_disasters', False):
                    users_with_global.append(uid)
            
            if not users_with_global:
                add_log_line("⏭️ No hay usuarios suscritos a alertas globales")
                
                # Aún así marcamos eventos como procesados
                for event in new_events:
                    weather_manager.mark_global_event_sent(event['id'])
                
                await asyncio.sleep(300)
                continue
            
            add_log_line(f"📤 Notificando a {len(users_with_global)} usuarios...")
            
            # 4. Procesar cada evento nuevo
            for event in new_events:
                event_lat = event.get('lat', 0)
                event_lon = event.get('lon', 0)
                has_coords = (event_lat != 0 and event_lon != 0)
                
                severity = event.get('severity', 'Green')
                
                users_notified = 0
                
                for user_id in users_with_global:
                    sub = weather_manager.get_user_subscription(user_id)
                    user_lat = sub.get('lat')
                    user_lon = sub.get('lon')
                    
                    should_send = False
                    distance_km = None
                    
                    # ========================================
                    # LÓGICA DE PRIORIDAD POR DISTANCIA
                    # ========================================
                    
                    # Calcular distancia si hay coordenadas
                    if has_coords and user_lat and user_lon:
                        distance_km = calculate_distance(
                            user_lat, user_lon, 
                            event_lat, event_lon
                        )
                    
                    # REGLAS DE ENVÍO:
                    # 1. Eventos CRÍTICOS (Red): Siempre se envían a TODOS
                    # 2. Eventos ALTOS (Orange): Siempre se envían a TODOS
                    # 3. Eventos MODERADOS (Green/Yellow):
                    #    - Solo si están a menos de 1000 km del usuario
                    
                    if severity in ['Red', 'Orange']:
                        should_send = True
                    elif distance_km and distance_km < 1000:
                        should_send = True
                    
                    if should_send:
                        try:
                            msg = format_disaster_message(event, distance_km)
                            
                            await bot.send_message(
                                chat_id=user_id,
                                text=msg,
                                parse_mode=ParseMode.MARKDOWN,
                                disable_web_page_preview=False
                            )
                            
                            users_notified += 1
                            
                            add_log_line(
                                f"✅ Alerta global enviada a {user_id} "
                                f"(distancia: {distance_km:.0f if distance_km else '∞'} km)"
                            )
                            
                            await asyncio.sleep(0.5)  # Anti-flood
                            
                        except Exception as e:
                            add_log_line(f"❌ Error enviando a {user_id}: {str(e)[:100]}")
                            continue
                
                # ========================================
                # ✅ MARCAR COMO ENVIADO EN JSON (PERSISTENCIA)
                # ========================================
                weather_manager.mark_global_event_sent(event['id'])
                
                if users_notified > 0:
                    add_log_line(
                        f"✅ Evento {event['id']} notificado a {users_notified} usuarios "
                        f"y marcado como procesado"
                    )
                else:
                    add_log_line(
                        f"⏭️ Evento {event['id']} no cumplió criterios de notificación "
                        f"pero se marcó como procesado"
                    )
            
            add_log_line(f"✅ Ciclo #{loop_count} completado")
            
            # Esperar 5 minutos antes del siguiente ciclo
            await asyncio.sleep(300)
        
        except Exception as e:
            add_log_line(f"❌ Error crítico en global_disasters_loop: {str(e)[:200]}")
            import traceback
            add_log_line(f"Traceback: {traceback.format_exc()[:1000]}")
            
            # Esperar 2 minutos antes de reintentar
            await asyncio.sleep(120)
