import json
from unittest.mock import patch

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
class FlujoIntegralPlantillasTest(TestCase):
    def setUp(self):
        self.tipo = TipoEstudio.objects.create(nombre='Resonancia magnética')
        self.region = Region.objects.create(nombre='Miembro superior')
        self.autor = User.objects.create_user(
            username='autor_flujo_integral',
            password='test',
            rol='medico_residente',
            perfil_completo=True,
        )
        self.jefe = User.objects.create_user(
            username='jefe_flujo_integral',
            password='test',
            rol='jefe_servicio',
            perfil_completo=True,
        )
        self.otro_medico = User.objects.create_user(
            username='medico_flujo_integral',
            password='test',
            rol='medico_staff',
            perfil_completo=True,
        )

    def borrador_no_persistido(self):
        return PropuestaPlantillaPreinforme(
            autor=self.autor,
            tipo_estudio=self.tipo,
            region=self.region,
            estudio_especifico='RM de carpo',
            instruccion_usuario='Plantilla normal breve.',
            titulo='RESONANCIA MAGNÉTICA DE CARPO',
            encabezado='Se realizó RM de carpo con secuencias multiplanares.',
            hallazgos=(
                'Estructuras óseas sin alteraciones.\n'
                'Tendones de trayecto conservado.\n'
                'Partes blandas sin colecciones.'
            ),
            variables=[],
            fuentes=[],
            proveedor_ia='test',
            modelo_ia='modelo-test',
            version_instrucciones='plantilla-institucional-v2',
        )

    @patch('preinformes.views.TemplateGeneratorService.generar_propuesta')
    def test_circuito_desde_borrador_temporal_hasta_biblioteca(self, generar):
        generar.return_value = self.borrador_no_persistido()
        self.client.force_login(self.autor)

        generada = self.client.post(
            reverse('preinformes:generar_plantilla_ia'),
            data=json.dumps({
                'tipo_estudio': self.tipo.pk,
                'region': self.region.pk,
                'estudio_especifico': 'RM de carpo',
                'instruccion_usuario': 'Plantilla normal breve.',
            }),
            content_type='application/json',
        )
        self.assertEqual(generada.status_code, 200)
        self.assertEqual(PropuestaPlantillaPreinforme.objects.count(), 0)

        aceptada = self.client.post(
            reverse('preinformes:aceptar_borrador_plantilla_ia'),
            data=json.dumps({
                'borrador_token': generada.json()['borrador_token'],
                'titulo': generada.json()['propuesta']['titulo'],
                'hallazgos': generada.json()['propuesta']['hallazgos'],
            }),
            content_type='application/json',
        )
        self.assertEqual(aceptada.status_code, 200)
        propuesta = PropuestaPlantillaPreinforme.objects.get()
        self.assertEqual(propuesta.estado, propuesta.ESTADO_PENDIENTE)

        biblioteca_autor = self.client.get(
            reverse('preinformes:cargar_plantillas'),
            {
                'tipo_estudio_id': self.tipo.pk,
                'region_id': self.region.pk,
                'sistema_destino': 'eges',
            },
        )
        self.assertIn(
            f'propuesta-{propuesta.pk}',
            [item['id'] for item in biblioteca_autor.json()['plantillas']],
        )

        aplicada_pendiente = self.client.post(
            reverse('preinformes:aplicar_plantilla_ia', args=[propuesta.pk]),
            data=json.dumps({'valores': {}}),
            content_type='application/json',
        )
        self.assertEqual(aplicada_pendiente.status_code, 200)
        self.assertIn('RESONANCIA MAGNÉTICA DE CARPO', aplicada_pendiente.json()['contenido'])

        self.client.force_login(self.jefe)
        aprobada = self.client.post(
            reverse('preinformes:validar_plantilla', args=[propuesta.pk]),
            {
                'accion': 'aprobar',
                'titulo': propuesta.titulo,
                'encabezado': propuesta.encabezado,
                'hallazgos': propuesta.hallazgos,
                'observacion_revision': 'Aprobada en prueba integral.',
            },
        )
        self.assertRedirects(
            aprobada,
            reverse('preinformes:lista_validacion_plantillas'),
        )
        propuesta.refresh_from_db()
        self.assertEqual(propuesta.estado, propuesta.ESTADO_APROBADA)
        self.assertTrue(
            VersionPlantillaPreinforme.objects.filter(
                propuesta_origen=propuesta,
                vigente=True,
            ).exists()
        )

        self.client.force_login(self.otro_medico)
        biblioteca_institucional = self.client.get(
            reverse('preinformes:cargar_plantillas'),
            {
                'tipo_estudio_id': self.tipo.pk,
                'region_id': self.region.pk,
                'sistema_destino': 'eges',
            },
        )
        institucional = next(
            item for item in biblioteca_institucional.json()['plantillas']
            if item['id'] == f'propuesta-{propuesta.pk}'
        )
        self.assertTrue(institucional['es_institucional'])

        aplicada_institucional = self.client.post(
            reverse('preinformes:aplicar_plantilla_ia', args=[propuesta.pk]),
            data=json.dumps({'valores': {}}),
            content_type='application/json',
        )
        self.assertEqual(aplicada_institucional.status_code, 200)
        self.assertNotIn('[[', aplicada_institucional.json()['contenido'])
