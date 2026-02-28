# tests/test_telemetry.py
"""
Tests unitarios para el sistema de telemetry.

Cubre:
- log_event: eventos validos e invalidos
- get_event_stats: estructura correcta de estadisticas
- get_user_journey: eventos ordenados por timestamp
- get_retention_metrics: calculos con datos mock
- get_commands_per_user: calculos de promedios
- get_daily_events: conteos diarios
- Limpieza de eventos antiguos (90 dias)
- Rotacion de archivos cuando excede el limite de tamano
"""

import unittest
import json
import sys
import os
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, mock_open

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestLogEvent(unittest.TestCase):
    """Test para log_event con tipos de eventos validos e invalidos."""

    @patch('utils.telemetry._file_lock')
    @patch('utils.telemetry._load_events')
    @patch('utils.telemetry._save_events')
    @patch('utils.telemetry.logger')
    def test_log_event_valid_type(self, mock_logger, mock_save, mock_load, mock_lock):
        """Evento con tipo valido debe ser registrado exitosamente."""
        from utils.telemetry import log_event, VALID_EVENT_TYPES

        mock_load.return_value = []
        mock_lock.acquire.return_value = True

        result = log_event('command_used', 'USER_123', {'command': 'ver'})

        self.assertTrue(result)
        mock_save.assert_called_once()
        saved_events = mock_save.call_args[0][0]
        self.assertEqual(len(saved_events), 1)
        self.assertEqual(saved_events[0]['event_type'], 'command_used')
        self.assertEqual(saved_events[0]['user_id'], 'USER_123')
        self.assertEqual(saved_events[0]['metadata'], {'command': 'ver'})
        self.assertIn('timestamp', saved_events[0])

    @patch('utils.telemetry.logger')
    def test_log_event_invalid_type(self, mock_logger):
        """Evento con tipo invalido debe retornar False."""
        from utils.telemetry import log_event, VALID_EVENT_TYPES

        result = log_event('invalid_event_type', 'USER_123', {})

        self.assertFalse(result)
        mock_logger.warning.assert_called_once()
        self.assertIn('invalid_event_type', str(mock_logger.warning.call_args))

    @patch('utils.telemetry._file_lock')
    @patch('utils.telemetry.logger')
    def test_log_event_lock_timeout(self, mock_logger, mock_lock):
        """Si no se puede adquirir el lock, debe retornar False."""
        from utils.telemetry import log_event

        mock_lock.acquire.return_value = False

        result = log_event('command_used', 'USER_123', {})

        self.assertFalse(result)
        mock_logger.error.assert_called_once()

    @patch('utils.telemetry._file_lock')
    @patch('utils.telemetry._load_events')
    @patch('utils.telemetry._save_events')
    @patch('utils.telemetry.logger')
    def test_log_event_user_id_converted_to_string(self, mock_logger, mock_save, mock_load, mock_lock):
        """El user_id debe convertirse a string."""
        from utils.telemetry import log_event

        mock_load.return_value = []
        mock_lock.acquire.return_value = True

        log_event('user_joined', 987654321, {})

        saved_events = mock_save.call_args[0][0]
        self.assertEqual(saved_events[0]['user_id'], '987654321')

    @patch('utils.telemetry._file_lock')
    @patch('utils.telemetry._load_events')
    @patch('utils.telemetry._save_events')
    @patch('utils.telemetry.logger')
    def test_log_event_corrupted_log_recovery(self, mock_logger, mock_save, mock_load, mock_lock):
        """Si el log esta corrupto, debe iniciar uno nuevo."""
        from utils.telemetry import log_event, EventLogCorruptedError

        mock_load.side_effect = EventLogCorruptedError("Corrupted")
        mock_lock.acquire.return_value = True

        result = log_event('user_joined', 'USER_123', {})

        self.assertTrue(result)
        mock_logger.warning.assert_called_once()
        saved_events = mock_save.call_args[0][0]
        self.assertEqual(len(saved_events), 1)


