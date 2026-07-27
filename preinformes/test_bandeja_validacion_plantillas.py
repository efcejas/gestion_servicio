from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import (
    PropuestaPlantillaPreinforme,
    Region,
    TipoEstudio,
    VersionPlantillaPreinforme,
)


User = get_user_model()


@override_settings(
    SECURE_SSL_REDIRECT=False,
    PREINFORMES_GENERADOR_PLANTILLAS_IA_HABILITADO=True,
)
class BandejaValidacionPlantillasTest(TestCase):
    def setUp(self):
        self.tipo_estudio = TipoEstudio.objects.create(nombre='Resonancia magnética')
        self.region = Region.objects.create(nombre='Miembro superior')
        self.residente = User.objects.create_user(
            username='residente_bandeja',
            password='test',
            rol='medico_residente',
            perfil_completo=True,
        )
        self.jefe = User.objects.create_user(
            username='jefe_bandeja',
            password='test',
            rol='jefe_servicio',
            perfil_completo=True,
        )
        self.propuesta = PropuestaPlantillaPreinforme.objects.create(
            autor=self.residente,
            tipo_estudio=self.tipo_estudio,
            region=self.region,
            estudio_especifico='Muñeca',
            titulo='RESONANCIA MAGNÉTICA DE MUÑECA',
            encabezado='Se exploró la muñeca en los diferentes planos.',
            hallazgos=(
                'Estructuras óseas sin alteraciones.\n'
                'Tendones de trayecto conservado.\n'
                'Partes blandas sin colecciones.'
            ),
            variables=[],
        )
        self.propuesta.enviar_a_revision()

    def test_solo_jefe_puede_acceder_a_bandeja(self):
        self.client.force_login(self.residente)
        respuesta = self.client.get(reverse('preinformes:lista_validacion_plantillas'))
        self.assertEqual(respuesta.status_code, 302)

        self.client.force_login(self.jefe)
        respuesta = self.client.get(reverse('preinformes:lista_validacion_plantillas'))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, self.propuesta.estudio_especifico)

    def test_validador_edita_y_deja_propuesta_en_revision(self):
        self.client.force_login(self.jefe)
        respuesta = self.client.post(
            reverse('preinformes:validar_plantilla', args=[self.propuesta.pk]),
            {
                'accion': 'guardar',
                'titulo': self.propuesta.titulo,
                'encabezado': self.propuesta.encabezado,
                'hallazgos': (
                    'Estructuras óseas revisadas sin alteraciones.\n'
                    'Tendones de trayecto conservado.\n'
                    'Partes blandas sin colecciones.'
                ),
                'observacion_revision': 'Revisión iniciada.',
            },
        )
        self.assertRedirects(
            respuesta,
            reverse('preinformes:validar_plantilla', args=[self.propuesta.pk]),
        )
        self.propuesta.refresh_from_db()
        self.assertEqual(self.propuesta.estado, self.propuesta.ESTADO_EN_REVISION)
        self.assertIn('Estructuras óseas revisadas', self.propuesta.hallazgos)

    def test_aprobar_publica_plantilla_y_version_vigente(self):
        self.client.force_login(self.jefe)
        respuesta = self.client.post(
            reverse('preinformes:validar_plantilla', args=[self.propuesta.pk]),
            {
                'accion': 'aprobar',
                'titulo': self.propuesta.titulo,
                'encabezado': self.propuesta.encabezado,
                'hallazgos': self.propuesta.hallazgos,
                'observacion_revision': 'Aprobada para uso institucional.',
            },
        )
        self.assertRedirects(
            respuesta,
            reverse('preinformes:lista_validacion_plantillas'),
        )
        self.propuesta.refresh_from_db()
        self.assertEqual(self.propuesta.estado, self.propuesta.ESTADO_APROBADA)
        version = VersionPlantillaPreinforme.objects.get(
            propuesta_origen=self.propuesta,
        )
        self.assertTrue(version.vigente)
        self.assertEqual(version.numero, 1)
        self.assertEqual(version.aprobada_por, self.jefe)
        self.assertEqual(version.plantilla.estado, 'publica')
        self.assertEqual(version.plantilla.sistema_destino, 'universal')

    def test_rechazo_sin_observacion_no_resuelve_propuesta(self):
        self.client.force_login(self.jefe)
        respuesta = self.client.post(
            reverse('preinformes:validar_plantilla', args=[self.propuesta.pk]),
            {
                'accion': 'rechazar',
                'titulo': self.propuesta.titulo,
                'encabezado': self.propuesta.encabezado,
                'hallazgos': self.propuesta.hallazgos,
                'observacion_revision': '',
            },
        )
        self.assertEqual(respuesta.status_code, 200)
        self.propuesta.refresh_from_db()
        self.assertNotEqual(self.propuesta.estado, self.propuesta.ESTADO_RECHAZADA)

    def test_plantilla_aprobada_queda_disponible_para_otro_medico(self):
        from .template_generator_service import TemplateGeneratorService

        TemplateGeneratorService().aprobar_y_publicar(
            propuesta=self.propuesta,
            usuario=self.jefe,
            observacion='Aprobada.',
        )
        otro_medico = User.objects.create_user(
            username='otro_medico_bandeja',
            password='test',
            rol='medico_staff',
            perfil_completo=True,
        )
        self.client.force_login(otro_medico)

        respuesta = self.client.get(
            reverse('preinformes:cargar_plantillas'),
            {
                'tipo_estudio_id': self.tipo_estudio.pk,
                'region_id': self.region.pk,
                'sistema_destino': 'eges',
            },
        )
        self.assertEqual(respuesta.status_code, 200)
        ids = [item['id'] for item in respuesta.json()['plantillas']]
        self.assertIn(f'propuesta-{self.propuesta.pk}', ids)

        detalle = self.client.get(
            reverse('preinformes:propuesta_plantilla_json', args=[self.propuesta.pk])
        )
        self.assertEqual(detalle.status_code, 200)
        self.assertEqual(detalle.json()['propuesta']['estado'], 'aprobada')

        aplicada = self.client.post(
            reverse('preinformes:aplicar_plantilla_ia', args=[self.propuesta.pk]),
            data='{"valores": {}}',
            content_type='application/json',
        )
        self.assertEqual(aplicada.status_code, 200)
        self.assertIn('RESONANCIA MAGNÉTICA DE MUÑECA', aplicada.json()['contenido'])
