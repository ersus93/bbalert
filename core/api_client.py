# cmc_api.py

import requests
from telegram import Update
from core.config import CMC_API_KEY_ALERTA, CMC_API_KEY_CONTROL
from datetime import datetime, timedelta
from core.i18n import _ 
# No se necesitan imports de file_manager aquí

# === LÓGICA DE ALERTA (HBD) ===

# Se añade chat_id=None a la firma de la función
def generar_alerta(precios_actuales, precio_anterior_hbd, user_id: int | None):
    """
    Determina si se debe enviar una alerta de HBD e incluye los precios de BTC, HIVE y HBD.
    precios_actuales es el diccionario completo: {'BTC': float, 'HIVE': float, 'HBD': float}
    """
    
    if precio_anterior_hbd is None:
        return None, None
    
    precio_actual_hbd = precios_actuales.get('HBD')
    btc = precios_actuales.get('BTC', 'N/A')
    hive = precios_actuales.get('HIVE', 'N/A')
    ton = precios_actuales.get('TON', 'N/A')
    
    if precio_actual_hbd is None:
         return None, None
         
    # --- Estructura del mensaje adicional (que se adjuntará a la alerta) ---
    detalle_precios = (
        _("\n\n**Precios Actuales:**\n", user_id) + # <-- chat_id para msg
        f"🟠 *BTC/USD*: ${btc:.2f}\n"
        f"🔷 *TON/USD*: ${ton:.4f}\n"
        f"🐝 *HIVE/USD*: ${hive:.4f}\n"
        f"💰 *HBD/USD*: ${precio_actual_hbd:.4f}"
    )

    # Lógica de alerta

    # 1. Alerta: HBD sube por encima de $1.10
    if precio_actual_hbd >= 1.10 and precio_anterior_hbd < 1.10:
        msg = _("🤯 *HBD TOCÓ $1.10 (O MÁS)*", user_id) + detalle_precios # <-- chat_id para msg
        log = _("🤯 Alerta MÁXIMA: HBD ≥ $1.10", None) # <-- None para log
        return msg, log
    
    # 2. Alerta: HBD cae por debajo de $1.10
    elif precio_actual_hbd < 1.10 and precio_anterior_hbd >= 1.10:
        msg = _("📉 *HBD acaba de caer de $1.10*", user_id) + detalle_precios
        log = _("📉 Alerta: HBD bajó de $1.10", None)
        return msg, log

    
    elif precio_actual_hbd > 1.05 and precio_anterior_hbd <= 1.05:
        msg = _("📈 *HBD acaba de superar $1.05.*", user_id) + detalle_precios
        log = _("📈 Alerta: HBD superó $1.05", None)
        return msg, log
    
    elif precio_actual_hbd <= 1.05 and precio_anterior_hbd > 1.05:
        msg = _("📉 *HBD acaba de caer de $1.05.*", user_id) + detalle_precios
        log = _("📉 Alerta: HBD cayó de $1.05", None)
        return msg, log
    
    elif precio_actual_hbd >= 1.005 and precio_anterior_hbd < 1.005:
        msg = _("⚠️ *HBD superó $1.005.*", user_id) + detalle_precios
        log = _("⚠️ Alerta: HBD superó $1.005", None)
        return msg, log

    elif precio_actual_hbd < 1.005 and precio_anterior_hbd >= 1.005:
        msg = _("📉 *HBD cayó de $1.005.*", user_id) + detalle_precios
        log = _("📉 Alerta: HBD cayó de $1.005", None)
        return msg, log
    
    elif precio_actual_hbd >= 1.00 and precio_anterior_hbd < 1.00:
        msg = _("⚠️ *HBD superó $1.00.*", user_id) + detalle_precios
        log = _("⚠️ Alerta: HBD superó $1.00", None)
        return msg, log

    elif precio_actual_hbd < 1.00 and precio_anterior_hbd >= 1.00:
        msg = _("📉 *HBD cayó de $1.00.*", user_id) + detalle_precios
        log = _("📉 Alerta: HBD cayó de $1.00", None)
        return msg, log

    elif precio_actual_hbd < 0.995 and precio_anterior_hbd >= 0.995:
        msg = _("🚨 *HBD cayó por debajo de $0.995.", user_id) + detalle_precios
        log = _("🚨 Alerta: 😣 HBD cayó por debajo de $0.995", None)
        return msg, log
    
    elif precio_actual_hbd >= 0.995 and precio_anterior_hbd < 0.995:
        msg = _("🚨 *HBD subió por encima de $0.995.*", user_id) + detalle_precios
        log = _("🚨 Alerta: 😃 HBD subió por encima de $0.995", None)
        return msg, log
      
    elif precio_actual_hbd >= 0.98 and precio_anterior_hbd < 0.98:
        msg = _("🚨 *HBD subió por encima de $0.98.*", user_id) + detalle_precios
        log = _("🚨 Alerta: 😃 HBD subió por encima de $0.98", None)
        return msg, log
    
    elif precio_actual_hbd < 0.98 and precio_anterior_hbd >= 0.98:
        msg = _("🚨 *HBD cayó por debajo de $0.98.*", user_id) + detalle_precios
        log = _("🚨 Alerta: 😣 HBD cayó por debajo de $0.98", None)
        return msg, log

    elif precio_actual_hbd >= 0.95 and precio_anterior_hbd < 0.95:
        msg = _("🚨 *HBD subió por encima de $0.95.*", user_id) + detalle_precios
        log = _("🚨 Alerta: 😃 HBD subió por encima de $0.95", None)
        return msg, log
    
    elif precio_actual_hbd < 0.95 and precio_anterior_hbd >= 0.95:
        msg = _("🚨 *HBD cayó por debajo de $0.95.*", user_id) + detalle_precios
        log = _("🚨 Alerta: 😣 HBD cayó por debajo de $0.95", None)
        return msg, log
        
    return None, None
