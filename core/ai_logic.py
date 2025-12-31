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

def escape_markdown(text):
    """
    Escapa o elimina caracteres que rompen el ParseMode.MARKDOWN de Telegram.
    """
    if not text:
        return ""
    # Eliminamos caracteres que suelen causar errores si la IA los usa como listas
    # o si olvida cerrarlos (como * o _)
    return text.replace("*", "").replace("_", "").replace("`", "").replace("[", "(").replace("]", ")")

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

        "OBJETIVO: Interpretar los datos (Precio, RSI, MACD, Zonas, Niveles y lo demas del reporte tecnico) para crear una narrativa fluida. No hagas listas simples.\n\n"

        "ESTRUCTURA EXACTA:\n"
        "📚 *Contexto de Mercado*\n"
        "[Integra precio, score y volatilidad (ATR) en un párrafo narrativo sobre el significado y sentimiento actual].\n\n"
        
        "📚 *Interpretación Técnica*\n"
        "[Analiza la confluencia de indicadores. ¿Qué dicen y significan la tabla de indicadores y el Diagnóstico de Momentum juntos?, ¿Confirman la tendencia?].\n\n"
        
        "📚 *Niveles y Estructura*\n"
        "[Evalúa la posición respecto a los Pivotes, Ichimoku o Fibonacci mencionados en el reporte].\n\n"
        
        "📚 *Veredicto y Gestión*\n"
        "[Conclusión directa de compra/venta/espera y un consejo de riesgo, tambien puedes opinar algun criterio extra].\n\n"

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
    


def get_groq_weather_advice(weather_report_text):
    """
    Analiza el reporte del clima y genera recomendaciones breves.
    """
    if not GROQ_API_KEY:
        return "⚠️ (IA no configurada)"

    # Prompt especializado para meteorología
    prompt = (
        "Eres un Asistente Meteorológico personal, amable y práctico. "
        "Tu tarea es leer el siguiente reporte del clima y dar consejos breves, informativos y útiles.\n\n"
        
        f"REPORTE:\n{weather_report_text}\n\n"
        
        "Instrucciones:\n"
        "Responde usando listas o parafo, lo que consideres que es major, pero se atento y basa tu respuesta en los datos del mensaje"
        "analiza la hora local no tienes que repetirala es solo para que bases tu respuesta segun el momento para evitar que digas sal a tomar el sol si es de noche"
        "Recomienda qué vestir (ej. paraguas, abrigo, ropa ligera etc... segun las condiciones del clima)."
        "Hogar/Coche Consejos prácticos (ej. cerrar ventanas, lavar coche, regar plantas, cosas asi se creativo)."
        "Salud/Aire Libre: analiza si es buen momento para salir, a realizar acividades, explica la respuesta.\n"
        
        "Reglas:\n"
        "- Usa emojis.\n"
        "- NO repitas los datos numéricos (temperatura, humedad) a menos que sea para explicar el consejo.\n"
        "- Sé muy conciso (máximo 1000 caracteres).\n"
        "- Tono: Informativo y cercano."
    )

    url = "https://api.groq.com/openai/v1/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "llama-3.3-70b-versatile", # O el modelo que prefieras usar
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.5, # Un poco más creativo que en trading, pero no mucho
        "max_tokens": 1000
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        response.raise_for_status()
        data = response.json()
        raw_content = data['choices'][0]['message']['content'].strip()
        return escape_markdown(raw_content)
    except Exception as e:
        print(f"❌ Error Groq Weather: {e}")
        return "⚠️ No pude generar consejos inteligentes hoy, pero cuídate mucho."