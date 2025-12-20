# utils/cadeca_scraper.py

import requests
import urllib3
from bs4 import BeautifulSoup
from utils.file_manager import add_log_line

# Desactivar warnings de SSL inseguro
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def obtener_tasas_cadeca():
    URL = "https://www.cadeca.cu/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    try:
        # verify=False ayuda con servidores .cu lentos en handshake SSL
        # timeout reducido a 7s para conectar, 7s para leer
        response = requests.get(URL, headers=headers, timeout=(7, 7), verify=False)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')
        contenedor_casas = soup.find('div', id='quicktabs-tabpage-m_dulo_tasa_de_cambio-0')

        if not contenedor_casas:
            return None

        tabla = contenedor_casas.find('table')
        if not tabla:
            return None

        resultados = {}
        filas = tabla.find('tbody').find_all('tr')

        for fila in filas:
            columnas = fila.find_all('td')
            if len(columnas) >= 4:
                moneda = columnas[1].get_text(strip=True)
                compra_txt = columnas[2].get_text(strip=True)
                venta_txt = columnas[3].get_text(strip=True)

                try:
                    compra_val = float(compra_txt)
                    venta_val = float(venta_txt)
                    resultados[moneda] = {'compra': compra_val, 'venta': venta_val}
                except ValueError:
                    continue
        
        return resultados if resultados else None

    except Exception as e:
        # Loguear solo el mensaje corto para no llenar el log
        add_log_line(f"❌ Error CADECA: {str(e)[:100]}") 
        return None