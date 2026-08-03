from datetime import date

from django.core.exceptions import ValidationError
from django.test import TestCase

from .models import Estudios, GrupoTarifario, ReglaDescuentoResidencia
from .services import estudio_aplica_descuento_residencia


class ReglaDescuentoResidenciaModelTest(TestCase):
    def setUp(self):
        self.grupo = GrupoTarifario.objects.create(
            codigo='DOP_REG_TEST',
            nombre='Doppler regla test',
            modalidad='DOP',
            activo=True,
        )
        self.estudio = Estudios.objects.create(
            codigo='DOP-REG-1',
            nombre='Doppler regla test',
            tipo='DOP',
            grupo_tarifario=self.grupo,
            conteo_regiones=1,
            conteo_regiones_default=1,
            activo=True,
        )

    def test_requiere_estudio_o_grupo(self):
        regla = ReglaDescuentoResidencia(vigencia_desde=date(2026, 6, 1))

        with self.assertRaises(ValidationError):
            regla.full_clean()

    def test_no_permite_estudio_y_grupo_simultaneamente(self):
        regla = ReglaDescuentoResidencia(
            estudio=self.estudio,
            grupo_tarifario=self.grupo,
            vigencia_desde=date(2026, 6, 1),
        )

        with self.assertRaises(ValidationError):
            regla.full_clean()

    def test_no_permite_vigencia_hasta_anterior(self):
        regla = ReglaDescuentoResidencia(
            estudio=self.estudio,
            vigencia_desde=date(2026, 6, 10),
            vigencia_hasta=date(2026, 6, 1),
        )

        with self.assertRaises(ValidationError):
            regla.full_clean()

    def test_no_permite_solapamiento_activo_misma_entidad(self):
        ReglaDescuentoResidencia.objects.create(
            estudio=self.estudio,
            vigencia_desde=date(2026, 6, 1),
            vigencia_hasta=date(2026, 6, 30),
            activo=True,
        )
        regla_solapada = ReglaDescuentoResidencia(
            estudio=self.estudio,
            vigencia_desde=date(2026, 6, 15),
            activo=True,
        )

        with self.assertRaises(ValidationError):
            regla_solapada.full_clean()


