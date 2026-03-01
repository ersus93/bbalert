# tests/test_command_tracking_integration.py
"""
Tests de integración para el sistema de tracking de comandos.

Verifica que:
- registrar_uso_comando incrementa correctamente los contadores
- Los datos se almacenan correctamente en daily_usage
- El dashboard de admin puede leer y agregar estos datos
- last_seen se actualiza con cada uso de comando
"""

import unittest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, call
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestRegistrarUsoComando(unittest.TestCase):
    """Verifica que registrar_uso_comando funciona correctamente."""

    @patch('utils.file_manager.guardar_usuarios')
    @patch('utils.file_manager.cargar_usuarios')
    @patch('utils.file_manager.obtener_datos_usuario_seguro')
    def test_registrar_uso_comando_increments_counter(self, mock_obtener, mock_cargar, mock_guardar):
        """
        Verifica que registrar_uso_comando incrementa el contador del comando.
        
        BUG-3/4: Asegura que el contador de uso diario se incrementa correctamente
        y que last_seen se actualiza.
        """
        from utils.file_manager import registrar_uso_comando
        
        today_str = datetime.now().strftime('%Y-%m-%d')
        test_user_id = 'USER_001'
        
        # Mock de usuario con daily_usage existente
        mock_usuarios = {
            test_user_id: {
                'chat_id': test_user_id,
                'monedas': ['BTC'],
                'daily_usage': {
                    'date': today_str,
                    'ver': 3,
                    'tasa': 1,
                    'ta': 0,
                    'temp_changes': 0,
                    'reminders': 0,
                    'weather': 0,
                    'btc': 0,
                },
                'last_seen': (datetime.now() - timedelta(hours=2)).strftime('%Y-%m-%d %H:%M:%S'),
                'registered_at': (datetime.now() - timedelta(days=5)).strftime('%Y-%m-%d %H:%M:%S'),
            }
        }
        
        mock_cargar.return_value = mock_usuarios
        mock_obtener.return_value = mock_usuarios[test_user_id]
        
        # Ejecutar: registrar uso del comando 'ver'
        registrar_uso_comando(test_user_id, 'ver')
        
        # Verificar que guardar_usuarios fue llamado
        mock_guardar.assert_called_once()
        
        # Verificar que los datos guardados tienen el contador incrementado
        saved_data = mock_guardar.call_args[0][0]
        self.assertIn(test_user_id, saved_data)
        
        user_data = saved_data[test_user_id]
        self.assertIn('daily_usage', user_data)
        
        # El contador 'ver' debe haberse incrementado de 3 a 4
        self.assertEqual(user_data['daily_usage']['ver'], 4)
        # Los demás contadores no deben cambiar
        self.assertEqual(user_data['daily_usage']['tasa'], 1)
        self.assertEqual(user_data['daily_usage']['ta'], 0)

    @patch('utils.file_manager.guardar_usuarios')
    @patch('utils.file_manager.cargar_usuarios')
    @patch('utils.file_manager.obtener_datos_usuario_seguro')
    def test_registrar_uso_comando_updates_last_seen(self, mock_obtener, mock_cargar, mock_guardar):
        """
        Verifica que registrar_uso_comando actualiza last_seen.
        
        MEJORA: Cada uso de comando debe actualizar last_seen para
        un seguimiento preciso de la actividad del usuario.
        """
        from utils.file_manager import registrar_uso_comando
        
        today_str = datetime.now().strftime('%Y-%m-%d')
        test_user_id = 'USER_002'
        old_last_seen = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
        
        mock_usuarios = {
            test_user_id: {
                'chat_id': test_user_id,
                'monedas': ['EUR'],
                'daily_usage': {
                    'date': today_str,
                    'ver': 0,
                    'tasa': 0,
                    'ta': 0,
                    'temp_changes': 0,
                    'reminders': 0,
                    'weather': 0,
                    'btc': 0,
                },
                'last_seen': old_last_seen,
            }
        }
        
        mock_cargar.return_value = mock_usuarios
        mock_obtener.return_value = mock_usuarios[test_user_id]
        
        # Ejecutar
        registrar_uso_comando(test_user_id, 'tasa')
        
        # Verificar que last_seen fue actualizado
        saved_data = mock_guardar.call_args[0][0]
        user_data = saved_data[test_user_id]
        
        new_last_seen = user_data['last_seen']
        self.assertNotEqual(new_last_seen, old_last_seen)
        
        # Verificar que la nueva fecha es reciente (dentro de los últimos segundos)
        now = datetime.now()
        new_last_seen_dt = datetime.strptime(new_last_seen, '%Y-%m-%d %H:%M:%S')
        diff_seconds = (now - new_last_seen_dt).total_seconds()
        self.assertLess(diff_seconds, 5, "last_seen debe ser actualizado a la fecha/hora actual")

    @patch('utils.file_manager.guardar_usuarios')
    @patch('utils.file_manager.cargar_usuarios')
    @patch('utils.file_manager.obtener_datos_usuario_seguro')
    def test_registrar_uso_comando_creates_key_if_missing(self, mock_obtener, mock_cargar, mock_guardar):
        """
        Verifica que registrar_uso_comando crea la clave si no existe.
        """
        from utils.file_manager import registrar_uso_comando
        
        today_str = datetime.now().strftime('%Y-%m-%d')
        test_user_id = 'USER_003'
        
        # Usuario sin la clave 'ta' en daily_usage
        mock_usuarios = {
            test_user_id: {
                'chat_id': test_user_id,
                'daily_usage': {
                    'date': today_str,
                    'ver': 2,
                    # 'ta' no existe
                },
            }
        }
        
        mock_cargar.return_value = mock_usuarios
        mock_obtener.return_value = mock_usuarios[test_user_id]
        
        # Ejecutar comando 'ta' que no existe en el diccionario
        registrar_uso_comando(test_user_id, 'ta')
        
        # Verificar que se creó la clave con valor 1
        saved_data = mock_guardar.call_args[0][0]
        user_data = saved_data[test_user_id]
        self.assertEqual(user_data['daily_usage']['ta'], 1)


