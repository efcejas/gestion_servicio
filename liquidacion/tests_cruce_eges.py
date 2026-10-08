from datetime import date, time
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from eges_import.models import EgesRow, ImportBatch
from control_guardias.models import Feriado

from .models import (
    ControlEgesSesion,
    CorreccionPacsRegistro,
    HistorialRecalculoTarifaRegistro,
    Estudios,
    RegistroEstudio,
    RegistroEstudiosPorMedico,
    ResultadoControlEgesRegistro,
    RevisionCruceEgesRegistro,
    RevisionAuditoriaEcoRegistro,
    SesionContable,
)
from .services_auditoria import resumir_pendientes_auditoria_eco
from .services_eges import (
    construir_preview_cruce_liquidacion_eges,
    procesar_control_eges_sesion,
    resumir_control_eges_sesion,
)


User = get_user_model()


class CruceEgesLiquidacionPreviewTest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username='admin_eges',
            password='x',
            rol='administrativo',
            perfil_completo=True,
        )
        self.jefe = User.objects.create_user(
            username='jefe_eges',
            password='x',
            rol='jefe_servicio',
            perfil_completo=True,
        )
        self.residente = User.objects.create_user(
            username='res_eges',
            password='x',
            rol='medico_residente',
            first_name='Carlos',
            last_name='Puente',
            perfil_completo=True,
        )
        self.sesion = SesionContable.objects.create(mes=5, año=2026, estado='REVISION')
        self.batch = ImportBatch.objects.create(usuario=self.admin, archivo_nombre='Turnos-Mayo-ECO.xls')
        self.estudio = Estudios.objects.create(
            nombre='ECOGRAFIA COMPLETA DE ABDOMEN',
            tipo='ECO',
            conteo_regiones=1,
            conteo_regiones_default=1,
            precio_cober=Decimal('1000.00'),
            precio_otras_os=Decimal('1000.00'),
            activo=True,
        )
        self.estudio_tv = Estudios.objects.create(
            nombre='ECOGRAFIA TRANSVAGINAL SIN BIOPSIA',
            tipo='ECO',
            conteo_regiones=1,
            conteo_regiones_default=1,
            precio_cober=Decimal('1000.00'),
            precio_otras_os=Decimal('1000.00'),
            activo=True,
        )
        self.estudio_abdominal_corto = Estudios.objects.create(
            nombre='ECO ABDOMINAL',
            tipo='ECO',
            conteo_regiones=1,
            conteo_regiones_default=1,
            precio_cober=Decimal('1000.00'),
            precio_otras_os=Decimal('1000.00'),
            activo=True,
        )
        self.estudio_dop = Estudios.objects.create(
            nombre='ECODOPPLER VENOSO MM INFERIORES',
            tipo='DOP',
            conteo_regiones=1,
            conteo_regiones_default=1,
            precio_cober=Decimal('200.00'),
            precio_otras_os=Decimal('200.00'),
            activo=True,
        )

    def _registro(self, horario='INTRA', fecha=date(2026, 5, 12), dni='12345678', estudios=None):
        registro = RegistroEstudiosPorMedico.objects.create(
            sesion_contable=self.sesion,
            medico=self.residente,
            nombre_paciente='Juan',
            apellido_paciente='Perez',
            dni_paciente=dni,
            fecha_del_informe=fecha,
            tipo_obra_social='COBER',
            horario=horario,
            cantidad_regiones=1,
            monto_calculado=Decimal('1000.00'),
        )
        for estudio in estudios or [self.estudio]:
            RegistroEstudio.objects.create(registro=registro, estudio=estudio, cantidad=1)
        return registro

    def _eges_row(
        self,
        hora_turno,
        hora_hasta,
        tipo_atencion='Guardia',
        dni='12345678',
        fecha=date(2026, 5, 12),
        practica='ECOGRAFIA COMPLETA DE ABDOMEN',
        codigo_practica='180112/0',
        modalidad='ECO',
        servicio='Ecografia',
        medico_informante='Médico No Especificado',
        medico_actuante='PUENTE CARLOS',
    ):
        return EgesRow.objects.create(
            batch=self.batch,
            dni_paciente=dni,
            historia_clinica=dni,
            apellido_nombre='PEREZ JUAN',
            fecha_turno=fecha,
            hora_turno=hora_turno,
            hora_hasta=hora_hasta,
            tipo_atencion=tipo_atencion,
            medico_informante=medico_informante,
            medico_actuante=medico_actuante,
            practica=practica,
            codigo_practica=codigo_practica,
            cantidad=Decimal('1.00'),
            servicio=servicio,
            estado_turno='Informado',
            modalidad=modalidad,
            sub_modalidad='ECO_ABDOMINAL',
            es_insumo=False,
        )

    def _previsualizar_correccion_doppler(self, registros, observacion='Doppler verificado contra EGES.'):
        return self.client.post(
            reverse('liquidacion:cruce_eges_corregir_doppler', kwargs={'pk': self.sesion.pk}),
            {
                'accion': 'previsualizar', 'batch': self.batch.pk,
                'registros_doppler': [registro.pk for registro in registros],
                'observacion': observacion,
                'next': reverse('liquidacion:cruce_eges_liquidacion_preview', kwargs={'pk': self.sesion.pk})
                + f'?batch={self.batch.pk}',
            },
        )

    def _aplicar_correccion_doppler_previsualizada(self, response, observacion='Doppler verificado contra EGES.', **cambios):
        datos = {
            'accion': 'aplicar', 'confirmar': '1', 'batch': self.batch.pk,
            'preview_token': response.context['token'], 'observacion': observacion,
            'next': response.context['next'],
        }
        datos.update(cambios)
        return self.client.post(
            reverse('liquidacion:cruce_eges_corregir_doppler', kwargs={'pk': self.sesion.pk}),
            datos,
        )

    def test_guardia_entre_8_y_17_valida_intra(self):
        self._registro(horario='INTRA')
        self._eges_row(time(9, 0), time(9, 15), tipo_atencion='Guardia')

        preview = construir_preview_cruce_liquidacion_eges(self.sesion, self.batch)

        self.assertEqual(preview['resumen']['ok'], 1)
        resultado = preview['resultados'][0]
        self.assertEqual(resultado['estado'], 'ok')
        self.assertEqual(resultado['mejor_match']['horario_esperado'], 'INTRA')
        self.assertEqual(resultado['mejor_match']['rol_medico_eges'], 'actuante')

    def test_cruce_explica_cuando_pagina_actual_no_tiene_casillas_doppler(self):
        self._registro(horario='INTRA')
        self.client.force_login(self.jefe)
        response = self.client.get(
            reverse('liquidacion:cruce_eges_liquidacion_preview', kwargs={'pk': self.sesion.pk}),
            {'batch': self.batch.pk},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['preview']['doppler_correccion_elegibles_pagina'], 0)
        self.assertContains(response, 'No hay Doppler elegibles en esta página.')
        self.assertNotContains(response, 'name="registros_doppler"')

    def test_medico_coincide_con_nombre_en_distinto_orden_y_apellido_extra(self):
        self.residente.first_name = 'Juan David'
        self.residente.last_name = 'Cervantes'
        self.residente.save(update_fields=['first_name', 'last_name'])
        self._registro(horario='INTRA')
        self._eges_row(
            time(9, 0),
            time(9, 15),
            tipo_atencion='Guardia',
            medico_informante='CERVANTES ALVAREZ JUAN DAVID',
            medico_actuante='CERVANTES ALVAREZ JUAN DAVID',
        )

        preview = construir_preview_cruce_liquidacion_eges(self.sesion, self.batch)

        self.assertEqual(preview['resumen']['ok'], 1)
        resultado = preview['resultados'][0]
        self.assertEqual(resultado['estado'], 'ok')
        self.assertEqual(resultado['mejor_match']['rol_medico_eges'], 'informante')
        self.assertNotIn(
            'El profesional no coincide claramente como informante ni actuante.',
            resultado['motivos'],
        )

    def test_guardia_fuera_de_17_alerta_si_liquidacion_esta_intra(self):
        self._registro(horario='INTRA')
        self._eges_row(time(18, 0), time(18, 15), tipo_atencion='Guardia')

        preview = construir_preview_cruce_liquidacion_eges(self.sesion, self.batch)

        self.assertEqual(preview['resumen']['advertencia'], 1)
        resultado = preview['resultados'][0]
        self.assertEqual(resultado['mejor_match']['horario_esperado'], 'EXTRA')
        self.assertIn('EGES sugiere EXTRA; liquidación figura INTRA.', resultado['motivos'])

    def test_sabado_de_manana_alerta_si_liquidacion_esta_intra(self):
        fecha_sabado = date(2026, 5, 9)
        self._registro(horario='INTRA', fecha=fecha_sabado)
        self._eges_row(time(10, 0), time(10, 15), tipo_atencion='Guardia', fecha=fecha_sabado)

        preview = construir_preview_cruce_liquidacion_eges(self.sesion, self.batch)

        self.assertEqual(preview['resumen']['advertencia'], 1)
        resultado = preview['resultados'][0]
        self.assertEqual(resultado['mejor_match']['horario_esperado'], 'EXTRA')
        self.assertIn('EGES sugiere EXTRA; liquidación figura INTRA.', resultado['motivos'])

    def test_feriado_de_manana_alerta_si_liquidacion_esta_intra(self):
        fecha_feriado = date(2026, 5, 11)
        Feriado.objects.create(fecha=fecha_feriado, descripcion='Feriado test')
        self._registro(horario='INTRA', fecha=fecha_feriado)
        self._eges_row(time(10, 0), time(10, 15), tipo_atencion='Guardia', fecha=fecha_feriado)

        preview = construir_preview_cruce_liquidacion_eges(self.sesion, self.batch)

        self.assertEqual(preview['resumen']['advertencia'], 1)
        resultado = preview['resultados'][0]
        self.assertEqual(resultado['mejor_match']['horario_esperado'], 'EXTRA')
        self.assertIn('EGES sugiere EXTRA; liquidación figura INTRA.', resultado['motivos'])

    def test_preview_precarga_feriados_y_estudios_sin_consultas_por_registro(self):
        fecha_feriado = date(2026, 5, 11)
        Feriado.objects.create(fecha=fecha_feriado, descripcion='Feriado test')
        for indice in range(3):
            dni = f'1234567{indice}'
            self._registro(horario='EXTRA', fecha=fecha_feriado, dni=dni)
            self._eges_row(
                time(10, 0),
                time(10, 15),
                fecha=fecha_feriado,
                dni=dni,
            )

        with CaptureQueriesContext(connection) as consultas:
            preview = construir_preview_cruce_liquidacion_eges(self.sesion, self.batch)

        sql = [consulta['sql'].lower() for consulta in consultas.captured_queries]
        consultas_feriados = [
            consulta for consulta in sql
            if 'from "control_guardias_feriado"' in consulta
        ]
        tabla_relaciones = RegistroEstudio._meta.db_table.lower()
        consultas_relaciones = [
            consulta for consulta in sql
            if f'from "{tabla_relaciones}"' in consulta
        ]
        self.assertEqual(preview['resumen']['total'], 3)
        self.assertEqual(len(consultas_feriados), 1)
        self.assertEqual(len(consultas_relaciones), 1)

    def test_detecta_practica_eges_mismo_turno_no_cargada_en_liquidacion(self):
        self._registro(horario='INTRA', estudios=[self.estudio])
        self._eges_row(time(9, 0), time(9, 15), practica='ECOGRAFIA COMPLETA DE ABDOMEN')
        self._eges_row(
            time(9, 0),
            time(9, 15),
            practica='ECOGRAFIA TRANSVAGINAL SIN BIOPSIA',
            codigo_practica='180118/0',
        )

        preview = construir_preview_cruce_liquidacion_eges(self.sesion, self.batch)

        self.assertEqual(preview['resumen']['advertencia'], 1)
        resultado = preview['resultados'][0]
        self.assertEqual(len(resultado['matches_practicas']), 1)
        self.assertEqual(len(resultado['eges_sin_liquidacion']), 1)
        self.assertEqual(resultado['eges_sin_liquidacion'][0].practica, 'ECOGRAFIA TRANSVAGINAL SIN BIOPSIA')
        self.assertIn(
            'Hay prácticas EGES ECO del mismo paciente/fecha/profesional no cargadas en liquidación.',
            resultado['motivos'],
        )

    def test_multiples_practicas_del_mismo_turno_eges_no_generan_advertencia(self):
        self._registro(horario='INTRA', estudios=[self.estudio, self.estudio_tv])
        self._eges_row(time(9, 0), time(9, 15), practica='ECOGRAFIA COMPLETA DE ABDOMEN')
        self._eges_row(
            time(9, 0),
            time(9, 15),
            practica='ECOGRAFIA TRANSVAGINAL SIN BIOPSIA',
            codigo_practica='180118/0',
        )

        preview = construir_preview_cruce_liquidacion_eges(self.sesion, self.batch)

        self.assertEqual(preview['resumen']['ok'], 1)
        resultado = preview['resultados'][0]
        self.assertEqual(resultado['estado'], 'ok')
        self.assertEqual(len(resultado['matches_practicas']), 2)
        self.assertEqual(resultado['candidatos_count'], 2)
        self.assertNotIn('Hay mÃºltiples coincidencias EGES posibles.', resultado['motivos'])

    def test_eco_abdominal_equivale_a_ecografia_completa_de_abdomen(self):
        self._registro(horario='INTRA', estudios=[self.estudio_abdominal_corto])
        self._eges_row(time(9, 0), time(9, 15), practica='ECOGRAFIA COMPLETA DE ABDOMEN')

        preview = construir_preview_cruce_liquidacion_eges(self.sesion, self.batch)

        self.assertEqual(preview['resumen']['ok'], 1)
        resultado = preview['resultados'][0]
        self.assertEqual(resultado['estado'], 'ok')
        self.assertEqual(len(resultado['matches_practicas']), 1)
        self.assertFalse(resultado['liquidacion_sin_match'])
        self.assertFalse(resultado['eges_sin_liquidacion'])

    def test_practica_del_mismo_turno_con_otro_profesional_genera_advertencia(self):
        self._registro(horario='INTRA', estudios=[self.estudio, self.estudio_tv])
        self._eges_row(
            time(9, 0),
            time(9, 15),
            practica='ECOGRAFIA COMPLETA DE ABDOMEN',
            medico_informante='GAVILANES IBARRA ANGEL CAMILO',
            medico_actuante='GAVILANES IBARRA ANGEL CAMILO',
        )
        self._eges_row(
            time(9, 0),
            time(9, 15),
            practica='ECOGRAFIA TRANSVAGINAL SIN BIOPSIA',
            codigo_practica='180118/0',
        )

        preview = construir_preview_cruce_liquidacion_eges(self.sesion, self.batch)

        self.assertEqual(preview['resumen']['advertencia'], 1)
        resultado = preview['resultados'][0]
        self.assertEqual(resultado['estado'], 'advertencia')
        self.assertEqual(len(resultado['matches_practicas']), 2)
        self.assertTrue(any(not match['medico_ok'] for match in resultado['matches_practicas']))
        self.assertIn(
            'Hay prácticas EGES del mismo paciente/fecha realizadas por otro profesional.',
            resultado['motivos'],
        )

    def test_detecta_practica_liquidada_sin_match_eges(self):
        self._registro(horario='INTRA', estudios=[self.estudio, self.estudio_tv])
        self._eges_row(time(9, 0), time(9, 15), practica='ECOGRAFIA COMPLETA DE ABDOMEN')

        preview = construir_preview_cruce_liquidacion_eges(self.sesion, self.batch)

        self.assertEqual(preview['resumen']['advertencia'], 1)
        resultado = preview['resultados'][0]
        self.assertEqual(len(resultado['matches_practicas']), 1)
        self.assertEqual(len(resultado['liquidacion_sin_match']), 1)
        self.assertEqual(resultado['liquidacion_sin_match'][0]['nombre'], 'ECOGRAFIA TRANSVAGINAL SIN BIOPSIA')
        self.assertIn(
            'Hay prácticas cargadas en liquidación sin coincidencia EGES ECO.',
            resultado['motivos'],
        )

    def test_no_contrasta_filas_eges_de_otra_modalidad(self):
        self._registro(horario='INTRA', estudios=[self.estudio])
        self._eges_row(
            time(9, 0),
            time(9, 15),
            practica='RADIOGRAFIA DE TORAX',
            codigo_practica='RX/1',
            modalidad='RX',
            servicio='Radiologia',
        )

        preview = construir_preview_cruce_liquidacion_eges(self.sesion, self.batch)

        self.assertEqual(preview['resumen']['manual'], 1)
        resultado = preview['resultados'][0]
        self.assertIn('No se encontró práctica EGES ECO para el DNI y fecha del registro.', resultado['motivos'])

    def test_vista_renderiza_preview_con_batch(self):
        self._registro(horario='INTRA')
        self._eges_row(time(9, 0), time(9, 15), tipo_atencion='Guardia')
        self.client.force_login(self.admin)

        response = self.client.get(
            reverse('liquidacion:cruce_eges_liquidacion_preview', kwargs={'pk': self.sesion.pk}),
            {'batch': self.batch.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Cruce EGES vs Liquidación')
        self.assertContains(response, 'EGES: Guardia · actuante')
        self.assertContains(response, 'Esperado: INTRA')
        self.assertContains(response, 'Ver 1 práctica EGES encontrada')
        self.assertContains(response, 'Informante:')
        self.assertContains(response, 'Actuante:')

    def test_resolver_cruce_eges_crea_revision_sin_modificar_registro(self):
        registro = self._registro(horario='INTRA', estudios=[self.estudio, self.estudio_tv])
        registro.refresh_from_db()
        monto_original = registro.monto_calculado
        self._eges_row(time(9, 0), time(9, 15), practica='ECOGRAFIA COMPLETA DE ABDOMEN')
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse('liquidacion:cruce_eges_registro_resolver', kwargs={
                'pk': self.sesion.pk,
                'registro_pk': registro.pk,
            }),
            {
                'batch': self.batch.pk,
                'estado': RevisionCruceEgesRegistro.ESTADO_VALIDADO,
                'observacion': 'Validado manualmente contra EGES.',
            },
        )

        self.assertEqual(response.status_code, 302)
        revision = RevisionCruceEgesRegistro.objects.get(registro=registro, batch_eges=self.batch)
        self.assertEqual(revision.estado, RevisionCruceEgesRegistro.ESTADO_VALIDADO)
        self.assertIn('Hay prácticas cargadas', revision.motivos_json[0])
        registro.refresh_from_db()
        self.assertEqual(registro.monto_calculado, monto_original)

    def test_preview_descuenta_pendiente_si_advertencia_fue_validada(self):
        registro = self._registro(horario='INTRA', estudios=[self.estudio, self.estudio_tv])
        self._eges_row(time(9, 0), time(9, 15), practica='ECOGRAFIA COMPLETA DE ABDOMEN')

        preview_sin_revision = construir_preview_cruce_liquidacion_eges(self.sesion, self.batch)
        self.assertEqual(preview_sin_revision['resumen']['pendientes_revision'], 1)

        RevisionCruceEgesRegistro.objects.create(
            sesion_contable=self.sesion,
            registro=registro,
            batch_eges=self.batch,
            estado=RevisionCruceEgesRegistro.ESTADO_VALIDADO,
            motivos_json=['Validado manual.'],
            snapshot_json={},
            observacion='Validado manualmente.',
            revisado_por=self.admin,
        )

        preview = construir_preview_cruce_liquidacion_eges(self.sesion, self.batch)
        self.assertEqual(preview['resumen']['pendientes_revision'], 0)
        self.assertEqual(preview['resumen']['resueltos'], 1)

    def test_validar_ok_visibles_crea_revision_eges(self):
        registro = self._registro(horario='INTRA')
        registro.refresh_from_db()
        monto_original = registro.monto_calculado
        self._eges_row(time(9, 0), time(9, 15), tipo_atencion='Guardia')
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse('liquidacion:cruce_eges_validar_ok', kwargs={'pk': self.sesion.pk}),
            {
                'batch': self.batch.pk,
                'estado_cruce': 'ok',
                'estado_revision': 'SIN_REVISAR',
            },
        )

        self.assertEqual(response.status_code, 302)
        revision = RevisionCruceEgesRegistro.objects.get(registro=registro, batch_eges=self.batch)
        self.assertEqual(revision.estado, RevisionCruceEgesRegistro.ESTADO_VALIDADO)
        registro.refresh_from_db()
        self.assertEqual(registro.monto_calculado, monto_original)

    def test_validar_seleccion_masiva_valida_advertencia_y_manual_sin_cambiar_montos(self):
        advertencia = self._registro(
            horario='INTRA',
            dni='11111111',
            estudios=[self.estudio, self.estudio_tv],
        )
        manual = self._registro(horario='INTRA', dni='22222222')
        self._eges_row(
            time(9, 0),
            time(9, 15),
            dni='11111111',
            practica='ECOGRAFIA COMPLETA DE ABDOMEN',
        )
        advertencia.refresh_from_db()
        manual.refresh_from_db()
        montos_originales = {
            advertencia.pk: advertencia.monto_calculado,
            manual.pk: manual.monto_calculado,
        }
        horarios_originales = {
            advertencia.pk: advertencia.horario,
            manual.pk: manual.horario,
        }
        self.client.force_login(self.jefe)

        response = self.client.post(
            reverse('liquidacion:cruce_eges_validar_seleccion', kwargs={'pk': self.sesion.pk}),
            {
                'batch': self.batch.pk,
                'registros': [advertencia.pk, manual.pk],
                'observacion': 'Coincidencias verificadas sin correccion economica.',
            },
        )

        self.assertEqual(response.status_code, 302)
        revisiones = RevisionCruceEgesRegistro.objects.filter(
            batch_eges=self.batch,
            registro_id__in=[advertencia.pk, manual.pk],
        )
        self.assertEqual(revisiones.count(), 2)
        self.assertFalse(revisiones.exclude(estado=RevisionCruceEgesRegistro.ESTADO_VALIDADO).exists())
        for registro in (advertencia, manual):
            registro.refresh_from_db()
            self.assertEqual(registro.monto_calculado, montos_originales[registro.pk])
            self.assertEqual(registro.horario, horarios_originales[registro.pk])

    def test_validar_seleccion_masiva_omite_registro_con_revision_previa(self):
        registro = self._registro(horario='INTRA')
        revision = RevisionCruceEgesRegistro.objects.create(
            sesion_contable=self.sesion,
            registro=registro,
            batch_eges=self.batch,
            estado=RevisionCruceEgesRegistro.ESTADO_REQUIERE_CORRECCION,
            motivos_json=['Pendiente.'],
            snapshot_json={},
            observacion='Requiere correccion previa.',
            revisado_por=self.jefe,
        )
        self.client.force_login(self.jefe)

        self.client.post(
            reverse('liquidacion:cruce_eges_validar_seleccion', kwargs={'pk': self.sesion.pk}),
            {
                'batch': self.batch.pk,
                'registros': [registro.pk],
                'observacion': 'Intento de validacion masiva.',
            },
        )

        self.assertEqual(
            RevisionCruceEgesRegistro.objects.filter(registro=registro, batch_eges=self.batch).count(),
            1,
        )
        revision.refresh_from_db()
        self.assertEqual(revision.estado, RevisionCruceEgesRegistro.ESTADO_REQUIERE_CORRECCION)

    def test_corregir_doppler_residente_na_recalcula_sin_revision_previa(self):
        registro = self._registro(horario='NA', estudios=[self.estudio_dop])
        RegistroEstudiosPorMedico.objects.filter(pk=registro.pk).update(
            horario='NA',
            monto_calculado=Decimal('200.00'),
        )
        self._eges_row(
            time(10, 0),
            time(10, 15),
            practica='ECODOPPLER VENOSO MM INFERIORES',
            codigo_practica='900048/0',
        )
        self.client.force_login(self.jefe)

        response = self._previsualizar_correccion_doppler([registro])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['candidatos']), 1)
        self.assertEqual(response.context['candidatos'][0]['monto_anterior'], Decimal('200.00'))
        self.assertEqual(response.context['candidatos'][0]['monto_nuevo'], Decimal('100.00'))
        self.assertFalse(CorreccionPacsRegistro.objects.exists())
        registro.refresh_from_db()
        self.assertEqual(registro.horario, 'NA')
        self.assertEqual(registro.monto_calculado, Decimal('200.00'))

        response = self._aplicar_correccion_doppler_previsualizada(response)
        self.assertEqual(response.status_code, 302)
        registro.refresh_from_db()
        self.assertEqual(registro.horario, 'INTRA')
        self.assertEqual(registro.monto_calculado, Decimal('100.00'))
        correccion = CorreccionPacsRegistro.objects.get(registro=registro)
        self.assertEqual(correccion.horario_anterior, 'NA')
        self.assertEqual(correccion.horario_nuevo, 'INTRA')
        self.assertEqual(correccion.monto_anterior, Decimal('200.00'))
        self.assertEqual(correccion.monto_nuevo, Decimal('100.00'))
        self.assertFalse(RevisionCruceEgesRegistro.objects.filter(registro=registro).exists())

    def _crear_correccion_para_reversion(self, dni='12345678', con_revision_eges=False):
        registro = self._registro(horario='NA', estudios=[self.estudio_dop], dni=dni)
        RegistroEstudiosPorMedico.objects.filter(pk=registro.pk).update(horario='NA', monto_calculado=Decimal('200.00'))
        self._eges_row(time(10, 0), time(10, 15), dni=dni, practica='ECODOPPLER VENOSO MM INFERIORES', codigo_practica='900048/0')
        if con_revision_eges:
            RevisionCruceEgesRegistro.objects.create(
                sesion_contable=self.sesion, registro=registro, batch_eges=self.batch,
                estado='REQUIERE_CORRECCION', revisado_por=self.jefe,
                observacion='Validacion previa pendiente', snapshot_json={'origen': 'prueba'},
            )
        self.client.force_login(self.jefe)
        preview = self._previsualizar_correccion_doppler([registro], 'Aplicacion incorrecta de prueba')
        self._aplicar_correccion_doppler_previsualizada(preview, 'Aplicacion incorrecta de prueba')
        return registro, CorreccionPacsRegistro.objects.get(registro=registro)

    def test_correccion_requiere_seleccion_explicita_y_preview_no_escribe(self):
        registro = self._registro(horario='NA', estudios=[self.estudio_dop])
        RegistroEstudiosPorMedico.objects.filter(pk=registro.pk).update(horario='NA', monto_calculado=Decimal('200.00'))
        self._eges_row(time(10, 0), time(10, 15), practica='ECODOPPLER VENOSO MM INFERIORES', codigo_practica='900048/0')
        self.client.force_login(self.jefe)
        url = reverse('liquidacion:cruce_eges_corregir_doppler', kwargs={'pk': self.sesion.pk})
        sin_seleccion = self.client.post(url, {
            'accion': 'previsualizar', 'batch': self.batch.pk, 'observacion': 'Sin seleccion',
        })
        self.assertEqual(sin_seleccion.status_code, 302)
        self.assertFalse(CorreccionPacsRegistro.objects.exists())
        registro.refresh_from_db()
        self.assertEqual((registro.horario, registro.monto_calculado), ('NA', Decimal('200.00')))

    def test_corregir_solo_aplica_los_registros_seleccionados(self):
        primero = self._registro(horario='NA', dni='11111111', estudios=[self.estudio_dop])
        segundo = self._registro(horario='NA', dni='22222222', estudios=[self.estudio_dop])
        for registro in (primero, segundo):
            RegistroEstudiosPorMedico.objects.filter(pk=registro.pk).update(horario='NA', monto_calculado=Decimal('200.00'))
        self._eges_row(time(10, 0), time(10, 15), dni='11111111', practica='ECODOPPLER VENOSO MM INFERIORES', codigo_practica='900048/0')
        self._eges_row(time(10, 0), time(10, 15), dni='22222222', practica='ECODOPPLER VENOSO MM INFERIORES', codigo_practica='900048/0')
        self.client.force_login(self.jefe)
        preview = self._previsualizar_correccion_doppler([primero])
        self.assertEqual([c['registro'].pk for c in preview.context['candidatos']], [primero.pk])
        self.assertEqual(preview.context['candidatos'][0]['practicas'][0]['nombre'], self.estudio_dop.nombre)
        self._aplicar_correccion_doppler_previsualizada(preview)
        primero.refresh_from_db()
        segundo.refresh_from_db()
        self.assertEqual((primero.horario, primero.monto_calculado), ('INTRA', Decimal('100.00')))
        self.assertEqual((segundo.horario, segundo.monto_calculado), ('NA', Decimal('200.00')))
        self.assertEqual(CorreccionPacsRegistro.objects.count(), 1)

    def test_corregir_rechaza_cambio_de_registro_entre_preview_y_confirmacion(self):
        registro = self._registro(horario='NA', estudios=[self.estudio_dop])
        RegistroEstudiosPorMedico.objects.filter(pk=registro.pk).update(horario='NA', monto_calculado=Decimal('200.00'))
        self._eges_row(time(10, 0), time(10, 15), practica='ECODOPPLER VENOSO MM INFERIORES', codigo_practica='900048/0')
        self.client.force_login(self.jefe)
        preview = self._previsualizar_correccion_doppler([registro])
        RegistroEstudiosPorMedico.objects.filter(pk=registro.pk).update(monto_calculado=Decimal('180.00'))
        response = self._aplicar_correccion_doppler_previsualizada(preview)
        self.assertEqual(response.status_code, 302)
        registro.refresh_from_db()
        self.assertEqual((registro.horario, registro.monto_calculado), ('NA', Decimal('180.00')))
        self.assertFalse(CorreccionPacsRegistro.objects.exists())

    def test_corregir_rechaza_cambio_de_fila_eges_entre_preview_y_confirmacion(self):
        registro = self._registro(horario='NA', estudios=[self.estudio_dop])
        RegistroEstudiosPorMedico.objects.filter(pk=registro.pk).update(horario='NA', monto_calculado=Decimal('200.00'))
        fila = self._eges_row(time(10, 0), time(10, 15), practica='ECODOPPLER VENOSO MM INFERIORES', codigo_practica='900048/0')
        self.client.force_login(self.jefe)
        preview = self._previsualizar_correccion_doppler([registro])
        EgesRow.objects.filter(pk=fila.pk).update(hora_turno=time(18, 0))
        response = self._aplicar_correccion_doppler_previsualizada(preview)
        self.assertEqual(response.status_code, 302)
        registro.refresh_from_db()
        self.assertEqual((registro.horario, registro.monto_calculado), ('NA', Decimal('200.00')))
        self.assertFalse(CorreccionPacsRegistro.objects.exists())

    def test_corregir_exige_confirmacion_explicita_despues_del_preview(self):
        registro = self._registro(horario='NA', estudios=[self.estudio_dop])
        RegistroEstudiosPorMedico.objects.filter(pk=registro.pk).update(horario='NA', monto_calculado=Decimal('200.00'))
        self._eges_row(time(10, 0), time(10, 15), practica='ECODOPPLER VENOSO MM INFERIORES', codigo_practica='900048/0')
        self.client.force_login(self.jefe)
        preview = self._previsualizar_correccion_doppler([registro])
        response = self._aplicar_correccion_doppler_previsualizada(preview, confirmar='')
        self.assertEqual(response.status_code, 302)
        registro.refresh_from_db()
        self.assertEqual((registro.horario, registro.monto_calculado), ('NA', Decimal('200.00')))
        self.assertFalse(CorreccionPacsRegistro.objects.exists())

    def test_corregir_rechaza_motivo_modificado_despues_del_preview(self):
        registro = self._registro(horario='NA', estudios=[self.estudio_dop])
        RegistroEstudiosPorMedico.objects.filter(pk=registro.pk).update(horario='NA', monto_calculado=Decimal('200.00'))
        self._eges_row(time(10, 0), time(10, 15), practica='ECODOPPLER VENOSO MM INFERIORES', codigo_practica='900048/0')
        self.client.force_login(self.jefe)
        preview = self._previsualizar_correccion_doppler([registro], 'Motivo del preview')
        response = self._aplicar_correccion_doppler_previsualizada(preview, 'Motivo cambiado')
        self.assertEqual(response.status_code, 302)
        registro.refresh_from_db()
        self.assertEqual((registro.horario, registro.monto_calculado), ('NA', Decimal('200.00')))
        self.assertFalse(CorreccionPacsRegistro.objects.exists())

    def test_corregir_rechaza_preview_si_sesion_cambia_antes_de_confirmar(self):
        registro = self._registro(horario='NA', estudios=[self.estudio_dop])
        RegistroEstudiosPorMedico.objects.filter(pk=registro.pk).update(horario='NA', monto_calculado=Decimal('200.00'))
        self._eges_row(time(10, 0), time(10, 15), practica='ECODOPPLER VENOSO MM INFERIORES', codigo_practica='900048/0')
        self.client.force_login(self.jefe)
        preview = self._previsualizar_correccion_doppler([registro])
        self.sesion.estado = 'CERRADA'
        self.sesion.save(update_fields=['estado'])
        response = self._aplicar_correccion_doppler_previsualizada(preview)
        self.assertEqual(response.status_code, 302)
        registro.refresh_from_db()
        self.assertEqual((registro.horario, registro.monto_calculado), ('NA', Decimal('200.00')))
        self.assertFalse(CorreccionPacsRegistro.objects.exists())

    def test_preview_mixto_muestra_exclusion_y_no_permite_aplicar(self):
        registro = self._registro(horario='NA', estudios=[self.estudio_dop, self.estudio], dni='33333333')
        RegistroEstudiosPorMedico.objects.filter(pk=registro.pk).update(horario='NA', monto_calculado=Decimal('1200.00'))
        self._eges_row(time(10, 0), time(10, 15), dni='33333333', practica='ECODOPPLER VENOSO MM INFERIORES', codigo_practica='900048/0')
        self.client.force_login(self.jefe)
        preview = self._previsualizar_correccion_doppler([registro])
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(len(preview.context['candidatos']), 0)
        self.assertEqual(len(preview.context['excluidos']), 1)
        self.assertFalse(preview.context['puede_confirmar'])
        self.assertContains(preview, 'exclusivamente estudios Doppler')
        self.assertFalse(CorreccionPacsRegistro.objects.exists())

    def test_preview_resume_seleccion_parcial_y_sumatoria_sin_escrituras(self):
        primero = self._registro(horario='NA', dni='44444444', estudios=[self.estudio_dop])
        segundo = self._registro(horario='NA', dni='55555555', estudios=[self.estudio_dop])
        for registro in (primero, segundo):
            RegistroEstudiosPorMedico.objects.filter(pk=registro.pk).update(horario='NA', monto_calculado=Decimal('200.00'))
            self._eges_row(time(10, 0), time(10, 15), dni=registro.dni_paciente, practica='ECODOPPLER VENOSO MM INFERIORES', codigo_practica='900048/0')
        self.client.force_login(self.jefe)
        preview = self._previsualizar_correccion_doppler([segundo])
        self.assertEqual(len(preview.context['candidatos']), 1)
        self.assertEqual(preview.context['total_anterior'], Decimal('200.00'))
        self.assertEqual(preview.context['total_nuevo'], Decimal('100.00'))
        self.assertFalse(CorreccionPacsRegistro.objects.exists())
        primero.refresh_from_db()
        segundo.refresh_from_db()
        self.assertEqual(primero.monto_calculado, Decimal('200.00'))
        self.assertEqual(segundo.monto_calculado, Decimal('200.00'))

    def test_preview_admite_monto_registrado_cero(self):
        registro = self._registro(horario='NA', estudios=[self.estudio_dop])
        RegistroEstudiosPorMedico.objects.filter(pk=registro.pk).update(horario='NA', monto_calculado=Decimal('0.00'))
        self._eges_row(time(10, 0), time(10, 15), practica='ECODOPPLER VENOSO MM INFERIORES', codigo_practica='900048/0')
        self.client.force_login(self.jefe)
        preview = self._previsualizar_correccion_doppler([registro])
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview.context['candidatos'][0]['monto_anterior'], Decimal('0.00'))
        self.assertEqual(preview.context['candidatos'][0]['monto_nuevo'], Decimal('100.00'))
        registro.refresh_from_db()
        self.assertEqual(registro.monto_calculado, Decimal('0.00'))
        self.assertFalse(CorreccionPacsRegistro.objects.exists())

    def test_usuario_sin_permiso_no_puede_generar_preview(self):
        registro = self._registro(horario='NA', estudios=[self.estudio_dop])
        self._eges_row(time(10, 0), time(10, 15), practica='ECODOPPLER VENOSO MM INFERIORES', codigo_practica='900048/0')
        self.client.force_login(self.admin)
        response = self._previsualizar_correccion_doppler([registro])
        self.assertEqual(response.status_code, 302)
        self.assertFalse(CorreccionPacsRegistro.objects.exists())

    def test_corregir_preview_no_autoriza_otro_usuario(self):
        registro = self._registro(horario='NA', estudios=[self.estudio_dop])
        RegistroEstudiosPorMedico.objects.filter(pk=registro.pk).update(horario='NA', monto_calculado=Decimal('200.00'))
        self._eges_row(time(10, 0), time(10, 15), practica='ECODOPPLER VENOSO MM INFERIORES', codigo_practica='900048/0')
        self.client.force_login(self.jefe)
        preview = self._previsualizar_correccion_doppler([registro])
        self.client.force_login(self.admin)
        response = self._aplicar_correccion_doppler_previsualizada(preview)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(CorreccionPacsRegistro.objects.exists())

    def test_reversion_preview_no_escribe_y_aplicacion_restaura_snapshot(self):
        from .services_reversiones import revertir_correcciones_doppler_eges
        registro, origen = self._crear_correccion_para_reversion()
        argumentos = dict(correccion_ids=[origen.pk], sesion_id=self.sesion.pk,
                          autor_correccion_id=self.jefe.pk, usuario=self.jefe, motivo='Accion aplicada sin revisar orden')
        preview = revertir_correcciones_doppler_eges(**argumentos)
        self.assertEqual(preview['conflictos'], [])
        self.assertFalse(preview['aplicado'])
        self.assertEqual(CorreccionPacsRegistro.objects.count(), 1)
        resultado = revertir_correcciones_doppler_eges(**argumentos, aplicar=True)
        self.assertTrue(resultado['aplicado'])
        registro.refresh_from_db()
        self.assertEqual(registro.horario, 'NA')
        self.assertEqual(registro.monto_calculado, Decimal('200.00'))
        self.assertEqual(registro.registroestudio_set.get().cantidad, 1)
        self.assertEqual(RevisionAuditoriaEcoRegistro.objects.filter(registro=registro).first().estado, 'REQUIERE_CORRECCION')
        inversa = CorreccionPacsRegistro.objects.exclude(pk=origen.pk).get()
        self.assertEqual(inversa.monto_anterior, origen.monto_nuevo)
        self.assertEqual(inversa.monto_nuevo, origen.monto_anterior)
        self.assertIn(f'#{origen.pk};', inversa.observacion)
        with self.assertRaises(ValidationError):
            revertir_correcciones_doppler_eges(**argumentos, aplicar=True)
        self.assertEqual(CorreccionPacsRegistro.objects.count(), 2)

    def test_reversion_bloquea_cambios_posteriores_y_sesion_cerrada(self):
        from .services_reversiones import revertir_correcciones_doppler_eges
        registro, origen = self._crear_correccion_para_reversion()
        argumentos = dict(correccion_ids=[origen.pk], sesion_id=self.sesion.pk,
                          autor_correccion_id=self.jefe.pk, usuario=self.jefe, motivo='Revertir error')
        RegistroEstudiosPorMedico.objects.filter(pk=registro.pk).update(monto_calculado=Decimal('90.00'))
        preview = revertir_correcciones_doppler_eges(**argumentos)
        self.assertTrue(preview['conflictos'])
        with self.assertRaises(ValidationError):
            revertir_correcciones_doppler_eges(**argumentos, aplicar=True)
        self.assertEqual(CorreccionPacsRegistro.objects.count(), 1)
        for estado in ('CERRADA', 'FACTURADA', 'PAGADA'):
            self.sesion.estado = estado
            self.sesion.save(update_fields=['estado'])
            with self.assertRaises(ValidationError):
                revertir_correcciones_doppler_eges(**argumentos, aplicar=True)

    def test_reversion_lote_conflictivo_no_modifica_el_registro_valido(self):
        from .services_reversiones import revertir_correcciones_doppler_eges
        primero, correccion_primera = self._crear_correccion_para_reversion()
        segundo, correccion_segunda = self._crear_correccion_para_reversion(dni='98765432')
        RegistroEstudiosPorMedico.objects.filter(pk=segundo.pk).update(monto_calculado=Decimal('90.00'))
        with self.assertRaises(ValidationError):
            revertir_correcciones_doppler_eges(
                correccion_ids=[correccion_primera.pk, correccion_segunda.pk],
                sesion_id=self.sesion.pk, autor_correccion_id=self.jefe.pk,
                usuario=self.jefe, motivo='Revertir lote', aplicar=True,
            )
        primero.refresh_from_db()
        self.assertEqual(primero.horario, 'INTRA')
        self.assertEqual(primero.monto_calculado, Decimal('100.00'))
        self.assertEqual(CorreccionPacsRegistro.objects.count(), 2)

    def test_reversion_conserva_validaciones_y_agrega_revision_pendiente_eges(self):
        from .services_reversiones import revertir_correcciones_doppler_eges
        registro, origen = self._crear_correccion_para_reversion(con_revision_eges=True)
        validacion = RevisionCruceEgesRegistro.objects.filter(registro=registro).first()
        self.assertEqual(validacion.estado, 'VALIDADO')
        resultado = revertir_correcciones_doppler_eges(
            correccion_ids=[origen.pk], sesion_id=self.sesion.pk,
            autor_correccion_id=self.jefe.pk, usuario=self.jefe, motivo='Error de validacion', aplicar=True,
        )
        self.assertEqual(len(resultado['revisiones_eges_pendientes_ids']), 1)
        validacion.refresh_from_db()
        self.assertEqual(validacion.estado, 'VALIDADO')
        nueva = RevisionCruceEgesRegistro.objects.filter(registro=registro).first()
        self.assertEqual(nueva.estado, 'REQUIERE_CORRECCION')
        self.assertEqual(nueva.snapshot_json, validacion.snapshot_json)

    def test_reversion_bloquea_recalculos_y_revisiones_posteriores(self):
        from .services_reversiones import revertir_correcciones_doppler_eges
        registro, origen = self._crear_correccion_para_reversion()
        HistorialRecalculoTarifaRegistro.objects.create(
            sesion_contable=self.sesion, registro=registro,
            fecha_desde=date(2026, 5, 1), fecha_hasta=date(2026, 5, 31),
            monto_anterior=origen.monto_nuevo, monto_nuevo=origen.monto_nuevo,
            diferencia=0, motivo='Recalculo posterior', recalculado_por=self.jefe,
        )
        RevisionAuditoriaEcoRegistro.objects.create(
            sesion_contable=self.sesion, registro=registro, estado='DESCARTADO',
            observacion='Revision humana posterior', revisado_por=self.jefe,
        )
        argumentos = dict(correccion_ids=[origen.pk], sesion_id=self.sesion.pk,
                          autor_correccion_id=self.jefe.pk, usuario=self.jefe, motivo='Revertir')
        preview = revertir_correcciones_doppler_eges(**argumentos)
        motivos = preview['conflictos'][0]['motivos']
        self.assertTrue(any('recalculo' in motivo for motivo in motivos))
        self.assertTrue(any('ECO' in motivo for motivo in motivos))
        with self.assertRaises(ValidationError):
            revertir_correcciones_doppler_eges(**argumentos, aplicar=True)
        self.assertEqual(CorreccionPacsRegistro.objects.count(), 1)

    def test_reversion_rechaza_usuario_sin_permiso(self):
        from .services_reversiones import revertir_correcciones_doppler_eges
        registro, origen = self._crear_correccion_para_reversion()
        with self.assertRaises(ValidationError):
            revertir_correcciones_doppler_eges(
                correccion_ids=[origen.pk], sesion_id=self.sesion.pk,
                autor_correccion_id=self.jefe.pk, usuario=self.admin, motivo='Revertir', aplicar=True,
            )
        self.assertEqual(CorreccionPacsRegistro.objects.count(), 1)

    def test_reversion_reabre_solo_revision_posterior_autorizada(self):
        from .services_reversiones import revertir_correcciones_doppler_eges
        registro, origen = self._crear_correccion_para_reversion()
        posterior = RevisionCruceEgesRegistro.objects.create(
            sesion_contable=self.sesion, registro=registro, batch_eges=self.batch,
            estado='VALIDADO', observacion='Validacion posterior independiente', revisado_por=self.jefe,
        )
        argumentos = dict(correccion_ids=[origen.pk], sesion_id=self.sesion.pk,
                          autor_correccion_id=self.jefe.pk, usuario=self.jefe, motivo='Reversion confirmada')
        self.assertTrue(revertir_correcciones_doppler_eges(**argumentos)['conflictos'])
        argumentos.update(revisiones_eges_a_reabrir_ids=[posterior.pk], batch_eges_autorizado_id=self.batch.pk)
        self.assertFalse(revertir_correcciones_doppler_eges(**argumentos)['conflictos'])
        resultado = revertir_correcciones_doppler_eges(**argumentos, aplicar=True)
        posterior.refresh_from_db()
        self.assertEqual(posterior.estado, 'VALIDADO')
        self.assertEqual(len(resultado['revisiones_eges_pendientes_ids']), 1)
        self.assertEqual(RevisionCruceEgesRegistro.objects.first().estado, 'REQUIERE_CORRECCION')

    def test_reversion_no_ignora_nuevas_revisiones_fuera_de_autorizacion(self):
        from .services_reversiones import revertir_correcciones_doppler_eges
        registro, origen = self._crear_correccion_para_reversion()
        autorizada = RevisionCruceEgesRegistro.objects.create(
            sesion_contable=self.sesion, registro=registro, batch_eges=self.batch,
            estado='VALIDADO', observacion='Autorizada', revisado_por=self.jefe,
        )
        RevisionCruceEgesRegistro.objects.create(
            sesion_contable=self.sesion, registro=registro, batch_eges=self.batch,
            estado='VALIDADO', observacion='Otra decision posterior', revisado_por=self.jefe,
        )
        argumentos = dict(correccion_ids=[origen.pk], sesion_id=self.sesion.pk,
                          autor_correccion_id=self.jefe.pk, usuario=self.jefe, motivo='Reversion',
                          revisiones_eges_a_reabrir_ids=[autorizada.pk], batch_eges_autorizado_id=self.batch.pk)
        self.assertTrue(revertir_correcciones_doppler_eges(**argumentos)['conflictos'])
        with self.assertRaises(ValidationError):
            revertir_correcciones_doppler_eges(**argumentos, aplicar=True)
        self.assertEqual(CorreccionPacsRegistro.objects.count(), 1)

    def test_corregir_doppler_recalcula_monto_historico_intra_con_preview_explicit(self):
        registro = self._registro(horario='INTRA', estudios=[self.estudio_dop], dni='98765432')
        RegistroEstudiosPorMedico.objects.filter(pk=registro.pk).update(
            monto_calculado=Decimal('200.00'),
        )
        self._eges_row(
            time(10, 0),
            time(10, 15),
            dni='98765432',
            practica='ECODOPPLER VENOSO MM INFERIORES',
            codigo_practica='900048/0',
        )
        self.client.force_login(self.jefe)

        preview = self._previsualizar_correccion_doppler([registro], 'Aplicar descuento Doppler INTRA vigente.')
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview.context['candidatos'][0]['horario_anterior'], 'INTRA')
        self.assertEqual(preview.context['candidatos'][0]['horario_nuevo'], 'INTRA')
        self.assertEqual(preview.context['candidatos'][0]['monto_nuevo'], Decimal('100.00'))
        response = self._aplicar_correccion_doppler_previsualizada(preview, 'Aplicar descuento Doppler INTRA vigente.')
        self.assertEqual(response.status_code, 302)
        registro.refresh_from_db()
        self.assertEqual(registro.horario, 'INTRA')
        self.assertEqual(registro.monto_calculado, Decimal('100.00'))
        correccion = CorreccionPacsRegistro.objects.get(registro=registro)
        self.assertEqual(correccion.horario_anterior, 'INTRA')
        self.assertEqual(correccion.horario_nuevo, 'INTRA')
        self.assertEqual(correccion.monto_anterior, Decimal('200.00'))
        self.assertEqual(correccion.monto_nuevo, Decimal('100.00'))

    def test_administrativo_no_puede_validar_seleccion_masiva(self):
        registro = self._registro(horario='INTRA')
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse('liquidacion:cruce_eges_validar_seleccion', kwargs={'pk': self.sesion.pk}),
            {
                'batch': self.batch.pk,
                'registros': [registro.pk],
                'observacion': 'No autorizado.',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(RevisionCruceEgesRegistro.objects.filter(registro=registro).exists())

    def test_jefe_ve_seleccion_masiva_en_advertencia_sin_revisar(self):
        registro = self._registro(horario='INTRA', estudios=[self.estudio, self.estudio_tv])
        self._eges_row(time(9, 0), time(9, 15), practica='ECOGRAFIA COMPLETA DE ABDOMEN')
        self.client.force_login(self.jefe)

        response = self.client.get(
            reverse('liquidacion:cruce_eges_liquidacion_preview', kwargs={'pk': self.sesion.pk}),
            {'batch': self.batch.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Validar seleccionadas')
        self.assertContains(response, f'value="{registro.pk}"')
        self.assertContains(response, 'form="bulk-eges-form"')

    def test_resumen_auditoria_eco_descuenta_revision_eges_validada(self):
        registro = self._registro(horario='INTRA')
        RevisionCruceEgesRegistro.objects.create(
            sesion_contable=self.sesion,
            registro=registro,
            batch_eges=self.batch,
            estado=RevisionCruceEgesRegistro.ESTADO_VALIDADO,
            motivos_json=['Coincidencia EGES OK.'],
            snapshot_json={},
            observacion='Validado por cruce EGES.',
            revisado_por=self.admin,
        )
        auditoria = {
            'items': [{
                'medico_id': self.residente.pk,
                'medico_nombre': 'Carlos Puente',
                'severidad': 'roja',
                'alertas': [{'severidad': 'roja'}],
                'registros_alerta': [{'registro_id': registro.pk}],
            }]
        }

        resumen = resumir_pendientes_auditoria_eco(auditoria)

        self.assertEqual(resumen['registros_alerta_pendientes_total'], 0)
        self.assertEqual(resumen['residentes_con_alertas_pendientes'], 0)

    def test_resumen_auditoria_eco_mantiene_pendiente_si_eges_requiere_correccion(self):
        registro = self._registro(horario='INTRA')
        RevisionCruceEgesRegistro.objects.create(
            sesion_contable=self.sesion,
            registro=registro,
            batch_eges=self.batch,
            estado=RevisionCruceEgesRegistro.ESTADO_REQUIERE_CORRECCION,
            motivos_json=['Requiere correccion.'],
            snapshot_json={},
            observacion='Debe corregirse.',
            revisado_por=self.admin,
        )
        auditoria = {
            'items': [{
                'medico_id': self.residente.pk,
                'medico_nombre': 'Carlos Puente',
                'severidad': 'roja',
                'alertas': [{'severidad': 'roja'}],
                'registros_alerta': [{'registro_id': registro.pk}],
            }]
        }

        resumen = resumir_pendientes_auditoria_eco(auditoria)

        self.assertEqual(resumen['registros_alerta_pendientes_total'], 1)
        self.client.force_login(self.admin)
        response = self.client.get(
            reverse('liquidacion:cruce_eges_liquidacion_preview', kwargs={'pk': self.sesion.pk}),
            {'batch': self.batch.pk},
        )
        self.assertContains(response, 'Aplicar ajuste auditado')

    def test_control_eges_no_genera_alertas_antes_de_consolidar(self):
        self._registro(horario='INTRA')
        self._eges_row(time(18, 0), time(18, 15), tipo_atencion='Guardia')

        resumen = resumir_control_eges_sesion(self.sesion)

        self.assertEqual(resumen['estado'], 'NO_REALIZADO')
        self.assertEqual(resumen['pendientes'], 0)

    def test_consolidar_control_persiste_resultados_y_pendientes(self):
        registro = self._registro(horario='INTRA')
        self._eges_row(time(18, 0), time(18, 15), tipo_atencion='Guardia')

        control = procesar_control_eges_sesion(self.sesion, self.batch, self.admin)

        self.assertEqual(control.version, 1)
        self.assertEqual(control.total_advertencias, 1)
        resultado = ResultadoControlEgesRegistro.objects.get(control=control, registro=registro)
        self.assertEqual(resultado.estado, ResultadoControlEgesRegistro.ESTADO_ADVERTENCIA)
        resumen = resumir_control_eges_sesion(self.sesion)
        self.assertEqual(resumen['estado'], 'COMPLETADO')
        self.assertEqual(resumen['pendientes'], 1)

        RevisionCruceEgesRegistro.objects.create(
            sesion_contable=self.sesion,
            registro=registro,
            batch_eges=self.batch,
            estado=RevisionCruceEgesRegistro.ESTADO_VALIDADO,
            motivos_json=['Excepcion revisada.'],
            snapshot_json={},
            observacion='Validado administrativamente.',
            revisado_por=self.admin,
        )
        resumen_resuelto = resumir_control_eges_sesion(self.sesion)
        self.assertEqual(resumen_resuelto['pendientes'], 0)

    def test_post_consolidar_crea_nueva_version_sin_modificar_monto(self):
        registro = self._registro(horario='INTRA')
        registro.refresh_from_db()
        monto_original = registro.monto_calculado
        self._eges_row(time(9, 0), time(9, 15), tipo_atencion='Guardia')
        self.client.force_login(self.admin)

        for _ in range(2):
            response = self.client.post(
                reverse('liquidacion:cruce_eges_procesar_control', kwargs={'pk': self.sesion.pk}),
                {'batch': self.batch.pk},
            )
            self.assertEqual(response.status_code, 302)

        self.assertEqual(ControlEgesSesion.objects.filter(sesion_contable=self.sesion).count(), 2)
        self.assertEqual(
            list(
                ControlEgesSesion.objects
                .filter(sesion_contable=self.sesion)
                .order_by('version')
                .values_list('version', flat=True)
            ),
            [1, 2],
        )
        registro.refresh_from_db()
        self.assertEqual(registro.monto_calculado, monto_original)
