import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from .buscador_casos_service import BuscadorCasosIA


class BuscadorCasosIAServiceTest(SimpleTestCase):
    @patch('preinformes.buscador_casos_service.cache')
    @patch('preinformes.buscador_casos_service.OpenAI')
    @patch('preinformes.buscador_casos_service.config')
    def test_interpreta_con_salida_estructurada_y_sanitiza_documento(
        self, config_mock, openai_mock, cache_mock
    ):
        config_mock.return_value = 'fake-key'
        cache_mock.get.return_value = None
        cliente = MagicMock()
        openai_mock.return_value = cliente
        payload = {
            'consulta_corregida': 'tumor de colon',
            'terminos': ['adenocarcinoma de colon', 'neoplasia colónica'],
            'tipo_estudio': 'TC',
            'region': 'colon',
            'explicacion': 'Busca tumores colónicos y sinónimos.',
        }
        cliente.chat.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(payload)))]
        )

        resultado = BuscadorCasosIA().interpretar(
            'tumro de colon del paciente DNI 12345678'
        )

        self.assertTrue(resultado['success'])
        self.assertEqual(resultado['tipo_estudio'], 'TC')
        llamada = cliente.chat.completions.create.call_args.kwargs
        self.assertEqual(llamada['response_format']['type'], 'json_schema')
        self.assertNotIn('12345678', llamada['messages'][1]['content'])
        self.assertIn('[documento omitido]', llamada['messages'][1]['content'])

    @patch('preinformes.buscador_casos_service.config', return_value=None)
    def test_sin_api_key_degrada_a_busqueda_literal(self, _config_mock):
        resultado = BuscadorCasosIA().interpretar('neumonía redonda')

        self.assertFalse(resultado['success'])
        self.assertEqual(resultado['terminos'], ['neumonía redonda'])
