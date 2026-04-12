#!/usr/bin/env python3
"""
Script de migración de archivos JSON a Redis.
Este script lee los datos de los archivos JSON actuales y los guarda en Redis.
Se ejecuta antes de iniciar el bot para migrar los datos existentes.
"""

import os
import json
import shutil
from pathlib import Path
import sys

# Añadir el directorio del proyecto al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import DATA_DIR, USUARIOS_PATH, PRICE_ALERTS_PATH, HBD_HISTORY_PATH, CUSTOM_ALERT_HISTORY_PATH, \
    ELTOQUE_HISTORY_PATH, LAST_PRICES_PATH, ADS_PATH, HBD_THRESHOLDS_PATH, WEATHER_SUBS_PATH, \
    WEATHER_LAST_ALERTS_PATH, YEAR_QUOTES_PATH, YEAR_SUBS_PATH, EVENTS_LOG_PATH

from core.redis_fallback import (
    save_user, get_all_user_ids,
    save_price_alerts,
    save_hbd_history,
    save_custom_alert_history,
    save_eltoque_history,
    save_last_prices,
    save_ads,
    save_hbd_thresholds,
    save_weather_subs,
    save_weather_last_alerts,
    save_year_quotes,
    save_year_subs,
    save_events_log,
)

def backup_files():
    """Crea un backup de los archivos JSON actuales."""
    backup_dir = Path("backup")
    backup_dir.mkdir(exist_ok=True)
    
    data_dir = Path(DATA_DIR)
    files_to_backup = [
        "users.json",
        "price_alerts.json",
        "hbd_price_history.json",
        "custom_alert_history.json",
        "eltoque_history.json",
        "last_prices.json",
        "ads.json",
        "hbd_thresholds.json",
        "weather_subs.json",
        "weather_last_alerts.json",
        "year_quotes.json",
        "year_subs.json",
        "events_log.json"
    ]
    
    for file in files_to_backup:
        src = data_dir / file
        if src.exists():
            dst = backup_dir / f"{file}.backup"
            shutil.copy2(src, dst)
            print(f"✅ Backup de {file} creado en {dst}")

def migrate_users():
    """Migra los usuarios de JSON a Redis."""
    if not os.path.exists(USUARIOS_PATH):
        print(f"⚠️ No se encontró el archivo de usuarios: {USUARIOS_PATH}")
        return
    
    with open(USUARIOS_PATH, 'r', encoding='utf-8') as f:
        usuarios = json.load(f)
    
    for user_id_str, datos in usuarios.items():
        try:
            user_id = int(user_id_str)
            save_user(user_id, datos)
        except (ValueError, TypeError) as e:
            print(f"❌ Error migrando usuario {user_id_str}: {e}")
    
    print(f"✅ {len(usuarios)} usuarios migrados a Redis")

def migrate_price_alerts():
    """Migra las alertas de precio de JSON a Redis."""
    if not os.path.exists(PRICE_ALERTS_PATH):
        print(f"⚠️ No se encontró el archivo de alertas: {PRICE_ALERTS_PATH}")
        return
    
    with open(PRICE_ALERTS_PATH, 'r', encoding='utf-8') as f:
        alerts_dict = json.load(f)
    
    for user_id_str, alerts in alerts_dict.items():
        try:
            user_id = int(user_id_str)
            save_price_alerts(user_id, alerts)
        except (ValueError, TypeError) as e:
            print(f"❌ Error migrando alertas del usuario {user_id_str}: {e}")
    
    print(f"✅ Alertas de precio migradas para {len(alerts_dict)} usuarios")

def migrate_hbd_history():
    """Migra el historial de HBD de JSON a Redis."""
    if not os.path.exists(HBD_HISTORY_PATH):
        print(f"⚠️ No se encontró el archivo de historial HBD: {HBD_HISTORY_PATH}")
        return
    
    with open(HBD_HISTORY_PATH, 'r', encoding='utf-8') as f:
        history = json.load(f)
    
    save_hbd_history(history)
    print(f"✅ Historial HBD migrado ({len(history)} registros)")

def migrate_custom_alert_history():
    """Migra el historial de alertas personalizadas de JSON a Redis."""
    if not os.path.exists(CUSTOM_ALERT_HISTORY_PATH):
        print(f"⚠️ No se encontró el archivo de historial de alertas personalizadas: {CUSTOM_ALERT_HISTORY_PATH}")
        return
    
    with open(CUSTOM_ALERT_HISTORY_PATH, 'r', encoding='utf-8') as f:
        history = json.load(f)
    
    save_custom_alert_history(history)
    print(f"✅ Historial de alertas personalizadas migrado ({len(history)} claves)")

def migrate_eltoque_history():
    """Migra el historial de ElToque de JSON a Redis."""
    if not os.path.exists(ELTOQUE_HISTORY_PATH):
        print(f"⚠️ No se encontró el archivo de historial ElToque: {ELTOQUE_HISTORY_PATH}")
        return
    
    with open(ELTOQUE_HISTORY_PATH, 'r', encoding='utf-8') as f:
        history = json.load(f)
    
    save_eltoque_history(history)
    print(f"✅ Historial ElToque migrado ({len(history)} registros)")

def migrate_last_prices():
    """Migra los últimos precios de JSON a Redis."""
    if not os.path.exists(LAST_PRICES_PATH):
        print(f"⚠️ No se encontró el archivo de últimos precios: {LAST_PRICES_PATH}")
        return
    
    with open(LAST_PRICES_PATH, 'r', encoding='utf-8') as f:
        prices = json.load(f)
    
    save_last_prices(prices)
    print(f"✅ Últimos precios migrados")

