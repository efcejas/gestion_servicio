import io
from datetime import time
from decimal import Decimal

import openpyxl
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import (
    Estudios,
    GrupoTarifario,
    PreparacionLiquidacionRRHH,
    CorreccionPacsRegistro,
    ReglaDescuentoResidencia,
    RegistroEstudio,
    RegistroEstudiosPorMedico,
    RevisionAuditoriaEcoRegistro,
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

    def test_vista_sesion_contable_auditoria_eco_muestra_detalle_accionable(self):
        registros = []
        for _ in range(35):
            registros.append(self._crear_registro(monto=Decimal('1000.00')))
        self.client.force_login(self.admin)

        response = self.client.get(reverse('liquidacion:sesiones_list'), secure=True)

        self.assertEqual(response.status_code, 200)
        sesiones_data = response.context['sesiones_data']
        dato = next(item for item in sesiones_data if item['sesion'].pk == self.sesion.pk)
        auditoria_item = next(
            item for item in dato['checklist_cierre']['items']
            if item['key'] == 'auditoria_residentes_eco'
        )
        self.assertEqual(auditoria_item['url'], f'#auditoria-eco-sesion-{self.sesion.pk}')
        self.assertContains(response, 'Cantidad de registros EXTRA mensual elevada')
        self.assertContains(response, 'Ver todos')
        self.assertContains(response, 'Registros que explican la alerta')
        self.assertContains(response, 'Inspeccionar')
        self.assertContains(
            response,
            reverse('liquidacion:registroestudios_admin_detalle', args=[registros[-1].pk]),
        )
        self.assertContains(response, reverse('liquidacion:auditoria_eco_sesion', args=[self.sesion.pk]))

    def test_vista_completa_auditoria_eco_lista_registros_sospechosos(self):
        registros = []
        for _ in range(35):
            registros.append(self._crear_registro(monto=Decimal('1000.00')))
        self.client.force_login(self.admin)

        response = self.client.get(
            reverse('liquidacion:auditoria_eco_sesion', args=[self.sesion.pk]),
            secure=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Auditoria residentes ECO')
        self.assertContains(response, 'Registros sospechosos')
        self.assertContains(response, 'EXTRA')
        self.assertContains(response, 'Inspeccionar')
        self.assertContains(
            response,
            reverse('liquidacion:registroestudios_admin_detalle', args=[registros[-1].pk]),
        )

    def test_vista_completa_auditoria_eco_filtra_por_motivo(self):
        for _ in range(35):
            self._crear_registro(monto=Decimal('1000.00'))
        self.client.force_login(self.admin)

        response = self.client.get(
            reverse('liquidacion:auditoria_eco_sesion', args=[self.sesion.pk]) + '?motivo=MotivoInexistente',
            secure=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'No hay registros sospechosos para los filtros seleccionados.')

    def test_vista_completa_auditoria_eco_deniega_residente(self):
        self.client.force_login(self.residente)

        response = self.client.get(
            reverse('liquidacion:auditoria_eco_sesion', args=[self.sesion.pk]),
            secure=True,
        )

        self.assertIn(response.status_code, [302, 403])

    def test_resolver_alerta_eco_crea_revision_auditada(self):
        registro = self._crear_registro(monto=Decimal('1000.00'))
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse('liquidacion:auditoria_eco_registro_resolver', args=[self.sesion.pk, registro.pk]),
            {
                'estado': RevisionAuditoriaEcoRegistro.ESTADO_VALIDADO,
                'observacion': 'Validado contra PACS.',
                'motivos': ['EXTRA'],
            },
            secure=True,
        )

        self.assertEqual(response.status_code, 302)
        revision = RevisionAuditoriaEcoRegistro.objects.get(registro=registro)
        self.assertEqual(revision.sesion_contable, self.sesion)
        self.assertEqual(revision.estado, RevisionAuditoriaEcoRegistro.ESTADO_VALIDADO)
        self.assertEqual(revision.revisado_por, self.admin)
        self.assertEqual(revision.motivos_json, ['EXTRA'])

    def test_vista_completa_auditoria_eco_muestra_revision_existente(self):
        registro = self._crear_registro(monto=Decimal('1000.00'))
        RevisionAuditoriaEcoRegistro.objects.create(
            sesion_contable=self.sesion,
            registro=registro,
            estado=RevisionAuditoriaEcoRegistro.ESTADO_REQUIERE_CORRECCION,
            motivos_json=['EXTRA'],
            observacion='Difiere de PACS.',
            revisado_por=self.admin,
        )
        for _ in range(34):
            self._crear_registro(monto=Decimal('1000.00'))
        self.client.force_login(self.admin)

        response = self.client.get(
            reverse('liquidacion:auditoria_eco_sesion', args=[self.sesion.pk]),
            secure=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Requiere correccion')
        self.assertContains(response, 'Difiere de PACS.')

    def test_resolver_alerta_eco_deniega_residente(self):
        registro = self._crear_registro(monto=Decimal('1000.00'))
        self.client.force_login(self.residente)

        response = self.client.post(
            reverse('liquidacion:auditoria_eco_registro_resolver', args=[self.sesion.pk, registro.pk]),
            {
                'estado': RevisionAuditoriaEcoRegistro.ESTADO_VALIDADO,
                'observacion': 'Intento no permitido.',
            },
            secure=True,
        )

        self.assertIn(response.status_code, [302, 403])
        self.assertFalse(RevisionAuditoriaEcoRegistro.objects.exists())

    def test_correccion_pacs_requiere_revision_en_requiere_correccion(self):
        registro = self._crear_registro(monto=Decimal('1000.00'))
        RevisionAuditoriaEcoRegistro.objects.create(
            sesion_contable=self.sesion,
            registro=registro,
            estado=RevisionAuditoriaEcoRegistro.ESTADO_VALIDADO,
            motivos_json=['EXTRA'],
            observacion='Validado.',
            revisado_por=self.admin,
        )
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse('liquidacion:auditoria_eco_registro_corregir', args=[self.sesion.pk, registro.pk]),
            {
                'monto_nuevo': '800.00',
                'observacion': 'No corresponde ajustar.',
            },
            secure=True,
        )

        self.assertEqual(response.status_code, 302)
        registro.refresh_from_db()
        self.assertEqual(registro.monto_calculado, Decimal('1000.00'))
        self.assertFalse(CorreccionPacsRegistro.objects.exists())

    def test_correccion_pacs_actualiza_monto_y_auditoria_del_registro(self):
        registro = self._crear_registro(monto=Decimal('1000.00'))
        revision = RevisionAuditoriaEcoRegistro.objects.create(
            sesion_contable=self.sesion,
            registro=registro,
            estado=RevisionAuditoriaEcoRegistro.ESTADO_REQUIERE_CORRECCION,
            motivos_json=['EXTRA'],
            observacion='Difiere de PACS.',
            revisado_por=self.admin,
        )
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse('liquidacion:auditoria_eco_registro_corregir', args=[self.sesion.pk, registro.pk]),
            {
                'monto_nuevo': '650.00',
                'observacion': 'PACS confirma menor valor.',
            },
            secure=True,
        )

        self.assertEqual(response.status_code, 302)
        registro.refresh_from_db()
        self.assertEqual(registro.monto_calculado, Decimal('650.00'))
        self.assertEqual(registro.modificado_por, self.admin)
        self.assertIsNotNone(registro.fecha_modificacion)
        self.assertIn('Ajuste por control PACS', registro.motivo_modificacion)
        correccion = CorreccionPacsRegistro.objects.get(registro=registro)
        self.assertEqual(correccion.revision_auditoria_eco, revision)
        self.assertEqual(correccion.monto_anterior, Decimal('1000.00'))
        self.assertEqual(correccion.monto_nuevo, Decimal('650.00'))
        self.assertEqual(correccion.corregido_por, self.admin)
        ultima_revision = RevisionAuditoriaEcoRegistro.objects.filter(registro=registro).order_by('-fecha_revision').first()
        self.assertEqual(ultima_revision.estado, RevisionAuditoriaEcoRegistro.ESTADO_VALIDADO)
        self.assertIn('Correccion PACS aplicada', ultima_revision.observacion)

    def test_correccion_pacs_recalcula_monto_por_horario_corregido(self):
        registro = self._crear_registro(monto=Decimal('1000.00'))
        revision = RevisionAuditoriaEcoRegistro.objects.create(
            sesion_contable=self.sesion,
            registro=registro,
            estado=RevisionAuditoriaEcoRegistro.ESTADO_REQUIERE_CORRECCION,
            motivos_json=['EXTRA'],
            observacion='PACS confirma horario previo a 17.',
            revisado_por=self.admin,
        )
        ReglaDescuentoResidencia.objects.create(
            estudio=self.estudio,
            aplica_medico_residente=True,
            vigencia_desde=timezone.datetime(2026, 1, 1).date(),
            activo=True,
            creado_por=self.admin,
            actualizado_por=self.admin,
        )
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse('liquidacion:auditoria_eco_registro_corregir', args=[self.sesion.pk, registro.pk]),
            {
                'tipo_correccion': CorreccionPacsRegistro.TIPO_HORARIO_RECALCULADO,
                'horario_corregido': 'INTRA',
                'hora_pacs': '16:30',
                'observacion': 'Horario real antes de las 17 segun PACS.',
            },
            secure=True,
        )

        self.assertEqual(response.status_code, 302)
        registro.refresh_from_db()
        self.assertEqual(registro.horario, 'INTRA')
        self.assertEqual(registro.monto_calculado, Decimal('500.00'))
        self.assertEqual(registro.modificado_por, self.admin)
        self.assertIn('Horario: EXTRA -> INTRA', registro.motivo_modificacion)
        correccion = CorreccionPacsRegistro.objects.get(registro=registro)
        self.assertEqual(correccion.revision_auditoria_eco, revision)
        self.assertEqual(correccion.tipo_correccion, CorreccionPacsRegistro.TIPO_HORARIO_RECALCULADO)
        self.assertEqual(correccion.horario_anterior, 'EXTRA')
        self.assertEqual(correccion.horario_nuevo, 'INTRA')
        self.assertEqual(correccion.hora_pacs, time(16, 30))
        self.assertEqual(correccion.monto_anterior, Decimal('1000.00'))
        self.assertEqual(correccion.monto_nuevo, Decimal('500.00'))
        ultima_revision = RevisionAuditoriaEcoRegistro.objects.filter(registro=registro).order_by('-fecha_revision').first()
        self.assertEqual(ultima_revision.estado, RevisionAuditoriaEcoRegistro.ESTADO_VALIDADO)

    def test_vista_auditoria_no_muestra_formulario_de_ajuste_si_ya_hay_correccion_pacs(self):
        registro = self._crear_registro(monto=Decimal('650.00'))
        revision = RevisionAuditoriaEcoRegistro.objects.create(
            sesion_contable=self.sesion,
            registro=registro,
            estado=RevisionAuditoriaEcoRegistro.ESTADO_REQUIERE_CORRECCION,
            motivos_json=['EXTRA'],
            observacion='Difiere de PACS.',
            revisado_por=self.admin,
        )
        CorreccionPacsRegistro.objects.create(
            sesion_contable=self.sesion,
            registro=registro,
            revision_auditoria_eco=revision,
            tipo_correccion=CorreccionPacsRegistro.TIPO_HORARIO_RECALCULADO,
            horario_anterior='EXTRA',
            horario_nuevo='INTRA',
            hora_pacs=time(16, 30),
            monto_anterior=Decimal('1000.00'),
            monto_nuevo=Decimal('650.00'),
            observacion='PACS confirma horario real.',
            corregido_por=self.admin,
        )
        self.client.force_login(self.admin)

        response = self.client.get(
            reverse('liquidacion:auditoria_eco_sesion', args=[self.sesion.pk]),
            secure=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Ajuste PACS aplicado')
        self.assertNotContains(response, 'Aplicar ajuste por control PACS')

    def test_correccion_pacs_bloquea_sesion_facturada(self):
        registro = self._crear_registro(monto=Decimal('1000.00'))
        RevisionAuditoriaEcoRegistro.objects.create(
            sesion_contable=self.sesion,
            registro=registro,
            estado=RevisionAuditoriaEcoRegistro.ESTADO_REQUIERE_CORRECCION,
            motivos_json=['EXTRA'],
            observacion='Difiere de PACS.',
            revisado_por=self.admin,
        )
        self.sesion.estado = 'FACTURADA'
        self.sesion.save(update_fields=['estado'])
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse('liquidacion:auditoria_eco_registro_corregir', args=[self.sesion.pk, registro.pk]),
            {
                'monto_nuevo': '650.00',
                'observacion': 'PACS confirma menor valor.',
            },
            secure=True,
        )

        self.assertEqual(response.status_code, 302)
        registro.refresh_from_db()
        self.assertEqual(registro.monto_calculado, Decimal('1000.00'))
        self.assertFalse(CorreccionPacsRegistro.objects.exists())

    def test_lista_personal_muestra_ajuste_pacs_aplicado(self):
        registro = self._crear_registro(monto=Decimal('650.00'))
        revision = RevisionAuditoriaEcoRegistro.objects.create(
            sesion_contable=self.sesion,
            registro=registro,
            estado=RevisionAuditoriaEcoRegistro.ESTADO_REQUIERE_CORRECCION,
            motivos_json=['EXTRA'],
            observacion='Difiere de PACS.',
            revisado_por=self.admin,
        )
        CorreccionPacsRegistro.objects.create(
            sesion_contable=self.sesion,
            registro=registro,
            revision_auditoria_eco=revision,
            monto_anterior=Decimal('1000.00'),
            monto_nuevo=Decimal('650.00'),
            observacion='PACS confirma menor valor.',
            corregido_por=self.admin,
        )
        self.client.force_login(self.residente)

        response = self.client.get(
            reverse('liquidacion:registroestudios_list') + '?mes=6&aÃ±o=2026',
            secure=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Ajuste PACS aplicado')
        self.assertContains(response, 'PACS confirma menor valor.')

    def test_liquidacion_mensual_muestra_resumen_y_detalle_de_ajustes_pacs(self):
        registro = self._crear_registro(monto=Decimal('650.00'))
        revision = RevisionAuditoriaEcoRegistro.objects.create(
            sesion_contable=self.sesion,
            registro=registro,
            estado=RevisionAuditoriaEcoRegistro.ESTADO_VALIDADO,
            motivos_json=['EXTRA'],
            observacion='Correccion PACS aplicada.',
            revisado_por=self.admin,
        )
        CorreccionPacsRegistro.objects.create(
            sesion_contable=self.sesion,
            registro=registro,
            revision_auditoria_eco=revision,
            tipo_correccion=CorreccionPacsRegistro.TIPO_HORARIO_RECALCULADO,
            horario_anterior='EXTRA',
            horario_nuevo='INTRA',
            hora_pacs=time(16, 30),
            monto_anterior=Decimal('1000.00'),
            monto_nuevo=Decimal('650.00'),
            observacion='PACS confirma horario real.',
            corregido_por=self.admin,
        )
        self.client.force_login(self.admin)

        response = self.client.get(
            reverse('liquidacion:liquidacion_mensual'),
            {'mes': 6, 'año': 2026},
            secure=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Ajustes PACS: 1')
        self.assertContains(response, 'Impacto total: $-350,00')
        self.assertContains(response, 'Horario EXTRA -> INTRA')
        self.assertContains(response, 'Hora PACS 16:30')
        self.assertContains(response, 'PACS confirma horario real.')

    def test_export_liquidacion_incluye_columnas_de_ajuste_pacs(self):
        registro = self._crear_registro(monto=Decimal('650.00'))
        revision = RevisionAuditoriaEcoRegistro.objects.create(
            sesion_contable=self.sesion,
            registro=registro,
            estado=RevisionAuditoriaEcoRegistro.ESTADO_VALIDADO,
            motivos_json=['EXTRA'],
            observacion='Correccion PACS aplicada.',
            revisado_por=self.admin,
        )
        CorreccionPacsRegistro.objects.create(
            sesion_contable=self.sesion,
            registro=registro,
            revision_auditoria_eco=revision,
            tipo_correccion=CorreccionPacsRegistro.TIPO_HORARIO_RECALCULADO,
            horario_anterior='EXTRA',
            horario_nuevo='INTRA',
            hora_pacs=time(16, 30),
            monto_anterior=Decimal('1000.00'),
            monto_nuevo=Decimal('650.00'),
            observacion='PACS confirma horario real.',
            corregido_por=self.admin,
        )
        self.client.force_login(self.admin)

        response = self.client.get(
            reverse('liquidacion:exportar_excel_liquidacion'),
            {'mes': 6, 'año': 2026},
            secure=True,
        )

        self.assertEqual(response.status_code, 200)
        workbook = openpyxl.load_workbook(io.BytesIO(response.content))
        sheet = workbook.active
        headers = [cell.value for cell in sheet[1]]
        self.assertIn('Ajuste PACS', headers)
        self.assertIn('Monto anterior PACS', headers)
        self.assertIn('Hora PACS', headers)
        self.assertIn('Observacion ajuste PACS', headers)
        rows = list(sheet.iter_rows(values_only=True))
        self.assertTrue(any(row[10] == 'SI' for row in rows[1:]))
        self.assertTrue(any(row[12] == 'EXTRA' and row[13] == 'INTRA' for row in rows[1:]))
        self.assertTrue(any(row[16] == '16:30' for row in rows[1:]))
        self.assertTrue(any(row[17] == 'PACS confirma horario real.' for row in rows[1:]))

    def test_admin_puede_inspeccionar_registro_desde_cierre(self):
        registro = self._crear_registro(monto=Decimal('0.00'))
        self.client.force_login(self.admin)

        response = self.client.get(
            reverse('liquidacion:registroestudios_admin_detalle', args=[registro.pk]),
            secure=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['registro'].pk, registro.pk)
