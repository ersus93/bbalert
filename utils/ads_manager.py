# utils/ads_manager.py

import json
import os
import random
from core.config import ADS_PATH

def load_ads():
    """Carga la lista de anuncios desde el JSON."""
    if not os.path.exists(ADS_PATH):
        return []
    try:
        with open(ADS_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return []

def save_ads(ads_list):
    """Guarda la lista de anuncios en el JSON."""
    try:
        with open(ADS_PATH, 'w', encoding='utf-8') as f:
            json.dump(ads_list, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error guardando anuncios: {e}")
        return False

def get_random_ad_text():
    """
    Devuelve un anuncio aleatorio formateado.
    Si no hay anuncios, devuelve una cadena vacía.
    """
    ads = load_ads()
    if not ads:
        return ""
    
    anuncio = random.choice(ads)
    
    # Formato visual del anuncio (puedes cambiar los emojis o separadores)
    return f"\n\n📌========== ADs ==========📌\n👉 {anuncio}\n"

def add_ad(text):
    """Añade un nuevo anuncio a la lista."""
    ads = load_ads()
    ads.append(text)
    save_ads(ads)

def delete_ad(index):
    """Elimina un anuncio por su número (índice 1-based)."""
    ads = load_ads()
    if 0 <= index < len(ads):
        removed = ads.pop(index)
        save_ads(ads)
        return removed
    return None