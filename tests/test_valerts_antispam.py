# tests/test_valerts_antispam.py
"""
Tests unitarios para validar la lógica anti-spam de valerts para fuente TradingView.

Cubr:
- Cuando el precio está por encima de R3, marcar P_UP, R1, R2, R3 como ya alertados
- Cuando el precio está por encima de R2, marcar P_UP, R1, R2 como ya alertados
- Cuando el precio está por debajo de S3, marcar P_DOWN, S1, S2, S3 como ya alertados
- Lógica de Golden Pocket funciona correctamente para ambos escenarios (UP y DOWN)

Este test replica la lógica de la Fase 1 de valerts_loop.py para fuente TV (líneas 214-248)
para verificar que funciona correctamente sin depender de async/telegram.
"""

import unittest
import sys
import os

# Añadir el directorio raíz al path para importar módulos del proyecto
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestValertsAntiSpam(unittest.TestCase):
    """
    Verifica la lógica anti-spam para fuente TradingView.
    
    Cuando se inicializa una nueva sesión con fuente TV, el sistema debe marcar
    como 'ya alertados' los niveles que el precio ya ha cruzado para evitar
    spam de alertas históricas.
    """

    def _apply_tv_antispm_logic(self, current_price, levels_fib):
        """
        Replica la lógica anti-spam de valerts_loop.py líneas 214-248.
        
        Args:
            current_price: Precio actual del activo
            levels_fib: Diccionario con niveles de Fibonacci (P, R1, R2, R3, S1, S2, S3, FIB_618)
            
        Returns:
            Lista de niveles marcados como ya alertados
        """
        pre_filled_alerts = []

        # A) ANÁLISIS ALCISTA - Marcar niveles ya superados como alertados
        if current_price >= levels_fib['R3']:
            pre_filled_alerts.extend(['P_UP', 'R1', 'R2', 'R3'])
        elif current_price >= levels_fib['R2']:
            pre_filled_alerts.extend(['P_UP', 'R1', 'R2'])
        elif current_price >= levels_fib['R1']:
            pre_filled_alerts.extend(['P_UP', 'R1'])
        elif current_price >= levels_fib['P']:
            pre_filled_alerts.append('P_UP')

        # B) ANÁLISIS BAJISTA - Marcar niveles ya perforados como alertados
        elif current_price <= levels_fib['S3']:
            pre_filled_alerts.extend(['P_DOWN', 'S1', 'S2', 'S3'])
        elif current_price <= levels_fib['S2']:
            pre_filled_alerts.extend(['P_DOWN', 'S1', 'S2'])
        elif current_price <= levels_fib['S1']:
            pre_filled_alerts.extend(['P_DOWN', 'S1'])
        elif current_price < levels_fib['P']:
            pre_filled_alerts.append('P_DOWN')

        # C) GOLDEN POCKET
        if current_price >= levels_fib['FIB_618']:
            if 'FIB_618_UP' not in pre_filled_alerts:
                pre_filled_alerts.append('FIB_618_UP')
        else:
            if 'FIB_618_DOWN' not in pre_filled_alerts:
                pre_filled_alerts.append('FIB_618_DOWN')

        return pre_filled_alerts

    def setUp(self):
        """Setup común para todos los tests - niveles típicos de BTC."""
        self.levels_btc = {
            'P': 85000.0,
            'R1': 87500.0,
            'R2': 90000.0,
            'R3': 92500.0,
            'S1': 82500.0,
            'S2': 80000.0,
            'S3': 77500.0,
            'FIB_618': 88000.0  # Golden Pocket
        }

    # ==========================================================================
    # TESTS PARA ESCENARIOS ALCISTAS (BULLISH)
    # ==========================================================================

    def test_price_above_r3_marks_all_resistance_and_pivot_up(self):
        """
        CUANDO el precio está por encima de R3,
        ENTONCES debe marcar P_UP, R1, R2, R3 como ya alertados.
        
        Esto evita que al iniciar la sesión se envíen alertas de niveles
        que el precio ya superó históricamente.
        """
        current_price = 95000.0  # Por encima de R3 (92500)
        
        alerted = self._apply_tv_antispm_logic(current_price, self.levels_btc)
        
        self.assertIn('P_UP', alerted, "Debe marcar P_UP cuando precio > R3")
        self.assertIn('R1', alerted, "Debe marcar R1 cuando precio > R3")
        self.assertIn('R2', alerted, "Debe marcar R2 cuando precio > R3")
        self.assertIn('R3', alerted, "Debe marcar R3 cuando precio > R3")
        self.assertNotIn('P_DOWN', alerted, "No debe marcar P_DOWN en escenario alcista")
        self.assertNotIn('S1', alerted, "No debe marcar niveles de soporte en escenario alcista")

    def test_price_above_r2_marks_pivot_up_r1_and_r2(self):
        """
        CUANDO el precio está entre R2 y R3,
        ENTONCES debe marcar P_UP, R1, R2 como ya alertados (pero NO R3).
        """
        current_price = 91000.0  # Entre R2 (90000) y R3 (92500)
        
        alerted = self._apply_tv_antispm_logic(current_price, self.levels_btc)
        
        self.assertIn('P_UP', alerted, "Debe marcar P_UP cuando precio > R2")
        self.assertIn('R1', alerted, "Debe marcar R1 cuando precio > R2")
        self.assertIn('R2', alerted, "Debe marcar R2 cuando precio > R2")
        self.assertNotIn('R3', alerted, "NO debe marcar R3 si precio < R3")
        self.assertNotIn('P_DOWN', alerted, "No debe marcar P_DOWN en escenario alcista")

    def test_price_above_r1_marks_pivot_up_and_r1(self):
        """
        CUANDO el precio está entre R1 y R2,
        ENTONCES debe marcar P_UP, R1 como ya alertados (pero NO R2).
        """
        current_price = 88500.0  # Entre R1 (87500) y R2 (90000)
        
        alerted = self._apply_tv_antispm_logic(current_price, self.levels_btc)
        
        self.assertIn('P_UP', alerted, "Debe marcar P_UP cuando precio > R1")
        self.assertIn('R1', alerted, "Debe marcar R1 cuando precio > R1")
        self.assertNotIn('R2', alerted, "NO debe marcar R2 si precio < R2")
        self.assertNotIn('R3', alerted, "NO debe marcar R3 si precio < R3")
        self.assertNotIn('P_DOWN', alerted, "No debe marcar P_DOWN en escenario alcista")

    def test_price_above_pivot_marks_only_pivot_up(self):
        """
        CUANDO el precio está entre P y R1,
        ENTONCES debe marcar solo P_UP como ya alertado.
        """
        current_price = 86000.0  # Entre P (85000) y R1 (87500)
        
        alerted = self._apply_tv_antispm_logic(current_price, self.levels_btc)
        
        self.assertIn('P_UP', alerted, "Debe marcar P_UP cuando precio > P")
        self.assertNotIn('R1', alerted, "NO debe marcar R1 si precio < R1")
        self.assertNotIn('R2', alerted, "NO debe marcar R2 si precio < R2")
        self.assertNotIn('R3', alerted, "NO debe marcar R3 si precio < R3")
        self.assertNotIn('P_DOWN', alerted, "No debe marcar P_DOWN cuando precio > P")

    # ==========================================================================
    # TESTS PARA ESCENARIOS BAJISTAS (BEARISH)
    # ==========================================================================

    def test_price_below_s3_marks_all_support_and_pivot_down(self):
        """
        CUANDO el precio está por debajo de S3,
        ENTONCES debe marcar P_DOWN, S1, S2, S3 como ya alertados.
        
        Esto evita spam de alertas de soportes ya perforados.
        """
        current_price = 75000.0  # Por debajo de S3 (77500)
        
        alerted = self._apply_tv_antispm_logic(current_price, self.levels_btc)
        
        self.assertIn('P_DOWN', alerted, "Debe marcar P_DOWN cuando precio < S3")
        self.assertIn('S1', alerted, "Debe marcar S1 cuando precio < S3")
        self.assertIn('S2', alerted, "Debe marcar S2 cuando precio < S3")
        self.assertIn('S3', alerted, "Debe marcar S3 cuando precio < S3")
        self.assertNotIn('P_UP', alerted, "No debe marcar P_UP en escenario bajista")
        self.assertNotIn('R1', alerted, "No debe marcar niveles de resistencia en escenario bajista")

    def test_price_below_s2_marks_pivot_down_s1_and_s2(self):
        """
        CUANDO el precio está entre S3 y S2,
        ENTONCES debe marcar P_DOWN, S1, S2 como ya alertados (pero NO S3).
        """
        current_price = 78500.0  # Entre S3 (77500) y S2 (80000)
        
        alerted = self._apply_tv_antispm_logic(current_price, self.levels_btc)
        
        self.assertIn('P_DOWN', alerted, "Debe marcar P_DOWN cuando precio < S2")
        self.assertIn('S1', alerted, "Debe marcar S1 cuando precio < S2")
        self.assertIn('S2', alerted, "Debe marcar S2 cuando precio < S2")
        self.assertNotIn('S3', alerted, "NO debe marcar S3 si precio > S3")
        self.assertNotIn('P_UP', alerted, "No debe marcar P_UP en escenario bajista")

    def test_price_below_s1_marks_pivot_down_and_s1(self):
        """
        CUANDO el precio está entre S2 y S1,
        ENTONCES debe marcar P_DOWN, S1 como ya alertados (pero NO S2).
        """
        current_price = 81500.0  # Entre S2 (80000) y S1 (82500)
        
        alerted = self._apply_tv_antispm_logic(current_price, self.levels_btc)
        
        self.assertIn('P_DOWN', alerted, "Debe marcar P_DOWN cuando precio < S1")
        self.assertIn('S1', alerted, "Debe marcar S1 cuando precio < S1")
        self.assertNotIn('S2', alerted, "NO debe marcar S2 si precio > S2")
        self.assertNotIn('S3', alerted, "NO debe marcar S3 si precio > S3")
        self.assertNotIn('P_UP', alerted, "No debe marcar P_UP en escenario bajista")

    def test_price_below_pivot_marks_only_pivot_down(self):
        """
        CUANDO el precio está entre S1 y P,
        ENTONCES debe marcar solo P_DOWN como ya alertado.
        """
        current_price = 84000.0  # Entre S1 (82500) y P (85000)
        
        alerted = self._apply_tv_antispm_logic(current_price, self.levels_btc)
        
        self.assertIn('P_DOWN', alerted, "Debe marcar P_DOWN cuando precio < P")
        self.assertNotIn('S1', alerted, "NO debe marcar S1 si precio > S1")
        self.assertNotIn('S2', alerted, "NO debe marcar S2 si precio > S2")
        self.assertNotIn('S3', alerted, "NO debe marcar S3 si precio > S3")
        self.assertNotIn('P_UP', alerted, "No debe marcar P_UP cuando precio < P")

    # ==========================================================================
    # TESTS PARA GOLDEN POCKET
    # ==========================================================================

    def test_golden_pocket_up_when_price_above_fib_618(self):
        """
        CUANDO el precio está por encima del Golden Pocket (FIB_618),
        ENTONCES debe marcar FIB_618_UP como ya alertado.
        """
        current_price = 89000.0  # Por encima de FIB_618 (88000)
        
        alerted = self._apply_tv_antispm_logic(current_price, self.levels_btc)
        
        self.assertIn('FIB_618_UP', alerted, "Debe marcar FIB_618_UP cuando precio > FIB_618")
        self.assertNotIn('FIB_618_DOWN', alerted, "NO debe marcar FIB_618_DOWN cuando precio > FIB_618")

    def test_golden_pocket_down_when_price_below_fib_618(self):
        """
        CUANDO el precio está por debajo del Golden Pocket (FIB_618),
        ENTONCES debe marcar FIB_618_DOWN como ya alertado.
        """
        current_price = 87000.0  # Por debajo de FIB_618 (88000)
        
        alerted = self._apply_tv_antispm_logic(current_price, self.levels_btc)
        
        self.assertIn('FIB_618_DOWN', alerted, "Debe marcar FIB_618_DOWN cuando precio < FIB_618")
        self.assertNotIn('FIB_618_UP', alerted, "NO debe marcar FIB_618_UP cuando precio < FIB_618")

    def test_golden_pocket_combined_with_resistance_levels(self):
        """
        CUANDO el precio está por encima de R3 Y por encima del Golden Pocket,
        ENTONCES debe marcar todos los niveles de resistencia + FIB_618_UP.
        """
        current_price = 95000.0  # Por encima de todo
        
        alerted = self._apply_tv_antispm_logic(current_price, self.levels_btc)
        
        # Verificar niveles de resistencia
        self.assertIn('P_UP', alerted)
        self.assertIn('R1', alerted)
        self.assertIn('R2', alerted)
        self.assertIn('R3', alerted)
        # Verificar Golden Pocket
        self.assertIn('FIB_618_UP', alerted)

    def test_golden_pocket_combined_with_support_levels(self):
        """
        CUANDO el precio está por debajo de S3 Y por debajo del Golden Pocket,
        ENTONCES debe marcar todos los niveles de soporte + FIB_618_DOWN.
        """
        current_price = 75000.0  # Por debajo de todo
        
        alerted = self._apply_tv_antispm_logic(current_price, self.levels_btc)
        
        # Verificar niveles de soporte
        self.assertIn('P_DOWN', alerted)
        self.assertIn('S1', alerted)
        self.assertIn('S2', alerted)
        self.assertIn('S3', alerted)
        # Verificar Golden Pocket
        self.assertIn('FIB_618_DOWN', alerted)

    def test_golden_pocket_exact_at_fib_618(self):
        """
        CUANDO el precio está EXACTAMENTE en el Golden Pocket,
        ENTONCES debe marcar FIB_618_UP (por condicion >=).
        """
        current_price = 88000.0  # Exactamente en FIB_618
        
        alerted = self._apply_tv_antispm_logic(current_price, self.levels_btc)
        
        # El código usa >=, así que debe ser UP
        self.assertIn('FIB_618_UP', alerted, "Precio exacto en FIB_618 debe marcar FIB_618_UP (>=)")

    # ==========================================================================
    # TESTS PARA PRECISIÓN EN LÍMITES (EDGE CASES)
    # ==========================================================================

    def test_price_exactly_at_r3(self):
        """CUANDO el precio está EXACTAMENTE en R3, debe marcar hasta R3."""
        current_price = 92500.0  # Exactamente R3
        
        alerted = self._apply_tv_antispm_logic(current_price, self.levels_btc)
        
        self.assertIn('R3', alerted, "Precio exacto en R3 debe marcar R3")
        self.assertIn('R2', alerted)
        self.assertIn('R1', alerted)
        self.assertIn('P_UP', alerted)

    def test_price_exactly_at_pivot(self):
        """CUANDO el precio está EXACTAMENTE en P, debe marcar P_UP (>=)."""
        current_price = 85000.0  # Exactamente P
        
        alerted = self._apply_tv_antispm_logic(current_price, self.levels_btc)
        
        self.assertIn('P_UP', alerted, "Precio exacto en P debe marcar P_UP (>=)")
        self.assertNotIn('P_DOWN', alerted)

    def test_price_exactly_at_s3(self):
        """CUANDO el precio está EXACTAMENTE en S3, debe marcar hasta S3 (<=)."""
        current_price = 77500.0  # Exactamente S3
        
        alerted = self._apply_tv_antispm_logic(current_price, self.levels_btc)
        
        self.assertIn('S3', alerted, "Precio exacto en S3 debe marcar S3 (<=)")
        self.assertIn('S2', alerted)
        self.assertIn('S1', alerted)
        self.assertIn('P_DOWN', alerted)

    # ==========================================================================
    # TESTS CON DIFERENTES VALORES DE NIVELES
    # ==========================================================================

    def test_with_eth_levels(self):
        """Test con niveles típicos de ETH para verificar que funciona con diferentes valores."""
        levels_eth = {
            'P': 2500.0,
            'R1': 2600.0,
            'R2': 2700.0,
            'R3': 2800.0,
            'S1': 2400.0,
            'S2': 2300.0,
            'S3': 2200.0,
            'FIB_618': 2620.0
        }
        
        # Precio por encima de R2
        current_price = 2750.0
        alerted = self._apply_tv_antispm_logic(current_price, levels_eth)
        
        self.assertIn('P_UP', alerted)
        self.assertIn('R1', alerted)
        self.assertIn('R2', alerted)
        self.assertNotIn('R3', alerted)

    def test_with_low_price_levels(self):
        """Test con niveles bajos (ej: XRP, DOGE)."""
        levels_low = {
            'P': 0.50,
            'R1': 0.55,
            'R2': 0.60,
            'R3': 0.65,
            'S1': 0.45,
            'S2': 0.40,
            'S3': 0.35,
            'FIB_618': 0.56
        }

        # Precio por debajo de P pero por encima de S1 (0.45 < 0.47 < 0.50)
        # Debe marcar solo P_DOWN, no S1 porque 0.47 > S1(0.45)
        current_price = 0.47
        alerted = self._apply_tv_antispm_logic(current_price, levels_low)

        self.assertIn('P_DOWN', alerted)
        self.assertNotIn('S1', alerted)  # 0.47 > S1(0.45), no ha perforado S1
        self.assertNotIn('S2', alerted)

    # ==========================================================================
    # TEST DE INTEGRIDAD DE LA LISTA
    # ==========================================================================

    def test_no_duplicates_in_alerted_list(self):
        """
        Verifica que no haya duplicados en la lista de alertas.
        El código debe usar extend con listas únicas.
        """
        current_price = 95000.0
        alerted = self._apply_tv_antispm_logic(current_price, self.levels_btc)
        
        # Verificar que no hay duplicados
        self.assertEqual(len(alerted), len(set(alerted)), 
                        f"No debe haber duplicados en alerted_levels: {alerted}")

    def test_returns_list_type(self):
        """Verifica que siempre retorna una lista."""
        current_price = 86000.0
        alerted = self._apply_tv_antispm_logic(current_price, self.levels_btc)
        
        self.assertIsInstance(alerted, list, "Debe retornar una lista")


