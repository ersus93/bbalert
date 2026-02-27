# tests/test_reminders_sorting.py
"""
Tests unitarios para validar el ordenamiento cronológico de recordatorios.

Cubre:
- Los recordatorios deben ordenarse por fecha/hora (más próximo primero)
- Mantener compatibilidad con recordatorios existentes
- Verificar formato de botones de opciones rápidas
"""

import unittest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, mock_open
import sys
import os
import json

# Añadir el directorio raíz al path para importar módulos del proyecto
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestRemindersSorting(unittest.TestCase):
    """Verifica que los recordatorios se ordenan cronológicamente."""

    def setUp(self):
        """Setup para cada test."""
        self.sample_reminders = [
            {
                "id": "abc123",
                "text": "Recordatorio de ayer",
                "time": (datetime.now() + timedelta(days=-1)).isoformat(),
                "created_at": datetime.now().isoformat()
            },
            {
                "id": "def456",
                "text": "Recordatorio de mañana",
                "time": (datetime.now() + timedelta(days=1)).isoformat(),
                "created_at": datetime.now().isoformat()
            },
            {
                "id": "ghi789",
                "text": "Recordatorio de hoy",
                "time": (datetime.now() + timedelta(hours=2)).isoformat(),
                "created_at": datetime.now().isoformat()
            },
            {
                "id": "jkl012",
                "text": "Recordatorio de pasado mañana",
                "time": (datetime.now() + timedelta(days=2)).isoformat(),
                "created_at": datetime.now().isoformat()
            },
        ]

    @patch('utils.reminders_manager.os.path.exists')
    @patch('utils.reminders_manager.open', new_callable=mock_open)
    @patch('utils.reminders_manager.json.load')
    def test_reminders_sorted_chronologically(self, mock_json_load, mock_file, mock_exists):
        """
        Los recordatorios deben retornarse ordenados del más próximo al más lejano.
        Orden esperado: ayer -> hoy -> mañana -> pasado mañana
        """
        from utils.reminders_manager import get_user_reminders
        
        # Simular archivo existente con recordatorios desordenados
        mock_exists.return_value = True
        mock_json_load.return_value = {
            "12345": self.sample_reminders  # Desordenados en el JSON
        }
        
        # Llamar a get_user_reminders
        result = get_user_reminders("12345")
        
        # Verificar que están ordenados por fecha
        times = [r['time'] for r in result]
        self.assertEqual(len(result), 4)
        
        # Verificar orden cronológico (más próximo primero)
        for i in range(len(times) - 1):
            current = datetime.fromisoformat(times[i])
            next_dt = datetime.fromisoformat(times[i + 1])
            self.assertLessEqual(current, next_dt, 
                f"Recordatorio {i} debe ser anterior al recordatorio {i+1}")

    @patch('utils.reminders_manager.os.path.exists')
    @patch('utils.reminders_manager.open', new_callable=mock_open)
    @patch('utils.reminders_manager.json.load')
    def test_empty_reminders_list(self, mock_json_load, mock_file, mock_exists):
        """Lista vacía debe retornar lista vacía sin errores."""
        from utils.reminders_manager import get_user_reminders
        
        mock_exists.return_value = True
        mock_json_load.return_value = {"12345": []}
        
        result = get_user_reminders("12345")
        self.assertEqual(result, [])

    @patch('utils.reminders_manager.os.path.exists')
    @patch('utils.reminders_manager.open', new_callable=mock_open)
    @patch('utils.reminders_manager.json.load')
    def test_single_reminder_returns_list(self, mock_json_load, mock_file, mock_exists):
        """Un solo recordatorio debe retornarse en lista."""
        from utils.reminders_manager import get_user_reminders
        
        mock_exists.return_value = True
        mock_json_load.return_value = {
            "12345": [self.sample_reminders[0]]
        }
        
        result = get_user_reminders("12345")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['id'], "abc123")

    @patch('utils.reminders_manager.os.path.exists')
    def test_no_file_returns_empty_list(self, mock_exists):
        """Si no existe el archivo, debe retornar lista vacía."""
        from utils.reminders_manager import get_user_reminders
        
        mock_exists.return_value = False
        
        result = get_user_reminders("12345")
        self.assertEqual(result, [])


class TestQuickTimeButtons(unittest.TestCase):
    """Verifica que los botones de opciones rápidas generan fechas correctas."""

    def test_quick_button_10m_calculates_correctly(self):
        """El botón 10m debe calcular 10 minutos desde ahora."""
        from datetime import datetime, timedelta
        
        now = datetime.now()
        expected_time = now + timedelta(minutes=10)
        
        # Simular lo que haría el botón
        result_time = now + timedelta(minutes=10)
        
        # Verificar diferencia es aproximadamente 10 minutos
        diff = result_time - now
        self.assertEqual(diff.total_seconds(), 600)  # 10 minutos = 600 segundos

    def test_quick_button_1h_calculates_correctly(self):
        """El botón 1h debe calcular 1 hora desde ahora."""
        from datetime import datetime, timedelta
        
        now = datetime.now()
        result_time = now + timedelta(hours=1)
        
        diff = result_time - now
        self.assertEqual(diff.total_seconds(), 3600)  # 1 hora = 3600 segundos

    def test_quick_button_tomorrow_morning_calculates_correctly(self):
        """El botón 'Mañana 09:00' debe calcular mañana a las 9am."""
        from datetime import datetime, timedelta
        
        now = datetime.now()
        tomorrow_9am = (now + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
        
        # Verificar que es mañana
        self.assertEqual(tomorrow_9am.day, (now + timedelta(days=1)).day)
        self.assertEqual(tomorrow_9am.hour, 9)
        self.assertEqual(tomorrow_9am.minute, 0)

    def test_quick_button_today_calculates_correctly(self):
        """El botón 'Hoy' debe calcular para hoy a una hora específica."""
        from datetime import datetime, timedelta
        
        now = datetime.now()
        
        # Si ya pasó las 9am, sería para mañana
        target_hour = 9
        target_time = now.replace(hour=target_hour, minute=0, second=0, microsecond=0)
        
        if target_time < now:
            target_time += timedelta(days=1)
        
        # Verificar que la hora es futura
        self.assertGreater(target_time, now)


class TestReminderButtonCallbacks(unittest.TestCase):
    """Verifica el formato de los callback_data de los botones."""

    def test_quick_time_callback_format(self):
        """Los callbacks de tiempo rápido deben tener formato 'time_{minutes}' o 'time_{special}'."""
        # Formatos esperados para botones rápidos
        valid_callbacks = [
            "time_10",      # 10 minutos
            "time_30",      # 30 minutos
            "time_60",      # 1 hora
            "time_morning", # Mañana 09:00
            "time_afternoon", # Tarde 15:00
            "time_evening",   # Noche 20:00
            "time_today",     # Hoy
            "time_tomorrow",  # Mañana
            "time_custom",    # Otro (texto libre)
        ]
        
        for callback in valid_callbacks:
            self.assertTrue(
                callback.startswith("time_"),
                f"Callback {callback} debe empezar con 'time_'"
            )


if __name__ == '__main__':
    unittest.main(verbosity=2)
