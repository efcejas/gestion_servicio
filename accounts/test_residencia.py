from datetime import date

from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.context_processors import notificacion_ciclo_residencia
from accounts.models import CustomUser, NotificacionCicloResidencia
from accounts.services import procesar_cierre_residencia, ultimo_cierre_habilitado


class CierreResidenciaTests(TestCase):
    def crear_residente(self, username, anio, **extra):
        defaults = {
            'rol': 'medico_residente',
            'estado_residencia': 'ACTIVO',
            'anio_residencia': anio,
            'ultimo_cierre_residencia': 2025,
            'is_active': True,
        }
        defaults.update(extra)
        return CustomUser.objects.create_user(username=username, **defaults)

    def test_el_cambio_de_ciclo_ocurre_el_primero_de_agosto(self):
        self.assertEqual(ultimo_cierre_habilitado(date(2026, 7, 31)), 2025)
        self.assertEqual(ultimo_cierre_habilitado(date(2026, 8, 1)), 2026)

    def test_promueve_r1_a_r4_y_egresa_r4(self):
        r1 = self.crear_residente('r1', 'R1')
        r2 = self.crear_residente('r2', 'R2')
        r3 = self.crear_residente('r3', 'R3')
        r4 = self.crear_residente('r4', 'R4')

        procesar_cierre_residencia(cierre_anio=2026)

        for residente in (r1, r2, r3, r4):
            residente.refresh_from_db()
        self.assertEqual(r1.anio_residencia, 'R2')
        self.assertEqual(r2.anio_residencia, 'R3')
        self.assertEqual(r3.anio_residencia, 'R4')
        self.assertEqual(r4.estado_residencia, 'EGRESADO')
        self.assertIsNone(r4.anio_residencia)
        self.assertEqual(r4.fecha_egreso_residencia, date(2026, 8, 1))
        self.assertFalse(r4.es_residente_activo())
        self.assertEqual(NotificacionCicloResidencia.objects.count(), 4)
        self.assertEqual(
            r1.notificaciones_ciclo_residencia.get().tipo,
            NotificacionCicloResidencia.TIPO_PROMOCION,
        )
        self.assertEqual(r1.notificaciones_ciclo_residencia.get().anio_nuevo, 'R2')
        self.assertEqual(
            r4.notificaciones_ciclo_residencia.get().tipo,
            NotificacionCicloResidencia.TIPO_EGRESO,
        )

    def test_repetidor_conserva_anio_y_la_excepcion_se_limpia(self):
        residente = self.crear_residente('repite', 'R2', repite_anio_residencia=True)

        procesar_cierre_residencia(cierre_anio=2026)

        residente.refresh_from_db()
        self.assertEqual(residente.anio_residencia, 'R2')
        self.assertFalse(residente.repite_anio_residencia)
        self.assertEqual(residente.ultimo_cierre_residencia, 2026)
        self.assertFalse(residente.notificaciones_ciclo_residencia.exists())

    def test_el_cierre_es_idempotente(self):
        residente = self.crear_residente('idempotente', 'R1')

        procesar_cierre_residencia(cierre_anio=2026)
        procesar_cierre_residencia(cierre_anio=2026)

        residente.refresh_from_db()
        self.assertEqual(residente.anio_residencia, 'R2')

    def test_dry_run_no_modifica_datos(self):
        residente = self.crear_residente('simulacion', 'R4')

        resultado = procesar_cierre_residencia(cierre_anio=2026, dry_run=True)

        residente.refresh_from_db()
        self.assertEqual(len(resultado['egresados']), 1)
        self.assertEqual(residente.estado_residencia, 'ACTIVO')
        self.assertEqual(residente.anio_residencia, 'R4')
        self.assertFalse(NotificacionCicloResidencia.objects.exists())


@override_settings(SECURE_SSL_REDIRECT=False)
class NotificacionCicloResidenciaTests(TestCase):
    def setUp(self):
        self.usuario = CustomUser.objects.create_user(
            username='residente_modal',
            password='testpass123',
            rol='medico_residente',
            perfil_completo=True,
            anio_residencia='R2',
        )
        self.notificacion = NotificacionCicloResidencia.objects.create(
            usuario=self.usuario,
            cierre_anio=2026,
            tipo=NotificacionCicloResidencia.TIPO_PROMOCION,
            anio_anterior='R1',
            anio_nuevo='R2',
        )

    def test_context_processor_expone_notificacion_pendiente(self):
        request = type('Request', (), {'user': self.usuario})()
        contexto = notificacion_ciclo_residencia(request)
        self.assertEqual(contexto['notificacion_ciclo_residencia'], self.notificacion)

    def test_usuario_confirma_su_notificacion(self):
        self.client.login(username='residente_modal', password='testpass123')
        response = self.client.post(
            reverse('accounts:confirmar_notificacion_ciclo', args=[self.notificacion.pk]),
            {'next': '/accounts/editar-perfil/'},
        )

        self.assertRedirects(response, '/accounts/editar-perfil/', fetch_redirect_response=False)
        self.notificacion.refresh_from_db()
        self.assertIsNotNone(self.notificacion.vista_en)

    def test_modal_se_muestra_en_layout_global_hasta_confirmarlo(self):
        self.client.login(username='residente_modal', password='testpass123')

        response = self.client.get(reverse('accounts:editar_perfil'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '¡Felicitaciones')
        self.assertContains(response, 'Completaste tu primer año e iniciás un')
        self.assertContains(response, 'segundo año')
        self.assertContains(response, 'R1')
        self.assertContains(response, 'R2')
        self.assertContains(
            response,
            reverse('accounts:confirmar_notificacion_ciclo', args=[self.notificacion.pk]),
        )

    def test_usuario_no_puede_confirmar_notificacion_ajena(self):
        otro = CustomUser.objects.create_user(
            username='otro_residente', password='testpass123', rol='medico_residente'
        )
        ajena = NotificacionCicloResidencia.objects.create(
            usuario=otro,
            cierre_anio=2026,
            tipo=NotificacionCicloResidencia.TIPO_PROMOCION,
            anio_anterior='R2',
            anio_nuevo='R3',
        )
        self.client.login(username='residente_modal', password='testpass123')

        response = self.client.post(
            reverse('accounts:confirmar_notificacion_ciclo', args=[ajena.pk])
        )

        self.assertEqual(response.status_code, 404)
        ajena.refresh_from_db()
        self.assertIsNone(ajena.vista_en)