class TestGetEventStats(unittest.TestCase):
    """Test para get_event_stats."""

    @patch('utils.telemetry._file_lock')
    @patch('utils.telemetry._load_events')
    @patch('utils.telemetry.logger')
    def test_get_event_stats_structure(self, mock_logger, mock_load, mock_lock):
        """La estructura retornada debe tener todos los campos esperados."""
        from utils.telemetry import get_event_stats

        now = datetime.now()
        mock_events = [
            {
                'event_type': 'command_used',
                'user_id': 'USER_001',
                'timestamp': int((now - timedelta(days=1)).timestamp()),
                'metadata': {}
            },
            {
                'event_type': 'alert_triggered',
                'user_id': 'USER_002',
                'timestamp': int((now - timedelta(days=2)).timestamp()),
                'metadata': {}
            }
        ]
        mock_load.return_value = mock_events
        mock_lock.acquire.return_value = True

        stats = get_event_stats(days=7)

        required_fields = [
            'total_events', 'events_by_type', 'unique_users',
            'events_by_day', 'most_active_user', 'period_days', 'period_start'
        ]
        for field in required_fields:
            self.assertIn(field, stats, f"Campo '{field}' debe estar en stats")

        self.assertEqual(stats['total_events'], 2)
        self.assertEqual(stats['unique_users'], 2)
        self.assertEqual(stats['events_by_type']['command_used'], 1)
        self.assertEqual(stats['events_by_type']['alert_triggered'], 1)
        self.assertIsNotNone(stats['most_active_user'])

    @patch('utils.telemetry._file_lock')
    @patch('utils.telemetry._load_events')
    @patch('utils.telemetry.logger')
    def test_get_event_stats_empty_events(self, mock_logger, mock_load, mock_lock):
        """Sin eventos debe retornar estructura vacia."""
        from utils.telemetry import get_event_stats

        mock_load.return_value = []
        mock_lock.acquire.return_value = True

        stats = get_event_stats(days=30)

        self.assertEqual(stats['total_events'], 0)
        self.assertEqual(stats['unique_users'], 0)
        self.assertEqual(stats['events_by_type'], {})
        self.assertIsNone(stats['most_active_user'])

    @patch('utils.telemetry._file_lock')
    @patch('utils.telemetry._load_events')
    @patch('utils.telemetry.logger')
    def test_get_event_stats_old_events_filtered(self, mock_logger, mock_load, mock_lock):
        """Eventos mas antiguos que el periodo deben ser filtrados."""
        from utils.telemetry import get_event_stats

        now = datetime.now()
        mock_events = [
            {
                'event_type': 'command_used',
                'user_id': 'USER_001',
                'timestamp': int((now - timedelta(days=1)).timestamp()),
                'metadata': {}
            },
            {
                'event_type': 'command_used',
                'user_id': 'USER_001',
                'timestamp': int((now - timedelta(days=40)).timestamp()),
                'metadata': {}
            }
        ]
        mock_load.return_value = mock_events
        mock_lock.acquire.return_value = True

        stats = get_event_stats(days=30)

        self.assertEqual(stats['total_events'], 1)
        self.assertEqual(stats['events_by_type']['command_used'], 1)


