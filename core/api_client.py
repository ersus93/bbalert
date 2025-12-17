# cmc_api.py

import requests
import json
from telegram import Update
from core.config import CMC_API_KEY_ALERTA, CMC_API_KEY_CONTROL, SCREENSHOT_API_KEY, ELTOQUE_API_KEY
from datetime import datetime, timedelta
from utils.file_manager import load_hbd_thresholds
from core.i18n import _ 
# No se necesitan imports de file_manager aquí

# Funciones para obtener datos de CoinMarketCap y ElToque
def obtener_tasas_eltoque():
    """
    Obtiene las tasas de cambio más recientes de la API de eltoque.com.
    """

    URL_API_ELTOQUE = "https://tasas.eltoque.com/v1/trmi" 
    
    if not ELTOQUE_API_KEY:
        print("❌ Error: La variable ELTOQUE_API_KEY no está configurada en config.py.")
        return None


    headers = {
        "Authorization": f"Bearer {ELTOQUE_API_KEY}",
        "Accept": "application/json"
    }

    try:
        response = requests.get(URL_API_ELTOQUE, headers=headers, timeout=10)
        response.raise_for_status() 
        
        data = response.json()
        
        # --- AGREGAR ESTO TEMPORALMENTE PARA VERIFICAR ---
        print("🔍 RESPUESTA JSON DE ELTOQUE:", json.dumps(data, indent=2))
        # -------------------------------------------------

        return data
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Error al contactar la API de ElToque: {e}")
        return None
    except (KeyError, json.JSONDecodeError):
        print("❌ Error al procesar la respuesta JSON de ElToque.")
        return None
    
# === FUNCIONES DE ALERTA DE HBD ===
def generar_alerta(precios_actuales, precio_anterior_hbd, user_id: int | None):
    """
    Determina si se debe enviar una alerta de HBD comparando con los umbrales dinámicos.
    """
    
    if precio_anterior_hbd is None:
        return None, None
    
    precio_actual_hbd = precios_actuales.get('HBD')
    btc = precios_actuales.get('BTC', 'N/A')
    hive = precios_actuales.get('HIVE', 'N/A')
    ton = precios_actuales.get('TON', 'N/A')
    
    if precio_actual_hbd is None:
         return None, None

    # 1. Cargar umbrales dinámicos
    thresholds = load_hbd_thresholds()
    
    # 2. Variable para detectar el evento
    evento_detectado = None # Puede ser "subio" o "bajo"
    precio_cruce = 0.0

    # 3. Iterar sobre cada umbral configurado
    # Convertimos claves a float para comparar
    for price_str, is_running in thresholds.items():
        if not is_running:
            continue # Si está en 'stop', ignoramos
            
        target = float(price_str)
        
        # Lógica de Cruce hacia ARRIBA (Cruce Alcista)
        # Anterior < Target <= Actual
        if precio_anterior_hbd < target and precio_actual_hbd >= target:
            evento_detectado = "subio"
            precio_cruce = target
            break # Notificamos el primer cruce encontrado (prioridad)

        # Lógica de Cruce hacia ABAJO (Cruce Bajista)
        # Anterior > Target >= Actual
        # Usamos >= en target para asegurar capturar si toca exacto o cae
        if precio_anterior_hbd > target and precio_actual_hbd <= target:
            evento_detectado = "bajo"
            precio_cruce = target
            break 

    if not evento_detectado:
        return None, None

    # --- Construcción del Mensaje ---
    
    # Encabezado Fijo
    encabezado = _("🚨 *Alerta de precio de HBD* 🚨\n—————————————————\n\n", user_id)
    
    # Cuerpo del mensaje según evento
    if evento_detectado == "subio":
        cuerpo = _(
            "🚀 HBD acaba de *tocar o superar* los *${precio}*.",
            user_id
        ).format(precio=f"{precio_cruce:.4f}")
        log_msg = f"📈 Alerta HBD: Subió a {precio_cruce}"
    else:
        cuerpo = _(
            "🔻 HBD acaba de *tocar o bajar* de *${precio}*.",
            user_id
        ).format(precio=f"{precio_cruce:.4f}")
        log_msg = f"📉 Alerta HBD: Bajó a {precio_cruce}"

    # Detalles de precios (Footer)
    detalle_precios = (
        _("\n\n—————————————————\n📊 *Precios Actuales:*\n•\n", user_id) +
        f"🟠 *BTC/USD*: ${btc:.2f}\n"
        f"🔷 *TON/USD*: ${ton:.4f}\n"
        f"🐝 *HIVE/USD*: ${hive:.4f}\n"
        f"💰 *HBD/USD*: ${precio_actual_hbd:.4f}"
    )

    msg_final = encabezado + cuerpo + detalle_precios
    
    return msg_final, log_msg

