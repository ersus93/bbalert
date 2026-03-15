# tests/test_user_data.py
"""
Tests para el módulo utils/user_data.py
"""

import pytest
import json
import os
import tempfile
from unittest.mock import patch, MagicMock
from datetime import datetime

# Tests para funciones de user_data
# Nota: Estos tests son unitarios, no requieren el bot real


class TestUserDataImports:
    """Verificar que las funciones se importan correctamente."""
    
    def test_import_cargar_usuarios(self):
        """Test que se puede importar cargar_usuarios."""
        from utils.user_data import cargar_usuarios
        assert callable(cargar_usuarios)
    
    def test_import_guardar_usuarios(self):
        """Test que se puede importar guardar_usuarios."""
        from utils.user_data import guardar_usuarios
        assert callable(guardar_usuarios)
    
    def test_import_obtener_datos_usuario(self):
        """Test que se puede importar obtener_datos_usuario."""
        from utils.user_data import obtener_datos_usuario
        assert callable(obtener_datos_usuario)
    
    def test_import_registrar_usuario(self):
        """Test que se puede importar registrar_usuario."""
        from utils.user_data import registrar_usuario
        assert callable(registrar_usuario)


class TestUserDataFunctions:
    """Tests funcionales para user_data."""
    
    @patch('utils.user_data.USUARIOS_PATH', '/tmp/test_users.json')
    @patch('utils.user_data.cargar_usuarios')
    def test_obtener_datos_usuario_returns_dict(self, mock_cargar):
        """Test que obtener_datos_usuario retorna dict."""
        from utils.user_data import obtener_datos_usuario
        
        mock_cargar.return_value = {'123': {'name': 'test'}}
        result = obtener_datos_usuario(123)
        
        assert isinstance(result, dict)
    
    @patch('utils.user_data.USUARIOS_PATH', '/tmp/test_users.json')  
    @patch('utils.user_data.cargar_usuarios')
    def test_obtener_datos_usuario_none_for_unknown(self, mock_cargar):
        """Test que retorna dict vacío para usuario unknown."""
        from utils.user_data import obtener_datos_usuario
        
        mock_cargar.return_value = {}
        result = obtener_datos_usuario(999)
        
        assert isinstance(result, dict)


class TestLanguageFunctions:
    """Tests para funciones de idioma."""
    
    def test_get_user_language_default(self):
        """Test que idioma por defecto es español."""
        from utils.user_data import get_user_language
        
        with patch('utils.user_data.cargar_usuarios') as mock:
            mock.return_value = {}
            result = get_user_language(123)
            assert result == 'es'
    
    def test_get_user_language_english(self):
        """Test que puede retornar inglés."""
        from utils.user_data import get_user_language
        
        with patch('utils.user_data.cargar_usuarios') as mock:
            mock.return_value = {'123': {'language': 'en'}}
            result = get_user_language(123)
            assert result == 'en'


class TestMonedasFunctions:
    """Tests para funciones de monedas."""
    
    def test_obtener_monedAS_usuario_default(self):
        """Test que lista de monedas por defecto es vacía."""
        from utils.user_data import obtener_monedAS_usuario
        
        with patch('utils.user_data.cargar_usuarios') as mock:
            mock.return_value = {}
            result = obtener_monedAS_usuario(123)
            assert result == []
    
    def test_obtener_monedAS_usuario_with_coins(self):
        """Test que retorna monedas configuradas."""
        from utils.user_data import obtener_monedAS_usuario
        
        with patch('utils.user_data.cargar_usuarios') as mock:
            mock.return_value = {'123': {'monedas': ['BTC', 'ETH']}}
            result = obtener_monedAS_usuario(123)
            assert result == ['BTC', 'ETH']


class TestMetaFunctions:
    """Tests para funciones de meta."""
    
    def test_get_user_meta_default_value(self):
        """Test que get_user_meta retorna valor por defecto."""
        from utils.user_data import get_user_meta
        
        with patch('utils.user_data.cargar_usuarios') as mock:
            mock.return_value = {}
            result = get_user_meta(123, 'nonexistent_key', 'default_value')
            assert result == 'default_value'
    
    def test_get_user_meta_existing(self):
        """Test que retorna valor existente."""
        from utils.user_data import get_user_meta
        
        with patch('utils.user_data.cargar_usuarios') as mock:
            mock.return_value = {'123': {'meta': {'key': 'value'}}}
            result = get_user_meta(123, 'key')
            assert result == 'value'
