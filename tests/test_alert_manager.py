"""
Tests para el módulo utils/alert_manager.py
"""

import pytest
import json
import os
import tempfile
from unittest.mock import patch, MagicMock
from datetime import datetime


class TestAlertManagerImports:
    """Verificar que las funciones se importan correctamente."""
    
    def test_import_add_price_alert(self):
        """Test que se puede importar add_price_alert."""
        from utils.alert_manager import add_price_alert
        assert callable(add_price_alert)
    
    def test_import_get_user_alerts(self):
        """Test que se puede importar get_user_alerts."""
        from utils.alert_manager import get_user_alerts
        assert callable(get_user_alerts)
    
    def test_import_delete_price_alert(self):
        """Test que se puede importar delete_price_alert."""
        from utils.alert_manager import delete_price_alert
        assert callable(delete_price_alert)
    
    def test_import_delete_all_alerts(self):
        """Test que se puede importar delete_all_alerts."""
        from utils.alert_manager import delete_all_alerts
        assert callable(delete_all_alerts)
    
    def test_import_load_price_alerts(self):
        """Test que se puede importar load_price_alerts."""
        from utils.alert_manager import load_price_alerts
        assert callable(load_price_alerts)


class TestLoadPriceAlerts:
    """Tests para load_price_alerts."""
    
    def test_load_price_alerts_empty(self):
        """Test que retorna dict vacío si no existe archivo."""
        from utils.alert_manager import load_price_alerts
        
        with patch('utils.alert_manager.PRICE_ALERTS_PATH', '/nonexistent/path.json'):
            with patch('os.path.exists', return_value=False):
                result = load_price_alerts()
                assert result == {}
    
    def test_load_price_alerts_returns_dict(self):
        """Test que siempre retorna dict."""
        from utils.alert_manager import load_price_alerts
        
        with patch('utils.alert_manager.PRICE_ALERTS_PATH', '/tmp/test_alerts.json'):
            with patch('os.path.exists', return_value=False):
                result = load_price_alerts()
                assert isinstance(result, dict)


class TestGetUserAlerts:
    """Tests para get_user_alerts."""
    
    def test_get_user_alerts_empty(self):
        """Test que retorna lista vacía si no hay alertas."""
        from utils.alert_manager import get_user_alerts
        
        with patch('utils.alert_manager.load_price_alerts') as mock:
            mock.return_value = {}
            result = get_user_alerts(123)
            assert result == []
    
    def test_get_user_alerts_filters_active(self):
        """Test que solo retorna alertas activas."""
        from utils.alert_manager import get_user_alerts
        
        with patch('utils.alert_manager.load_price_alerts') as mock:
            mock.return_value = {
                '123': [
                    {'alert_id': '1', 'status': 'ACTIVE'},
                    {'alert_id': '2', 'status': 'TRIGGERED'},
                    {'alert_id': '3', 'status': 'ACTIVE'},
                ]
            }
            result = get_user_alerts(123)
            assert len(result) == 2
            assert all(a['status'] == 'ACTIVE' for a in result)


class TestAddPriceAlert:
    """Tests para add_price_alert."""
    
    def test_add_price_alert_creates_alerts(self):
        """Test que crea dos alertas (above y below)."""
        from utils.alert_manager import add_price_alert
        
        with patch('utils.alert_manager.load_price_alerts') as mock_load:
            with patch('utils.alert_manager.save_price_alerts') as mock_save:
                mock_load.return_value = {}
                
                result = add_price_alert(123, 'BTC', 50000)
                
                # Verificar que se llamó a save
                mock_save.assert_called_once()
                
                # Verificar la estructura guardada
                saved_data = mock_save.call_args[0][0]
                assert '123' in saved_data
                assert len(saved_data['123']) == 2