# === FUNCIONES DE API DE COINMARKETCAP ===
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
        
        return None if len(monedas) == 3 else {}

def obtener_precios_alerta():
    return _obtener_precios(["BTC", "TON", "HIVE", "HBD"], CMC_API_KEY_ALERTA)

def obtener_precios_control(monedas):
    return _obtener_precios(monedas, CMC_API_KEY_CONTROL)

# En core/api_client.py

def obtener_high_low_24h(moneda):
    """
    Obtiene el High y Low de las últimas 24h usando Binance (Gratis).
    Intenta buscar el par contra USDT.
    """
    # Estandarizamos el símbolo a mayúsculas y le pegamos USDT
    symbol = moneda.upper()
    pair = f"{symbol}USDT"
    
    url = [
        "https://api.binance.us/api/v3/ticker/24hr",
        "https://api.binance.com/api/v3/ticker/24hr"
        ]
    params = {"symbol": pair}

    try:
        # Timeout corto para no bloquear el bot si Binance tarda
        response = requests.get(url, params=params, timeout=2)
        
        # Si la moneda no existe en Binance (400 Bad Request), devolvemos 0,0 silenciosamente
        if response.status_code != 200:
            return 0, 0
            
        data = response.json()
        
        high = float(data.get('highPrice', 0))
        low = float(data.get('lowPrice', 0))
        
        return high, low

    except Exception as e:
        # En caso de error de conexión, retornamos 0 sin explotar
        return 0, 0
def obtener_datos_moneda(moneda):
    """Obtiene datos detallados de una moneda de CoinMarketCap."""
    headers = {
        "X-CMC_PRO_API_KEY": CMC_API_KEY_CONTROL,
        "Accept": "application/json"
    }
    
    # Solicitamos la moneda, ETH y BTC
    params = {
        "symbol": f"{moneda},ETH,BTC", 
        "convert": "USD" 
    }
    try:
        response = requests.get("https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest", headers=headers, params=params, timeout=10)
        response.raise_for_status()
        
        full_data = response.json()['data']
        
        # Verificar que las tres monedas estén en la respuesta
        if moneda not in full_data or 'ETH' not in full_data or 'BTC' not in full_data:
            print(f"Error: La respuesta de la API no contiene datos para {moneda}, ETH o BTC.")
            return None

        data_moneda = full_data[moneda]
        data_eth = full_data['ETH']
        data_btc = full_data['BTC'] # <-- Obtenemos datos de BTC
        
        quote_usd_moneda = data_moneda['quote']['USD']
        price_usd_eth = data_eth['quote']['USD']['price']
        price_usd_btc = data_btc['quote']['USD']['price'] # <-- Obtenemos precio de BTC en USD

        # Calcular el precio en ETH y BTC manualmente
        price_in_eth = quote_usd_moneda['price'] / price_usd_eth if price_usd_eth != 0 else 0
        price_in_btc = quote_usd_moneda['price'] / price_usd_btc if price_usd_btc != 0 else 0 # <-- Calculamos precio en BTC

        return {
            'symbol': data_moneda['symbol'],
            'price': quote_usd_moneda['price'],
            'price_eth': price_in_eth,
            'price_btc': price_in_btc, # <-- Añadimos al diccionario
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

