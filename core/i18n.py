# core/i18n.py

import gettext
import os
import logging
from utils.file_manager import get_user_language

# Configurar logging
logger = logging.getLogger(__name__)

# Define la ruta a la carpeta 'locales'
LOCALE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'locales')
DOMAIN = 'bbalert'

# Inicializador global para la función de traducción
_translators = {}
_default_translator = gettext.NullTranslations()


def get_translator(lang_code: str):
    """
    Obtiene o crea un objeto de traducción para el código de idioma dado.
    
    Args:
        lang_code: Código de idioma (ej: 'es', 'en')
        
    Returns:
        Objeto de traducción de gettext o NullTranslations si falla
    """
    global _translators
    
    # Normalizar código de idioma
    lang_code = lang_code.lower().strip() if lang_code else 'es'
    
    if lang_code in _translators:
        return _translators[lang_code]
    
    # Si el idioma es español (idioma base), usar traducción nula
    # ya que los textos fuente ya están en español
    if lang_code in ('es', 'spa', 'spanish'):
        _translators[lang_code] = _default_translator
        return _default_translator
    
    try:
        # Intenta cargar el traductor para el idioma
        # Usamos fallback=True para que si falla, devuelva el texto original
        translator = gettext.translation(
            DOMAIN,
            localedir=LOCALE_DIR,
            languages=[lang_code],
            fallback=True
        )
        
        # Verificar que no sea una traducción nula (fallback)
        if isinstance(translator, gettext.NullTranslations):
            logger.debug(f"Usando traducción nula para idioma '{lang_code}'")
        else:
            logger.info(f"Traductor cargado para idioma '{lang_code}'")
            
        _translators[lang_code] = translator
        return translator
        
    except (FileNotFoundError, UnicodeDecodeError, OSError) as e:
        logger.warning(f"Error cargando traducción para '{lang_code}': {e}. Usando texto original.")
        _translators[lang_code] = _default_translator
        return _default_translator
    except Exception as e:
        logger.error(f"Error inesperado con traducción '{lang_code}': {e}")
        _translators[lang_code] = _default_translator
        return _default_translator


def _(message: str, chat_id: int = None) -> str:
    """
    Función de traducción principal.
    
    Si se proporciona un chat_id, usa el idioma del usuario.
    Si no se proporciona, usa el idioma por defecto (texto original).
    
    Args:
        message: Texto a traducir
        chat_id: ID del chat/usuario para determinar idioma
        
    Returns:
        Texto traducido o original si falla
    """
    # Si no hay chat_id, devolver mensaje original
    if chat_id is None:
        return message
    
    try:
        lang_code = get_user_language(chat_id)
        translator = get_translator(lang_code)
        return translator.gettext(message)
    except Exception as e:
        logger.error(f"Error en traducción para chat_id {chat_id}: {e}")
        return message


# Exponer la función de traducción con el nombre estándar _ (underscore)
# para que se pueda importar en todos los handlers como: from core.i18n import _
