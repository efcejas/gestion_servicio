from datetime import date, time
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from eges_import.models import EgesRow, ImportBatch

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

    def _registro(self, horario='INTRA', fecha=date(2026, 5, 10), dni='12345678'):
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
        RegistroEstudio.objects.create(registro=registro, estudio=self.estudio, cantidad=1)
        return registro

    def _eges_row(self, hora_turno, hora_hasta, tipo_atencion='Guardia', dni='12345678'):
        return EgesRow.objects.create(
            batch=self.batch,
            dni_paciente=dni,
            historia_clinica=dni,
            apellido_nombre='PEREZ JUAN',
            fecha_turno=date(2026, 5, 10),
            hora_turno=hora_turno,
            hora_hasta=hora_hasta,
            tipo_atencion=tipo_atencion,
            medico_informante='Médico No Especificado',
            medico_actuante='PUENTE CARLOS',
            practica='ECOGRAFIA COMPLETA DE ABDOMEN',
            codigo_practica='180112/0',
            cantidad=Decimal('1.00'),
            servicio='Ecografia',
            estado_turno='Informado',
            modalidad='ECO',
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

    def test_guardia_fuera_de_17_alerta_si_liquidacion_esta_intra(self):
        self._registro(horario='INTRA')
        self._eges_row(time(18, 0), time(18, 15), tipo_atencion='Guardia')

        preview = construir_preview_cruce_liquidacion_eges(self.sesion, self.batch)

        self.assertEqual(preview['resumen']['advertencia'], 1)
        resultado = preview['resultados'][0]
        self.assertEqual(resultado['mejor_match']['horario_esperado'], 'EXTRA')
        self.assertIn('EGES sugiere EXTRA; liquidación figura INTRA.', resultado['motivos'])

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