class ReglaDescuentoResidenciaServiceTest(TestCase):
    def setUp(self):
        self.fecha = date(2026, 6, 16)
        self.grupo_eco = GrupoTarifario.objects.create(
            codigo='ECO_REG_TEST',
            nombre='Eco regla test',
            modalidad='ECO',
            activo=True,
        )
        self.grupo_dop = GrupoTarifario.objects.create(
            codigo='DOP_REG_SERVICE',
            nombre='Doppler regla service',
            modalidad='DOP',
            activo=True,
        )
        self.estudio_eco = Estudios.objects.create(
            codigo='ECO-REG-1',
            nombre='Eco abdominal regla',
            tipo='ECO',
            grupo_tarifario=self.grupo_eco,
            conteo_regiones=1,
            conteo_regiones_default=1,
            activo=True,
        )
        self.estudio_dop = Estudios.objects.create(
            codigo='DOP-REG-2',
            nombre='Doppler periferico regla',
            tipo='DOP',
            grupo_tarifario=self.grupo_dop,
            conteo_regiones=1,
            conteo_regiones_default=1,
            activo=True,
        )
        self.estudio_ecocar = Estudios.objects.create(
            codigo='ECOCAR-REG-1',
            nombre='Ecocardiograma regla',
            tipo='ECOCAR',
            conteo_regiones=1,
            conteo_regiones_default=1,
            activo=True,
        )

    def test_regla_por_estudio_tiene_prioridad_sobre_grupo(self):
        ReglaDescuentoResidencia.objects.create(
            grupo_tarifario=self.grupo_dop,
            aplica_medico_residente=False,
            vigencia_desde=date(2026, 1, 1),
        )
        regla_estudio = ReglaDescuentoResidencia.objects.create(
            estudio=self.estudio_dop,
            aplica_medico_residente=True,
            vigencia_desde=date(2026, 1, 1),
        )

        resultado = estudio_aplica_descuento_residencia(
            self.estudio_dop,
            'medico_residente',
            self.fecha,
        )

        self.assertTrue(resultado['aplica'])
        self.assertEqual(resultado['fuente'], 'estudio')
        self.assertEqual(resultado['regla_id'], regla_estudio.id)

    def test_regla_por_grupo_aplica_si_no_hay_regla_por_estudio(self):
        regla_grupo = ReglaDescuentoResidencia.objects.create(
            grupo_tarifario=self.grupo_dop,
            aplica_medico_residente=True,
            vigencia_desde=date(2026, 1, 1),
        )

        resultado = estudio_aplica_descuento_residencia(
            self.estudio_dop,
            'medico_residente',
            self.fecha,
        )

        self.assertTrue(resultado['aplica'])
        self.assertEqual(resultado['fuente'], 'grupo')
        self.assertEqual(resultado['regla_id'], regla_grupo.id)

    def test_roles_no_residencia_no_aplican(self):
        ReglaDescuentoResidencia.objects.create(
            estudio=self.estudio_dop,
            aplica_medico_residente=True,
            vigencia_desde=date(2026, 1, 1),
        )

        resultado = estudio_aplica_descuento_residencia(
            self.estudio_dop,
            'medico_staff',
            self.fecha,
        )

        self.assertFalse(resultado['aplica'])
        self.assertEqual(resultado['fuente'], 'rol_no_residencia')

    def test_jefe_e_instructor_no_aplican_descuento_intra_aunque_regla_lo_permita(self):
        ReglaDescuentoResidencia.objects.create(
            estudio=self.estudio_dop,
            aplica_medico_residente=True,
            aplica_jefe_residentes=True,
            aplica_instructor_residentes=True,
            vigencia_desde=date(2026, 1, 1),
        )

        resultado_jefe = estudio_aplica_descuento_residencia(
            self.estudio_dop,
            'jefe_residentes',
            self.fecha,
        )
        resultado_instructor = estudio_aplica_descuento_residencia(
            self.estudio_dop,
            'instructor_residentes',
            self.fecha,
        )

        self.assertFalse(resultado_jefe['aplica'])
        self.assertFalse(resultado_instructor['aplica'])
        self.assertEqual(resultado_jefe['fuente'], 'rol_residencia_sin_descuento_intra')
        self.assertEqual(resultado_instructor['fuente'], 'rol_residencia_sin_descuento_intra')

    def test_respeta_activo_y_vigencia(self):
        ReglaDescuentoResidencia.objects.create(
            estudio=self.estudio_dop,
            aplica_medico_residente=True,
            vigencia_desde=date(2026, 1, 1),
            vigencia_hasta=date(2026, 5, 31),
        )
        ReglaDescuentoResidencia.objects.create(
            grupo_tarifario=self.grupo_dop,
            aplica_medico_residente=True,
            vigencia_desde=date(2026, 1, 1),
            activo=False,
        )

        resultado = estudio_aplica_descuento_residencia(
            self.estudio_dop,
            'medico_residente',
            self.fecha,
        )

        self.assertFalse(resultado['aplica'])
        self.assertEqual(resultado['fuente'], 'fallback_legado')

    def test_fallback_legado_eco_general_aplica_y_dop_ecocar_no_aplican(self):
        resultado_eco = estudio_aplica_descuento_residencia(
            self.estudio_eco,
            'medico_residente',
            self.fecha,
        )
        resultado_dop = estudio_aplica_descuento_residencia(
            self.estudio_dop,
            'medico_residente',
            self.fecha,
        )
        resultado_ecocar = estudio_aplica_descuento_residencia(
            self.estudio_ecocar,
            'medico_residente',
            self.fecha,
        )

        self.assertTrue(resultado_eco['aplica'])
        self.assertFalse(resultado_dop['aplica'])
        self.assertFalse(resultado_ecocar['aplica'])
        self.assertEqual(resultado_eco['fuente'], 'fallback_legado')