class TestGetUserJourney(unittest.TestCase):
    """Test para get_user_journey."""

    @patch('utils.telemetry._file_lock')
    @patch('utils.telemetry._load_events')
    @patch('utils.telemetry.logger')
    def test_get_user_journey_sorted_by_timestamp(self, mock_logger, mock_load, mock_lock):
        """Los eventos deben estar ordenados por timestamp (nuevo primero)."""
        from utils.telemetry import get_user_journey

        now = datetime.now()
        mock_events = [
            {
                'event_type': 'command_used',
                'user_id': 'USER_001',
                'timestamp': int((now - timedelta(days=3)).timestamp()),
                'metadata': {'command': 'ver'}
            },
            {
                'event_type': 'alert_triggered',
                'user_id': 'USER_001',
                'timestamp': int((now - timedelta(days=1)).timestamp()),
                'metadata': {}
            },
            {
                'event_type': 'user_joined',
                'user_id': 'USER_001',
                'timestamp': int((now - timedelta(days=5)).timestamp()),
                'metadata': {}
            }
        ]
        mock_load.return_value = mock_events
        mock_lock.acquire.return_value = True

        journey = get_user_journey('USER_001', days=7)

        self.assertEqual(len(journey), 3)
        self.assertEqual(journey[0]['event_type'], 'alert_triggered')
        self.assertEqual(journey[1]['event_type'], 'command_used')
        self.assertEqual(journey[2]['event_type'], 'user_joined')

        for event in journey:
            self.assertIn('datetime', event)
            self.assertIn('timestamp', event)
            self.assertIn('metadata', event)

    @patch('utils.telemetry._file_lock')
    @patch('utils.telemetry._load_events')
    @patch('utils.telemetry.logger')
    def test_get_user_journey_other_users_filtered(self, mock_logger, mock_load, mock_lock):
        """Solo debe retornar eventos del usuario especificado."""
        from utils.telemetry import get_user_journey

        now = datetime.now()
        mock_events = [
            {
                'event_type': 'command_used',
                'user_id': 'USER_001',
                'timestamp': int(now.timestamp()),
                'metadata': {}
            },
            {
                'event_type': 'command_used',
                'user_id': 'USER_002',
                'timestamp': int(now.timestamp()),
                'metadata': {}
            }
        ]
        mock_load.return_value = mock_events
        mock_lock.acquire.return_value = True

        journey = get_user_journey('USER_001', days=7)

        self.assertEqual(len(journey), 1)
        self.assertEqual(journey[0]['event_type'], 'command_used')


class TestGetRetentionMetrics(unittest.TestCase):
    """Test para get_retention_metrics."""

    @patch('utils.telemetry.cargar_usuarios')
    def test_get_retention_metrics_structure(self, mock_cargar):
        """La estructura debe tener todos los campos de retencion."""
        from utils.telemetry import get_retention_metrics

        now = datetime.now()
        mock_usuarios = {
            'USER_001': {'last_seen': now.strftime('%Y-%m-%d %H:%M:%S')},
            'USER_002': {'last_seen': (now - timedelta(days=3)).strftime('%Y-%m-%d %H:%M:%S')},
            'USER_003': {'last_seen': (now - timedelta(days=15)).strftime('%Y-%m-%d %H:%M:%S')},
        }
        mock_cargar.return_value = mock_usuarios

        metrics = get_retention_metrics()

        required_fields = ['retention_7d', 'churn_rate', 'stickiness', 'dau', 'wau', 'mau']
        for field in required_fields:
            self.assertIn(field, metrics, f"Campo '{field}' debe estar en metrics")

        self.assertEqual(metrics['dau'], 1)
        self.assertEqual(metrics['wau'], 2)
        self.assertEqual(metrics['mau'], 3)

    @patch('utils.telemetry.cargar_usuarios')
    def test_get_retention_metrics_calculations(self, mock_cargar):
        """Los calculos de retencion deben ser correctos."""
        from utils.telemetry import get_retention_metrics

        now = datetime.now()
        mock_usuarios = {
            'USER_001': {'last_seen': now.strftime('%Y-%m-%d %H:%M:%S')},
            'USER_002': {'last_seen': now.strftime('%Y-%m-%d %H:%M:%S')},
            'USER_003': {'last_seen': (now - timedelta(days=3)).strftime('%Y-%m-%d %H:%M:%S')},
            'USER_004': {'last_seen': (now - timedelta(days=20)).strftime('%Y-%m-%d %H:%M:%S')},
        }
        mock_cargar.return_value = mock_usuarios

        metrics = get_retention_metrics()

        self.assertEqual(metrics['dau'], 2)
        self.assertEqual(metrics['wau'], 3)
        self.assertEqual(metrics['mau'], 4)

        expected_retention = (3 / 4) * 100
        self.assertEqual(metrics['retention_7d'], round(expected_retention, 1))

        expected_stickiness = (2 / 4) * 100
        self.assertEqual(metrics['stickiness'], round(expected_stickiness, 1))

    @patch('utils.telemetry.cargar_usuarios')
    def test_get_retention_metrics_fallback_to_last_alert(self, mock_cargar):
        """Debe usar last_alert_timestamp si no hay last_seen."""
        from utils.telemetry import get_retention_metrics

        now = datetime.now()
        mock_usuarios = {
            'USER_001': {'last_alert_timestamp': now.strftime('%Y-%m-%d %H:%M:%S')},
        }
        mock_cargar.return_value = mock_usuarios

        metrics = get_retention_metrics()

        self.assertEqual(metrics['dau'], 1)


