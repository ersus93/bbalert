"""
Tests unitarios para recordatorios repetitivos (recurring reminders).

Cubiertos:
- Cálculo de siguiente ocurrencia (daily, weekly, monthly, yearly)
- Recordatorios con intervalos personalizados
- Fecha límite (end_date)
- Compatibilidad hacia atrás (recordatorios sin recurrencia)
"""

import unittest
from datetime import datetime, timedelta
from unittest.mock import patch, mock_open
import sys
import os
import json

# Añadir directorio raíz al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestIsRecurring(unittest.TestCase):
    """Tests para la función is_recurring()."""

    def setUp(self):
        self.base_time = datetime(2026, 2, 28, 8, 0, 0)

    def test_reminder_without_recurrence_returns_false(self):
        """Recordatorio sin campo 'recurrence' no es recurrente."""
        from utils.reminders_manager import is_recurring
        reminder = {
            "id": "test123",
            "text": "Tomar medicina",
            "time": self.base_time.isoformat()
        }
        self.assertFalse(is_recurring(reminder))

    def test_reminder_with_disabled_recurrence_returns_false(self):
        """Recordatorio con recurrence.enabled=False no es recurrente."""
        from utils.reminders_manager import is_recurring
        reminder = {
            "id": "test123",
            "text": "Tomar medicina",
            "time": self.base_time.isoformat(),
            "recurrence": {
                "enabled": False,
                "type": "daily",
                "interval": 1,
                "end_date": None,
                "occurrence_count": 0
            }
        }
        self.assertFalse(is_recurring(reminder))

    def test_reminder_with_enabled_recurrence_returns_true(self):
        """Recordatorio con recurrence.enabled=True es recurrente."""
        from utils.reminders_manager import is_recurring
        reminder = {
            "id": "test123",
            "text": "Tomar medicina",
            "time": self.base_time.isoformat(),
            "recurrence": {
                "enabled": True,
                "type": "daily",
                "interval": 1,
                "end_date": None,
                "occurrence_count": 0
            }
        }
        self.assertTrue(is_recurring(reminder))