def migrate_ads():
    """Migra los anuncios de JSON a Redis."""
    if not os.path.exists(ADS_PATH):
        print(f"⚠️ No se encontró el archivo de anuncios: {ADS_PATH}")
        return
    
    with open(ADS_PATH, 'r', encoding='utf-8') as f:
        ads = json.load(f)
    
    save_ads(ads)
    print(f"✅ Anuncios migrados ({len(ads)} entradas)")

def migrate_hbd_thresholds():
    """Migra los umbrales de HBD de JSON a Redis."""
    if not os.path.exists(HBD_THRESHOLDS_PATH):
        print(f"⚠️ No se encontró el archivo de umbrales HBD: {HBD_THRESHOLDS_PATH}")
        return
    
    with open(HBD_THRESHOLDS_PATH, 'r', encoding='utf-8') as f:
        thresholds = json.load(f)
    
    save_hbd_thresholds(thresholds)
    print(f"✅ Umbrales HBD migrados ({len(thresholds)} umbrales)")

def migrate_weather_subs():
    """Migra las suscripciones de clima de JSON a Redis."""
    if not os.path.exists(WEATHER_SUBS_PATH):
        print(f"⚠️ No se encontró el archivo de suscripciones de clima: {WEATHER_SUBS_PATH}")
        return
    
    with open(WEATHER_SUBS_PATH, 'r', encoding='utf-8') as f:
        subs = json.load(f)
    
    save_weather_subs(subs)
    print(f"✅ Suscripciones de clima migradas")

def migrate_weather_last_alerts():
    """Migra los últimos alertas de clima de JSON a Redis."""
    if not os.path.exists(WEATHER_LAST_ALERTS_PATH):
        print(f"⚠️ No se encontró el archivo de últimos alertas de clima: {WEATHER_LAST_ALERTS_PATH}")
        return
    
    with open(WEATHER_LAST_ALERTS_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    save_weather_last_alerts(data)
    print(f"✅ Últimos alertas de clima migrados")

def migrate_year_quotes():
    """Migra las frases anuales de JSON a Redis."""
    if not os.path.exists(YEAR_QUOTES_PATH):
        print(f"⚠️ No se encontró el archivo de frases anuales: {YEAR_QUOTES_PATH}")
        return
    
    with open(YEAR_QUOTES_PATH, 'r', encoding='utf-8') as f:
        quotes = json.load(f)
    
    save_year_quotes(quotes)
    print(f"✅ Frases anuales migradas ({len(quotes)} frases)")

def migrate_year_subs():
    """Migra las suscripciones anuales de JSON a Redis."""
    if not os.path.exists(YEAR_SUBS_PATH):
        print(f"⚠️ No se encontró el archivo de suscripciones anuales: {YEAR_SUBS_PATH}")
        return
    
    with open(YEAR_SUBS_PATH, 'r', encoding='utf-8') as f:
        subs = json.load(f)
    
    save_year_subs(subs)
    print(f"✅ Suscripciones anuales migradas")

def migrate_events_log():
    """Migra el log de eventos de JSON a Redis."""
    if not os.path.exists(EVENTS_LOG_PATH):
        print(f"⚠️ No se encontró el archivo de log de eventos: {EVENTS_LOG_PATH}")
        return
    
    with open(EVENTS_LOG_PATH, 'r', encoding='utf-8') as f:
        log = json.load(f)
    
    save_events_log(log)
    print(f"✅ Log de eventos migrado ({len(log)} entradas)")

def verificar_migracion():
    """Verifica que los datos se hayan guardado correctamente en Redis."""
    print("\n🔍 Verificando migración...")
    
    # Intentar obtener lista de IDs de usuarios
    try:
        user_ids = list(get_all_user_ids())
        print(f"  ✅ Usuarios en Redis: {len(user_ids)} IDs")
    except Exception as e:
        print(f"  ❌ Error obteniendo IDs de usuarios: {e}")
    
    # Verificar algunos datos clave
    try:
        hbd_hist = get_hbd_history()
        print(f"  ✅ Historial HBD en Redis: {len(hbd_hist)} registros")
    except Exception as e:
        print(f"  ❌ Error obteniendo historial HBD: {e}")
    
    try:
        alerts = load_price_alerts()
        total_alertas = sum(len(a) for a in alerts.values())
        print(f"  ✅ Alertas en Redis: {total_alertas} alertas activas")
    except Exception as e:
        print(f"  ❌ Error cargando alertas: {e}")

def main():
    print("🚀 Iniciando migración a Redis")
    print(f"Directororio de datos: {DATA_DIR}")
    print(f"Archivo de configuración: {__file__}\n")
    
    # 1. Crear backup
    print("📁 1. Creando backup de archivos JSON...")
    backup_files()
    
    # 2. Migrar datos
    print("\n💾 2. Migración de datos a Redis:")
    migrate_users()
    migrate_price_alerts()
    migrate_hbd_history()
    migrate_custom_alert_history()
    migrate_eltoque_history()
    migrate_last_prices()
    migrate_ads()
    migrate_hbd_thresholds()
    migrate_weather_subs()
    migrate_weather_last_alerts()
    migrate_year_quotes()
    migrate_year_subs()
    migrate_events_log()
    
    # 3. Verificar
    verificar_migracion()
    
    print("\n✅ Migración completada exitosamente!")
    print("Nota: Asegúrese de que Redis esté corriendo antes de iniciar el bot.")
    print("El bot ahora usará Redis para almacenar datos.")

if __name__ == "__main__":
    main()