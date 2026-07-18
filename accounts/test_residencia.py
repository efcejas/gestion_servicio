from datetime import date

from django.test import TestCase

from accounts.models import CustomUser
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

    def test_repetidor_conserva_anio_y_la_excepcion_se_limpia(self):
        residente = self.crear_residente('repite', 'R2', repite_anio_residencia=True)

        procesar_cierre_residencia(cierre_anio=2026)

        residente.refresh_from_db()
        self.assertEqual(residente.anio_residencia, 'R2')
        self.assertFalse(residente.repite_anio_residencia)
        self.assertEqual(residente.ultimo_cierre_residencia, 2026)

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
