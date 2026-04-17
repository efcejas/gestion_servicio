"""
Tests para guardrails de modo estructurado en AIService.
"""
from django.test import TestCase

from dictado_informes.ai_services import AIService


class AIGuardrailsTests(TestCase):
    def setUp(self):
        self.ai = AIService()

    def test_guardrail_restaurar_linea_no_mencionada(self):
        texto_original = "Rodilla derecha con desgarro del ligamento cruzado anterior y derrame articular."
        texto_mejorado = """RM DE RODILLA DERECHA

INFORMACIÓN CLÍNICA
Trauma.

TÉCNICA
Se exploró la rodilla derecha.

COMENTARIO
Desgarro del ligamento cruzado anterior.
Derrame articular.

CONCLUSIÓN
Desgarro del LCA con derrame articular.
"""
        plantilla = {
            'comentarios': [
                'Meniscos de altura y señal normales.',
                'Ligamentos cruzados de trayecto y morfología conservados.',
                'Rótula centrada, sin lesión visible.',
            ]
        }

        texto_final, restauradas = self.ai._aplicar_guardrails_estructurado(
            texto_original=texto_original,
            texto_mejorado=texto_mejorado,
            plantilla_actual=plantilla,
        )

        self.assertIn('Meniscos de altura y señal normales.', texto_final)
        self.assertIn('Rótula centrada, sin lesión visible.', texto_final)
        self.assertNotIn('Ligamentos cruzados de trayecto y morfología conservados.', texto_final)
        self.assertEqual(len(restauradas), 2)

    def test_guardrail_no_repetir_linea_ya_presente(self):
        texto_original = "Rodilla sin hallazgos patológicos relevantes."
        texto_mejorado = """COMENTARIO
Meniscos de altura y señal normales.
Rótula centrada, sin lesión visible.

CONCLUSIÓN
Estudio dentro de parámetros normales.
"""
        plantilla = {
            'comentarios': [
                'Meniscos de altura y señal normales.',
                'Rótula centrada, sin lesión visible.',
            ]
        }

        texto_final, restauradas = self.ai._aplicar_guardrails_estructurado(
            texto_original=texto_original,
            texto_mejorado=texto_mejorado,
            plantilla_actual=plantilla,
        )

        self.assertEqual(texto_final.count('Meniscos de altura y señal normales.'), 1)
        self.assertEqual(texto_final.count('Rótula centrada, sin lesión visible.'), 1)
        self.assertEqual(restauradas, [])

    def test_detector_invencion_marca_termino_no_dictado(self):
        texto_original = "Dolor de rodilla derecha sin antecedente traumático."
        texto_mejorado = """COMENTARIO
Meniscos de altura y señal normales.
Desgarro del menisco interno.

CONCLUSIÓN
Desgarro meniscal.
"""
        plantilla = {
            'comentarios': [
                'Meniscos de altura y señal normales.',
                'Rótula centrada, sin lesión visible.',
            ]
        }

        analisis = self.ai._detectar_posible_invencion_estructurada(
            texto_original=texto_original,
            texto_mejorado=texto_mejorado,
            plantilla_actual=plantilla,
            modo='ESTRUCTURADO',
        )

        self.assertTrue(analisis['detectada'])
        self.assertIn('desgarro', analisis['terminos_sospechosos'])

    def test_detector_invencion_no_marca_termino_dictado(self):
        texto_original = "Dolor de rodilla con desgarro meniscal interno."
        texto_mejorado = """COMENTARIO
Desgarro del menisco interno.

CONCLUSIÓN
Desgarro meniscal.
"""
        plantilla = {'comentarios': []}

        analisis = self.ai._detectar_posible_invencion_estructurada(
            texto_original=texto_original,
            texto_mejorado=texto_mejorado,
            plantilla_actual=plantilla,
            modo='ESTRUCTURADO',
        )

        self.assertFalse(analisis['detectada'])

    def test_detector_invencion_no_marca_si_estructura_esta_en_dictado(self):
        texto_original = "Dolor de rodilla con menisco interno lesionado."
        texto_mejorado = """COMENTARIO
Desgarro del menisco interno.

CONCLUSIÓN
Desgarro meniscal.
"""
        plantilla = {'comentarios': []}

        analisis = self.ai._detectar_posible_invencion_estructurada(
            texto_original=texto_original,
            texto_mejorado=texto_mejorado,
            plantilla_actual=plantilla,
            modo='ESTRUCTURADO',
        )

        self.assertFalse(analisis['detectada'])