class TestDashboardReadsDailyUsage(unittest.TestCase):
    """
    Verifica que el dashboard de admin puede leer y agregar los datos de daily_usage.
    
    Esta clase simula la lógica de lectura que usa el dashboard en handlers/admin.py
    """

    def _aggregate_daily_usage(self, usuarios, now=None):
        """
        Simula la lógica del dashboard para agregar daily_usage.
        
        Retorna: dict con usage_breakdown y total_usage_today
        """
        if now is None:
            now = datetime.now()
        
        today_str = now.strftime('%Y-%m-%d')
        usage_breakdown = {
            'ver': 0, 'tasa': 0, 'ta': 0, 'temp_changes': 0,
            'reminders': 0, 'weather': 0, 'btc': 0
        }
        total_usage_today = 0
        
        for uid, u in usuarios.items():
            daily = u.get('daily_usage', {})
            if daily.get('date') == today_str:
                for cmd, count in daily.items():
                    if cmd != 'date' and isinstance(count, int):
                        usage_breakdown[cmd] = usage_breakdown.get(cmd, 0) + count
                        total_usage_today += count
        
        return {
            'usage_breakdown': usage_breakdown,
            'total_usage_today': total_usage_today
        }

    def test_dashboard_aggregates_multiple_users(self):
        """
        Verifica que el dashboard puede agregar daily_usage de múltiples usuarios.
        """
        today_str = datetime.now().strftime('%Y-%m-%d')
        
        usuarios = {
            'USER_001': {
                'daily_usage': {
                    'date': today_str,
                    'ver': 5,
                    'tasa': 2,
                    'ta': 1
                }
            },
            'USER_002': {
                'daily_usage': {
                    'date': today_str,
                    'ver': 3,
                    'tasa': 1,
                    'ta': 0
                }
            },
            'USER_003': {
                'daily_usage': {
                    'date': today_str,
                    'ver': 10,
                    'btc': 2
                }
            }
        }
        
        result = self._aggregate_daily_usage(usuarios)
        
        # Verificar agregación
        self.assertEqual(result['usage_breakdown']['ver'], 18)  # 5 + 3 + 10
        self.assertEqual(result['usage_breakdown']['tasa'], 3)  # 2 + 1 + 0
        self.assertEqual(result['usage_breakdown']['ta'], 1)    # 1 + 0 + 0
        self.assertEqual(result['usage_breakdown']['btc'], 2)   # 0 + 0 + 2
        self.assertEqual(result['total_usage_today'], 24)       # 18 + 3 + 1 + 2

    def test_dashboard_ignores_old_dates(self):
        """
        Verifica que el dashboard ignora daily_usage de días anteriores.
        """
        today_str = datetime.now().strftime('%Y-%m-%d')
        yesterday_str = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        
        usuarios = {
            'USER_001': {
                'daily_usage': {
                    'date': today_str,
                    'ver': 5
                }
            },
            'USER_002': {
                'daily_usage': {
                    'date': yesterday_str,  # Día anterior - debe ignorarse
                    'ver': 100
                }
            }
        }
        
        result = self._aggregate_daily_usage(usuarios)
        
        # Solo debe contar el usuario de hoy
        self.assertEqual(result['usage_breakdown']['ver'], 5)
        self.assertEqual(result['total_usage_today'], 5)

    def test_dashboard_counts_all_numeric_keys(self):
        """
        Verifica que el dashboard cuenta todos los valores numericos excepto 'date'.
        """
        today_str = datetime.now().strftime('%Y-%m-%d')
        
        usuarios = {
            'USER_001': {
                'daily_usage': {
                    'date': today_str,
                    'ver': 5,
                    'extra_key': 10  # Tambien se cuenta si es numerico
                }
            }
        }
        
        result = self._aggregate_daily_usage(usuarios)
        
        # Debe contar 'ver' y 'extra_key'
        self.assertEqual(result['usage_breakdown']['ver'], 5)
        self.assertEqual(result['usage_breakdown']['extra_key'], 10)
        self.assertEqual(result['total_usage_today'], 15)


