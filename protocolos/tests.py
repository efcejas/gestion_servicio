from django.test import TestCase


class ProtocolosSmokeTest(TestCase):
    """Tests mínimos: verifica que los modelos importan y el módulo carga correctamente."""

    def test_models_import(self):
        """Los modelos del módulo protocolos importan sin errores."""
        from protocolos import models  # noqa: F401

    def test_modalidad_model_has_str(self):
        """El modelo Modalidad puede instanciarse y tiene __str__."""
        from protocolos.models import Modalidad
        m = Modalidad(codigo='TC', nombre='Tomografía')
        self.assertIn('TC', str(m))

    def test_urls_resuelven(self):
        """Las URLs principales del módulo resuelven sin errores."""
        from django.urls import reverse
        lista = reverse('protocolos:lista')
        self.assertTrue(lista.startswith('/'))