class TestDeletePriceAlert:
    """Tests para delete_price_alert."""
    
    def test_delete_price_alert_exists(self):
        """Test que elimina alerta existente."""
        from utils.alert_manager import delete_price_alert
        
        with patch('utils.alert_manager.load_price_alerts') as mock_load:
            with patch('utils.alert_manager.save_price_alerts') as mock_save:
                mock_load.return_value = {
                    '123': [
                        {'alert_id': 'abc', 'coin': 'BTC'},
                        {'alert_id': 'def', 'coin': 'ETH'},
                    ]
                }
                
                result = delete_price_alert(123, 'abc')
                
                assert result is True
                mock_save.assert_called_once()
    
    def test_delete_price_alert_not_exists(self):
        """Test que retorna False si no existe."""
        from utils.alert_manager import delete_price_alert
        
        with patch('utils.alert_manager.load_price_alerts') as mock_load:
            mock_load.return_value = {
                '123': [
                    {'alert_id': 'abc', 'coin': 'BTC'},
                ]
            }
            
            result = delete_price_alert(123, 'nonexistent')
            
            assert result is False


class TestDeleteAllAlerts:
    """Tests para delete_all_alerts."""
    
    def test_delete_all_alerts(self):
        """Test que elimina todas las alertas."""
        from utils.alert_manager import delete_all_alerts
        
        with patch('utils.alert_manager.load_price_alerts') as mock_load:
            with patch('utils.alert_manager.save_price_alerts') as mock_save:
                mock_load.return_value = {
                    '123': [
                        {'alert_id': '1', 'coin': 'BTC'},
                        {'alert_id': '2', 'coin': 'ETH'},
                    ]
                }
                
                result = delete_all_alerts(123)
                
                assert result is True
                # Verificar que la lista quedó vacía
                saved_data = mock_save.call_args[0][0]
                assert saved_data['123'] == []


class TestCheckPriceAlerts:
    """Tests para check_price_alerts."""
    
    def test_check_price_alerts_trigger_above(self):
        """Test que activa alerta cuando precio sube."""
        from utils.alert_manager import check_price_alerts
        
        with patch('utils.alert_manager.load_price_alerts') as mock:
            mock.return_value = {
                '123': [
                    {
                        'alert_id': '1',
                        'coin': 'BTC',
                        'target_price': 50000,
                        'condition': 'BELOW',
                        'status': 'ACTIVE'
                    }
                ]
            }
            
            # Precio actual mayor que objetivo - NO debe activar (condition BELOW)
            prices = {'BTC': 55000}
            result = check_price_alerts(prices)
            assert len(result) == 0
            
            # Precio actual menor que objetivo - DEBE activar
            prices = {'BTC': 45000}
            result = check_price_alerts(prices)
            assert len(result) == 1
    
    def test_check_price_alerts_trigger_below(self):
        """Test que activa alerta cuando precio baja."""
        from utils.alert_manager import check_price_alerts
        
        with patch('utils.alert_manager.load_price_alerts') as mock:
            mock.return_value = {
                '123': [
                    {
                        'alert_id': '1',
                        'coin': 'BTC',
                        'target_price': 50000,
                        'condition': 'ABOVE',
                        'status': 'ACTIVE'
                    }
                ]
            }
            
            # Precio actual menor que objetivo - NO debe activar
            prices = {'BTC': 45000}
            result = check_price_alerts(prices)
            assert len(result) == 0
            
            # Precio actual mayor que objetivo - DEBE activar
            prices = {'BTC': 55000}
            result = check_price_alerts(prices)
            assert len(result) == 1
    
    def test_check_price_alerts_ignores_inactive(self):
        """Test que ignora alertas no activas."""
        from utils.alert_manager import check_price_alerts
        
        with patch('utils.alert_manager.load_price_alerts') as mock:
            mock.return_value = {
                '123': [
                    {
                        'alert_id': '1',
                        'coin': 'BTC',
                        'target_price': 50000,
                        'condition': 'ABOVE',
                        'status': 'TRIGGERED'  # No activa
                    }
                ]
            }
            
            prices = {'BTC': 55000}
            result = check_price_alerts(prices)
            assert len(result) == 0