class TestEndToEndCommandTracking(unittest.TestCase):
    """
    Test end-to-end: desde el registro del comando hasta la lectura del dashboard.
    """

    @patch('utils.file_manager.guardar_usuarios')
    @patch('utils.file_manager.cargar_usuarios')
    @patch('utils.file_manager.obtener_datos_usuario_seguro')
    def test_full_flow_command_to_dashboard(self, mock_obtener, mock_cargar, mock_guardar):
        """
        Flujo completo: registrar comando y verificar que el dashboard puede leerlo.
        """
        from utils.file_manager import registrar_uso_comando
        
        today_str = datetime.now().strftime('%Y-%m-%d')
        test_user_id = 'USER_004'
        
        # Estado inicial del usuario
        initial_data = {
            test_user_id: {
                'chat_id': test_user_id,
                'monedas': ['USD'],
                'daily_usage': {
                    'date': today_str,
                    'ver': 2,
                    'tasa': 1,
                    'ta': 0,
                    'temp_changes': 0,
                    'reminders': 0,
                    'weather': 0,
                    'btc': 0,
                },
                'last_seen': (datetime.now() - timedelta(hours=1)).strftime('%Y-%m-%d %H:%M:%S'),
            }
        }
        
        mock_cargar.return_value = initial_data
        mock_obtener.return_value = initial_data[test_user_id]
        
        # Simular múltiples usos de comandos
        registrar_uso_comando(test_user_id, 'ver')
        registrar_uso_comando(test_user_id, 'ver')
        registrar_uso_comando(test_user_id, 'tasa')
        
        # Obtener los datos guardados
        saved_calls = mock_guardar.call_args_list
        self.assertEqual(len(saved_calls), 3)
        
        # Verificar el estado final
        final_data = saved_calls[-1][0][0]
        user_data = final_data[test_user_id]
        
        # Verificar contadores
        self.assertEqual(user_data['daily_usage']['ver'], 4)   # 2 + 2
        self.assertEqual(user_data['daily_usage']['tasa'], 2)  # 1 + 1
        
        # Verificar que el dashboard puede leer estos datos
        dashboard = self._simulate_dashboard_read(final_data)
        self.assertEqual(dashboard['ver'], 4)
        self.assertEqual(dashboard['tasa'], 2)
        self.assertEqual(dashboard['total'], 6)

    def _simulate_dashboard_read(self, usuarios):
        """Simula cómo el dashboard lee los datos de daily_usage."""
        today_str = datetime.now().strftime('%Y-%m-%d')
        result = {'ver': 0, 'tasa': 0, 'ta': 0, 'total': 0}
        
        for uid, u in usuarios.items():
            daily = u.get('daily_usage', {})
            if daily.get('date') == today_str:
                for cmd in ['ver', 'tasa', 'ta']:
                    count = daily.get(cmd, 0)
                    result[cmd] += count
                    result['total'] += count
        
        return result


if __name__ == '__main__':
    unittest.main(verbosity=2)
