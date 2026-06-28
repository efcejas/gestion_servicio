from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import (
    Estudios,
    HistorialRecalculoSolicitudRevisionHorario,
    PreparacionLiquidacionRRHH,
    RegistroEstudio,
    RegistroEstudiosPorMedico,
    SesionContable,
    SolicitudRevisionHorarioRegistro,
)
from .services_rrhh import construir_snapshot_liquidacion_rrhh


User = get_user_model()


class PreparacionLiquidacionRRHHTest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username='admin_rrhh',
            password='x',
            rol='administrativo',
            perfil_completo=True,
        )
        self.jefe_servicio = User.objects.create_user(
            username='jefe_servicio_rrhh',
            password='x',
            rol='jefe_servicio',
            perfil_completo=True,
        )
        self.superuser = User.objects.create_superuser(
            username='super_rrhh',
            password='x',
            email='super@test.com',
        )
        self.residente = User.objects.create_user(
            username='res_rrhh',
            password='x',
            rol='medico_residente',
            first_name='Ana',
            last_name='Residente',
            perfil_completo=True,
        )
        self.jefe_residentes = User.objects.create_user(
            username='jefe_res_rrhh',
            password='x',
            rol='jefe_residentes',
            first_name='Bruno',
            last_name='Jefe',
            perfil_completo=True,
        )
        self.instructor = User.objects.create_user(
            username='inst_rrhh',
            password='x',
            rol='instructor_residentes',
            first_name='Carla',
            last_name='Instructor',
            perfil_completo=True,
        )
        self.staff = User.objects.create_user(
            username='staff_rrhh',
            password='x',
            rol='medico_staff',
            first_name='Diego',
            last_name='Staff',
            perfil_completo=True,
        )

        self.sesion = SesionContable.objects.create(mes=6, año=2026, estado='CERRADA')
        self.estudio = Estudios.objects.create(
            nombre='Eco RRHH',
            tipo='ECO',
            conteo_regiones=1,
            conteo_regiones_default=1,
            precio_cober=Decimal('1000.00'),
            precio_otras_os=Decimal('1000.00'),
            activo=True,
        )

    def _crear_registro(self, medico, monto=Decimal('1000.00'), sesion=None):
        registro = RegistroEstudiosPorMedico.objects.create(
            sesion_contable=sesion or self.sesion,
            medico=medico,
            nombre_paciente='Paciente',
            apellido_paciente='RRHH',
            dni_paciente=f'{medico.pk:08d}',
            fecha_del_informe=timezone.datetime(2026, 6, 10).date(),
            tipo_obra_social='COBER',
            horario='EXTRA',
            cantidad_regiones=1,
            monto_calculado=monto,
        )
        RegistroEstudio.objects.create(
            registro=registro,
            estudio=self.estudio,
            cantidad=1,
            contexto='SERVICIO',
        )
        RegistroEstudiosPorMedico.objects.filter(pk=registro.pk).update(
            monto_calculado=monto,
            horario='EXTRA',
        )
        registro.refresh_from_db()
        return registro

    def _post_preparacion(self, user, sesion=None, estado='BORRADOR', destinatarios=''):
        self.client.force_login(user)
        data = {
            'destinatarios': destinatarios,
            'cc': '',
            'asunto': 'Liquidacion residencia test',
            'cuerpo': 'Preview sin envio real',
        }
        boton = 'guardar_preparado' if estado == 'PREPARADO' else 'guardar_borrador'
        data[boton] = '1'
        return self.client.post(
            reverse('liquidacion:preparacion_rrhh_preview', args=[(sesion or self.sesion).pk]),
            data,
            secure=True,
        )

    def test_crea_preparacion_version_1(self):
        self._crear_registro(self.residente)
        response = self._post_preparacion(self.admin)

        self.assertEqual(response.status_code, 302)
        preparacion = PreparacionLiquidacionRRHH.objects.get()
        self.assertEqual(preparacion.version, 1)
        self.assertEqual(preparacion.estado, PreparacionLiquidacionRRHH.ESTADO_BORRADOR)

    def test_crea_version_2_para_misma_sesion(self):
        self._crear_registro(self.residente)
        self._post_preparacion(self.admin)
        self._post_preparacion(self.admin)

        versiones = list(
            PreparacionLiquidacionRRHH.objects.order_by('version').values_list('version', flat=True)
        )
        self.assertEqual(versiones, [1, 2])

    def test_no_duplica_misma_version(self):
        self._crear_registro(self.residente)
        PreparacionLiquidacionRRHH.objects.create(
            sesion_contable=self.sesion,
            version=1,
            estado=PreparacionLiquidacionRRHH.ESTADO_BORRADOR,
            asunto='A',
            cuerpo='B',
            resumen_json={},
            snapshot_hash='a' * 64,
            creado_por=self.admin,
            actualizado_por=self.admin,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                PreparacionLiquidacionRRHH.objects.create(
                    sesion_contable=self.sesion,
                    version=1,
                    estado=PreparacionLiquidacionRRHH.ESTADO_BORRADOR,
                    asunto='A',
                    cuerpo='B',
                    resumen_json={},
                    snapshot_hash='b' * 64,
                    creado_por=self.admin,
                    actualizado_por=self.admin,
                )

    def test_snapshot_incluye_solo_roles_residencia_y_excluye_otros(self):
        self._crear_registro(self.residente, Decimal('1000.00'))
        self._crear_registro(self.jefe_residentes, Decimal('2000.00'))
        self._crear_registro(self.instructor, Decimal('3000.00'))
        self._crear_registro(self.staff, Decimal('4000.00'))
        self._crear_registro(self.jefe_servicio, Decimal('5000.00'))
        self._crear_registro(self.admin, Decimal('6000.00'))

        snapshot = construir_snapshot_liquidacion_rrhh(self.sesion)
        roles = {item['rol'] for item in snapshot['profesionales']}

        self.assertEqual(roles, {'medico_residente', 'jefe_residentes', 'instructor_residentes'})
        self.assertEqual(snapshot['totales']['monto_practicas'], '6000.00')
        self.assertEqual(snapshot['totales']['total_general'], '6000.00')

    def test_snapshot_usa_monto_calculado_sin_recalcular(self):
        self._crear_registro(self.residente, Decimal('1234.00'))

        with patch.object(
            RegistroEstudiosPorMedico,
            'calcular_monto',
            side_effect=AssertionError('No debe recalcular'),
        ):
            snapshot = construir_snapshot_liquidacion_rrhh(self.sesion)

        self.assertEqual(snapshot['totales']['monto_practicas'], '1234.00')

    def test_snapshot_sin_practicas_residencia_marca_rrhh_no_requerido(self):
        self._crear_registro(self.staff, Decimal('4321.00'))

        with patch.object(
            RegistroEstudiosPorMedico,
            'calcular_monto',
            side_effect=AssertionError('No debe recalcular'),
        ):
            snapshot = construir_snapshot_liquidacion_rrhh(self.sesion)

        self.assertFalse(snapshot['sesion']['requiere_rrhh'])
        self.assertEqual(snapshot['totales']['profesionales'], 0)
        self.assertEqual(snapshot['totales']['cantidad_guardias'], 0)
        self.assertEqual(snapshot['totales']['monto_guardias'], '0.00')
        self.assertIn('RRHH no requerido', ' '.join(snapshot['validaciones']['advertencias']))

    def test_preparado_sin_practicas_residencia_bloqueado(self):
        self._crear_registro(self.staff, Decimal('4321.00'))

        response = self._post_preparacion(self.admin, estado='PREPARADO', destinatarios='rrhh@test.com')

        self.assertEqual(response.status_code, 200)
        self.assertFalse(PreparacionLiquidacionRRHH.objects.exists())

    def test_bloquea_abierta_y_revision(self):
        for estado in ['ABIERTA', 'REVISION']:
            sesion = SesionContable.objects.create(mes=7 if estado == 'ABIERTA' else 8, año=2026, estado=estado)
            self._crear_registro(self.residente, sesion=sesion)
            self.client.force_login(self.admin)
            response = self.client.get(
                reverse('liquidacion:preparacion_rrhh_preview', args=[sesion.pk]),
                secure=True,
            )
            self.assertEqual(response.status_code, 302)
            self.assertFalse(PreparacionLiquidacionRRHH.objects.filter(sesion_contable=sesion).exists())

    def test_permite_cerrada(self):
        self._crear_registro(self.residente)
        self.client.force_login(self.admin)
        response = self.client.get(
            reverse('liquidacion:preparacion_rrhh_preview', args=[self.sesion.pk]),
            secure=True,
        )
        self.assertEqual(response.status_code, 200)

    def test_preview_muestra_accion_para_bloqueante_de_registro(self):
        registro = self._crear_registro(self.residente, Decimal('0.00'))
        self.client.force_login(self.admin)

        response = self.client.get(
            reverse('liquidacion:preparacion_rrhh_preview', args=[self.sesion.pk]),
            secure=True,
        )

        self.assertEqual(response.status_code, 200)
        acciones = [
            issue.get('accion')
            for issue in response.context['validaciones_accionables_bloqueantes']
            if issue.get('registro_id') == registro.pk
        ]
        self.assertTrue(acciones)
        self.assertEqual(acciones[0]['label'], 'Inspeccionar registro')
        self.assertIn(reverse('liquidacion:registroestudios_admin_detalle', args=[registro.pk]), acciones[0]['url'])

    def test_bloquea_solicitud_pendiente(self):
        registro = self._crear_registro(self.residente)
        SolicitudRevisionHorarioRegistro.objects.create(
            registro=registro,
            solicitado_por=self.residente,
            horario_solicitado='INTRA',
            fecha_hora_real_declarada=timezone.now(),
            motivo_solicitud='Test',
        )

        response = self._post_preparacion(self.admin, estado='PREPARADO', destinatarios='rrhh@test.com')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(PreparacionLiquidacionRRHH.objects.exists())

    def test_bloquea_aprobada_sin_aplicar_y_permite_aplicada(self):
        registro = self._crear_registro(self.residente)
        solicitud = SolicitudRevisionHorarioRegistro.objects.create(
            registro=registro,
            solicitado_por=self.residente,
            horario_solicitado='INTRA',
            fecha_hora_real_declarada=timezone.now(),
            motivo_solicitud='Test',
            estado=SolicitudRevisionHorarioRegistro.ESTADO_APROBADA,
        )

        response = self._post_preparacion(self.admin, estado='PREPARADO', destinatarios='rrhh@test.com')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(PreparacionLiquidacionRRHH.objects.exists())

        solicitud.fecha_aplicacion = timezone.now()
        solicitud.aplicado_por = self.admin
        solicitud.horario_anterior = 'EXTRA'
        solicitud.horario_aplicado = 'INTRA'
        solicitud.monto_anterior = Decimal('1000.00')
        solicitud.monto_aplicado = Decimal('1000.00')
        solicitud.save()

        response = self._post_preparacion(self.admin, estado='PREPARADO', destinatarios='rrhh@test.com')
        self.assertEqual(response.status_code, 302)
        self.assertTrue(PreparacionLiquidacionRRHH.objects.exists())

    def test_borrador_sin_destinatarios_permitido(self):
        self._crear_registro(self.residente)
        response = self._post_preparacion(self.admin, estado='BORRADOR', destinatarios='')

        self.assertEqual(response.status_code, 302)
        self.assertEqual(PreparacionLiquidacionRRHH.objects.get().destinatarios_json, [])

    def test_preparado_sin_destinatarios_bloqueado(self):
        self._crear_registro(self.residente)
        response = self._post_preparacion(self.admin, estado='PREPARADO', destinatarios='')

        self.assertEqual(response.status_code, 200)
        self.assertFalse(PreparacionLiquidacionRRHH.objects.exists())

    def test_permisos_administrativos(self):
        self._crear_registro(self.residente)
        for user in [self.admin, self.jefe_servicio, self.superuser]:
            self.client.force_login(user)
            response = self.client.get(
                reverse('liquidacion:preparacion_rrhh_preview', args=[self.sesion.pk]),
                secure=True,
            )
            self.assertEqual(response.status_code, 200)

    def test_residente_y_staff_no_acceden(self):
        self._crear_registro(self.residente)
        for user in [self.residente, self.staff]:
            self.client.force_login(user)
            response = self.client.get(
                reverse('liquidacion:preparacion_rrhh_preview', args=[self.sesion.pk]),
                secure=True,
            )
            self.assertEqual(response.status_code, 302)

    def test_no_envia_email_real(self):
        self._crear_registro(self.residente)
        response = self._post_preparacion(self.admin, estado='PREPARADO', destinatarios='rrhh@test.com')

        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 0)

    def test_advierte_rechazada_y_recalculo_b3(self):
        registro = self._crear_registro(self.residente)
        SolicitudRevisionHorarioRegistro.objects.create(
            registro=registro,
            solicitado_por=self.residente,
            horario_solicitado='INTRA',
            fecha_hora_real_declarada=timezone.now(),
            motivo_solicitud='Test',
            estado=SolicitudRevisionHorarioRegistro.ESTADO_RECHAZADA,
        )
        HistorialRecalculoSolicitudRevisionHorario.objects.create(
            solicitud=SolicitudRevisionHorarioRegistro.objects.create(
                registro=self._crear_registro(self.jefe_residentes),
                solicitado_por=self.jefe_residentes,
                horario_solicitado='INTRA',
                fecha_hora_real_declarada=timezone.now(),
                motivo_solicitud='Test 2',
                estado=SolicitudRevisionHorarioRegistro.ESTADO_APROBADA,
                fecha_aplicacion=timezone.now(),
                aplicado_por=self.admin,
            ),
            registro=registro,
            recalculado_por=self.admin,
            horario_usado='INTRA',
            monto_registro_anterior=Decimal('1000.00'),
            monto_recalculado=Decimal('1000.00'),
        )

        snapshot = construir_snapshot_liquidacion_rrhh(self.sesion)
        advertencias = ' '.join(snapshot['validaciones']['advertencias'])
        self.assertIn('rechazada', advertencias)
        self.assertIn('B3', advertencias)
