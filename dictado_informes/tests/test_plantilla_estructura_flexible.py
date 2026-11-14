import json

from django.contrib.auth import get_user_model
from django.test import TestCase

from dictado_informes.ai_services import ai_service
from dictado_informes.forms import PlantillaEstructuradaForm
from dictado_informes.models import PlantillaEstructurada


class PlantillaEstructuraFlexibleTests(TestCase):
    def setUp(self):
        self.medico = get_user_model().objects.create_user(
            username='editor_plantillas', rol='piloto_dictado', perfil_completo=True,
        )

    def plantilla_editable(self):
        return PlantillaEstructurada.objects.create(
            codigo='IA_EDITABLE', nombre='RM Rodilla', titulo='RM DE RODILLA',
            seccion_tecnica='', comentarios_base=['Meniscos normales.'],
            creada_por=self.medico, compartida=False,
            origen='user', modo_estructura='estricta',
            estructura_documento={
                'modo': 'estricta', 'permitir_secciones_nuevas': False,
                'secciones': [
                    {'nombre': 'TITULO', 'tipo': 'titulo', 'contenido': 'RM DE RODILLA'},
                    {'nombre': 'HALLAZGOS', 'tipo': 'hallazgos',
                     'lineas_base': ['Meniscos normales.'], 'editable_por_ia': True},
                    {'nombre': 'CONCLUSION', 'tipo': 'conclusion', 'contenido': ''},
                ],
            },
        )

    def datos_edicion(self, plantilla):
        return {
            'codigo': plantilla.codigo, 'nombre': plantilla.nombre, 'titulo': plantilla.titulo,
            'seccion_tecnica': '', 'comentarios_base_texto': '\n'.join(plantilla.comentarios_base),
            'guia_estilo': '', 'modo_estructura': 'estricta',
            'estructura_documento_texto': json.dumps(plantilla.estructura_documento),
            'activa': 'on',
        }

    def test_edicion_sencilla_actualiza_contrato_sin_exigir_tecnica(self):
        plantilla = self.plantilla_editable()
        datos = self.datos_edicion(plantilla)
        datos.update(
            titulo='RM DE RODILLA IZQUIERDA',
            comentarios_base_texto='Meniscos de morfologia conservada.',
            guia_estilo='Redacción breve en párrafos.',
        )
        form = PlantillaEstructuradaForm(data=datos, instance=plantilla)
        self.assertTrue(form.is_valid(), form.errors.as_json())
        plantilla = form.save()
        salida = ai_service._get_plantilla_estructurada(plantilla.codigo, self.medico)
        self.assertEqual(salida['estructura_documento']['secciones'][0]['contenido'], datos['titulo'])
        self.assertEqual(salida['estructura_documento']['secciones'][1]['lineas_base'],
                         plantilla.comentarios_base)
        self.assertEqual(plantilla.seccion_tecnica, '')
        self.assertEqual([s['nombre'] for s in salida['estructura_documento']['secciones']],
                         ['TITULO', 'HALLAZGOS', 'CONCLUSION'])
        self.assertEqual(salida['guia_estilo'], datos['guia_estilo'])

    def test_edicion_avanzada_sincroniza_campos_y_conflicto_no_se_guarda(self):
        plantilla = self.plantilla_editable()
        datos = self.datos_edicion(plantilla)
        estructura = json.loads(datos['estructura_documento_texto'])
        estructura['secciones'][1]['lineas_base'] = ['Ligamentos conservados.']
        datos['estructura_documento_texto'] = json.dumps(estructura)
        form = PlantillaEstructuradaForm(data=datos, instance=plantilla)
        self.assertTrue(form.is_valid(), form.errors.as_json())
        plantilla = form.save()
        self.assertEqual(plantilla.comentarios_base, ['Ligamentos conservados.'])
        datos = self.datos_edicion(plantilla)
        estructura['secciones'][1]['lineas_base'] = ['Meniscos normales.']
        datos['estructura_documento_texto'] = json.dumps(estructura)
        datos['comentarios_base_texto'] = 'Tendones conservados.'
        form = PlantillaEstructuradaForm(data=datos, instance=plantilla)
        self.assertFalse(form.is_valid())
        self.assertIn('comentarios_base_texto', form.errors)

    def test_edicion_simple_no_aplana_multiples_secciones_anatomicas(self):
        plantilla = self.plantilla_editable()
        plantilla.estructura_documento['secciones'].insert(2, {
            'nombre': 'LIGAMENTOS', 'tipo': 'hallazgos', 'lineas_base': ['Ligamentos normales.'],
        })
        plantilla.save()
        datos = self.datos_edicion(plantilla)
        datos['comentarios_base_texto'] = 'Anatomia conservada.'
        form = PlantillaEstructuradaForm(data=datos, instance=plantilla)
        self.assertFalse(form.is_valid())
        self.assertIn('comentarios_base_texto', form.errors)

    def test_estilo_en_parrafos_no_impone_lineas_ni_duplica_normalidades(self):
        plantilla = self.plantilla_editable()
        plantilla.comentarios_base = ['Meniscos normales.', 'Ligamentos conservados.']
        plantilla.guia_estilo = 'Presentar hallazgos en párrafos.'
        plantilla.save()
        actual = ai_service._get_plantilla_estructurada(plantilla.codigo, self.medico)
        system = ai_service._system_message_estructurado(actual)
        self.assertIn('según la guía de estilo', system)
        self.assertNotIn('nunca todo junto en un párrafo', system)
        contrato = ai_service._construir_contrato_estructura_flexible(actual)
        self.assertIn('parrafos segun la guia de estilo', contrato['formato_salida'])
        informe = 'RM DE RODILLA\n\nHALLAZGOS\nMeniscos normales. Ligamentos conservados.\n\nCONCLUSION\n'
        resultado, restauradas = ai_service._aplicar_guardrails_estructurado('', informe, actual)
        self.assertEqual(resultado, informe)
        self.assertEqual(restauradas, [])
        self.assertIn('nunca todo junto en un párrafo', ai_service._system_message_estructurado({}))

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
