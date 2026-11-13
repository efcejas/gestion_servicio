from datetime import date, time
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from eges_import.tests_produccion import FuentesSinteticasMixin
from .models import (Estudios, RegistroEstudio, RegistroEstudiosPorMedico, SesionContable,
                     ResultadoControlEgesRegistro, RevisionCruceEgesRegistro,
                     ValidacionRespaldoFuenteRegistro)
from .services_respaldo_fuentes import construir_preview_respaldo_fuentes


class RespaldoFuentesTest(FuentesSinteticasMixin, TestCase):
    # Se reutilizan factories sinteticas, no archivos reales ni bases clinicas.
    def setUp(self):
        super().setUp()
        self.medico = get_user_model().objects.create_user(username='medico_respaldo', first_name='Carlos',
                                                          last_name='Puente', rol='medico_residente', perfil_completo=True)
        self.sesion = SesionContable.objects.create(mes=10, año=2026, estado='REVISION')
        self.estudio = Estudios.objects.create(nombre='ECOGRAFIA COMPLETA DE ABDOMEN', codigo='180112',
                                               tipo='ECO', conteo_regiones=1, precio_cober=Decimal('1000'), precio_otras_os=Decimal('1000'))

    def registro(self, estudio=None, medico=None, cantidad=1, documento='12345678'):
        registro = RegistroEstudiosPorMedico.objects.create(
            sesion_contable=self.sesion, medico=medico or self.medico, nombre_paciente='SINTETICO', apellido_paciente='QA',
            dni_paciente=documento, fecha_del_informe=date(2026, 10, 10), horario='EXTRA', monto_calculado=Decimal('1234.56'),
        )
        RegistroEstudio.objects.create(registro=registro, estudio=estudio or self.estudio, cantidad=cantidad)
        return registro

    def respaldo(self, **filtros):
        return construir_preview_respaldo_fuentes(sesion=self.sesion, batch_eges_ids=[self.batch.pk],
                                                  lote_netterm_ids=[self.lote.pk], filtros=filtros)

    def test_cierre_consume_respaldo_confirmado_solo_para_ausencia_eges(self):
        from .models import ControlEgesSesion
        from .services_eges import resumir_control_eges_sesion
        from .services_respaldo_fuentes import registrar_validacion_respaldo_fuente

        registro = self.registro()
        self.netterm()
        control = ControlEgesSesion.objects.create(
            sesion_contable=self.sesion, batch_eges=self.batch, version=1, procesado_por=self.usuario,
        )
        resultado = ResultadoControlEgesRegistro.objects.create(
            control=control, registro=registro, estado='MANUAL',
            motivos_json=['No se encontró práctica EGES ECO para el DNI y fecha del registro.'],
        )
        self.assertEqual(resumir_control_eges_sesion(self.sesion)['pendientes'], 1)
        linea = self.respaldo()['resultados'][0]['lineas'][0]
        antes = list(RegistroEstudiosPorMedico.objects.values())
        registrar_validacion_respaldo_fuente(
            sesion=self.sesion, linea_id=linea['relacion_id'], batch_eges_ids=[self.batch.pk],
            lote_netterm_ids=[self.lote.pk], firma_esperada=linea['firma_validacion'], usuario=self.usuario,
        )
        resumen = resumir_control_eges_sesion(self.sesion)
        self.assertEqual(resumen['pendientes'], 0)
        self.assertEqual(resumen['resueltos_respaldo'], 1)
        self.assertFalse(resumen['desactualizado'])
        self.assertEqual(antes, list(RegistroEstudiosPorMedico.objects.values()))
        resultado.motivos_json = ['Hay prácticas con cantidad distinta entre liquidación y EGES.']
        resultado.save()
        self.assertEqual(resumir_control_eges_sesion(self.sesion)['pendientes'], 1)
        resultado.motivos_json = ['No se encontró práctica EGES ECO para el DNI y fecha del registro.']
        resultado.save()
        RegistroEstudio.objects.filter(registro=registro).update(cantidad=2)
        self.assertEqual(resumir_control_eges_sesion(self.sesion)['pendientes'], 1)

    def parametros_preview(self):
        return {'lotes_eges': [self.batch.pk], 'lotes_netterm': [self.lote.pk]}

    def validar_linea(self, linea):
        return self.client.post(
            reverse('liquidacion:respaldo_fuentes_validar', kwargs={'pk': self.sesion.pk}),
            {
                'relacion_id': linea['relacion_id'],
                'firma_validacion': linea['firma_validacion'],
                'lotes_eges': [self.batch.pk],
                'lotes_netterm': [self.lote.pk],
                'estado_respaldo': '',
            },
        )

    def validar_lineas_masivo(self, preview, linea_ids):
        return self.client.post(
            reverse('liquidacion:respaldo_fuentes_validar_masivo', kwargs={'pk': self.sesion.pk}),
            {
                'relacion_ids': linea_ids,
                'firma_fuentes': preview['firma_fuentes'],
                'lotes_eges': [self.batch.pk],
                'lotes_netterm': [self.lote.pk],
                'page': '1',
                'estado_respaldo': '',
            },
        )

    def test_faltante_eges_tiene_respaldo_netterm_sin_certificar_cantidad_o_monto(self):
        registro = self.registro(cantidad=3)
        # Simula un monto historico ya fijado; crear la relacion dispara el
        # calculo normal del modelo, que no forma parte del servicio de respaldo.
        RegistroEstudiosPorMedico.objects.filter(pk=registro.pk).update(monto_calculado=Decimal('1234.56'))
        self.netterm(estado='PENDIENTE')
        antes = (list(RegistroEstudiosPorMedico.objects.values()), list(RegistroEstudio.objects.values()))
        with CaptureQueriesContext(connection) as consultas:
            resultado = self.respaldo()
        linea = resultado['resultados'][0]['lineas'][0]
        self.assertEqual(resultado['resultados'][0]['estado_respaldo'], 'OK_RESPALDO')
        self.assertEqual(linea['estado'], 'OK_NETTERM')
        self.assertEqual(linea['cantidad_declarada'], 3)
        self.assertFalse(linea['cantidad_economica_validada'])
        self.assertFalse(linea['horario_economico_validado'])
        self.assertEqual(antes, (list(RegistroEstudiosPorMedico.objects.values()), list(RegistroEstudio.objects.values())))
        self.assertFalse(any(q['sql'].lstrip().upper().startswith(('INSERT ', 'UPDATE ', 'DELETE ')) for q in consultas))
        self.assertFalse(ResultadoControlEgesRegistro.objects.exists())
        self.assertFalse(RevisionCruceEgesRegistro.objects.exists())
        registro.refresh_from_db()
        self.assertEqual(registro.monto_calculado, Decimal('1234.56'))

    def test_eges_tiene_prioridad_y_otro_informante_netterm_no_lo_quita(self):
        self.registro()
        self.eges(estado_turno='Fin Practica')
        self.netterm(informante='OTRO PROFESIONAL')
        linea = self.respaldo()['resultados'][0]['lineas'][0]
        self.assertEqual(linea['estado'], 'OK_EGES')
        self.assertTrue(linea['reafirmado_netterm'])
        self.assertTrue(any('conserva el respaldo EGES' in m for m in linea['motivos']))

    def test_tomografia_sin_eges_puede_respaldarse_con_netterm(self):
        estudio = Estudios.objects.create(nombre='TOMOGRAFIA DE TORAX', codigo='340101', tipo='TOM', conteo_regiones=1)
        self.registro(estudio)
        self.netterm(codigo='340101', practica='TOMOGRAFIA DE TORAX', estado='NO_DEFINITIVO')
        self.assertEqual(self.respaldo()['resultados'][0]['lineas'][0]['estado'], 'OK_NETTERM')

    def test_cierre_tomografia_staff_exige_respaldo_confirmado_vigente(self):
        from .services_eges import resumir_control_eges_sesion
        from .services_respaldo_fuentes import registrar_validacion_respaldo_fuente

        self.medico.rol = 'medico_staff'
        self.medico.save(update_fields=['rol'])
        estudio = Estudios.objects.create(nombre='TOMOGRAFIA DE TORAX', codigo='340101', tipo='TOM', conteo_regiones=1)
        registro = self.registro(estudio)
        self.netterm(codigo='340101', practica='TOMOGRAFIA DE TORAX')
        antes = (list(RegistroEstudiosPorMedico.objects.values()), list(RegistroEstudio.objects.values()))

        resumen = resumir_control_eges_sesion(self.sesion)
        self.assertEqual(resumen['pendientes'], 1)
        linea = self.respaldo()['resultados'][0]['lineas'][0]
        registrar_validacion_respaldo_fuente(
            sesion=self.sesion, linea_id=linea['relacion_id'], batch_eges_ids=[self.batch.pk],
            lote_netterm_ids=[self.lote.pk], firma_esperada=linea['firma_validacion'], usuario=self.usuario,
        )

        resumen = resumir_control_eges_sesion(self.sesion)
        self.assertEqual(resumen['estado'], 'COMPLETADO')
        self.assertEqual(resumen['pendientes'], 0)
        self.assertEqual(resumen['resueltos_respaldo'], 1)
        self.assertFalse(resumen['desactualizado'])
        self.assertEqual(antes, (list(RegistroEstudiosPorMedico.objects.values()), list(RegistroEstudio.objects.values())))
        self.assertFalse(ResultadoControlEgesRegistro.objects.exists())
        RegistroEstudio.objects.filter(registro=registro).update(cantidad=2)
        self.assertEqual(resumir_control_eges_sesion(self.sesion)['pendientes'], 1)

    def test_cierre_tomografia_acepta_eges_confirmado_sin_control_eco(self):
        from .services_eges import resumir_control_eges_sesion

        estudio = Estudios.objects.create(nombre='TOMOGRAFIA DE TORAX', codigo='340101', tipo='TOM', conteo_regiones=1)
        self.registro(estudio)
        self.eges(practica='TOMOGRAFIA DE TORAX', codigo_practica='340101', modalidad='TC')
        preview = self.respaldo()
        linea = preview['resultados'][0]['lineas'][0]
        self.assertEqual(linea['estado'], 'OK_EGES')
        self.client.force_login(self.usuario)
        self.assertEqual(self.validar_lineas_masivo(preview, [linea['relacion_id']]).status_code, 302)
        resumen = resumir_control_eges_sesion(self.sesion)
        self.assertEqual(resumen['pendientes'], 0)
        self.assertEqual(resumen['resueltos_tomografia'], 1)

    def test_cierre_tomografia_parcial_exige_todas_las_lineas(self):
        from .services_eges import resumir_control_eges_sesion

        torax = Estudios.objects.create(nombre='TOMOGRAFIA DE TORAX', codigo='340101', tipo='TOM', conteo_regiones=1)
        abdomen = Estudios.objects.create(nombre='TOMOGRAFIA DE ABDOMEN', codigo='340102', tipo='TOM', conteo_regiones=1)
        registro = self.registro(torax)
        RegistroEstudio.objects.create(registro=registro, estudio=abdomen, cantidad=1)
        self.netterm(codigo='340101', practica=torax.nombre)
        self.netterm(pedido='2', codigo='340102', practica=abdomen.nombre)
        self.client.force_login(self.usuario)
        preview = self.respaldo()
        lineas = preview['resultados'][0]['lineas']
        self.assertEqual(self.validar_lineas_masivo(preview, [lineas[0]['relacion_id']]).status_code, 302)
        self.assertEqual(resumir_control_eges_sesion(self.sesion)['pendientes_tomografia'], 1)
        self.assertEqual(self.validar_lineas_masivo(preview, [lineas[1]['relacion_id']]).status_code, 302)
        self.assertEqual(resumir_control_eges_sesion(self.sesion)['pendientes_tomografia'], 0)

    def test_cierre_tomografia_no_sustituye_control_eco_no_realizado(self):
        from .services_eges import resumir_control_eges_sesion

        self.registro()
        torax = Estudios.objects.create(nombre='TOMOGRAFIA DE TORAX', codigo='340101', tipo='TOM', conteo_regiones=1)
        tomografia = self.registro(torax)
        self.netterm(codigo='340101', practica=torax.nombre)
        preview = self.respaldo()
        linea = next(item['lineas'][0] for item in preview['resultados'] if item['registro'].pk == tomografia.pk)
        self.client.force_login(self.usuario)
        self.assertEqual(self.validar_lineas_masivo(preview, [linea['relacion_id']]).status_code, 302)
        resumen = resumir_control_eges_sesion(self.sesion)
        self.assertEqual(resumen['estado'], 'NO_REALIZADO')
        self.assertEqual(resumen['resueltos_tomografia'], 1)

    def test_cierre_mixto_conserva_pendientes_eco_y_correccion_tc(self):
        from .models import ControlEgesSesion
        from .services_eges import resumir_control_eges_sesion

        eco = self.registro()
        torax = Estudios.objects.create(nombre='TOMOGRAFIA DE TORAX', codigo='340101', tipo='TOM', conteo_regiones=1)
        tomografia = self.registro(torax)
        self.netterm(codigo='340101', practica=torax.nombre)
        control = ControlEgesSesion.objects.create(
            sesion_contable=self.sesion, batch_eges=self.batch, version=1, procesado_por=self.usuario,
        )
        ResultadoControlEgesRegistro.objects.create(
            control=control, registro=eco, estado='MANUAL',
            motivos_json=['Hay prácticas con cantidad distinta entre liquidación y EGES.'],
        )
        self.client.force_login(self.usuario)
        preview = self.respaldo()
        linea = next(item['lineas'][0] for item in preview['resultados'] if item['registro'].pk == tomografia.pk)
        self.assertEqual(self.validar_lineas_masivo(preview, [linea['relacion_id']]).status_code, 302)
        resumen = resumir_control_eges_sesion(self.sesion)
        self.assertEqual(resumen['total'], 2)
        self.assertEqual(resumen['pendientes'], 1)
        self.assertEqual(resumen['resueltos_tomografia'], 1)
        self.assertFalse(resumen['desactualizado'])
        RevisionCruceEgesRegistro.objects.create(
            sesion_contable=self.sesion, registro=tomografia, batch_eges=self.batch,
            estado='REQUIERE_CORRECCION', observacion='Correccion pendiente de QA.', revisado_por=self.usuario,
        )
        resumen = resumir_control_eges_sesion(self.sesion)
        self.assertEqual(resumen['pendientes'], 2)
        self.assertEqual(resumen['requieren_correccion'], 1)

    def test_cierre_no_cuenta_tomografia_anulada(self):
        from .services_eges import resumir_control_eges_sesion

        torax = Estudios.objects.create(nombre='TOMOGRAFIA DE TORAX', codigo='340101', tipo='TOM', conteo_regiones=1)
        tomografia = self.registro(torax)
        self.assertEqual(resumir_control_eges_sesion(self.sesion)['pendientes_tomografia'], 1)
        RegistroEstudiosPorMedico.objects.filter(pk=tomografia.pk).update(anulado=True)
        resumen = resumir_control_eges_sesion(self.sesion)
        self.assertEqual(resumen['total_tomografia'], 0)
        self.assertEqual(resumen['pendientes'], 0)

    def test_cierre_registro_mixto_cuenta_una_vez_y_exige_todas_las_lineas(self):
        from .models import ControlEgesSesion
        from .services_cierre import construir_checklist_cierre_sesion
        from .services_eges import resumir_control_eges_sesion

        registro = self.registro()
        torax = Estudios.objects.create(nombre='TOMOGRAFIA DE TORAX', codigo='340101', tipo='TOM', conteo_regiones=1)
        RegistroEstudio.objects.create(registro=registro, estudio=torax, cantidad=1)
        self.netterm()
        self.netterm(pedido='2', codigo='340101', practica=torax.nombre)
        control = ControlEgesSesion.objects.create(
            sesion_contable=self.sesion, batch_eges=self.batch, version=1, procesado_por=self.usuario,
        )
        ResultadoControlEgesRegistro.objects.create(
            control=control, registro=registro, estado='MANUAL',
            motivos_json=['No se encontró práctica EGES ECO para el DNI y fecha del registro.'],
        )
        resumen = resumir_control_eges_sesion(self.sesion)
        self.assertEqual(resumen['total'], 1)
        self.assertEqual(resumen['pendientes'], 1)
        self.client.force_login(self.usuario)
        preview = self.respaldo()
        self.assertEqual(self.validar_lineas_masivo(
            preview, [linea['relacion_id'] for linea in preview['resultados'][0]['lineas']],
        ).status_code, 302)
        resumen = resumir_control_eges_sesion(self.sesion)
        self.assertEqual(resumen['total'], 1)
        self.assertEqual(resumen['resueltos'], 1)
        self.assertEqual(resumen['pendientes'], 0)
        checklist = construir_checklist_cierre_sesion(self.sesion)
        control_item = next(item for item in checklist['items'] if item['key'] == 'control_eges')
        self.assertEqual(control_item['estado'], 'ok')

    def test_informante_netterm_distinto_sin_eges_queda_para_revisar(self):
        self.registro()
        self.netterm(informante='OTRO PROFESIONAL')
        self.assertEqual(self.respaldo()['resultados'][0]['estado_respaldo'], 'REVISAR')

    def test_dos_pedidos_no_se_resuelven_por_primera_fila(self):
        self.registro()
        self.netterm()
        self.netterm(pedido='2')
        self.assertEqual(self.respaldo()['resultados'][0]['estado_respaldo'], 'REVISAR')

    def test_filtrar_profesional_no_permite_reusar_una_evidencia(self):
        self.registro()
        otro = get_user_model().objects.create_user(username='otro', first_name='Otro', last_name='Profesional')
        self.registro(medico=otro)
        self.netterm()
        resultado = self.respaldo(profesional=self.medico.pk)
        self.assertEqual(resultado['total'], 1)
        self.assertEqual(resultado['resultados'][0]['estado_respaldo'], 'REVISAR')
        self.assertTrue(any('más de una línea' in m for m in resultado['resultados'][0]['lineas'][0]['motivos']))

    def test_eges_cancelado_no_se_elude_con_netterm(self):
        self.registro()
        self.eges(estado_turno='Cancelado')
        self.netterm()
        self.assertEqual(self.respaldo()['resultados'][0]['estado_respaldo'], 'REVISAR')

    def test_netterm_puede_confirmar_realizacion_de_eges_recepcionado(self):
        self.registro()
        self.eges(estado_turno='Recepcionado')
        self.netterm()
        self.assertEqual(self.respaldo()['resultados'][0]['lineas'][0]['estado'], 'OK_NETTERM')

    def test_codigo_diferente_no_se_tapa_con_nombre_igual(self):
        self.registro()
        self.netterm(codigo='999')
        self.assertEqual(self.respaldo()['resultados'][0]['estado_respaldo'], 'SIN_RESPALDO')

    def test_nombre_exacto_o_alias_explicitado_sirve_si_no_hay_codigo_numerico(self):
        self.estudio.codigo = None
        self.estudio.nombre = 'ECO ABDOMINAL'
        self.estudio.save()
        self.registro()
        self.netterm()
        linea = self.respaldo()['resultados'][0]['lineas'][0]
        self.assertEqual(linea['estado'], 'OK_NETTERM')
        self.assertEqual(linea['evidencia'][0]['metodo'], 'NOMBRE_EQUIVALENTE')

    def test_pendiente_realizacion_no_da_ok(self):
        self.registro()
        self.netterm(estado='PENDIENTE', realizada=False)
        self.assertEqual(self.respaldo()['resultados'][0]['estado_respaldo'], 'REVISAR')

    def test_varias_practicas_combinan_fuentes_y_muestran_respaldo_parcial(self):
        registro = self.registro()
        renal = Estudios.objects.create(nombre='ECOGRAFIA RENAL', codigo='180113', tipo='ECO', conteo_regiones=1)
        RegistroEstudio.objects.create(registro=registro, estudio=renal, cantidad=1)
        self.eges()
        self.assertEqual(self.respaldo()['resultados'][0]['estado_respaldo'], 'PARCIAL')
        self.netterm(codigo='180113', practica='ECOGRAFIA RENAL')
        resultado = self.respaldo()['resultados'][0]
        self.assertEqual(resultado['estado_respaldo'], 'OK_RESPALDO')
        self.assertCountEqual([l['estado'] for l in resultado['lineas']], ['OK_EGES', 'OK_NETTERM'])

    def test_persistir_ok_eges_netterm_no_modifica_datos_ni_control_economico(self):
        registro = self.registro(cantidad=2)
        self.eges(estado_turno='Fin Practica')
        self.netterm()
        RegistroEstudiosPorMedico.objects.filter(pk=registro.pk).update(monto_calculado=Decimal('1234.56'))
        self.client.force_login(self.usuario)
        url = reverse('liquidacion:respaldo_fuentes_preview', kwargs={'pk': self.sesion.pk})
        response = self.client.get(url, self.parametros_preview())
        linea = response.context['pagina'][0]['lineas'][0]
        monto_antes = RegistroEstudiosPorMedico.objects.get(pk=registro.pk).monto_calculado
        cantidad_antes = RegistroEstudio.objects.get(registro=registro).cantidad

        guardado = self.validar_linea(linea)

        self.assertEqual(guardado.status_code, 302)
        validacion = ValidacionRespaldoFuenteRegistro.objects.get(linea_estudio_id=linea['relacion_id'])
        self.assertEqual(validacion.estado, 'OK_RESPALDO')
        self.assertEqual(validacion.evidencia_json, linea['evidencia'])
        self.assertEqual(validacion.validado_por, self.usuario)
        self.assertNotIn('12345678', str(validacion.snapshot_json))
        self.assertEqual(RegistroEstudiosPorMedico.objects.get(pk=registro.pk).monto_calculado, monto_antes)
        self.assertEqual(RegistroEstudio.objects.get(registro=registro).cantidad, cantidad_antes)
        self.assertFalse(ResultadoControlEgesRegistro.objects.exists())
        self.assertFalse(RevisionCruceEgesRegistro.objects.exists())

        actualizado = self.client.get(url, self.parametros_preview())
        linea_actualizada = actualizado.context['pagina'][0]['lineas'][0]
        self.assertEqual(linea_actualizada['validacion_persistida'].pk, validacion.pk)
        self.assertContains(actualizado, 'OK definitivo de respaldo')
        self.assertNotContains(actualizado, 'Confirmar OK definitivo')
        self.assertRaises(ValidationError, validacion.delete)
        self.assertRaises(
            ValidationError,
            lambda: ValidacionRespaldoFuenteRegistro.objects.filter(pk=validacion.pk).update(estado='ANULADO'),
        )

    def test_persistir_ok_netterm_solo_si_coincide_con_linea_y_profesional(self):
        registro = self.registro(cantidad=1)
        self.netterm()
        RegistroEstudiosPorMedico.objects.filter(pk=registro.pk).update(monto_calculado=Decimal('1234.56'))
        self.client.force_login(self.usuario)
        url = reverse('liquidacion:respaldo_fuentes_preview', kwargs={'pk': self.sesion.pk})
        response = self.client.get(url, self.parametros_preview())
        linea = response.context['pagina'][0]['lineas'][0]
        self.assertEqual(linea['estado'], 'OK_NETTERM')

        guardado = self.validar_linea(linea)

        self.assertEqual(guardado.status_code, 302)
        validacion = ValidacionRespaldoFuenteRegistro.objects.get(linea_estudio_id=linea['relacion_id'])
        self.assertEqual([e['origen'] for e in validacion.evidencia_json], ['NETTERM'])
        self.assertEqual(RegistroEstudiosPorMedico.objects.get(pk=registro.pk).monto_calculado, Decimal('1234.56'))
        self.assertFalse(ResultadoControlEgesRegistro.objects.exists())
        self.assertFalse(RevisionCruceEgesRegistro.objects.exists())

    def test_post_respaldo_rechaza_linea_ambigua_y_usuario_sin_permiso(self):
        registro = self.registro()
        otro_medico = get_user_model().objects.create_user(
            username='otro_respaldo', first_name='Otro', last_name='Profesional',
        )
        self.registro(medico=otro_medico)
        self.netterm()
        self.client.force_login(self.usuario)
        url = reverse('liquidacion:respaldo_fuentes_preview', kwargs={'pk': self.sesion.pk})
        response = self.client.get(url, self.parametros_preview())
        linea = response.context['pagina'][0]['lineas'][0]
        self.assertEqual(linea['estado'], 'REVISAR')
        self.assertEqual(self.validar_linea(linea).status_code, 302)
        self.assertFalse(ValidacionRespaldoFuenteRegistro.objects.exists())
        self.client.force_login(self.medico)
        self.assertEqual(self.validar_linea(linea).status_code, 302)
        self.assertFalse(ValidacionRespaldoFuenteRegistro.objects.exists())

    def test_post_respaldo_rechaza_snapshot_obsoleto(self):
        registro = self.registro(cantidad=1)
        self.eges()
        self.netterm()
        self.client.force_login(self.usuario)
        response = self.client.get(
            reverse('liquidacion:respaldo_fuentes_preview', kwargs={'pk': self.sesion.pk}),
            self.parametros_preview(),
        )
        linea = response.context['pagina'][0]['lineas'][0]
        RegistroEstudio.objects.filter(registro=registro).update(cantidad=2)

        self.assertEqual(self.validar_linea(linea).status_code, 302)
        self.assertFalse(ValidacionRespaldoFuenteRegistro.objects.exists())

    def test_confirmar_multiples_ok_visibles_es_idempotente_y_no_economico(self):
        registro = self.registro(cantidad=2)
        renal = Estudios.objects.create(nombre='ECOGRAFIA RENAL', codigo='180113', tipo='ECO', conteo_regiones=1)
        renal_linea = RegistroEstudio.objects.create(registro=registro, estudio=renal, cantidad=1)
        self.eges()
        self.eges(codigo_practica='180113', practica='ECOGRAFIA RENAL', hora_turno=time(11))
        self.netterm()
        self.netterm(pedido='2', codigo='180113', practica='ECOGRAFIA RENAL')
        RegistroEstudiosPorMedico.objects.filter(pk=registro.pk).update(monto_calculado=Decimal('1234.56'))
        self.client.force_login(self.usuario)
        preview = self.respaldo()
        lineas = preview['resultados'][0]['lineas']
        self.assertCountEqual([linea['estado'] for linea in lineas], ['OK_EGES', 'OK_EGES'])
        ids = [linea['relacion_id'] for linea in lineas]
        monto_antes = RegistroEstudiosPorMedico.objects.get(pk=registro.pk).monto_calculado
        cantidades_antes = list(RegistroEstudio.objects.filter(registro=registro).order_by('pk').values_list('cantidad', flat=True))

        primera = self.validar_lineas_masivo(preview, ids)
        segunda = self.validar_lineas_masivo(preview, ids)

        self.assertEqual(primera.status_code, 302)
        self.assertEqual(segunda.status_code, 302)
        self.assertEqual(ValidacionRespaldoFuenteRegistro.objects.count(), 2)
        self.assertEqual(RegistroEstudiosPorMedico.objects.get(pk=registro.pk).monto_calculado, monto_antes)
        self.assertEqual(list(RegistroEstudio.objects.filter(registro=registro).order_by('pk').values_list('cantidad', flat=True)), cantidades_antes)
        self.assertEqual(renal_linea.cantidad, 1)
        self.assertFalse(ResultadoControlEgesRegistro.objects.exists())
        self.assertFalse(RevisionCruceEgesRegistro.objects.exists())

    def test_confirmacion_masiva_rechaza_seleccion_invalida_sin_escrituras_parciales(self):
        registro = self.registro()
        self.eges()
        self.netterm()
        RegistroEstudiosPorMedico.objects.filter(pk=registro.pk).update(monto_calculado=Decimal('1234.56'))
        self.client.force_login(self.usuario)
        preview = self.respaldo()
        linea_id = preview['resultados'][0]['lineas'][0]['relacion_id']

        response = self.validar_lineas_masivo(preview, [linea_id, 999999])

        self.assertEqual(response.status_code, 302)
        self.assertFalse(ValidacionRespaldoFuenteRegistro.objects.exists())
        registro.refresh_from_db()
        self.assertEqual(registro.monto_calculado, Decimal('1234.56'))

    @override_settings(SECURE_SSL_REDIRECT=False, SESSION_ENGINE='django.contrib.sessions.backends.signed_cookies')
    def test_vista_restringida_renderiza_respaldo_y_no_admite_escrituras(self):
        registro = self.registro()
        self.netterm()
        url = reverse('liquidacion:respaldo_fuentes_preview', kwargs={'pk': self.sesion.pk})
        self.client.force_login(self.medico)
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.usuario)
        with CaptureQueriesContext(connection) as consultas:
            response = self.client.get(url, {'lotes_eges': [self.batch.pk], 'lotes_netterm': [self.lote.pk]})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'OK de respaldo Netterm')
        self.assertContains(response, 'no modifica montos')
        self.assertEqual(response.context['pagina'][0]['registro'].pk, registro.pk)
        self.assertFalse(any(q['sql'].lstrip().upper().startswith(('INSERT ', 'UPDATE ', 'DELETE ')) for q in consultas))
        self.assertEqual(self.client.post(url).status_code, 405)
