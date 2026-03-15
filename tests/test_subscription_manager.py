# tests/test_subscription_manager.py
"""
Tests para el módulo utils/subscription_manager.py
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock


class TestSubscriptionManagerImports:
    """Verificar que las funciones se importan correctamente."""
    
    def test_import_check_feature_access(self):
        """Test que se puede importar check_feature_access."""
        from utils.subscription_manager import check_feature_access
        assert callable(check_feature_access)
    
    def test_import_registrar_uso_comando(self):
        """Test que se puede importar registrar_uso_comando."""
        from utils.subscription_manager import registrar_uso_comando
        assert callable(registrar_uso_comando)
    
    def test_import_add_subscription_days(self):
        """Test que se puede importar add_subscription_days."""
        from utils.subscription_manager import add_subscription_days
        assert callable(add_subscription_days)


class TestCheckFeatureAccess:
    """Tests para check_feature_access."""
    
    @patch('utils.subscription_manager.ADMIN_CHAT_IDS', [123])
    def test_admin_has_access(self):
        """Test que admins siempre tienen acceso."""
        from utils.subscription_manager import check_feature_access
        
        with patch('utils.subscription_manager.obtener_datos_usuario_seguro') as mock:
            result, msg = check_feature_access(123, 'ver_limit')
            assert result is True
    
    def test_unknown_user_no_access(self):
        """Test que usuario desconocido no tiene acceso."""
        from utils.subscription_manager import check_feature_access
        
        with patch('utils.subscription_manager.obtener_datos_usuario_seguro') as mock:
            mock.return_value = None
            
            result, msg = check_feature_access(999, 'ver_limit')
            
            assert result is False
            assert "no registrado" in msg.lower()
    
    def test_free_user_ver_limit(self):
        """Test límite para usuario free."""
        from utils.subscription_manager import check_feature_access
        
        mock_user = {
            'subscriptions': {
                'watchlist_bundle': {'active': False, 'expires': None}
            },
            'daily_usage': {
                'date': datetime.now().strftime('%Y-%m-%d'),
                'ver': 8
            }
        }
        
        with patch('utils.subscription_manager.obtener_datos_usuario_seguro') as mock:
            mock.return_value = mock_user
            
            result, msg = check_feature_access(456, 'ver_limit')
            
            assert result is False
            assert "límite" in msg.lower()
    
    def test_premium_user_ver_limit(self):
        """Test que usuario premium tiene más límite."""
        from utils.subscription_manager import check_feature_access
        
        future_date = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S')
        
        mock_user = {
            'subscriptions': {
                'watchlist_bundle': {'active': True, 'expires': future_date}
            },
            'daily_usage': {
                'date': datetime.now().strftime('%Y-%m-%d'),
                'ver': 30
            }
        }
        
        with patch('utils.subscription_manager.obtener_datos_usuario_seguro') as mock:
            mock.return_value = mock_user
            
            result, msg = check_feature_access(456, 'ver_limit')
            
            assert result is True


class TestRegistrarUsoComando:
    """Tests para registrar_uso_comando."""
    
    def test_registrar_uso_comando(self):
        """Test que registra uso de comando."""
        from utils.subscription_manager import registrar_uso_comando
        
        with patch('utils.subscription_manager.cargar_usuarios') as mock_load:
            with patch('utils.subscription_manager.guardar_usuarios') as mock_save:
                mock_load.return_value = {
                    '123': {
                        'daily_usage': {
                            'date': datetime.now().strftime('%Y-%m-%d'),
                            'ver': 0
                        }
                    }
                }
                
                registrar_uso_comando(123, 'ver')
                
                mock_save.assert_called_once()
    
    def test_registrar_uso_creates_daily_usage(self):
        """Test que crea daily_usage si no existe."""
        from utils.subscription_manager import registrar_uso_comando
        
        with patch('utils.subscription_manager.cargar_usuarios') as mock_load:
            with patch('utils.subscription_manager.guardar_usuarios') as mock_save:
                mock_load.return_value = {'123': {}}
                
                registrar_uso_comando(123, 'ver')
                
                # Verificar que se creó la estructura
                call_args = mock_save.call_args[0][0]
                assert 'daily_usage' in call_args['123']


class TestAddSubscriptionDays:
    """Tests para add_subscription_days."""
    
    def test_add_subscription_days(self):
        """Test que añade días de suscripción."""
        from utils.subscription_manager import add_subscription_days
        
        with patch('utils.subscription_manager.cargar_usuarios') as mock_load:
            with patch('utils.subscription_manager.guardar_usuarios') as mock_save:
                mock_load.return_value = {
                    '123': {
                        'subscriptions': {
                            'ta_vip': {'active': False, 'expires': None}
                        }
                    }
                }
                
                result = add_subscription_days(123, 'ta_vip', 30)
                
                assert result is True
                mock_save.assert_called_once()
    
    def test_add_subscription_days_calculates_expiry(self):
        """Test que calcula fecha de expiración correcta."""
        from utils.subscription_manager import add_subscription_days
        
        with patch('utils.subscription_manager.cargar_usuarios') as mock_load:
            with patch('utils.subscription_manager.guardar_usuarios') as mock_save:
                mock_load.return_value = {'123': {'subscriptions': {}}}
                
                add_subscription_days(123, 'ta_vip', 30)
                
                # Verificar que se guardó con fecha futura
                call_args = mock_save.call_args[0][0]
                expires = call_args['123']['subscriptions']['ta_vip']['expires']
                
                # Verificar formato
                exp_date = datetime.strptime(expires, '%Y-%m-%d %H:%M:%S')
                assert exp_date > datetime.now()


class TestToggleHbdAlertStatus:
    """Tests para toggle_hbd_alert_status."""
    
    def test_toggle_hbd_alert_status(self):
        """Test que toggle cambia estado."""
        from utils.subscription_manager import toggle_hbd_alert_status
        
        with patch('utils.subscription_manager.cargar_usuarios') as mock_load:
            with patch('utils.subscription_manager.guardar_usuarios') as mock_save:
                mock_load.return_value = {
                    '123': {'hbd_alerts_enabled': True}
                }
                
                result = toggle_hbd_alert_status(123)
                
                assert result is False  # Se toggló a False
                mock_save.assert_called_once()


class TestGetHbdAlertRecipients:
    """Tests para get_hbd_alert_recipients."""
    
    def test_get_hbd_alert_recipients(self):
        """Test que retorna usuarios con alertas activas."""
        from utils.subscription_manager import get_hbd_alert_recipients
        
        with patch('utils.subscription_manager.cargar_usuarios') as mock:
            mock.return_value = {
                '123': {'hbd_alerts_enabled': True},
                '456': {'hbd_alerts_enabled': False},
                '789': {},  # Por defecto True
            }
            
            result = get_hbd_alert_recipients()
            
            assert 123 in result
            assert 789 in result
            assert 456 not in result
