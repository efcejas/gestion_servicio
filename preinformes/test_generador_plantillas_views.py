import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from equipos.models import AreaServicio, EquipoImagen

from .models import (
    AplicacionPlantillaPreinforme,
    PropuestaPlantillaPreinforme,
    Region,
    TipoEstudio,
)


User = get_user_model()


@override_settings(
    SECURE_SSL_REDIRECT=False,
    PREINFORMES_GENERADOR_PLANTILLAS_IA_HABILITADO=True,
)
class GeneradorPlantillasViewsTest(TestCase):
    def setUp(self):
        self.tipo = TipoEstudio.objects.create(nombre='Resonancia magnética')
        self.region = Region.objects.create(nombre='Miembro superior')
        self.residente = User.objects.create_user(
            username='residente_vistas_plantilla',
            password='test',
            rol='medico_residente',
            perfil_completo=True,
        )
        self.administrativo = User.objects.create_user(
            username='administrativo_vistas_plantilla',
            password='test',
            rol='administrativo',
            perfil_completo=True,
        )
        self.equipo = EquipoImagen.objects.create(
            nombre='Resonador principal',
            area=AreaServicio.RESONANCIA,
            fabricante='Philips',
            modelo='Ingenia',
        )

    def crear_propuesta(self, estado='borrador'):
        return PropuestaPlantillaPreinforme.objects.create(
            autor=self.residente,
            tipo_estudio=self.tipo,
            region=self.region,
            estudio_especifico='RM de muñeca',
            titulo='RESONANCIA MAGNÉTICA DE MUÑECA [[lateralidad]]',
            encabezado='Se exploró la muñeca [[lateralidad]] en [[equipo]].',
            hallazgos=(
                'Estructuras óseas de señal conservada.\n'
                'Tendones flexores y extensores sin alteraciones.\n'
                'Fibrocartílago triangular de aspecto conservado.'
            ),
            variables=[
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
            estado=estado,
        )

    def test_formulario_muestra_boton_con_feature_flag(self):
        self.client.force_login(self.residente)

        response = self.client.get(reverse('preinformes:crear_preinforme'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'btnGenerarPlantillaIA')
        self.assertContains(response, 'function getCsrfToken()')
        self.assertContains(response, "'X-CSRFToken': getCsrfToken()")
        self.assertContains(response, 'bg-white bg-opacity-20 backdrop-blur-sm')
        self.assertContains(response, 'aria-modal="true"')
        self.assertContains(response, "document.body.classList.add('overflow-hidden')")
        self.assertContains(
            response,
            "btnRegenerarPropuesta.classList.add('hidden')",
        )

    @patch('preinformes.views.TemplateGeneratorService.generar_propuesta')
    def test_endpoint_generar_devuelve_borrador_temporal_y_equipos(self, generar_mock):
        propuesta = self.crear_propuesta()
        propuesta.delete()
        generar_mock.return_value = propuesta
        EquipoImagen.objects.create(
            nombre='Tomógrafo no aplicable',
            area=AreaServicio.TOMOGRAFIA,
        )
        self.client.force_login(self.residente)

        response = self.client.post(
            reverse('preinformes:generar_plantilla_ia'),
            data=json.dumps({
                'tipo_estudio': self.tipo.pk,
                'region': self.region.pk,
                'estudio_especifico': 'RM de muñeca',
                'instruccion_usuario': '',
                'lateralidad_aplicable': True,
                'equipo_aplicable': True,
                'contraste_ev_aplicable': False,
                'contraste_oral_aplicable': False,
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertNotIn('id', data['propuesta'])
        self.assertTrue(data['borrador_token'])
        self.assertEqual(PropuestaPlantillaPreinforme.objects.count(), 0)
        self.assertFalse(generar_mock.call_args.kwargs['persistir'])
        self.assertEqual(
            [equipo['id'] for equipo in data['equipos']],
            [self.equipo.pk],
        )

        aceptar = self.client.post(
            reverse('preinformes:aceptar_borrador_plantilla_ia'),
            data=json.dumps({
                'borrador_token': data['borrador_token'],
                'titulo': propuesta.titulo,
                'hallazgos': propuesta.hallazgos,
            }),
            content_type='application/json',
        )
        self.assertEqual(aceptar.status_code, 200)
        guardada = PropuestaPlantillaPreinforme.objects.get()
        self.assertEqual(guardada.estado, guardada.ESTADO_PENDIENTE)

    def test_perfil_no_medico_no_puede_generar(self):
        self.client.force_login(self.administrativo)

        response = self.client.post(
            reverse('preinformes:generar_plantilla_ia'),
            data='{}',
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 302)

    def test_no_acepta_borrador_temporal_adulterado(self):
        self.client.force_login(self.residente)

        response = self.client.post(
            reverse('preinformes:aceptar_borrador_plantilla_ia'),
            data=json.dumps({
                'borrador_token': 'token-adulterado',
                'titulo': 'Título',
                'hallazgos': 'Hallazgo 1\nHallazgo 2\nHallazgo 3',
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(PropuestaPlantillaPreinforme.objects.count(), 0)

    def test_aplicar_edita_renderiza_y_envia_a_revision(self):
        propuesta = self.crear_propuesta()
        self.client.force_login(self.residente)

        aceptar = self.client.post(
            reverse('preinformes:aceptar_plantilla_ia', args=[propuesta.pk]),
            data=json.dumps({
                'titulo': propuesta.titulo,
                'hallazgos': propuesta.hallazgos,
            }),
            content_type='application/json',
        )
        self.assertEqual(aceptar.status_code, 200)

        response = self.client.post(
            reverse('preinformes:aplicar_plantilla_ia', args=[propuesta.pk]),
            data=json.dumps({
                'valores': {
                    'lateralidad': 'derecha',
                    'equipo': str(self.equipo.pk),
                },
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        propuesta.refresh_from_db()
        self.assertEqual(
            propuesta.estado,
            PropuestaPlantillaPreinforme.ESTADO_PENDIENTE,
        )
        self.assertIn('MUÑECA DERECHA', response.json()['contenido'])

    def test_solo_el_autor_puede_aplicar_su_propuesta(self):
        propuesta = self.crear_propuesta(
            estado=PropuestaPlantillaPreinforme.ESTADO_PENDIENTE,
        )
        otro = User.objects.create_user(
            username='otro_residente',
            password='test',
            rol='medico_residente',
            perfil_completo=True,
        )
        self.client.force_login(otro)

        response = self.client.post(
            reverse('preinformes:aplicar_plantilla_ia', args=[propuesta.pk]),
            data='{}',
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 404)

    def test_propuesta_pendiente_aparece_en_desplegable_del_autor(self):
        propuesta = self.crear_propuesta(
            estado=PropuestaPlantillaPreinforme.ESTADO_PENDIENTE,
        )
        self.client.force_login(self.residente)

        response = self.client.get(
            reverse('preinformes:cargar_plantillas'),
            {
                'tipo_estudio_id': self.tipo.pk,
                'region_id': self.region.pk,
                'sistema_destino': 'eges',
            },
        )

        self.assertEqual(response.status_code, 200)
        opciones = response.json()['plantillas']
        pendiente = next(
            opcion for opcion in opciones
            if opcion['id'] == f'propuesta-{propuesta.pk}'
        )
        self.assertTrue(pendiente['es_propuesta_ia'])
        self.assertEqual(pendiente['sistema_destino'], 'Pendiente de aprobación')

    def test_propuesta_pendiente_no_aparece_para_otro_usuario(self):
        propuesta = self.crear_propuesta(
            estado=PropuestaPlantillaPreinforme.ESTADO_PENDIENTE,
        )
        otro = User.objects.create_user(
            username='residente_biblioteca_ajena',
            password='test',
            rol='medico_residente',
            perfil_completo=True,
        )
        self.client.force_login(otro)

        response = self.client.get(
            reverse('preinformes:cargar_plantillas'),
            {
                'tipo_estudio_id': self.tipo.pk,
                'region_id': self.region.pk,
            },
        )

        ids = [opcion['id'] for opcion in response.json()['plantillas']]
        self.assertNotIn(f'propuesta-{propuesta.pk}', ids)

    def test_autor_puede_recuperar_variables_de_propuesta_pendiente(self):
        propuesta = self.crear_propuesta(
            estado=PropuestaPlantillaPreinforme.ESTADO_PENDIENTE,
        )
        self.client.force_login(self.residente)

        response = self.client.get(
            reverse('preinformes:propuesta_plantilla_json', args=[propuesta.pk]),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['propuesta']['id'], propuesta.pk)
        self.assertEqual(response.json()['equipos'][0]['id'], self.equipo.pk)

    def test_propuesta_antigua_con_contraste_incorpora_marca_otro(self):
        propuesta = self.crear_propuesta(
            estado=PropuestaPlantillaPreinforme.ESTADO_PENDIENTE,
        )
        propuesta.variables.extend([
            {
                'codigo': 'contraste_ev',
                'tipo': 'booleano',
                'requerida': True,
                'opciones': [],
            },
            {
                'codigo': 'volumen_contraste_ml',
                'tipo': 'numero',
                'requerida': False,
                'opciones': [],
            },
        ])
        propuesta.encabezado += '[[contraste_ev]]'
        propuesta.save(update_fields=['variables', 'encabezado'])
        self.client.force_login(self.residente)

        recuperar = self.client.get(
            reverse('preinformes:propuesta_plantilla_json', args=[propuesta.pk]),
        )

        self.assertEqual(recuperar.status_code, 200)
        codigos = [
            variable['codigo']
            for variable in recuperar.json()['propuesta']['variables']
        ]
        self.assertIn('marca_contraste', codigos)

        aplicar = self.client.post(
            reverse('preinformes:aplicar_plantilla_ia', args=[propuesta.pk]),
            data=json.dumps({
                'valores': {
                    'lateralidad': 'derecha',
                    'equipo': '',
                    'contraste_ev': True,
                    'volumen_contraste_ml': '95',
                },
            }),
            content_type='application/json',
        )

        self.assertEqual(aplicar.status_code, 200)
        self.assertEqual(aplicar.json()['valores']['marca_contraste'], 'Otro')
        self.assertIn('con un volumen de 95 ml', aplicar.json()['contenido'])
        self.assertNotIn('(95 ml)', aplicar.json()['contenido'])

    def test_guardar_preinforme_registra_aplicacion_y_snapshot(self):
        propuesta = self.crear_propuesta(
            estado=PropuestaPlantillaPreinforme.ESTADO_PENDIENTE,
        )
        self.client.force_login(self.residente)
        contenido = '<p><strong>RM DE MUÑECA DERECHA</strong></p><p>Contenido.</p>'

        response = self.client.post(
            reverse('preinformes:crear_preinforme'),
            data={
                'numero_estudio': 'RM-IA-001',
                'tipo_estudio': self.tipo.pk,
                'region': self.region.pk,
                'sistema_destino': 'eges',
                'plantilla_utilizada': '',
                'revisor': '',
                'apellido_paciente': 'Paciente',
                'nombre_paciente': 'Prueba',
                'dni_paciente': '',
                'edad_paciente': '',
                'sexo_paciente': '',
                'contexto_clinico': '',
                'informe_html': contenido,
                'propuesta_plantilla_ia_id': propuesta.pk,
                'valores_plantilla_ia': json.dumps({
                    'lateralidad': 'derecha',
                    'equipo': str(self.equipo.pk),
                }),
                'guardar_y_continuar': '1',
            },
        )

        self.assertEqual(response.status_code, 302)
        aplicacion = AplicacionPlantillaPreinforme.objects.get()
        self.assertEqual(aplicacion.propuesta, propuesta)
        self.assertEqual(aplicacion.equipo, self.equipo)
        self.assertEqual(aplicacion.lateralidad, 'derecha')
        self.assertEqual(aplicacion.contenido_renderizado, contenido)
