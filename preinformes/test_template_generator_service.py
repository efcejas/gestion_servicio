from types import SimpleNamespace
from unittest.mock import MagicMock

from django.contrib.auth import get_user_model
from django.test import TestCase

from dictado_informes.ai_services import AIService
from equipos.models import AreaServicio, EquipoImagen

from .exceptions import GeneracionPlantillaError, RespuestaPlantillaInvalidaError
from .models import PropuestaPlantillaPreinforme, Region, TipoEstudio
from .template_generator_service import (
    PLANTILLA_RESPONSE_SCHEMA,
    TemplateGeneratorService,
)


User = get_user_model()


class FakeAIGateway:
    def __init__(self, data):
        self.data = data
        self.calls = []

    def generate_structured_json(self, **kwargs):
        self.calls.append(kwargs)
        return {
            'data': self.data,
            'model_used': 'modelo-prueba',
            'provider': 'proveedor-prueba',
        }


def respuesta_rm_muneca():
    return {
        'titulo': 'RESONANCIA MAGNÉTICA DE MUÑECA [[lateralidad]]',
        'encabezado': (
            'Se exploró la muñeca [[lateralidad]] en el equipo [[equipo]], '
            'con secuencias ponderadas en T1, T2 y STIR.'
        ),
        'hallazgos': [
            'Estructuras óseas de morfología y señal conservadas.',
            'Tendones flexores y extensores sin alteraciones.',
            'Fibrocartílago triangular de morfología y señal conservadas.',
        ],
        'variables': [
            {
                'codigo': 'lateralidad',
                'tipo': 'opcion',
                'requerida': True,
                'opciones': ['derecha', 'izquierda', 'bilateral'],
            },
            {
                'codigo': 'equipo',
                'tipo': 'equipo',
                'requerida': True,
                'opciones': [],
            },
        ],
        'fuentes_utilizadas': ['fuente-rm-muneca'],
        'advertencias': [],
    }


