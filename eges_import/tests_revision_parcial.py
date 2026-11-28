import json
from datetime import date
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from .models import RevisionProduccionParcial, ProduccionValidada
from .services_revision_parcial import decisiones_guardadas, guardar_revision_parcial
from .tests_produccion import FuentesSinteticasMixin
from .services_validacion_produccion import preparar_validacion_produccion


class RevisionParcialTest(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_superuser('revisor', 'qa@example.invalid', 'test')
        self.preparacion = {
            'firma': 'a' * 64,
            'excepciones': [
                {'id': str(i), 'vigencia_incierta': False,
                 'candidatas': [{'accion': 'VINCULAR:10', 'modalidad': 'ECO'}]}
                for i in (1, 2)
            ],
            'grupos_bilaterales': [{'id': 'mmii:prueba'}], 'grupos_procedimientos': [],
        }

    def guardar(self, decisiones, **kwargs):
        return guardar_revision_parcial(
            preparacion=self.preparacion, firma_esperada=self.preparacion['firma'],
            decisiones=decisiones, usuario=self.usuario, motivo='Comprobación sintética', **kwargs,
        )

    def test_guarda_incompleto_sin_aprobar_y_restaura(self):
        decisiones = {'1': {'accion': 'VINCULAR:10', 'modalidad': 'ECO'}}
        self.assertEqual(self.guardar(decisiones), 1)
        self.assertEqual(decisiones_guardadas(self.preparacion), decisiones)
        self.assertFalse(ProduccionValidada.objects.exists())
        self.assertEqual(self.guardar(decisiones), 0)

    def test_cambio_fuentes_no_reutiliza_revision(self):
        self.guardar({'1': {'accion': 'EXCLUIR'}})
        otra = {**self.preparacion, 'firma': 'b' * 64}
        self.assertEqual(decisiones_guardadas(otra), {})
        with self.assertRaises(ValidationError):
            guardar_revision_parcial(preparacion=otra, firma_esperada='a' * 64,
                decisiones={'1': {'accion': 'EXCLUIR'}}, usuario=self.usuario, motivo='Prueba')
        self.assertEqual(RevisionProduccionParcial.objects.count(), 1)

    def test_volver_pendiente_conserva_historial(self):
        self.guardar({'1': {'accion': 'EXCLUIR'}})
        self.guardar({'1': {'accion': ''}})
        self.assertEqual(decisiones_guardadas(self.preparacion), {})
        self.assertEqual(RevisionProduccionParcial.objects.count(), 2)

    def test_rechaza_candidata_ajena_y_doble_vinculo_atomicamente(self):
        for decisiones in (
            {'1': {'accion': 'VINCULAR:999', 'modalidad': 'ECO'}},
            {str(i): {'accion': 'VINCULAR:10', 'modalidad': 'ECO'} for i in (1, 2)},
            {'ajena': {'accion': 'EXCLUIR'}},
        ):
            with self.assertRaises(ValidationError):
                self.guardar(decisiones)
        self.assertFalse(RevisionProduccionParcial.objects.exists())

    def test_permiso_y_motivo_obligatorios(self):
        self.usuario.is_superuser = False
        with self.assertRaises(ValidationError):
            self.guardar({'1': {'accion': 'EXCLUIR'}})
        self.usuario.is_superuser = True
        with self.assertRaises(ValidationError):
            guardar_revision_parcial(preparacion=self.preparacion, firma_esperada='a' * 64,
                decisiones={'1': {'accion': 'EXCLUIR'}}, usuario=self.usuario, motivo='')

    def test_grupos_se_guardan_sin_decidir_otras_excepciones(self):
        self.guardar({'mmii:prueba': {'accion': 'INDEPENDIENTES'}})
        self.assertEqual(decisiones_guardadas(self.preparacion),
                         {'mmii:prueba': {'accion': 'INDEPENDIENTES'}})


@override_settings(SECURE_SSL_REDIRECT=False, SESSION_ENGINE='django.contrib.sessions.backends.signed_cookies')
class PantallaRevisionParcialTest(FuentesSinteticasMixin, TestCase):
    def test_guardado_y_recuperacion_en_pantalla_sin_confirmar(self):
        for pedido in ('1', '2'):
            self.netterm(pedido=pedido, codigo='900048', practica='ECODOPPLER VENOSO MM INF')
        preparacion = preparar_validacion_produccion(batch_eges_ids=[self.batch.pk],
            lote_netterm_ids=[self.lote.pk], fecha_desde=date(2026, 10, 1), fecha_hasta=date(2026, 10, 31))
        grupo = preparacion['grupos_bilaterales'][0]['id']
        params = {'lotes_eges': [self.batch.pk], 'lotes_netterm': [self.lote.pk],
                  'fecha_desde': '2026-10-01', 'fecha_hasta': '2026-10-31'}
        self.client.force_login(self.usuario)
        url = reverse('eges_import:validar_produccion')
        respuesta = self.client.post(url, {**params, 'accion': 'guardar_revision',
            'firma': preparacion['firma'], 'motivo_revision': 'Dos realizaciones verificadas',
            'decisiones_json': json.dumps({grupo: {'accion': 'INDEPENDIENTES'}})})
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()['guardadas'], 1)
        self.assertEqual(respuesta.json()['decisiones_guardadas'][grupo], {'accion': 'INDEPENDIENTES'})
        self.assertFalse(ProduccionValidada.objects.exists())
        pagina = self.client.get(url, params)
        self.assertEqual(pagina.status_code, 200)
        self.assertEqual(pagina.context['preparacion']['grupos_bilaterales'][0]['accion_seleccionada'], 'INDEPENDIENTES')
        self.assertContains(pagina, 'Guardar revisión y continuar después')
        self.assertContains(pagina, 'revisiones-guardadas')
        self.assertContains(pagina, 'data-estado-guardado')
        error = self.client.post(url, {**params, 'accion': 'guardar_revision', 'firma': 'vieja',
            'motivo_revision': 'Prueba', 'decisiones_json': '{}'})
        self.assertEqual(error.status_code, 400)
        self.assertEqual(RevisionProduccionParcial.objects.count(), 1)
