# utils/image_generator.py

from PIL import Image, ImageDraw, ImageFont
from datetime import datetime
import io
import os

from utils.tasa_manager import load_eltoque_history
from core.config import TEMPLATE_PATH # Importamos la ruta desde config


# Configuración de estilo (Azul oscuro tomado de tu imagen)
COLOR_TINTA = "#0B1E38"

def generar_imagen_tasas_eltoque():
    """
    Carga la plantilla 'img.jpg' desde la carpeta data y superpone
    las tasas de cambio y la fecha en el área en blanco.
    """
    # 1. Cargar datos del historial
    tasas = load_eltoque_history()
    if not tasas:
        print("⚠️ No hay datos de tasas disponibles.")
        return None

    # 2. Cargar la Plantilla
    try:
        # Usamos .convert("RGBA") para asegurar compatibilidad al dibujar
        if not os.path.exists(TEMPLATE_PATH):
             print(f"❌ ERROR: No se encuentra la plantilla en: {TEMPLATE_PATH}")
             return None
             
        img = Image.open(TEMPLATE_PATH).convert("RGBA")
        W, H = img.size # Detectamos dimensiones automáticamente
    except Exception as e:
        print(f"❌ Error al abrir la imagen plantilla: {e}")
        return None

    draw = ImageDraw.Draw(img)

    # 3. Configuración de Fuentes
    # Ajustamos el tamaño relativo al alto de la imagen para que se vea bien
    try:
        font_path = "arial.ttf" if os.name == 'nt' else "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        # Si tienes una fuente personalizada en data/, úsala: os.path.join(DATA_DIR, "TuFuente.ttf")
        
        # --- CAMBIOS AQUÍ ---
        # Se redujeron los multiplicadores para que el texto sea más pequeño
        # Antes era 0.045, ahora 0.032
        font_lg = ImageFont.truetype(font_path, int(H * 0.032)) # Para el nombre de la moneda
        # Antes era 0.045, ahora 0.032
        font_val = ImageFont.truetype(font_path, int(H * 0.032)) # Para el valor numérico
        # Antes era 0.025, ahora 0.020
        font_sm = ImageFont.truetype(font_path, int(H * 0.021)) # Para el footer (fecha)
        # --------------------
        
    except OSError:
        font_lg = font_val = font_sm = ImageFont.load_default()

    # --- 4. DIBUJANDO EL CONTENIDO ---

    # Definimos el área de trabajo basada en tu plantilla visualmente:
    # El encabezado "Tasas de cambio" termina aprox al 38% de la altura.
    # Las líneas de abajo empiezan aprox al 80% de la altura.
    start_y = H * 0.48 
    
    # Lista de monedas a mostrar
    monedas_orden = ['EUR', 'USD', 'MLC', 'BTC', 'TRX', 'USDT_TRC20']
    
    # Calculamos el espacio entre líneas dinámicamente según cuántas monedas hay
    # Espacio disponible aprox 40% de la altura total
    espacio_disponible = H * 0.28
    row_height = espacio_disponible / (len(monedas_orden) + 1)

    for i, moneda_key in enumerate(monedas_orden):
        tasa_val = tasas.get('ECU' if moneda_key == 'EUR' else moneda_key)
        
        if tasa_val:
            y_pos = start_y + (i * row_height)
            
            moneda_display = 'USDT' if moneda_key == 'USDT_TRC20' else moneda_key
            valor_str = f"{tasa_val:,.2f} CUP"

            # Dibujar Moneda (Alineada a la izquierda, con margen del 20% del ancho)
            # El margen izquierdo del pan parece estar al 20%
            draw.text((W * 0.30, y_pos), f"{moneda_display}:", fill=COLOR_TINTA, anchor="lm", font=font_lg)
            
            # Dibujar Valor (Alineada a la derecha, con margen del 20% del ancho)
            draw.text((W * 0.70, y_pos), valor_str, fill=COLOR_TINTA, anchor="rm", font=font_val)

    # --- 5. FOOTER (Fecha y Fuente) ---
    # Colocamos esto justo encima de las líneas decorativas inferiores (aprox 82% de altura)
    fecha_gen = datetime.now().strftime('%Y-%m-%d %H:%M')
    footer_text = f"Actualizado: {fecha_gen}\nFuente: elTOQUE"
    
    # Posición Y: Un poco más abajo de la última moneda, cerca de las líneas del dibujo
    footer_y = H * 0.75
    draw.text((W / 2, footer_y), footer_text, fill=COLOR_TINTA, anchor="mm", font=font_sm)

    # 6. Guardar y retornar
    bio = io.BytesIO()
    img.save(bio, 'PNG')
    bio.seek(0)
    return bio