class TemplateGeneratorServiceTest(TestCase):
    def setUp(self):
        self.tipo_estudio = TipoEstudio.objects.create(nombre='Resonancia magnética')
        self.region = Region.objects.create(nombre='Miembro superior')
        self.residente = User.objects.create_user(
            username='residente_generador',
            password='test',
            rol='medico_residente',
            perfil_completo=True,
        )
        self.administrativo = User.objects.create_user(
            username='administrativo_generador',
            password='test',
            rol='administrativo',
            perfil_completo=True,
        )
        self.fuentes = [
            {
                'id': 'fuente-rm-muneca',
                'titulo': 'Guía institucional de RM musculoesquelética',
                'entidad': 'Servicio de Diagnóstico por Imágenes',
                'version': '1',
                'criterios': 'Describir estructuras óseas, tendones y FCT.',
            }
        ]

    def generar(self, gateway, **kwargs):
        datos = {
            'autor': self.residente,
            'tipo_estudio': self.tipo_estudio,
            'region': self.region,
            'estudio_especifico': 'RM de muñeca',
            'instruccion_usuario': 'Necesito una plantilla breve.',
            'lateralidad_aplicable': True,
            'equipo_aplicable': True,
            'fuentes_autorizadas': self.fuentes,
        }
        datos.update(kwargs)
        return TemplateGeneratorService(gateway).generar_propuesta(**datos)

    def test_genera_y_persiste_propuesta_estructurada(self):
        gateway = FakeAIGateway(respuesta_rm_muneca())

        propuesta = self.generar(gateway)

        self.assertEqual(
            propuesta.estado,
            PropuestaPlantillaPreinforme.ESTADO_BORRADOR,
        )
        self.assertEqual(propuesta.modelo_ia, 'modelo-prueba')
        self.assertEqual(propuesta.proveedor_ia, 'proveedor-prueba')
        self.assertEqual(propuesta.version_instrucciones, 'plantilla-institucional-v2')
        self.assertEqual(propuesta.fuentes[0]['id'], 'fuente-rm-muneca')
        self.assertEqual(len(propuesta.hallazgos.splitlines()), 3)
        self.assertEqual(len(gateway.calls), 1)
        self.assertEqual(
            gateway.calls[0]['schema'],
            PLANTILLA_RESPONSE_SCHEMA,
        )
        self.assertEqual(
            propuesta.titulo,
            'RESONANCIA MAGNÉTICA DE MUÑECA [[lateralidad]]',
        )
        self.assertNotIn('contraste', propuesta.encabezado.lower())

    def test_limpia_html_de_la_respuesta(self):
        data = respuesta_rm_muneca()
        data['titulo'] = '<strong>RM DE MUÑECA [[lateralidad]]</strong>'
        data['hallazgos'][0] = '<script>alert(1)</script>Estructuras óseas conservadas.'

        propuesta = self.generar(FakeAIGateway(data))

        self.assertNotIn('<strong>', propuesta.titulo)
        self.assertNotIn('<script>', propuesta.hallazgos)

    def test_impone_opciones_canonicas_de_lateralidad(self):
        data = respuesta_rm_muneca()
        data['variables'][0]['opciones'] = ['BILATERAL', 'IZQUIERDA', 'DERECHA']

        propuesta = self.generar(FakeAIGateway(data))

        self.assertEqual(
            propuesta.variables[0]['opciones'],
            ['derecha', 'izquierda', 'bilateral'],
        )

    def test_descarta_opciones_generadas_para_variables_booleanas_y_numericas(self):
        data = respuesta_rm_muneca()
        data['encabezado'] += ' [[contraste_ev]]'
        data['variables'].extend([
            {
                'codigo': 'contraste_ev',
                'tipo': 'booleano',
                'requerida': True,
                'opciones': ['sí', 'no'],
            },
            {
                'codigo': 'volumen_contraste_ml',
                'tipo': 'numero',
                'requerida': True,
                'opciones': ['10', '20'],
            },
        ])

        propuesta = self.generar(
            FakeAIGateway(data),
            contraste_ev_aplicable=True,
        )

        variables = {
            variable['codigo']: variable
            for variable in propuesta.variables
        }
        self.assertEqual(variables['contraste_ev']['opciones'], [])
        self.assertEqual(variables['volumen_contraste_ml']['opciones'], [])

    def test_corrige_tipo_de_variable_declarado_por_la_ia(self):
        data = respuesta_rm_muneca()
        data['encabezado'] += ' [[contraste_ev]]'
        data['variables'].append({
            'codigo': 'contraste_ev',
            'tipo': 'texto',
            'requerida': True,
            'opciones': [],
        })

        propuesta = self.generar(
            FakeAIGateway(data),
            contraste_ev_aplicable=True,
        )

        contraste = next(
            variable for variable in propuesta.variables
            if variable['codigo'] == 'contraste_ev'
        )
        self.assertEqual(contraste['tipo'], 'booleano')

    def test_completa_variables_y_marcadores_omitidos_por_la_ia(self):
        data = respuesta_rm_muneca()
        data['encabezado'] = 'Se exploró la articulación en los diferentes planos.'
        data['variables'] = [data['variables'][0]]

        propuesta = self.generar(
            FakeAIGateway(data),
            contraste_ev_aplicable=True,
        )

        codigos = [variable['codigo'] for variable in propuesta.variables]
        self.assertEqual(
            codigos,
            [
                'lateralidad',
                'equipo',
                'contraste_ev',
                'marca_contraste',
                'volumen_contraste_ml',
            ],
        )
        self.assertIn('[[equipo]]', propuesta.encabezado)
        self.assertIn('[[contraste_ev]]', propuesta.encabezado)

    def test_lateralidad_concuerda_con_sustantivo_masculino(self):
        data = respuesta_rm_muneca()
        gateway = FakeAIGateway(data)

        propuesta = self.generar(
            gateway,
            estudio_especifico='RM de tobillo',
        )

        lateralidad = next(
            variable for variable in propuesta.variables
            if variable['codigo'] == 'lateralidad'
        )
        self.assertEqual(
            lateralidad['opciones'],
            ['derecho', 'izquierdo', 'bilateral'],
        )
        equipo = EquipoImagen.objects.create(
            nombre='Resonador',
            area=AreaServicio.RESONANCIA,
        )
        contenido = TemplateGeneratorService(gateway).renderizar_propuesta(
            propuesta=propuesta,
            valores={
                'lateralidad': 'derecho',
                'equipo': equipo.pk,
            },
        )
        self.assertIn('TOBILLO DERECHO', contenido)

    def test_rechaza_fuente_inventada(self):
        data = respuesta_rm_muneca()
        data['fuentes_utilizadas'] = ['bibliografia-inventada']

        with self.assertRaises(RespuestaPlantillaInvalidaError):
            self.generar(FakeAIGateway(data))

    def test_rechaza_conclusion(self):
        data = respuesta_rm_muneca()
        data['hallazgos'].append('Conclusión: estudio sin alteraciones.')

        with self.assertRaises(RespuestaPlantillaInvalidaError):
            self.generar(FakeAIGateway(data))

    def test_rechaza_variables_que_no_coinciden_con_el_formulario(self):
        data = respuesta_rm_muneca()
        data['variables'].append({
            'codigo': 'contraste_ev',
            'tipo': 'booleano',
            'requerida': True,
            'opciones': [],
        })
        data['encabezado'] += ' [[contraste_ev]]'

        with self.assertRaises(RespuestaPlantillaInvalidaError):
            self.generar(FakeAIGateway(data), contraste_ev_aplicable=False)

    def test_rechaza_marcadores_desconocidos(self):
        data = respuesta_rm_muneca()
        data['encabezado'] += ' [[campo_libre]]'

        with self.assertRaises(RespuestaPlantillaInvalidaError):
            self.generar(FakeAIGateway(data))

    def test_usuario_no_medico_no_invoca_la_ia(self):
        gateway = FakeAIGateway(respuesta_rm_muneca())

        with self.assertRaises(GeneracionPlantillaError):
            self.generar(gateway, autor=self.administrativo)

        self.assertEqual(gateway.calls, [])

    def test_error_del_proveedor_no_deja_propuesta_parcial(self):
        gateway = MagicMock()
        gateway.generate_structured_json.side_effect = RuntimeError('API caída')

        with self.assertRaises(GeneracionPlantillaError):
            self.generar(gateway)

        self.assertEqual(PropuestaPlantillaPreinforme.objects.count(), 0)

    def test_renderiza_variables_sin_dejar_marcadores(self):
        data = respuesta_rm_muneca()
        gateway = FakeAIGateway(data)
        propuesta = self.generar(gateway)
        equipo = EquipoImagen.objects.create(
            nombre='Resonador principal',
            area=AreaServicio.RESONANCIA,
            fabricante='Philips',
            modelo='Ingenia',
        )

        contenido = TemplateGeneratorService(gateway).renderizar_propuesta(
            propuesta=propuesta,
            valores={
                'lateralidad': 'derecha',
                'equipo': str(equipo.pk),
            },
        )

        self.assertIn('MUÑECA DERECHA', contenido)
        self.assertIn('Resonador principal (Philips Ingenia)', contenido)
        self.assertNotIn('[[', contenido)

    def test_renderiza_contraste_ev_y_volumen_condicional(self):
        data = respuesta_rm_muneca()
        data['encabezado'] += ' [[contraste_ev]]'
        data['variables'].extend([
            {
                'codigo': 'contraste_ev',
                'tipo': 'booleano',
                'requerida': True,
                'opciones': [],
            },
            {
                'codigo': 'volumen_contraste_ml',
                'tipo': 'numero',
                'requerida': True,
                'opciones': [],
            },
        ])
        gateway = FakeAIGateway(data)
        propuesta = self.generar(
            gateway,
            contraste_ev_aplicable=True,
            contraste_oral_aplicable=True,
        )
        equipo = EquipoImagen.objects.create(
            nombre='Resonador',
            area=AreaServicio.RESONANCIA,
        )

        contenido = TemplateGeneratorService(gateway).renderizar_propuesta(
            propuesta=propuesta,
            valores={
                'lateralidad': 'izquierda',
                'equipo': equipo.pk,
                'contraste_ev': True,
                'marca_contraste': 'Otro',
                'volumen_contraste_ml': '12.5',
                'contraste_oral': True,
            },
        )

        self.assertIn('contraste paramagnético Otro', contenido)
        self.assertIn('con un volumen de 12.5 ml', contenido)
        self.assertNotIn('(12.5 ml)', contenido)
        self.assertIn('CON CTE. EV. Y ORAL', contenido)

    def test_titulo_sin_contraste_no_agrega_sufijo(self):
        gateway = FakeAIGateway(respuesta_rm_muneca())
        propuesta = self.generar(gateway)
        equipo = EquipoImagen.objects.create(
            nombre='Resonador sin contraste',
            area=AreaServicio.RESONANCIA,
        )

        contenido = TemplateGeneratorService(gateway).renderizar_propuesta(
            propuesta=propuesta,
            valores={
                'lateralidad': 'derecha',
                'equipo': equipo.pk,
            },
        )

        self.assertNotIn('CON CTE.', contenido)

    def test_angio_tc_fija_contraste_y_no_lo_agrega_al_titulo(self):
        tipo_tc = TipoEstudio.objects.create(nombre='Tomografía computada')
        data = respuesta_rm_muneca()
        data['titulo'] = 'ANGIO-TC DE TÓRAX - PROTOCOLO PARA TEP'
        data['encabezado'] = (
            'Se realizó Angio-TC de tórax mediante adquisición angiográfica '
            '[[equipo]] [[contraste_ev]].'
        )
        data['variables'] = [
            {
                'codigo': 'equipo',
                'tipo': 'equipo',
                'requerida': False,
                'opciones': [],
            },
            {
                'codigo': 'contraste_ev',
                'tipo': 'booleano',
                'requerida': True,
                'opciones': [],
            },
            {
                'codigo': 'marca_contraste',
                'tipo': 'texto',
                'requerida': False,
                'opciones': [],
            },
            {
                'codigo': 'volumen_contraste_ml',
                'tipo': 'numero',
                'requerida': False,
                'opciones': [],
            },
        ]
        gateway = FakeAIGateway(data)
        propuesta = self.generar(
            gateway,
            tipo_estudio=tipo_tc,
            estudio_especifico='Angio-TC de tórax - Protocolo para TEP',
            lateralidad_aplicable=False,
            contraste_ev_aplicable=True,
        )

        contraste = next(
            variable for variable in propuesta.variables
            if variable['codigo'] == 'contraste_ev'
        )
        self.assertIs(contraste['valor_fijo'], True)

        contenido = TemplateGeneratorService(gateway).renderizar_propuesta(
            propuesta=propuesta,
            valores={
                'equipo': '',
                'contraste_ev': True,
                'marca_contraste': 'Iopamidol',
                'volumen_contraste_ml': '90',
            },
        )

        titulo = contenido.split('</strong>', 1)[0]
        self.assertNotIn('CON CTE. EV.', titulo)
        self.assertIn('adquisición angiográfica', contenido)
        self.assertIn('contraste yodado Iopamidol', contenido)
        self.assertIn('un volumen de 90 ml', contenido)
        self.assertNotIn('previas y posteriores', contenido)

        TemplateGeneratorService(gateway).actualizar_borrador(
            propuesta=propuesta,
            usuario=self.residente,
            titulo=propuesta.titulo,
            encabezado=propuesta.encabezado,
            hallazgos=propuesta.hallazgos,
        )

        with self.assertRaises(RespuestaPlantillaInvalidaError):
            TemplateGeneratorService(gateway).renderizar_propuesta(
                propuesta=propuesta,
                valores={
                    'equipo': '',
                    'contraste_ev': False,
                    'marca_contraste': '',
                    'volumen_contraste_ml': '',
                },
            )

    def test_inferencia_reconoce_angio_tc(self):
        tipo_tc = TipoEstudio.objects.create(nombre='Tomografía computada')

        condiciones = TemplateGeneratorService.inferir_condiciones(
            tipo_tc,
            'Angio-TC de tórax para TEP',
        )

        self.assertTrue(condiciones['contraste_ev_aplicable'])


