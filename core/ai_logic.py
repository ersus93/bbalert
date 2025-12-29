import requests
import json
import math
from core.config import GROQ_API_KEY

def clean_data(data):
    """
    Limpia el diccionario de valores NaN (Not a Number) o Infinite.
    JSON estándar NO soporta NaN, y enviarlo causa error 400 Bad Request.
    """
    cleaned = {}
    for k, v in data.items():
        # Verificamos si es un número (float o int)
        if isinstance(v, (float, int)):
            # Si es NaN (ej: fallo de cálculo) o Infinito
            if math.isnan(v) or math.isinf(v):
                cleaned[k] = "N/A"  # Lo pasamos como texto para que la IA entienda que falta
            else:
                cleaned[k] = round(v, 4)  # Redondeamos para ahorrar tokens y limpiar formato
        else:
            cleaned[k] = v
    return cleaned

def get_groq_crypto_analysis(symbol, timeframe, technical_report_text):
    """
    Recibe el TEXTO del reporte (lo que ve el usuario) y genera una narrativa.
    """
    if not GROQ_API_KEY:
        return "⚠️ Error: Falta configurar la GROQ_API_KEY."

    # Prompt Narrativo basado en el texto del mensaje
    prompt = (
        f"Eres un Analista Senior de Inversiones Institucionales. "
        f"Analiza este reporte técnico de {symbol} ({timeframe}) y escribe un MEMORANDO ESTRATÉGICO.\n\n"
        
        f"--- REPORTE TÉCNICO ---\n"
        f"{technical_report_text}\n"
        f"--- FIN REPORTE ---\n\n"

        "OBJETIVO: Interpretar los datos (Precio, RSI, MACD, Zonas, Niveles) y crear una narrativa fluida. No hagas listas simples.\n\n"

        "ESTRUCTURA EXACTA:\n"
        "📚 **Contexto de Mercado**\n"
        "[Integra precio, score y volatilidad (ATR) en un párrafo narrativo sobre el sentimiento actual].\n\n"
        
        "📚 **Interpretación Técnica**\n"
        "[Analiza la confluencia de indicadores. ¿Qué dicen el RSI y el MACD juntos? ¿Confirman la tendencia?].\n\n"
        
        "📚 **Niveles y Estructura**\n"
        "[Evalúa la posición respecto a los Pivotes, Ichimoku o Fibonacci mencionados en el reporte].\n\n"
        
        "📚 **Veredicto y Gestión**\n"
        "[Conclusión directa de compra/venta/espera y un consejo de riesgo].\n\n"

        "REGLAS:\n"
        "- Idioma: Español Profesional.\n"
        "- Basa tu análisis SOLO en el texto proporcionado.\n"
        "- Máximo 1500 caracteres."
    )

    url = "https://api.groq.com/openai/v1/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.6,
        "max_tokens": 1000
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        response.raise_for_status()
        result = response.json()
        return result['choices'][0]['message']['content']

    except Exception as e:
        print(f"❌ Error interno IA: {e}")
        return "⚠️ Ocurrió un error al procesar el análisis."