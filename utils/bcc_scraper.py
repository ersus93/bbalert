# utils/bcc_scraper.py

import requests
import json
import html
import urllib3
from bs4 import BeautifulSoup
from utils.file_manager import add_log_line

# Deshabilitar advertencias de certificados SSL (común en sitios .cu)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def obtener_tasas_bcc():
    """
    Scrapea las tasas de cambio del Banco Central de Cuba (BCC).
    Maneja la estructura serializada de Astro/Qwik.
    """
    url = "https://www.bc.gob.cu/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=5, verify=False)
        
        if response.status_code != 200:
            add_log_line(f"⚠️ BCC retornó estado {response.status_code}")
            return None

        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 1. Buscar todos los componentes astro-island
        islands = soup.find_all('astro-island')
        data = None
        
        for island in islands:
            props_raw = island.get('props')
            if not props_raw:
                continue
                
            props_json = html.unescape(props_raw)
            try:
                temp_data = json.loads(props_json)
                # Verificamos que contenga 'tasas' y que NO sea solo un link en noticias
                if 'tasas' in temp_data and isinstance(temp_data['tasas'], list):
                    data = temp_data
                    break # Encontramos el correcto
            except:
                continue
        
        if not data:
            add_log_line("⚠️ No se encontró el componente de datos de tasas en BCC.")
            return None

        print(f"DEBUG BCC DATA CORRECTO: {data}")       
    
        # 3. Navegar la estructura de serialización de Astro
        # Estructura observada: 
        # data['tasas'] -> [1, [ARRAY_DE_MONEDAS]]
        # ARRAY_DE_MONEDAS item -> [0, {DICCIONARIO_DE_ATRIBUTOS}]
        # ATRIBUTO -> [0, valor]
        
        if 'tasas' not in data or len(data['tasas']) < 2:
            return None

        lista_monedas = data['tasas'][1]
        
        tasas_finales = {}
        
        for item_wrapper in lista_monedas:
            # item_wrapper suele ser [0, {datos}]
            if len(item_wrapper) < 2:
                continue
                
            info = item_wrapper[1]
            
            # Extraer código de moneda (ej: USD) y tasa (ej: 410)
            # La estructura interna es "campo": [tipo, valor]
            
            # Obtener Código
            codigo_obj = info.get('codigoMoneda')
            if not codigo_obj or len(codigo_obj) < 2: continue
            codigo = codigo_obj[1]
            
            # Obtener Tasa (Usamos 'tasaEspecial' que coincide con el 410.00 del ejemplo)
            tasa_obj = info.get('tasaEspecial')
            if not tasa_obj or len(tasa_obj) < 2: continue
            valor = float(tasa_obj[1])
            
            # Filtramos solo las principales para no llenar el mensaje
            monedas_interes = ['USD', 'EUR', 'MLC', 'CAD', 'GBP', 'MXN', 'CHF', 'RUB', 'JPY', 'AUD']
            
            if codigo in monedas_interes:
                tasas_finales[codigo] = valor

        add_log_line(f"✅ Tasas BCC obtenidas: {len(tasas_finales)} monedas.")
        return tasas_finales

    except Exception as e:
        add_log_line(f"❌ Error scraping BCC: {e}")
        return None