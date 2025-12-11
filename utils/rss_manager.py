# utils/rss_manager.py

import json
import os
import feedparser
from datetime import datetime
from core.config import DATA_DIR
from utils.file_manager import add_log_line

RSS_DATA_PATH = os.path.join(DATA_DIR, "rss_data.json")

# Estructura inicial
# {
#   "user_id": {
#      "channels": [{"id": -100xxx, "title": "Mi Canal"}],
#      "feeds": [
#         {
#           "id": "uuid", "url": "...", "target_channel_id": -100xxx,
#           "format": "img_text", "frequency": 60, "last_checked": ts,
#           "last_entry_id": "..."
#         }
#       ],
#       "slots": {"channels": 2, "feeds": 10} # Base + Comprados
#   }
# }

def load_rss_data():
    if not os.path.exists(RSS_DATA_PATH):
        return {}
    try:
        with open(RSS_DATA_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}

def save_rss_data(data):
    try:
        with open(RSS_DATA_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        add_log_line(f"❌ Error guardando RSS Data: {e}")

def get_user_rss(user_id):
    data = load_rss_data()
    uid = str(user_id)
    if uid not in data:
        # Inicializar usuario RSS
        data[uid] = {
            "channels": [],
            "feeds": [],
            "extra_slots": {"channels": 0, "feeds": 0} # Slots comprados extra
        }
        save_rss_data(data)
    return data[uid]

def check_rss_limits(user_id, type_check):
    """
    Verifica si el usuario puede añadir más canales o feeds.
    type_check: 'channels' o 'feeds'
    """
    user_data = get_user_rss(user_id)
    
    # Límites Base (Gratis)
    LIMITS_BASE = {"channels": 2, "feeds": 10}
    
    current_count = len(user_data[type_check])
    extra = user_data["extra_slots"].get(type_check, 0)
    total_limit = LIMITS_BASE[type_check] + extra
    
    if current_count >= total_limit:
        return False, current_count, total_limit
    return True, current_count, total_limit

def add_rss_channel(user_id, channel_id, title):
    data = load_rss_data()
    uid = str(user_id)
    
    # Verificar si ya existe
    for ch in data[uid]['channels']:
        if str(ch['id']) == str(channel_id):
            return False, "Ya tienes este canal agregado."
            
    data[uid]['channels'].append({"id": channel_id, "title": title})
    save_rss_data(data)
    return True, "Canal agregado correctamente."

def add_rss_feed(user_id, url, channel_id):
    # Validar URL
    try:
        f = feedparser.parse(url)
        if not f.entries and not f.feed.get('title'):
            return False, "No parece ser un RSS válido o está vacío."
    except Exception as e:
        return False, f"Error al leer URL: {e}"

    data = load_rss_data()
    uid = str(user_id)
    
    import uuid
    new_feed = {
        "id": str(uuid.uuid4())[:8],
        "url": url,
        "title": f.feed.get('title', 'Sin Titulo'),
        "target_channel_id": channel_id,
        "format": "img_text", # Opciones: img_text, text_only, title_link
        "frequency": 60, # Minutos
        "last_checked": 0,
        "last_entry_link": None,
        "active": True,
        "filters": []
    }
    
    data[uid]['feeds'].append(new_feed)
    save_rss_data(data)
    return True, new_feed 

def delete_rss_item(user_id, type_item, item_id):
    data = load_rss_data()
    uid = str(user_id)
    original_len = len(data[uid][type_item])
    
    if type_item == 'feeds':
        data[uid][type_item] = [x for x in data[uid][type_item] if x['id'] != item_id]
    elif type_item == 'channels':
        data[uid][type_item] = [x for x in data[uid][type_item] if str(x['id']) != str(item_id)]
        
    if len(data[uid][type_item]) < original_len:
        save_rss_data(data)
        return True
    return False

def add_purchased_slot(user_id, slot_type, qty):
    data = load_rss_data()
    uid = str(user_id)
    if uid not in data: get_user_rss(user_id) # init si no existe
    
    data = load_rss_data() # Recargar
    current = data[uid]["extra_slots"].get(slot_type, 0)
    data[uid]["extra_slots"][slot_type] = current + qty
    save_rss_data(data)

def get_feed_details(user_id, feed_id):
    """Obtiene los datos de un feed específico."""
    data = load_rss_data()
    uid = str(user_id)
    if uid in data:
        for f in data[uid]['feeds']:
            if f['id'] == feed_id:
                return f
    return None

def update_feed_template(user_id, feed_id, template_text):
    """Guarda la plantilla personalizada para un feed."""
    data = load_rss_data()
    uid = str(user_id)
    found = False
    
    if uid in data:
        for f in data[uid]['feeds']:
            if f['id'] == feed_id:
                f['template'] = template_text
                # Reseteamos el formato antiguo para dar prioridad a la plantilla
                f['format'] = 'custom' 
                found = True
                break
    
    if found:
        save_rss_data(data)
        return True
    return False

def toggle_feed_active(user_id, feed_id):
    """Activa o Pausa un feed."""
    data = load_rss_data()
    uid = str(user_id)
    new_status = False
    if uid in data:
        for f in data[uid]['feeds']:
            if f['id'] == feed_id:
                # Si no tiene la key 'active', asumimos True y lo ponemos False
                curr = f.get('active', True)
                f['active'] = not curr
                new_status = f['active']
                break
    save_rss_data(data)
    return new_status

def manage_feed_filter(user_id, feed_id, word, action='add'):
    """Añade o borra palabras de la blacklist."""
    data = load_rss_data()
    uid = str(user_id)
    if uid not in data: return False
    
    found = False
    for f in data[uid]['feeds']:
        if f['id'] == feed_id:
            current_filters = f.get('filters', [])
            
            if action == 'add':
                if word.lower() not in current_filters:
                    current_filters.append(word.lower())
            elif action == 'del':
                if word.lower() in current_filters:
                    current_filters.remove(word.lower())
            
            f['filters'] = current_filters
            found = True
            break
            
    if found:
        save_rss_data(data)
    return found