class TestGetCommandsPerUser(unittest.TestCase):
    """Test para get_commands_per_user."""

    @patch('utils.telemetry.cargar_usuarios')
    @patch('utils.telemetry.datetime')
    def test_get_commands_per_user_calculations(self, mock_datetime, mock_cargar):
        """Los calculos de comandos por usuario deben ser correctos."""
        from utils.telemetry import get_commands_per_user

        mock_datetime.now.return_value = datetime(2025, 1, 15, 12, 0, 0)
        mock_datetime.strftime = datetime.strftime

        mock_usuarios = {
            'USER_001': {
                'daily_usage': {
                    'date': '2025-01-15',
                    'ver': 5,
                    'tasa': 2,
                    'ta': 1
                }
            },
            'USER_002': {
                'daily_usage': {
                    'date': '2025-01-15',
                    'ver': 3,
                    'tasa': 1
                }
            },
            'USER_003': {
                'daily_usage': {
                    'date': '2025-01-14',
                    'ver': 10
                }
            }
        }
        mock_cargar.return_value = mock_usuarios

        result = get_commands_per_user()

        self.assertEqual(result['total_commands'], 12)
        self.assertEqual(result['active_users_today'], 2)
        self.assertEqual(result['avg_per_user'], 6.0)

    @patch('utils.telemetry.cargar_usuarios')
    @patch('utils.telemetry.datetime')
    def test_get_commands_per_user_no_active_users(self, mock_datetime, mock_cargar):
        """Sin usuarios activos hoy, el promedio debe ser 0."""
        from utils.telemetry import get_commands_per_user

        mock_datetime.now.return_value = datetime(2025, 1, 15, 12, 0, 0)

        mock_usuarios = {
            'USER_001': {
                'daily_usage': {
                    'date': '2025-01-14',
                    'ver': 5
                }
            }
        }
        mock_cargar.return_value = mock_usuarios

        result = get_commands_per_user()

        self.assertEqual(result['total_commands'], 0)
        self.assertEqual(result['active_users_today'], 0)
        self.assertEqual(result['avg_per_user'], 0.0)


class TestGetDailyEvents(unittest.TestCase):
    """Test para get_daily_events."""

    @patch('utils.telemetry.cargar_usuarios')
    def test_get_daily_events_counts(self, mock_cargar):
        """Los conteos diarios deben ser correctos."""
        from utils.telemetry import get_daily_events

        # Usamos la fecha/hora actual real para evitar problemas con replace()
        from datetime import datetime as real_datetime
        today = real_datetime.now()
        today_str = today.strftime('%Y-%m-%d')
        today_start = today.replace(hour=0, minute=0, second=0, microsecond=0)

        mock_usuarios = {
            'USER_001': {
                'registered_at': (today_start + __import__('datetime').timedelta(hours=10)).strftime('%Y-%m-%d %H:%M:%S'),
                'daily_usage': {
                    'date': today_str,
                    'ver': 5,
                    'tasa': 2
                }
            },
            'USER_002': {
                'registered_at': (today_start - __import__('datetime').timedelta(days=1, hours=2)).strftime('%Y-%m-%d %H:%M:%S'),
                'daily_usage': {
                    'date': today_str,
                    'ver': 3
                }
            },
            'USER_003': {
                'registered_at': (today_start + __import__('datetime').timedelta(hours=14)).strftime('%Y-%m-%d %H:%M:%S'),
                'daily_usage': {
                    'date': (today - __import__('datetime').timedelta(days=1)).strftime('%Y-%m-%d'),
                    'ver': 10
                }
            }
        }
        mock_cargar.return_value = mock_usuarios

        result = get_daily_events()

        # USER_001 y USER_003 se unieron hoy; USER_002 se unió ayer
        self.assertEqual(result['joins_today'], 2)
        # USER_001: 7 comandos, USER_002: 3 comandos, USER_003: 0 comandos hoy = 10
        self.assertEqual(result['commands_today'], 10)

    @patch('utils.telemetry.cargar_usuarios')
    @patch('utils.telemetry.datetime')
    def test_get_daily_events_invalid_date_ignored(self, mock_datetime, mock_cargar):
        """Fechas invalidas deben ser ignoradas sin errores."""
        from utils.telemetry import get_daily_events

        mock_datetime.now.return_value = datetime(2025, 1, 15, 12, 0, 0)

        mock_usuarios = {
            'USER_001': {
                'registered_at': 'invalid-date',
                'daily_usage': {
                    'date': '2025-01-15',
                    'ver': 5
                }
            }
        }
        mock_cargar.return_value = mock_usuarios

        result = get_daily_events()

        self.assertEqual(result['joins_today'], 0)
        self.assertEqual(result['commands_today'], 5)


