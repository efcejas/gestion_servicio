import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.core import signing
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse

from dictado_informes.ai_services import AIService, ai_service
from dictado_informes.models import PlantillaEstructurada, TrazaAgenteDictado
from dictado_informes.template_drafts import (
    REGIONES_BORRADOR, SALT, seleccionar_referencias, validar_borrador,
)


@override_settings(SECURE_SSL_REDIRECT=False, ALLOWED_HOSTS=['testserver'],
                   DICTADO_AGENTE_HABILITADO=True)
class PlantillaInexistenteTests(TestCase):
    def setUp(self):
        # Las migraciones cargan plantillas legacy; aislar las referencias de estos tests.
        PlantillaEstructurada.objects.all().delete()
        User = get_user_model()
        self.medico = User.objects.create_user(
            username='draft_medico', rol='piloto_dictado', perfil_completo=True,
        )
        self.otro = User.objects.create_user(
            username='draft_otro', rol='piloto_dictado', perfil_completo=True,
        )
        self.client.force_login(self.medico)
        self.url = reverse('dictado_informes:plantilla_inexistente')
        # Sólo referencias de otro miembro; el orden no usa propiedad ni trazas.
        self.referencia = self.crear('REF', 'RM de hombro')
        self.borrador = {
            'nombre': 'RM de rodilla', 'titulo': 'RM DE RODILLA',
            'comentarios_base': ['Meniscos de morfología normal.', 'Ligamentos cruzados conservados.'],
            'seccion_tecnica': '', 'conclusion': '',
        }

    def crear(self, codigo, nombre, **kwargs):
        return PlantillaEstructurada.objects.create(
            codigo=codigo, nombre=nombre, titulo=nombre.upper(),
            seccion_tecnica='Referencia técnica que NO debe enviarse.',
            comentarios_base=['Estructuras de morfología normal.'],
            creada_por=self.otro, **kwargs,
        )

    def post(self, data):
        return self.client.post(self.url, json.dumps(data), content_type='application/json')

    def generar(self):
        with patch.object(ai_service, 'generar_plantilla_normal', return_value=self.borrador):
            response = self.post({'accion': 'generar', 'region': 'RODILLA', 'modalidad': 'RES'})
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def confirmacion(self, propuesta, **kwargs):
        return {
            'accion': 'confirmar', 'token': propuesta['token'],
            'borrador': propuesta['borrador'], 'confirmar': True, **kwargs,
        }

    @patch.object(ai_service, 'generar_plantilla_normal')
    def test_contexto_obligatorio_y_referencias_insuficientes(self, generar):
        self.assertEqual(REGIONES_BORRADOR['BRAZO'], 'Brazo')
        self.assertEqual(REGIONES_BORRADOR['DEDO'], 'Dedo')
        for data in ({}, {'region': 'RODILLA'}, {'region': 'texto libre de paciente', 'modalidad': 'RES'}):
            with self.subTest(data=data):
                self.assertEqual(self.post({'accion': 'generar', **data}).status_code, 400)
        self.referencia.activa = False
        self.referencia.save()
        self.assertEqual(self.post({
            'accion': 'generar', 'region': 'RODILLA', 'modalidad': 'RES',
        }).status_code, 400)
        generar.assert_not_called()

    def test_generacion_aislada_y_referencias_visibles_sin_frecuencia(self):
        cercana = self.crear('CERCANA', 'RM de rodilla')
        self.crear('PRIVADA', 'RM de rodilla', compartida=False)
        self.crear('INACTIVA', 'RM de rodilla', activa=False)
        self.crear('OTRA_MODALIDAD', 'TC de rodilla')
        for _ in range(4):
            TrazaAgenteDictado.objects.create(
                usuario=self.medico, plantilla_seleccionada=self.referencia,
            )
        self.assertEqual(
            seleccionar_referencias(self.medico, 'RODILLA', 'RES'),
            [cercana, self.referencia],
        )
        cantidad = PlantillaEstructurada.objects.count()
        with patch.object(ai_service, 'generar_plantilla_normal', return_value=self.borrador) as generar:
            response = self.post({
                'accion': 'generar', 'region': 'RODILLA', 'modalidad': 'RES',
                'texto_original': 'NO ENVIAR DICTADO', 'paciente': 'NO ENVIAR PACIENTE',
            })
        self.assertEqual(response.status_code, 200)
        llamada = json.dumps(generar.call_args.kwargs)
        self.assertNotIn('NO ENVIAR', llamada)
        self.assertNotIn('Referencia técnica', llamada)
        self.assertNotIn('PRIVADA', json.dumps(response.json()))
        self.assertEqual(PlantillaEstructurada.objects.count(), cantidad)
        self.assertIn('Sin frecuencia', response.json()['criterio_referencias'])

    def test_validacion_de_borrador_en_generacion_y_confirmacion(self):
        for cambios in (
            {'titulo': 'TC DE RODILLA'}, {'titulo': 'RM DE HOMBRO'},
            {'comentarios_base': []}, {'comentarios_base': ['Rotura meniscal.']},
            {'comentarios_base': ['Sin lesiones musculares y edema.']},
            {'seccion_tecnica': 'T1 T2'}, {'conclusion': 'Normal.'},
            {'comentarios_base': ['Secuencias T1 normales.']},
            {'comentarios_base': ['Meniscos normales con rotura.']},
            {'titulo': 'RM DE RODILLA CON CONTRASTE'},
            {'comentarios_base': ['Meniscos normales.'] * 2},
            {'estructura_documento': {}},
        ):
            with self.subTest(cambios=cambios):
                with self.assertRaises(ValidationError):
                    validar_borrador({**self.borrador, **cambios}, 'RODILLA', 'RES')
        normalidad_negativa = validar_borrador({
            **self.borrador,
            'comentarios_base': [
                'Sin lesiones en los diferentes compartimentos musculares evaluados, ausencia de lesiones óseas.'
            ],
        }, 'RODILLA', 'RES')
        self.assertIn('ausencia de lesiones óseas', normalidad_negativa['comentarios_base'][0])
        with patch.object(ai_service, 'generar_plantilla_normal', return_value={'titulo': 'INCOMPLETA'}):
            self.assertEqual(self.post({
                'accion': 'generar', 'region': 'RODILLA', 'modalidad': 'RES',
            }).status_code, 400)
        propuesta = self.generar()
        data = self.confirmacion(propuesta)
        data['borrador'] = {**self.borrador, 'conclusion': 'Normal.'}
        self.assertEqual(self.post(data).status_code, 400)

    def test_reconoce_normalidad_negativa_sin_ocultar_patologia_afirmativa(self):
        for linea in (
            'No se identifican adenopatías.',
            'No se observa líquido libre.',
            'Sin colecciones ni edema.',
            'Ausencia de lesiones óseas.',
        ):
            with self.subTest(linea=linea):
                resultado = validar_borrador(
                    {**self.borrador, 'comentarios_base': [linea]}, 'RODILLA', 'RES',
                )
                self.assertEqual(resultado['comentarios_base'], [linea])
        for linea in (
            'No se identifican lesiones, pero hay edema.',
            'Sin lesiones con edema.',
            'Estructuras conservadas. Adenopatías presentes.',
        ):
            with self.subTest(linea=linea):
                with self.assertRaises(ValidationError):
                    validar_borrador(
                        {**self.borrador, 'comentarios_base': [linea]}, 'RODILLA', 'RES',
                    )

    def test_normalidad_no_reconocida_se_muestra_para_editar_antes_de_guardar(self):
        self.borrador['comentarios_base'] = ['Contornos lisos y señal homogénea.']
        cantidad = PlantillaEstructurada.objects.count()
        propuesta = self.generar()
        self.assertEqual(propuesta['borrador']['comentarios_base'], self.borrador['comentarios_base'])
        self.assertIn('Línea 1', propuesta['advertencias'][0])
        self.assertEqual(PlantillaEstructurada.objects.count(), cantidad)
        rechazo = self.post(self.confirmacion(propuesta))
        self.assertEqual(rechazo.status_code, 400)
        self.assertIn('Línea 1', rechazo.json()['error'])
        self.assertEqual(PlantillaEstructurada.objects.count(), cantidad)
        propuesta['borrador']['comentarios_base'] = ['Estructuras de señal habitual.']
        self.assertEqual(self.post(self.confirmacion(propuesta)).status_code, 200)

    def test_preview_no_relaja_bloqueo_de_patologia_o_tecnica(self):
        for linea in ('Edema muscular.', 'Secuencias T1 normales.'):
            with self.subTest(linea=linea):
                self.borrador['comentarios_base'] = [linea]
                with patch.object(ai_service, 'generar_plantilla_normal', return_value=self.borrador):
                    response = self.post({
                        'accion': 'generar', 'region': 'RODILLA', 'modalidad': 'RES',
                    })
                self.assertEqual(response.status_code, 400)

    def test_confirmacion_explicita_token_permisos_y_vencimiento(self):
        propuesta = self.generar()
        cantidad = PlantillaEstructurada.objects.count()
        for confirmar in (None, False, 'true', 1):
            self.assertEqual(self.post(self.confirmacion(propuesta, confirmar=confirmar)).status_code, 400)
        self.assertEqual(self.post(self.confirmacion(propuesta, token='alterado')).status_code, 400)
        with patch('django.core.signing.time.time', return_value=0):
            vencido = signing.dumps({
                'usuario': self.medico.pk, 'region': 'RODILLA', 'modalidad': 'RES', 'codigo': 'VENCIDO',
            }, salt=SALT)
        self.assertEqual(self.post(self.confirmacion(propuesta, token=vencido)).status_code, 400)
        self.client.force_login(self.otro)
        self.assertEqual(self.post(self.confirmacion(propuesta)).status_code, 400)
        self.assertEqual(PlantillaEstructurada.objects.count(), cantidad)
        self.client.logout()
        self.assertEqual(self.post({'accion': 'generar'}).status_code, 302)
        self.client.force_login(self.otro)
        self.otro.rol = 'medico_staff'
        self.otro.save()
        self.assertEqual(self.post({'accion': 'generar'}).status_code, 403)
        self.assertEqual(self.post(self.confirmacion(propuesta)).status_code, 403)

    def test_guardado_editado_privado_idempotente_y_uso_actual_y_futuro(self):
        propuesta = self.generar()
        propuesta['borrador']['nombre'] = 'Mi RM de rodilla'
        propuesta['borrador']['comentarios_base'] = ['Meniscos de configuración habitual.']
        response = self.post(self.confirmacion(propuesta))
        self.assertEqual(response.status_code, 200, response.content)
        codigo = response.json()['plantilla']['codigo']
        plantilla = PlantillaEstructurada.objects.get(codigo=codigo)
        self.assertEqual(plantilla.creada_por, self.medico)
        self.assertEqual(plantilla.origen, 'user')
        self.assertFalse(plantilla.compartida)
        self.assertEqual(plantilla.seccion_tecnica, '')
        self.assertEqual(plantilla.comentarios_base, ['Meniscos de configuración habitual.'])
        cantidad = PlantillaEstructurada.objects.count()
        self.assertEqual(self.post(self.confirmacion(propuesta)).status_code, 200)
        self.assertEqual(PlantillaEstructurada.objects.count(), cantidad)
        self.referencia.refresh_from_db()
        self.assertEqual(self.referencia.nombre, 'RM de hombro')
        self.assertFalse(PlantillaEstructurada.visibles_para_usuario(self.otro).filter(pk=plantilla.pk).exists())
        self.assertEqual(ai_service._get_plantilla_estructurada(codigo, self.medico)['comentarios'],
                         plantilla.comentarios_base)
        with patch.object(ai_service, 'improve_medical_text', return_value={
            'texto_mejorado': 'COMENTARIO:\nHallazgo dictado.\nCONCLUSION:\nHallazgo dictado.',
        }) as mejorar:
            response = self.client.post(reverse('dictado_informes:mejorar_texto'), json.dumps({
                'modo': 'AGENTE', 'texto_original': 'RM de rodilla. Hallazgo dictado.',
                'plantilla_confirmada_codigo': codigo,
            }), content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['tipo_plantilla_usada'], codigo)
        self.assertEqual(mejorar.call_args.args[2]['tipo_plantilla'], codigo)
        self.assertEqual(TrazaAgenteDictado.objects.latest('pk').plantilla_seleccionada, plantilla)

    def test_comparticion_explicita_y_flag_backend(self):
        propuesta = self.generar()
        response = self.post(self.confirmacion(propuesta, compartida=True))
        plantilla = PlantillaEstructurada.objects.get(codigo=response.json()['plantilla']['codigo'])
        self.assertTrue(PlantillaEstructurada.visibles_para_usuario(self.otro).filter(pk=plantilla.pk).exists())
        with override_settings(DICTADO_AGENTE_HABILITADO=False):
            self.assertEqual(self.post({'accion': 'generar'}).status_code, 403)
            self.assertEqual(self.post(self.confirmacion(propuesta)).status_code, 403)
        self.assertEqual(self.client.get(self.url).status_code, 405)

    @override_settings(DICTADO_SELECTOR_CONFIRMACION_ACTIVA=False)
    @patch.object(ai_service, 'improve_medical_text')
    def test_sin_match_no_aplica_fallback_y_modal_ofrece_creacion(self, mejorar):
        response = self.client.post(reverse('dictado_informes:mejorar_texto'), json.dumps({
            'modo': 'AGENTE', 'texto_original': 'TC de rodilla.',
        }), content_type='application/json')
        self.assertTrue(response.json()['requiere_seleccion_plantilla'])
        self.assertTrue(response.json()['puede_crear_plantilla'])
        mejorar.assert_not_called()
        response = self.client.get(reverse('dictado_informes:dictado_rapido'))
        self.assertContains(response, 'Crear plantilla inexistente')
        self.assertContains(response, 'id="previewNuevaPlantilla"')
        self.assertContains(response, 'option value="" selected disabled>Elegí una plantilla...')
        self.assertContains(response, 'payload.plantilla_confirmada_codigo = codigoElegido')
        self.assertContains(response, self.url)

    def test_generador_json_y_fallback_sin_acceso_a_informes(self):
        servicio = AIService.__new__(AIService)
        servicio.llm_enabled = True
        servicio.llm_client = Mock()
        servicio.llm_provider = 'openai'
        servicio.llm_model = 'modelo-prueba'
        servicio.llm_fallback_model = None
        servicio.llm_reasoning_effort = None
        respuesta = SimpleNamespace(choices=[SimpleNamespace(
            message=SimpleNamespace(content=json.dumps(self.borrador)),
        )])
        servicio._crear_chat_completion_openai = Mock(return_value=(respuesta, 'modelo'))
        servicio.groq_fallback = Mock()
        kwargs = {'region': 'Rodilla', 'modalidad': 'RM',
                  'referencias': [{'nombre': 'RM de hombro', 'comentarios_base': ['Normal.']}]}
        self.assertEqual(servicio.generar_plantilla_normal(**kwargs), self.borrador)
        mensajes = servicio._crear_chat_completion_openai.call_args.kwargs['messages']
        self.assertEqual(json.loads(mensajes[1]['content'])['region_objetivo'], 'Rodilla')
        response_format = servicio._crear_chat_completion_openai.call_args.kwargs['response_format']
        self.assertEqual(response_format['type'], 'json_schema')
        self.assertTrue(response_format['json_schema']['strict'])
        servicio._crear_chat_completion_openai.side_effect = RuntimeError('fallo simulado')
        servicio.groq_fallback.chat.completions.create.return_value = respuesta
        self.assertEqual(servicio.generar_plantilla_normal(**kwargs), self.borrador)
        respuesta.choices[0].message.content = 'no es JSON'
        with self.assertRaises(ValueError):
            servicio.generar_plantilla_normal(**kwargs)
