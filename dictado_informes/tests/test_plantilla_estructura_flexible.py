from django.test import TestCase

from dictado_informes.forms import PlantillaEstructuradaForm
from dictado_informes.models import PlantillaEstructurada


class PlantillaEstructuraFlexibleTests(TestCase):
    def test_legacy_deriva_estructura_con_conclusion_para_compatibilidad(self):
        plantilla = PlantillaEstructurada.objects.create(
            codigo='LEGACY_RODILLA',
            nombre='RM Rodilla legacy',
            titulo='RM DE RODILLA [<DERECHA/IZQUIERDA>]',
            seccion_tecnica='Se exploro la rodilla con secuencias habituales.',
            comentarios_base=[
                'Meniscos de altura y senal normales.',
                'No se observa aumento del liquido articular.',
            ],
            origen='legacy',
        )

        estructura = plantilla.obtener_estructura_documento()
        nombres = [s['nombre'] for s in estructura['secciones']]

        self.assertEqual(estructura['modo'], PlantillaEstructurada.MODO_ESTRUCTURA_LEGACY)
        self.assertIn('TITULO', nombres)
        self.assertIn('TECNICA', nombres)
        self.assertIn('COMENTARIO', nombres)
        self.assertIn('CONCLUSION', nombres)
        self.assertTrue(plantilla.tiene_seccion('conclusión'))

    def test_estructura_importada_sin_conclusion_no_permita_agregarla(self):
        plantilla = PlantillaEstructurada.objects.create(
            codigo='WORD_SIN_CONCLUSION',
            nombre='Plantilla Word sin conclusion',
            titulo='RM DE RODILLA',
            seccion_tecnica='Tecnica base',
            comentarios_base=[],
            origen='user',
            modo_estructura=PlantillaEstructurada.MODO_ESTRUCTURA_ESTRICTA,
            permitir_secciones_nuevas=False,
            estructura_documento={
                'modo': 'estricta',
                'permitir_secciones_nuevas': False,
                'secciones': [
                    {
                        'nombre': 'TITULO',
                        'tipo': 'titulo',
                        'contenido': 'RM DE RODILLA',
                        'editable_por_ia': True,
                    },
                    {
                        'nombre': 'TECNICA',
                        'tipo': 'tecnica',
                        'contenido': 'Tecnica base',
                        'editable_por_ia': False,
                    },
                    {
                        'nombre': 'HALLAZGOS',
                        'tipo': 'hallazgos',
                        'lineas_base': ['Meniscos de configuracion habitual.'],
                        'editable_por_ia': True,
                    },
                ],
            },
        )

        estructura = plantilla.obtener_estructura_documento()
        nombres = [s['nombre'] for s in estructura['secciones']]

        self.assertEqual(nombres, ['TITULO', 'TECNICA', 'HALLAZGOS'])
        self.assertFalse(plantilla.tiene_seccion('CONCLUSION'))
        self.assertFalse(plantilla.puede_agregar_seccion('CONCLUSION'))

    def test_estructura_flexible_permite_seccion_nueva_si_esta_habilitada(self):
        plantilla = PlantillaEstructurada.objects.create(
            codigo='WORD_FLEXIBLE',
            nombre='Plantilla Word flexible',
            titulo='RM',
            seccion_tecnica='Tecnica',
            comentarios_base=[],
            modo_estructura=PlantillaEstructurada.MODO_ESTRUCTURA_FLEXIBLE,
            permitir_secciones_nuevas=True,
            estructura_documento={
                'secciones': [
                    {'nombre': 'HALLAZGOS', 'tipo': 'hallazgos', 'lineas_base': []},
                ],
            },
        )

        self.assertTrue(plantilla.puede_agregar_seccion('CONCLUSION'))

    def test_form_guarda_estructura_flexible_valida(self):
        form = PlantillaEstructuradaForm(data={
            'codigo': 'FORM_FLEXIBLE',
            'nombre': 'Plantilla form flexible',
            'titulo': 'RM DE RODILLA',
            'seccion_tecnica': 'Tecnica base',
            'comentarios_base_texto': '',
            'guia_estilo': '',
            'modo_estructura': PlantillaEstructurada.MODO_ESTRUCTURA_ESTRICTA,
            'permitir_secciones_nuevas': '',
            'estructura_documento_texto': (
                '{"secciones": ['
                '{"nombre": "TITULO", "tipo": "titulo", "contenido": "RM DE RODILLA"},'
                '{"nombre": "HALLAZGOS", "tipo": "hallazgos", "lineas_base": ["Meniscos normales."]}'
                ']}'
            ),
            'activa': 'on',
        })

        self.assertTrue(form.is_valid(), form.errors.as_json())
        plantilla = form.save()

        self.assertEqual(plantilla.modo_estructura, PlantillaEstructurada.MODO_ESTRUCTURA_ESTRICTA)
        self.assertEqual(plantilla.estructura_documento['modo'], PlantillaEstructurada.MODO_ESTRUCTURA_ESTRICTA)
        self.assertFalse(plantilla.estructura_documento['permitir_secciones_nuevas'])
        self.assertFalse(plantilla.tiene_seccion('CONCLUSION'))

    def test_form_rechaza_modo_no_legacy_sin_json(self):
        form = PlantillaEstructuradaForm(data={
            'codigo': 'FORM_SIN_JSON',
            'nombre': 'Plantilla sin json',
            'titulo': 'RM',
            'seccion_tecnica': 'Tecnica',
            'comentarios_base_texto': '',
            'guia_estilo': '',
            'modo_estructura': PlantillaEstructurada.MODO_ESTRUCTURA_ESTRICTA,
            'estructura_documento_texto': '',
            'activa': 'on',
        })

        self.assertFalse(form.is_valid())
        self.assertIn('estructura_documento_texto', form.errors)

    def test_form_rechaza_json_sin_secciones(self):
        form = PlantillaEstructuradaForm(data={
            'codigo': 'FORM_JSON_MALO',
            'nombre': 'Plantilla json malo',
            'titulo': 'RM',
            'seccion_tecnica': 'Tecnica',
            'comentarios_base_texto': '',
            'guia_estilo': '',
            'modo_estructura': PlantillaEstructurada.MODO_ESTRUCTURA_ESTRICTA,
            'estructura_documento_texto': '{"modo": "estricta"}',
            'activa': 'on',
        })

        self.assertFalse(form.is_valid())
        self.assertIn('estructura_documento_texto', form.errors)
