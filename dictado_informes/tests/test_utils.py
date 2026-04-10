"""
test_utils.py — Tests para dictado_informes/utils.py.

Verifica que los regex precompilados están disponibles y bien formados.
"""
import re

from django.test import TestCase

from dictado_informes.utils import REGEX_COMANDOS_VOZ, REGEX_GRADOS, REGEX_LIMPIEZA


class RegexPrecompiladosTests(TestCase):
    """Verifica que los dicts de regex se importan y son objetos re.Pattern."""

    def test_regex_comandos_voz_importa(self):
        self.assertIn('nueva_linea', REGEX_COMANDOS_VOZ)
        self.assertIn('punto', REGEX_COMANDOS_VOZ)
        self.assertIn('coma', REGEX_COMANDOS_VOZ)

    def test_regex_grados_importa(self):
        self.assertIn('grado_1', REGEX_GRADOS)
        self.assertIn('grado_4', REGEX_GRADOS)

    def test_regex_limpieza_importa(self):
        self.assertIn('doble_punto', REGEX_LIMPIEZA)
        self.assertIn('newlines_multiples', REGEX_LIMPIEZA)

    def test_todos_son_pattern(self):
        """Todos los valores en los tres dicts son re.Pattern compilados."""
        for nombre, patron in REGEX_COMANDOS_VOZ.items():
            self.assertIsInstance(patron, re.Pattern, msg=f"REGEX_COMANDOS_VOZ['{nombre}']")
        for nombre, patron in REGEX_GRADOS.items():
            self.assertIsInstance(patron, re.Pattern, msg=f"REGEX_GRADOS['{nombre}']")
        for nombre, patron in REGEX_LIMPIEZA.items():
            self.assertIsInstance(patron, re.Pattern, msg=f"REGEX_LIMPIEZA['{nombre}']")

    def test_nueva_linea_matchea(self):
        """Comprueba que el patrón nueva_linea funciona con una frase real."""
        resultado = REGEX_COMANDOS_VOZ['nueva_linea'].sub('\n', 'hallazgo nueva línea otro hallazgo')
        self.assertIn('\n', resultado)
        self.assertNotIn('nueva línea', resultado)

    def test_grado_1_reemplaza(self):
        """El regex de grado 1 matchea 'grado 1' correctamente."""
        resultado = REGEX_GRADOS['grado_1'].sub('grado I', 'estenosis grado 1 leve')
        self.assertIn('grado I', resultado)
        self.assertNotIn('grado 1', resultado)
