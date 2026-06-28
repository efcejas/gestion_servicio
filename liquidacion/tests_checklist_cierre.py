from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import (
    Estudios,
    GrupoTarifario,
    PreparacionLiquidacionRRHH,
    RegistroEstudio,
    RegistroEstudiosPorMedico,
    SesionContable,
    SolicitudRevisionHorarioRegistro,
    TarifaGrupoTarifario,
)
from .services_cierre import construir_checklist_cierre_sesion


User = get_user_model()


class ChecklistCierreSesionTest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username='admin_checklist',
            password='x',
            rol='administrativo',
            perfil_completo=True,
        )
        self.residente = User.objects.create_user(
            username='res_checklist',
            password='x',
            rol='medico_residente',
            first_name='Ana',
            last_name='Checklist',
            perfil_completo=True,
        )
        self.staff = User.objects.create_user(
            username='staff_checklist',
            password='x',
            rol='medico_staff',
            first_name='Staff',
            last_name='Checklist',
            perfil_completo=True,
        )
        self.sesion = SesionContable.objects.create(mes=6, año=2026, estado='CERRADA')
        self.grupo = GrupoTarifario.objects.create(
            codigo='ECO_CHECKLIST',
            nombre='Eco Checklist',
            modalidad='ECO',
            activo=True,
        )
        TarifaGrupoTarifario.objects.create(
            grupo_tarifario=self.grupo,
            vigencia_desde=timezone.datetime(2026, 1, 1).date(),
            precio_cober=Decimal('1000.00'),
            precio_otras_os=Decimal('1000.00'),
            motivo_actualizacion='Test checklist',
        )
        self.estudio = Estudios.objects.create(
            nombre='Eco Checklist',
            tipo='ECO',
            conteo_regiones=1,
            conteo_regiones_default=1,
            precio_cober=Decimal('1000.00'),
            precio_otras_os=Decimal('1000.00'),
            activo=True,
            grupo_tarifario=self.grupo,
        )

    def _crear_registro(self, sesion=None, monto=Decimal('1000.00'), medico=None):
        registro = RegistroEstudiosPorMedico.objects.create(
            sesion_contable=sesion or self.sesion,
            medico=medico or self.residente,
            nombre_paciente='Paciente',
            apellido_paciente='Checklist',
            dni_paciente='12345678',
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

    def _item(self, checklist, key):
        return next(item for item in checklist['items'] if item['key'] == key)

    def test_sesion_sin_bloqueantes_devuelve_registros_validos_ok(self):
        self._crear_registro()

        checklist = construir_checklist_cierre_sesion(self.sesion)

        self.assertEqual(self._item(checklist, 'registros_validos')['estado'], 'ok')

    def test_solicitud_pendiente_devuelve_bloqueante(self):
        registro = self._crear_registro()
        SolicitudRevisionHorarioRegistro.objects.create(
            registro=registro,
            solicitado_por=self.residente,
            horario_solicitado='INTRA',
            fecha_hora_real_declarada=timezone.now(),
            motivo_solicitud='Test',
        )

        checklist = construir_checklist_cierre_sesion(self.sesion)

        self.assertEqual(self._item(checklist, 'solicitudes_pendientes')['estado'], 'bloqueante')

    def test_aprobada_sin_aplicar_devuelve_bloqueante(self):
        registro = self._crear_registro()
        SolicitudRevisionHorarioRegistro.objects.create(
            registro=registro,
            solicitado_por=self.residente,
            horario_solicitado='INTRA',
            fecha_hora_real_declarada=timezone.now(),
            motivo_solicitud='Test',
            estado=SolicitudRevisionHorarioRegistro.ESTADO_APROBADA,
        )

        checklist = construir_checklist_cierre_sesion(self.sesion)

        self.assertEqual(self._item(checklist, 'aprobadas_sin_aplicar')['estado'], 'bloqueante')

    def test_aprobada_aplicada_devuelve_ok(self):
        registro = self._crear_registro()
        SolicitudRevisionHorarioRegistro.objects.create(
            registro=registro,
            solicitado_por=self.residente,
            horario_solicitado='INTRA',
            fecha_hora_real_declarada=timezone.now(),
            motivo_solicitud='Test',
            estado=SolicitudRevisionHorarioRegistro.ESTADO_APROBADA,
            fecha_aplicacion=timezone.now(),
            aplicado_por=self.admin,
        )

        checklist = construir_checklist_cierre_sesion(self.sesion)

        self.assertEqual(self._item(checklist, 'aprobadas_sin_aplicar')['estado'], 'ok')

    def test_preparacion_rrhh_inexistente_en_cerrada_devuelve_pendiente(self):
        self._crear_registro()

        checklist = construir_checklist_cierre_sesion(self.sesion)

        self.assertEqual(self._item(checklist, 'preparacion_rrhh')['estado'], 'pendiente')

    def test_preparacion_rrhh_no_requerida_sin_practicas_residencia_devuelve_ok(self):
        self._crear_registro(medico=self.staff)

        checklist = construir_checklist_cierre_sesion(self.sesion)

        item = self._item(checklist, 'preparacion_rrhh')
        self.assertEqual(item['estado'], 'ok')
        self.assertEqual(item['detalle'], 'No requerido')

    def test_cerrada_con_residencia_sin_rrhh_preparado_no_esta_lista_para_facturar(self):
        self._crear_registro()

        checklist = construir_checklist_cierre_sesion(self.sesion)

        self.assertEqual(self._item(checklist, 'lista_para_facturar')['estado'], 'pendiente')

    def test_preparacion_rrhh_borrador_devuelve_advertencia(self):
        self._crear_registro()
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

        checklist = construir_checklist_cierre_sesion(self.sesion)

        self.assertEqual(self._item(checklist, 'preparacion_rrhh')['estado'], 'advertencia')

    def test_preparacion_rrhh_preparado_devuelve_ok(self):
        self._crear_registro()
        PreparacionLiquidacionRRHH.objects.create(
            sesion_contable=self.sesion,
            version=1,
            estado=PreparacionLiquidacionRRHH.ESTADO_PREPARADO,
            asunto='A',
            cuerpo='B',
            resumen_json={},
            snapshot_hash='a' * 64,
            creado_por=self.admin,
            actualizado_por=self.admin,
        )

        checklist = construir_checklist_cierre_sesion(self.sesion)

        self.assertEqual(self._item(checklist, 'preparacion_rrhh')['estado'], 'ok')
        self.assertEqual(self._item(checklist, 'lista_para_facturar')['estado'], 'ok')

    def test_sesion_facturada_marca_lista_para_facturar_ok(self):
        self.sesion.estado = 'FACTURADA'
        self.sesion.save(update_fields=['estado'])
        self._crear_registro()

        checklist = construir_checklist_cierre_sesion(self.sesion)

        self.assertEqual(self._item(checklist, 'lista_para_facturar')['estado'], 'ok')

    def test_sesion_pagada_marca_sesion_pagada_ok(self):
        self.sesion.estado = 'PAGADA'
        self.sesion.save(update_fields=['estado'])
        self._crear_registro()

        checklist = construir_checklist_cierre_sesion(self.sesion)

        self.assertEqual(self._item(checklist, 'sesion_pagada')['estado'], 'ok')

    def test_vista_sesion_contable_incluye_checklist_cierre(self):
        self._crear_registro()
        self.client.force_login(self.admin)

        response = self.client.get(reverse('liquidacion:sesiones_list'), secure=True)

        self.assertEqual(response.status_code, 200)
        sesiones_data = response.context['sesiones_data']
        dato = next(item for item in sesiones_data if item['sesion'].pk == self.sesion.pk)
        self.assertIn('checklist_cierre', dato)
        self.assertEqual(dato['checklist_cierre']['sesion_id'], self.sesion.pk)

    def test_vista_sesion_contable_incluye_accion_para_bloqueante_de_registro(self):
        registro = self._crear_registro(monto=Decimal('0.00'))
        self.client.force_login(self.admin)

        response = self.client.get(reverse('liquidacion:sesiones_list'), secure=True)

        self.assertEqual(response.status_code, 200)
        sesiones_data = response.context['sesiones_data']
        dato = next(item for item in sesiones_data if item['sesion'].pk == self.sesion.pk)
        acciones = [
            issue.get('accion')
            for issue in dato['gate_advertencias_accionables']
            if issue.get('registro_id') == registro.pk
        ]
        self.assertTrue(acciones)
        self.assertEqual(acciones[0]['label'], 'Inspeccionar registro')
        self.assertIn(reverse('liquidacion:registroestudios_admin_detalle', args=[registro.pk]), acciones[0]['url'])

    def test_admin_puede_inspeccionar_registro_desde_cierre(self):
        registro = self._crear_registro(monto=Decimal('0.00'))
        self.client.force_login(self.admin)

        response = self.client.get(
            reverse('liquidacion:registroestudios_admin_detalle', args=[registro.pk]),
            secure=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['registro'].pk, registro.pk)