class TestCalculateNextOccurrence(unittest.TestCase):
    """Tests para cálculo de siguiente ocurrencia."""

    def setUp(self):
        self.base_time = datetime(2026, 2, 28, 8, 0, 0)

    def test_daily_recurrence_adds_one_day(self):
        """Recurrencia diaria suma 1 día."""
        from utils.reminders_manager import calculate_next_occurrence
        reminder = {
            "id": "test123",
            "text": "Tomar medicina",
            "time": self.base_time.isoformat(),
            "recurrence": {
                "enabled": True,
                "type": "daily",
                "interval": 1,
                "end_date": None,
                "occurrence_count": 0
            }
        }
        next_time = calculate_next_occurrence(reminder)
        expected = self.base_time + timedelta(days=1)
        self.assertEqual(next_time, expected)

    def test_daily_recurrence_with_interval_adds_multiple_days(self):
        """Recurrencia diaria con interval=3 suma 3 días."""
        from utils.reminders_manager import calculate_next_occurrence
        reminder = {
            "id": "test123",
            "text": "Tomar medicina",
            "time": self.base_time.isoformat(),
            "recurrence": {
                "enabled": True,
                "type": "daily",
                "interval": 3,
                "end_date": None,
                "occurrence_count": 0
            }
        }
        next_time = calculate_next_occurrence(reminder)
        expected = self.base_time + timedelta(days=3)
        self.assertEqual(next_time, expected)

    def test_weekly_recurrence_adds_one_week(self):
        """Recurrencia semanal suma 7 días."""
        from utils.reminders_manager import calculate_next_occurrence
        reminder = {
            "id": "test456",
            "text": "Reunión de equipo",
            "time": self.base_time.isoformat(),
            "recurrence": {
                "enabled": True,
                "type": "weekly",
                "interval": 1,
                "end_date": None,
                "occurrence_count": 0
            }
        }
        next_time = calculate_next_occurrence(reminder)
        expected = self.base_time + timedelta(weeks=1)
        self.assertEqual(next_time, expected)

    def test_weekly_recurrence_with_interval_adds_multiple_weeks(self):
        """Recurrencia semanal con interval=2 suma 14 días."""
        from utils.reminders_manager import calculate_next_occurrence
        reminder = {
            "id": "test456",
            "text": "Reunión de equipo",
            "time": self.base_time.isoformat(),
            "recurrence": {
                "enabled": True,
                "type": "weekly",
                "interval": 2,
                "end_date": None,
                "occurrence_count": 0
            }
        }
        next_time = calculate_next_occurrence(reminder)
        expected = self.base_time + timedelta(weeks=2)
        self.assertEqual(next_time, expected)

    def test_monthly_recurrence_adds_one_month(self):
        """Recurrencia mensual suma 1 mes."""
        from utils.reminders_manager import calculate_next_occurrence
        reminder = {
            "id": "test789",
            "text": "Pago de factura",
            "time": self.base_time.isoformat(),
            "recurrence": {
                "enabled": True,
                "type": "monthly",
                "interval": 1,
                "end_date": None,
                "occurrence_count": 0
            }
        }
        next_time = calculate_next_occurrence(reminder)
        expected = datetime(2026, 3, 28, 8, 0, 0)
        self.assertEqual(next_time, expected)

    def test_monthly_recurrence_handles_different_month_lengths(self):
        """Recurrencia mensual maneja meses de diferente longitud (31 -> 30)."""
        from utils.reminders_manager import calculate_next_occurrence
        # 31 de enero -> 28 de febrero (2026 no es bisiesto)
        jan_31 = datetime(2026, 1, 31, 8, 0, 0)
        reminder = {
            "id": "test789",
            "text": "Pago de factura",
            "time": jan_31.isoformat(),
            "recurrence": {
                "enabled": True,
                "type": "monthly",
                "interval": 1,
                "end_date": None,
                "occurrence_count": 0
            }
        }
        next_time = calculate_next_occurrence(reminder)
        expected = datetime(2026, 2, 28, 8, 0, 0)  # Ajustado al último día de febrero
        self.assertEqual(next_time, expected)

    def test_yearly_recurrence_adds_one_year(self):
        """Recurrencia anual suma 1 año."""
        from utils.reminders_manager import calculate_next_occurrence
        reminder = {
            "id": "testabc",
            "text": "Cumpleaños",
            "time": self.base_time.isoformat(),
            "recurrence": {
                "enabled": True,
                "type": "yearly",
                "interval": 1,
                "end_date": None,
                "occurrence_count": 0
            }
        }
        next_time = calculate_next_occurrence(reminder)
        expected = datetime(2027, 2, 28, 8, 0, 0)
        self.assertEqual(next_time, expected)

    def test_yearly_recurrence_handles_leap_year(self):
        """Recurrencia anual maneja 29 febrero en años bisiestos."""
        from utils.reminders_manager import calculate_next_occurrence
        # 29 de febrero de 2024 (bisiesto) -> 28 de febrero de 2025 (no bisiesto)
        feb_29_2024 = datetime(2024, 2, 29, 8, 0, 0)
        reminder = {
            "id": "testabc",
            "text": "Cumpleaños bisiesto",
            "time": feb_29_2024.isoformat(),
            "recurrence": {
                "enabled": True,
                "type": "yearly",
                "interval": 1,
                "end_date": None,
                "occurrence_count": 0
            }
        }
        next_time = calculate_next_occurrence(reminder)
        expected = datetime(2025, 2, 28, 8, 0, 0)  # Ajustado a 28 feb
        self.assertEqual(next_time, expected)

    def test_recurrence_with_end_date_stops_after_limit(self):
        """Si next_time > end_date, retorna None."""
        from utils.reminders_manager import calculate_next_occurrence
        reminder = {
            "id": "test789",
            "text": "Curso temporal",
            "time": self.base_time.isoformat(),
            "recurrence": {
                "enabled": True,
                "type": "daily",
                "interval": 1,
                "end_date": "2026-03-01T00:00:00",  # Termina pronto
                "occurrence_count": 0
            }
        }
        # Próxima ocurrencia sería 2026-03-01 08:00, que es después de end_date 2026-03-01 00:00
        next_time = calculate_next_occurrence(reminder)
        self.assertIsNone(next_time)

    def test_recurrence_without_end_date_continues_indefinitely(self):
        """Sin end_date, calcula siguiente ocurrencia sin límite."""
        from utils.reminders_manager import calculate_next_occurrence
        reminder = {
            "id": "test789",
            "text": "Curso temporal",
            "time": self.base_time.isoformat(),
            "recurrence": {
                "enabled": True,
                "type": "daily",
                "interval": 1,
                "end_date": None,
                "occurrence_count": 0
            }
        }
        next_time = calculate_next_occurrence(reminder)
        self.assertIsNotNone(next_time)
        expected = self.base_time + timedelta(days=1)
        self.assertEqual(next_time, expected)

    def test_non_recurring_reminder_returns_none(self):
        """Recordatorio no recurrente retorna None."""
        from utils.reminders_manager import calculate_next_occurrence
        reminder = {
            "id": "test123",
            "text": "Tomar medicina",
            "time": self.base_time.isoformat()
        }
        next_time = calculate_next_occurrence(reminder)
        self.assertIsNone(next_time)