class TestCleanupOldEvents(unittest.TestCase):
    """Test para limpieza de eventos antiguos."""

    @patch('utils.telemetry._file_lock')
    @patch('utils.telemetry._load_events')
    @patch('utils.telemetry._save_events')
    @patch('utils.telemetry.logger')
    def test_cleanup_events_older_than_90_days(self, mock_logger, mock_save, mock_load, mock_lock):
        """Eventos mayores a 90 dias deben ser eliminados."""
        from utils.telemetry import log_event, CLEANUP_DAYS

        now = datetime.now()
        old_event = {
            'event_type': 'command_used',
            'user_id': 'USER_001',
            'timestamp': int((now - timedelta(days=100)).timestamp()),
            'metadata': {}
        }
        recent_event = {
            'event_type': 'command_used',
            'user_id': 'USER_001',
            'timestamp': int((now - timedelta(days=30)).timestamp()),
            'metadata': {}
        }

        mock_load.return_value = [old_event, recent_event]
        mock_lock.acquire.return_value = True

        log_event('user_joined', 'USER_002', {})

        saved_events = mock_save.call_args[0][0]
        self.assertEqual(len(saved_events), 2)

        mock_logger.info.assert_called()
        info_calls = [call for call in mock_logger.info.call_args_list if 'Cleaned up' in str(call)]
        self.assertEqual(len(info_calls), 1)

    @patch('utils.telemetry._file_lock')
    @patch('utils.telemetry._load_events')
    @patch('utils.telemetry._save_events')
    @patch('utils.telemetry.logger')
    def test_no_cleanup_if_all_events_recent(self, mock_logger, mock_save, mock_load, mock_lock):
        """Si todos los eventos son recientes, no debe haber limpieza."""
        from utils.telemetry import log_event

        now = datetime.now()
        recent_events = [
            {
                'event_type': 'command_used',
                'user_id': 'USER_001',
                'timestamp': int((now - timedelta(days=5)).timestamp()),
                'metadata': {}
            }
        ]

        mock_load.return_value = recent_events
        mock_lock.acquire.return_value = True

        log_event('user_joined', 'USER_002', {})

        saved_events = mock_save.call_args[0][0]
        self.assertEqual(len(saved_events), 2)


