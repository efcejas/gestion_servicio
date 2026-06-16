from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from .models import (
    Estudios,
    GrupoTarifario,
    ReglaDescuentoResidencia,
    RegistroEstudio,
    RegistroEstudiosPorMedico,
)


User = get_user_model()


class ReglaDescuentoResidenciaCalculoMontoTest(TestCase):
    def setUp(self):
        self.fecha_informe = date(2026, 6, 16)

        self.residente = User.objects.create_user(
            username='residente_c2',
            password='testpass123',
            rol='medico_residente',
        )
        self.jefe = User.objects.create_user(
            username='jefe_c2',
            password='testpass123',
            rol='jefe_residentes',
        )
        self.staff = User.objects.create_user(
            username='staff_c2',
            password='testpass123',
            rol='medico_staff',
        )

        self.grupo_eco = GrupoTarifario.objects.create(
            codigo='ECO_C2',
            nombre='Eco C2',
            modalidad='ECO',
            activo=True,
        )
        self.grupo_dop = GrupoTarifario.objects.create(
            codigo='DOP_C2',
            nombre='Doppler C2',
            modalidad='DOP',
            activo=True,
        )

        self.estudio_eco = Estudios.objects.create(
            codigo='ECO-C2',
            nombre='Eco abdominal C2',
            tipo='ECO',
            grupo_tarifario=self.grupo_eco,
            conteo_regiones=1,
            conteo_regiones_default=1,
            precio_cober=Decimal('100.00'),
            precio_otras_os=Decimal('100.00'),
            activo=True,
        )
        self.estudio_dop = Estudios.objects.create(
            codigo='DOP-C2',
            nombre='Doppler periferico C2',
            tipo='DOP',
            grupo_tarifario=self.grupo_dop,
            conteo_regiones=1,
            conteo_regiones_default=1,
            precio_cober=Decimal('200.00'),
            precio_otras_os=Decimal('200.00'),
            activo=True,
        )

    def _registro(self, medico=None, horario='INTRA', fecha_informe=None):
        return RegistroEstudiosPorMedico.objects.create(
            medico=medico or self.residente,
            nombre_paciente='Paciente',
            apellido_paciente='C2',
            dni_paciente='12345678',
            fecha_del_informe=fecha_informe or self.fecha_informe,
            tipo_obra_social='COBER',
            horario=horario,
            monto_calculado=Decimal('0.00'),
        )

    def _agregar_estudio(self, registro, estudio, cantidad=1):
        horario_original = registro.horario
        RegistroEstudio.objects.create(
            registro=registro,
            estudio=estudio,
            cantidad=cantidad,
            contexto='SERVICIO',
        )
        if registro.horario != horario_original:
            RegistroEstudiosPorMedico.objects.filter(pk=registro.pk).update(
                horario=horario_original,
            )
            registro.horario = horario_original

    def test_eco_general_real_residente_intra_sin_regla_sigue_descontando(self):
        registro = self._registro()
        self._agregar_estudio(registro, self.estudio_eco)

        self.assertEqual(registro.calcular_monto(), Decimal('50.000'))

    def test_dop_residente_intra_sin_regla_no_descuenta(self):
        registro = self._registro()
        self._agregar_estudio(registro, self.estudio_dop)

        self.assertEqual(registro.calcular_monto(), Decimal('200.00'))

    def test_dop_residente_intra_con_regla_activa_descuenta(self):
        ReglaDescuentoResidencia.objects.create(
            estudio=self.estudio_dop,
            aplica_medico_residente=True,
            vigencia_desde=date(2026, 1, 1),
        )
        registro = self._registro()
        self._agregar_estudio(registro, self.estudio_dop)

        self.assertEqual(registro.calcular_monto(), Decimal('100.000'))

    def test_dop_residente_extra_con_regla_activa_no_descuenta(self):
        ReglaDescuentoResidencia.objects.create(
            estudio=self.estudio_dop,
            aplica_medico_residente=True,
            vigencia_desde=date(2026, 1, 1),
        )
        registro = self._registro(horario='EXTRA')
        self._agregar_estudio(registro, self.estudio_dop)

        self.assertEqual(registro.calcular_monto(), Decimal('200.00'))

    def test_dop_jefe_con_regla_sin_flag_jefe_no_descuenta(self):
        ReglaDescuentoResidencia.objects.create(
            estudio=self.estudio_dop,
            aplica_medico_residente=True,
            aplica_jefe_residentes=False,
            vigencia_desde=date(2026, 1, 1),
        )
        registro = self._registro(medico=self.jefe)
        self._agregar_estudio(registro, self.estudio_dop)

        self.assertEqual(registro.calcular_monto(), Decimal('200.00'))

    def test_dop_jefe_con_flag_jefe_descuenta(self):
        ReglaDescuentoResidencia.objects.create(
            estudio=self.estudio_dop,
            aplica_medico_residente=False,
            aplica_jefe_residentes=True,
            vigencia_desde=date(2026, 1, 1),
        )
        registro = self._registro(medico=self.jefe)
        self._agregar_estudio(registro, self.estudio_dop)

        self.assertEqual(registro.calcular_monto(), Decimal('100.000'))

    def test_grupo_permite_y_estudio_deniega_no_descuenta(self):
        ReglaDescuentoResidencia.objects.create(
            grupo_tarifario=self.grupo_dop,
            aplica_medico_residente=True,
            vigencia_desde=date(2026, 1, 1),
        )
        ReglaDescuentoResidencia.objects.create(
            estudio=self.estudio_dop,
            aplica_medico_residente=False,
            vigencia_desde=date(2026, 1, 1),
        )
        registro = self._registro()
        self._agregar_estudio(registro, self.estudio_dop)

        self.assertEqual(registro.calcular_monto(), Decimal('200.00'))

    def test_grupo_deniega_y_estudio_permite_descuenta(self):
        ReglaDescuentoResidencia.objects.create(
            grupo_tarifario=self.grupo_dop,
            aplica_medico_residente=False,
            vigencia_desde=date(2026, 1, 1),
        )
        ReglaDescuentoResidencia.objects.create(
            estudio=self.estudio_dop,
            aplica_medico_residente=True,
            vigencia_desde=date(2026, 1, 1),
        )
        registro = self._registro()
        self._agregar_estudio(registro, self.estudio_dop)

        self.assertEqual(registro.calcular_monto(), Decimal('100.000'))

    def test_regla_fuera_de_vigencia_por_fecha_del_informe_no_aplica(self):
        ReglaDescuentoResidencia.objects.create(
            estudio=self.estudio_dop,
            aplica_medico_residente=True,
            vigencia_desde=date(2026, 7, 1),
        )
        registro = self._registro(fecha_informe=self.fecha_informe)
        self._agregar_estudio(registro, self.estudio_dop)

        self.assertEqual(registro.calcular_monto(), Decimal('200.00'))

    def test_mixto_eco_fallback_y_dop_con_regla_descuentan_ambos(self):
        ReglaDescuentoResidencia.objects.create(
            estudio=self.estudio_dop,
            aplica_medico_residente=True,
            vigencia_desde=date(2026, 1, 1),
        )
        registro = self._registro()
        self._agregar_estudio(registro, self.estudio_eco)
        self._agregar_estudio(registro, self.estudio_dop)

        self.assertEqual(registro.calcular_monto(), Decimal('150.000'))

    def test_mixto_eco_fallback_y_dop_sin_regla_descuenta_solo_eco(self):
        registro = self._registro()
        self._agregar_estudio(registro, self.estudio_eco)
        self._agregar_estudio(registro, self.estudio_dop)

        self.assertEqual(registro.calcular_monto(), Decimal('250.000'))

    def test_staff_no_descuenta_aunque_exista_regla(self):
        ReglaDescuentoResidencia.objects.create(
            estudio=self.estudio_dop,
            aplica_medico_residente=True,
            vigencia_desde=date(2026, 1, 1),
        )
        registro = self._registro(medico=self.staff)
        self._agregar_estudio(registro, self.estudio_dop)

        self.assertEqual(registro.calcular_monto(), Decimal('200.00'))