class TestUpdateReminderTime(unittest.TestCase):
    """Tests para actualización de hora de recordatorio."""

    def setUp(self):
        self.base_time = datetime(2026, 2, 28, 8, 0, 0)
        self.user_id = "12345"

    @patch('utils.reminders_manager.load_reminders')
    @patch('utils.reminders_manager.save_reminders')
    def test_update_time_changes_reminder_datetime(self, mock_save, mock_load):
        """Actualizar tiempo cambia el campo 'time' del recordatorio."""
        from utils.reminders_manager import update_reminder_time

        mock_load.return_value = {
            self.user_id: [
                {
                    "id": "rem1",
                    "text": "Tomar medicina",
                    "time": self.base_time.isoformat()
                }
            ]
        }

        new_time = datetime(2026, 2, 28, 9, 0, 0)
        result = update_reminder_time(self.user_id, "rem1", new_time)

        self.assertTrue(result)
        # Verificar que save_reminders fue llamado con el nuevo tiempo
        saved_data = mock_save.call_args[0][0]
        self.assertEqual(saved_data[self.user_id][0]["time"], new_time.isoformat())

    @patch('utils.reminders_manager.load_reminders')
    @patch('utils.reminders_manager.save_reminders')
    def test_update_recurring_increments_occurrence_count(self, mock_save, mock_load):
        """Actualizar tiempo de recurrente incrementa occurrence_count."""
        from utils.reminders_manager import update_reminder_time

        mock_load.return_value = {
            self.user_id: [
                {
                    "id": "rem1",
                    "text": "Tomar medicina",
                    "time": self.base_time.isoformat(),
                    "recurrence": {
                        "enabled": True,
                        "type": "daily",
                        "interval": 1,
                        "end_date": None,
                        "occurrence_count": 0
                    }
                }
            ]
        }

        new_time = datetime(2026, 2, 28, 9, 0, 0)
        result = update_reminder_time(self.user_id, "rem1", new_time)

        self.assertTrue(result)
        # Verificar que occurrence_count fue incrementado
        saved_data = mock_save.call_args[0][0]
        self.assertEqual(saved_data[self.user_id][0]["recurrence"]["occurrence_count"], 1)


class TestAddReminderWithRecurrence(unittest.TestCase):
    """Tests para creación de recordatorios con recurrencia."""

    def setUp(self):
        self.base_time = datetime(2026, 2, 28, 8, 0, 0)
        self.user_id = "12345"

    @patch('utils.reminders_manager.load_reminders')
    @patch('utils.reminders_manager.save_reminders')
    def test_add_reminder_without_recurrence_does_not_include_recurrence_field(self, mock_save, mock_load):
        """Sin recurrence_config, el recordatorio no tiene campo 'recurrence'."""
        from utils.reminders_manager import add_reminder

        mock_load.return_value = {}

        reminder_id = add_reminder(self.user_id, "Recordatorio simple", self.base_time)

        self.assertIsNotNone(reminder_id)
        # Verificar que save_reminders fue llamado sin campo recurrence
        saved_data = mock_save.call_args[0][0]
        reminder = saved_data[self.user_id][0]
        self.assertNotIn("recurrence", reminder)

    @patch('utils.reminders_manager.load_reminders')
    @patch('utils.reminders_manager.save_reminders')
    def test_add_reminder_with_recurrence_includes_recurrence_config(self, mock_save, mock_load):
        """Con recurrence_config, el recordatorio incluye el campo configurado."""
        from utils.reminders_manager import add_reminder

        mock_load.return_value = {}

        recurrence_config = {
            "enabled": True,
            "type": "daily",
            "interval": 1,
            "end_date": None,
            "occurrence_count": 0
        }

        reminder_id = add_reminder(self.user_id, "Recordatorio diario", self.base_time, recurrence_config)

        self.assertIsNotNone(reminder_id)
        # Verificar que save_reminders fue llamado con recurrence
        saved_data = mock_save.call_args[0][0]
        reminder = saved_data[self.user_id][0]
        self.assertIn("recurrence", reminder)
        self.assertEqual(reminder["recurrence"]["type"], "daily")
        self.assertEqual(reminder["recurrence"]["interval"], 1)


class TestBackwardCompatibility(unittest.TestCase):
    """Tests para compatibilidad hacia atrás."""

    def setUp(self):
        self.base_time = datetime(2026, 2, 28, 8, 0, 0)

    def test_old_reminders_without_recurrence_work_normally(self):
        """Recordatorios antiguos sin campo 'recurrence' funcionan correctamente."""
        from utils.reminders_manager import is_recurring, calculate_next_occurrence

        # Recordatorio viejo sin campo recurrence
        old_reminder = {
            "id": "old123",
            "text": "Recordatorio antiguo",
            "time": self.base_time.isoformat()
        }

        # is_recurring debe retornar False
        self.assertFalse(is_recurring(old_reminder))

        # calculate_next_occurrence debe retornar None
        self.assertIsNone(calculate_next_occurrence(old_reminder))


if __name__ == '__main__':
    unittest.main(verbosity=2)