class TestFileRotation(unittest.TestCase):
    """Test para rotacion de archivos cuando excede el limite."""

    @patch('utils.telemetry.os.path.exists')
    @patch('utils.telemetry.os.path.getsize')
    @patch('utils.telemetry._file_lock')
    @patch('utils.telemetry.logger')
    def test_rotation_triggered_when_size_exceeds_limit(
        self, mock_logger, mock_lock, mock_getsize, mock_exists
    ):
        """La rotacion debe activarse cuando el archivo excede 10MB."""
        from utils.telemetry import _load_events, MAX_FILE_SIZE_BYTES, _rotate_log_file

        mock_exists.return_value = True
        mock_getsize.return_value = MAX_FILE_SIZE_BYTES + 1
        mock_lock.acquire.return_value = True

        # Mock _rotate_log_file para verificar que se llama
        with patch('utils.telemetry._rotate_log_file') as mock_rotate:
            with patch('builtins.open', mock_open(read_data='[]')):
                _load_events()

        mock_rotate.assert_called_once()
        mock_logger.warning.assert_called_once()

    @patch('utils.telemetry._save_events')
    @patch('utils.telemetry._load_events')
    @patch('utils.telemetry.logger')
    def test_rotation_keeps_recent_events(self, mock_logger, mock_load, mock_save):
        """La rotacion debe mantener eventos recientes (ultimos 30 dias)."""
        from utils.telemetry import _rotate_log_file

        now = datetime.now()
        events = [
            {
                'event_type': 'command_used',
                'user_id': 'USER_001',
                'timestamp': int((now - timedelta(days=5)).timestamp()),
                'metadata': {}
            },
            {
                'event_type': 'command_used',
                'user_id': 'USER_001',
                'timestamp': int((now - timedelta(days=60)).timestamp()),
                'metadata': {}
            },
            {
                'event_type': 'command_used',
                'user_id': 'USER_001',
                'timestamp': int((now - timedelta(days=100)).timestamp()),
                'metadata': {}
            }
        ]

        mock_load.return_value = events

        _rotate_log_file()

        saved_events = mock_save.call_args[0][0]
        self.assertEqual(len(saved_events), 1)
        self.assertEqual(saved_events[0]['timestamp'], events[0]['timestamp'])

    @patch('utils.telemetry._save_events')
    @patch('utils.telemetry._load_events')
    @patch('utils.telemetry.logger')
    def test_rotation_limits_to_1000_events(self, mock_logger, mock_load, mock_save):
        """Si despues de filtrar aun hay mas de 1000 eventos, debe limitar a los ultimos 1000."""
        from utils.telemetry import _rotate_log_file

        now = datetime.now()
        many_events = [
            {
                'event_type': 'command_used',
                'user_id': f'USER_{i}',
                'timestamp': int((now - timedelta(days=i % 20)).timestamp()),
                'metadata': {}
            }
            for i in range(1500)
        ]

        mock_load.return_value = many_events

        _rotate_log_file()

        saved_events = mock_save.call_args[0][0]
        self.assertEqual(len(saved_events), 1000)


class TestGetUsersRegistrationStats(unittest.TestCase):
    """Test para get_users_registration_stats."""

    @patch('utils.telemetry.cargar_usuarios')
    def test_get_users_registration_stats_structure(self, mock_cargar):
        """La estructura debe tener todos los campos de estadisticas de registro."""
        from utils.telemetry import get_users_registration_stats

        mock_usuarios = {
            'USER_001': {'registered_at': '2025-01-01 10:00:00', 'last_seen': '2025-01-15 10:00:00'},
            'USER_002': {'registered_at': '2025-01-02 10:00:00'},
            'USER_003': {'last_seen': '2025-01-15 10:00:00'},
        }
        mock_cargar.return_value = mock_usuarios

        stats = get_users_registration_stats()

        required_fields = [
            'total_users', 'with_registered_at', 'without_registered_at',
            'with_last_seen', 'could_estimate', 'data_quality_pct'
        ]
        for field in required_fields:
            self.assertIn(field, stats, f"Campo '{field}' debe estar en stats")

        self.assertEqual(stats['total_users'], 3)
        self.assertEqual(stats['with_registered_at'], 2)
        self.assertEqual(stats['without_registered_at'], 1)
        self.assertEqual(stats['with_last_seen'], 2)
        self.assertEqual(stats['could_estimate'], 1)

    @patch('utils.telemetry.cargar_usuarios')
    def test_get_users_registration_stats_empty_users(self, mock_cargar):
        """Sin usuarios, los valores deben ser cero."""
        from utils.telemetry import get_users_registration_stats

        mock_cargar.return_value = {}

        stats = get_users_registration_stats()

        self.assertEqual(stats['total_users'], 0)
        self.assertEqual(stats['with_registered_at'], 0)
        self.assertEqual(stats['data_quality_pct'], 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
