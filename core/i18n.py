# core/i18n.py

import gettext
import os
from utils.file_manager import get_user_language # Importando la nueva función

# Define la ruta a la carpeta 'locales'
LOCALE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'locales')
DOMAIN = 'bbalert' # Nombre del dominio (el nombre del archivo .po/.mo)

# Inicializador global para la función de traducción
_translators = {}
_default_translator = gettext.NullTranslations()

def get_translator(lang_code: str):
    """
    Obtiene o crea un objeto de traducción para el código de idioma dado.
    """
    global _translators
    if lang_code in _translators:
        return _translators[lang_code]
    
    try:
        # Intenta cargar el traductor para el idioma
        translator = gettext.translation(
            DOMAIN, 
            localedir=LOCALE_DIR, 
            languages=[lang_code]
        )
        _translators[lang_code] = translator
        return translator
    except FileNotFoundError:
        # Si no se encuentra el archivo .mo para el idioma, usa la traducción nula
        # Esto significa que devolverá la cadena original (el texto en español)
        print(f"Advertencia: No se encontró el archivo de traducción para el idioma '{lang_code}'. Usando idioma original.")
        return _default_translator

def _(message: str, chat_id: int = None) -> str:
    """
    Función de traducción principal.
    Si se proporciona un chat_id, usa el idioma del usuario.
    Si no se proporciona, usa el idioma por defecto (español en este caso, 
    ya que el texto fuente está en español).
    """
    if chat_id is not None:
        lang_code = get_user_language(chat_id)
        translator = get_translator(lang_code)
        return translator.gettext(message)
    else:
        # Para mensajes sin un usuario específico (ej. logs, mensajes globales)
        # o cuando se usa la cadena de texto original (español)
        return message

# Exponer la función de traducción con el nombre estándar _ (underscore)
# para que se pueda importar en todos los handlers como: from core.i18n import _