class AIServiceStructuredOutputTest(TestCase):
    def test_openai_usa_json_schema_estricto(self):
        servicio = AIService.__new__(AIService)
        servicio.llm_enabled = True
        servicio.llm_client = MagicMock()
        servicio.llm_provider = 'openai'
        servicio.llm_model = 'modelo-prueba'
        servicio.llm_fallback_model = None
        servicio.llm_reasoning_effort = None
        servicio._crear_chat_completion_openai = MagicMock(return_value=(
            SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            content='{"resultado": "ok"}',
                            refusal=None,
                        )
                    )
                ]
            ),
            'modelo-prueba',
        ))
        schema = {
            'type': 'object',
            'additionalProperties': False,
            'properties': {'resultado': {'type': 'string'}},
            'required': ['resultado'],
        }

        resultado = servicio.generate_structured_json(
            messages=[{'role': 'user', 'content': 'Prueba'}],
            schema=schema,
            schema_name='respuesta_prueba',
        )

        self.assertEqual(resultado['data'], {'resultado': 'ok'})
        response_format = (
            servicio._crear_chat_completion_openai.call_args.kwargs['response_format']
        )
        self.assertEqual(response_format['type'], 'json_schema')
        self.assertTrue(response_format['json_schema']['strict'])
        self.assertEqual(response_format['json_schema']['schema'], schema)
