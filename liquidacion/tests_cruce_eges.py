from datetime import date, time
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from eges_import.models import EgesRow, ImportBatch
from control_guardias.models import Feriado

from .models import (
    Estudios,
    RegistroEstudio,
    RegistroEstudiosPorMedico,
    SesionContable,
)
from .services_eges import construir_preview_cruce_liquidacion_eges


User = get_user_model()


class CruceEgesLiquidacionPreviewTest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username='admin_eges',
            password='x',
            rol='administrativo',
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

    def test_guardia_entre_8_y_17_valida_intra(self):
        self._registro(horario='INTRA')
        self._eges_row(time(9, 0), time(9, 15), tipo_atencion='Guardia')

        preview = construir_preview_cruce_liquidacion_eges(self.sesion, self.batch)

        self.assertEqual(preview['resumen']['ok'], 1)
        resultado = preview['resultados'][0]
        self.assertEqual(resultado['estado'], 'ok')
        self.assertEqual(resultado['mejor_match']['horario_esperado'], 'INTRA')
        self.assertEqual(resultado['mejor_match']['rol_medico_eges'], 'actuante')

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