# ... (el resto del archivo sin cambios)

# === OBTENCIÓN DE PRECIOS CMC (Función genérica y wrappers) ===

def _obtener_precios(monedas, api_key):
    """Función genérica y síncrona para obtener precios de CMC."""
    headers = {
        "X-CMC_PRO_API_KEY": api_key,
        "Accept": "application/json"
    }
    params = {
        "symbol": ",".join(monedas),
        "convert": "USD"
    }
    precios = {}
    try:
        response = requests.get("https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest", headers=headers, params=params, timeout=10)
        response.raise_for_status() 
        data = response.json()
        
        if not data or "data" not in data:
            return None if len(monedas) == 3 else {} 
        
        for m in monedas:
            if m in data["data"]:
                precios[m] = data["data"][m]["quote"]["USD"]["price"]
        
        return precios
        
    except requests.exceptions.RequestException as e:
        # Se retorna None si es la alerta principal (BTC, HIVE, HBD)
        return None if len(monedas) == 3 else {}

def obtener_precios_alerta():
    return _obtener_precios(["BTC", "TON", "HIVE", "HBD"], CMC_API_KEY_ALERTA)

def obtener_precios_control(monedas):
    return _obtener_precios(monedas, CMC_API_KEY_CONTROL)

def obtener_high_low_24h(moneda):
    """Consulta el OHLCV histórico para calcular el high y low de las últimas 24h."""
    headers = {
        "X-CMC_PRO_API_KEY": CMC_API_KEY_CONTROL,
        "Accept": "application/json"
    }

    ahora = datetime.utcnow()
    hace_24h = ahora - timedelta(hours=24)

    params = {
        "symbol": moneda,
        "convert": "USD",
        "time_start": hace_24h.strftime("%Y-%m-%dT%H:%M:%S"),
        "time_end": ahora.strftime("%Y-%m-%dT%H:%M:%S")
    }

    try:
        response = requests.get("https://pro-api.coinmarketcap.com/v1/cryptocurrency/ohlcv/historical", headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        candles = data.get("data", {}).get("quotes", [])
        if not candles:
            return (0, 0)

        high = max(candle["quote"]["USD"]["high"] for candle in candles)
        low = min(candle["quote"]["USD"]["low"] for candle in candles)
        return (high, low)

    except (requests.exceptions.RequestException, KeyError) as e:
        print(f"Error al obtener HL histórico de {moneda}: {e}")
        return (0, 0)

def obtener_datos_moneda(moneda):
    """Obtiene datos detallados de una moneda de CoinMarketCap."""
    headers = {
        "X-CMC_PRO_API_KEY": CMC_API_KEY_CONTROL,
        "Accept": "application/json"
    }
    # Solicitamos la moneda deseada Y ETH, ambas convertidas a USD
    params = {
        "symbol": f"{moneda},ETH",
        "convert": "USD" 
    }
    try:
        response = requests.get("https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest", headers=headers, params=params, timeout=10)
        response.raise_for_status()
        
        full_data = response.json()['data']
        
        # Verificar que ambas monedas estén en la respuesta
        if moneda not in full_data or 'ETH' not in full_data:
            print(f"Error: La respuesta de la API no contiene datos para {moneda} o ETH.")
            return None

        data_moneda = full_data[moneda]
        data_eth = full_data['ETH']
        
        quote_usd_moneda = data_moneda['quote']['USD']
        price_usd_eth = data_eth['quote']['USD']['price']

        # Calcular el precio en ETH manualmente
        price_in_eth = quote_usd_moneda['price'] / price_usd_eth if price_usd_eth != 0 else 0

        return {
            'symbol': data_moneda['symbol'],
            'price': quote_usd_moneda['price'],
            'price_eth': price_in_eth,
            'high_24h': obtener_high_low_24h(moneda)[0],
            'low_24h': obtener_high_low_24h(moneda)[1],
            'percent_change_1h': quote_usd_moneda['percent_change_1h'],
            'percent_change_24h': quote_usd_moneda['percent_change_24h'],
            'percent_change_7d': quote_usd_moneda['percent_change_7d'],
            'market_cap_rank': data_moneda['cmc_rank'],
            'market_cap': quote_usd_moneda['market_cap'],
            'volume_24h': quote_usd_moneda['volume_24h']
        }
    except (requests.exceptions.RequestException, KeyError) as e:
        print(f"Error al obtener datos de {moneda}: {e}")
        return None

