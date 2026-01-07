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


# # --- INICIO FORMATEO MARKDOWN A HTML TELEGRAM ---
# # 1. Negrita: **texto** -> <b>texto</b>
# content = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', content)                        
# # 2. Encabezados: ### Texto -> <b>Texto</b> (Telegram no soporta h1-h3, usamos negrita)
# content = re.sub(r'#{1,6}\s+(.*?)$', r'<b>\1</b>', content, flags=re.MULTILINE)                        
# # 3. Listas: * item o - item -> • item (Mejora visual)
# content = re.sub(r'(?m)^[\*\-]\s+', '• ', content)                        
#  4. Código inline: `texto` -> <code>texto</code>
# content = re.sub(r'`([^`\n]+)`', r'<code>\1</code>', content)                        
# # 5. Bloques de código: ```python ... ``` -> <pre><code> ... </code></pre>
# # Nota: Esto es básico. Si el modelo envía ```python, Telegram a veces requiere <pre><code class="language-python">
# # Para simplificar y evitar errores de parseo, usamos pre+code genérico:
# content = re.sub(r'```(\w+)?\n(.*?)```', r'<pre><code>\2</code></pre>', content, flags=re.DOTALL)
# # --- FIN FORMATEO ---

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
        f"Eres un Analista Experto en Inversiones Institucionales, Trading y criptomonedas."
        f"Analiza este reporte técnico de {symbol} ({timeframe}) y escribe un Informe Completo en base a los datos del reporte.\n\n"
        
        f"--- REPORTE TÉCNICO ---\n"
        f"{technical_report_text}\n"
        f"--- FIN REPORTE ---\n\n"

        "OBJETIVO: Interpretar los datos y usar una narrativa fluida y facil de entender pero sin dejar de ser profecional\n"
        "Proporciona contexto y explicacion a las siguientes secciones sin repetir los datos del reporte a no ser que sea necesario.\n"
        "No repitas explicaciones en diferentes secciones usa para cada seccion el contexto que lleva.\n"

        "ESTRUCTURA EXACTA:\n"
        "📚 *Analisis y Tendencia*"
        "[pequeño reusmen del reporte y una analisis de la tendencia segun los datos]\n\n"
        
        "📚 *Fuerza de la Tendencia*\n"
        "[].\n\n"
        
        "📚 *Osciladores y Momentum*\n"
        "[].\n\n"
        
        "📚 *Niveles de Soporte y Resistencia*\n"
        "[].\n\n"

        "📚*Riesgo y Oportunidad*Riesgo y Oportunidad*\n"
        "[]\n\n"
        
        "📚 *Recomendación*\n"
        "[]\n\n"

        "📚 *Conclusión*\n"
        "[]\n\n"

        "REGLAS:\n"
        "- Idioma: Español Profesional.\n"
        "- Basa tu análisis SOLO en el texto proporcionado.\n"
        "- Máximo 1800 caracteres."
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
        "max_tokens": 2000
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