class TestValertsAntiSpamBoundaryConditions(unittest.TestCase):
    """Tests adicionales para condiciones de borde y casos extremos."""

    def setUp(self):
        """Niveles para tests de borde."""
        self.levels = {
            'P': 100.0,
            'R1': 110.0,
            'R2': 120.0,
            'R3': 130.0,
            'S1': 90.0,
            'S2': 80.0,
            'S3': 70.0,
            'FIB_618': 112.0
        }

    def _apply_logic(self, price, levels):
        """Helper con la misma lógica."""
        pre_filled_alerts = []
        
        if price >= levels['R3']:
            pre_filled_alerts.extend(['P_UP', 'R1', 'R2', 'R3'])
        elif price >= levels['R2']:
            pre_filled_alerts.extend(['P_UP', 'R1', 'R2'])
        elif price >= levels['R1']:
            pre_filled_alerts.extend(['P_UP', 'R1'])
        elif price >= levels['P']:
            pre_filled_alerts.append('P_UP')
        elif price <= levels['S3']:
            pre_filled_alerts.extend(['P_DOWN', 'S1', 'S2', 'S3'])
        elif price <= levels['S2']:
            pre_filled_alerts.extend(['P_DOWN', 'S1', 'S2'])
        elif price <= levels['S1']:
            pre_filled_alerts.extend(['P_DOWN', 'S1'])
        elif price < levels['P']:
            pre_filled_alerts.append('P_DOWN')
            
        if price >= levels['FIB_618']:
            if 'FIB_618_UP' not in pre_filled_alerts:
                pre_filled_alerts.append('FIB_618_UP')
        else:
            if 'FIB_618_DOWN' not in pre_filled_alerts:
                pre_filled_alerts.append('FIB_618_DOWN')
                
        return pre_filled_alerts

    def test_very_high_price(self):
        """Test con precio muy alto (10x R3)."""
        price = 1300.0
        alerted = self._apply_logic(price, self.levels)
        
        self.assertIn('P_UP', alerted)
        self.assertIn('R1', alerted)
        self.assertIn('R2', alerted)
        self.assertIn('R3', alerted)
        self.assertIn('FIB_618_UP', alerted)

    def test_very_low_price(self):
        """Test con precio muy bajo (casi 0)."""
        price = 0.01
        alerted = self._apply_logic(price, self.levels)
        
        self.assertIn('P_DOWN', alerted)
        self.assertIn('S1', alerted)
        self.assertIn('S2', alerted)
        self.assertIn('S3', alerted)
        self.assertIn('FIB_618_DOWN', alerted)

    def test_price_between_r1_and_fib_618(self):
        """
        CUANDO el precio está entre R1 y FIB_618,
        ENTONCES debe marcar P_UP, R1 (por >R1) y FIB_618_DOWN (por <FIB_618).
        """
        # FIB_618 está en 112, R1 en 110
        price = 111.0  # Entre R1 y FIB_618
        alerted = self._apply_logic(price, self.levels)
        
        self.assertIn('P_UP', alerted)
        self.assertIn('R1', alerted)
        self.assertNotIn('R2', alerted)
        self.assertIn('FIB_618_DOWN', alerted)  # Porque 111 < 112

    def test_price_between_fib_618_and_r2(self):
        """
        CUANDO el precio está entre FIB_618 y R2,
        ENTONCES debe marcar P_UP, R1 (por >R1) y FIB_618_UP (por >FIB_618).
        """
        price = 115.0  # Entre FIB_618 (112) y R2 (120)
        alerted = self._apply_logic(price, self.levels)
        
        self.assertIn('P_UP', alerted)
        self.assertIn('R1', alerted)
        self.assertNotIn('R2', alerted)
        self.assertIn('FIB_618_UP', alerted)  # Porque 115 > 112


if __name__ == '__main__':
    unittest.main(verbosity=2)
