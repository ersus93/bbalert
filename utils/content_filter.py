# utils/content_filter.py

import re
from typing import Dict, Tuple, List
from enum import Enum

class FilterMode(Enum):
    """Modos de filtrado."""
    BLOCK = "block"           # Bloquear entrada completa
    REPLACE = "replace"       # Reemplazar palabra
    PARTIAL_HIDE = "partial"  # Ocultar parcialmente

class ContentFilter:
    """
    Sistema robusto de filtrado con soporte para:
    - Listas negras (palabras bloqueantes)
    - Reemplazos (word -> replacement)
    - Expresiones regulares
    - Contexto sensible (case-insensitive, word boundaries)
    """
    
    def __init__(self):
        self.filters: List[Dict] = []
    
    def add_filter(
        self, 
        pattern: str, 
        mode: FilterMode = FilterMode.BLOCK,
        replacement: str = ""
    ):
        """Añade un filtro con validación."""
        try:
            # Validar regex si es necesario
            if self._is_regex(pattern):
                re.compile(pattern)
            
            self.filters.append({
                'pattern': pattern,
                'mode': mode,
                'replacement': replacement,
                'is_regex': self._is_regex(pattern)
            })
        except re.error as e:
            raise ValueError(f"Regex inválida: {e}")
    
    @staticmethod
    def _is_regex(pattern: str) -> bool:
        """Detecta si un patrón es regex."""
        regex_chars = r'[\[\](){}.*+?^$|\\]'
        return bool(re.search(regex_chars, pattern))
    
    def apply_filters(
        self, 
        content: str,
        filters_list: List[Dict]
    ) -> Tuple[bool, str]:
        """
        Aplica filtros a contenido.
        
        Retorna: (fue_bloqueado, contenido_modificado)
        """
        modified_content = content
        should_block = False
        
        for filter_item in filters_list:
            pattern = filter_item.get('pattern', '')
            mode = FilterMode(filter_item.get('mode', 'block'))
            replacement = filter_item.get('replacement', '')
            is_regex = filter_item.get('is_regex', False)
            
            if mode == FilterMode.BLOCK:
                # Bloquea la entrada si la palabra está presente
                if self._pattern_matches(content, pattern, is_regex):
                    should_block = True
                    break
            
            elif mode == FilterMode.REPLACE:
                # Reemplaza palabra/frase
                modified_content = self._replace_pattern(
                    modified_content, 
                    pattern, 
                    replacement,
                    is_regex
                )
            
            elif mode == FilterMode.PARTIAL_HIDE:
                # Oculta palabra manteniendo espacios
                if replacement == "":
                    # Si no hay reemplazo, ocultar completamente
                    modified_content = self._hide_pattern(
                        modified_content,
                        pattern,
                        is_regex
                    )
        
        return should_block, modified_content
    
    @staticmethod
    def _pattern_matches(
        text: str, 
        pattern: str, 
        is_regex: bool
    ) -> bool:
        """Detecta si un patrón coincide en el texto."""
        text_lower = text.lower()
        pattern_lower = pattern.lower()
        
        if is_regex:
            return bool(re.search(pattern_lower, text_lower, re.IGNORECASE))
        else:
            # Búsqueda exacta (palabra completa)
            return bool(re.search(
                r'\b' + re.escape(pattern_lower) + r'\b',
                text_lower,
                re.IGNORECASE
            ))
    
    @staticmethod
    def _replace_pattern(
        text: str,
        pattern: str,
        replacement: str,
        is_regex: bool
    ) -> str:
        """Reemplaza patrón en texto."""
        if is_regex:
            return re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        else:
            # Reemplazo preservando mayúsculas donde sea posible
            pattern_escaped = re.escape(pattern)
            return re.sub(
                pattern_escaped,
                replacement,
                text,
                flags=re.IGNORECASE
            )
    
    @staticmethod
    def _hide_pattern(
        text: str,
        pattern: str,
        is_regex: bool
    ) -> str:
        """Oculta patrón manteniendo espacios."""
        if is_regex:
            # Reemplazar con la misma cantidad de caracteres de espacio
            def replacer(match):
                return " " * len(match.group(0))
            return re.sub(pattern, replacer, text, flags=re.IGNORECASE)
        else:
            pattern_escaped = re.escape(pattern)
            def replacer(match):
                return " " * len(match.group(0))
            return re.sub(
                pattern_escaped,
                replacer,
                text,
                flags=re.IGNORECASE
            )
    
    @staticmethod
    def validate_filter_config(config: Dict) -> Tuple[bool, str]:
        """Valida configuración de filtro."""
        try:
            pattern = config.get('pattern', '')
            if not pattern:
                return False, "El patrón no puede estar vacío"
            
            mode = config.get('mode', 'block')
            if mode not in ['block', 'replace', 'partial']:
                return False, f"Modo inválido: {mode}"
            
            # Validar regex si es necesario
            if ContentFilter._is_regex(pattern):
                try:
                    re.compile(pattern)
                except re.error as e:
                    return False, f"Regex inválida: {e}"
            
            return True, "OK"
        except Exception as e:
            return False, str(e)
