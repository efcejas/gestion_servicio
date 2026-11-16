from datetime import date
from types import SimpleNamespace

from django.test import SimpleTestCase

from .services_coberturas import clave_cobertura, construir_equivalencias_coberturas


class CoberturasEstadisticasTest(SimpleTestCase):
    def fila(self, nombre, codigo):
        return SimpleNamespace(obra_social=nombre, codigo_obra_social=codigo)

    def practicas(self):
        return [{'fila': {'id': pk, 'fecha_turno': date(2026, 10, 1), 'paciente_clave': f'paciente{pk}'},
                 'netterm': {'id': pk}} for pk in (1, 2)]

    def test_formato_legal_y_puntuacion_se_normalizan(self):
        self.assertEqual(clave_cobertura('O.S.E.C.A.C.'), clave_cobertura('OSECAC (C)'))
        self.assertEqual(clave_cobertura('APRES S.A.'), clave_cobertura('APRES (C)'))
        self.assertNotEqual(clave_cobertura('SWISS MEDICAL SA'), clave_cobertura('SWISS MEDICAL ART'))

    def test_codigo_eges_unifica_descripciones_y_variante_sin_codigo(self):
        eges = {1: self.fila('OSPATCA (ADM.DE CONSTRUCCION)', '165'),
                2: self.fila('OSPATCA 165', '165'), 3: self.fila('OSPATCA 165', None)}
        resultado = construir_equivalencias_coberturas([], eges, {}, {})
        self.assertEqual(len(set(resultado['eges'].values())), 1)

    def test_nombre_exacto_normalizado_no_requiere_nuevas_correspondencias(self):
        resultado = construir_equivalencias_coberturas([], {1: self.fila('OSECAC', '1545')},
                                                       {1: {'cobertura': 'O.S.E.C.A.C.'}}, {})
        self.assertEqual(resultado['netterm'][clave_cobertura('OSECAC')], 'OSECAC')

    def test_nombre_abreviado_se_resuelve_con_estudios_de_pacientes_distintos(self):
        eges = {pk: self.fila('IOMA (C)', '1945') for pk in (1, 2)}
        nt = {pk: {'cobertura': 'IOMA Inst de Ob Med Asistenci'} for pk in (1, 2)}
        resultado = construir_equivalencias_coberturas(self.practicas(), eges, nt, {})
        self.assertEqual(set(resultado['netterm'].values()), {'IOMA (C)'})
        self.assertFalse(resultado['pendientes'])

    def test_descripcion_netterm_compartida_por_contratos_eges_queda_para_revision(self):
        eges = {1: self.fila('COBER (C)', '352'), 2: self.fila('COBER - OSMECON (C)', '1950')}
        nt = {1: {'cobertura': 'COBENSIL SA'}, 2: {'cobertura': 'COBENSIL S.A.'}}
        resultado = construir_equivalencias_coberturas(self.practicas(), eges, nt, {})
        self.assertEqual(len(resultado['netterm']), 1)
        self.assertEqual(len(resultado['pendientes'][clave_cobertura('COBENSIL SA')]['candidatas']), 2)
        self.assertEqual(len(set(resultado['eges'].values())), 2)

    def test_nombre_exacto_y_correspondencias_contradictorias_requieren_revision(self):
        eges = {1: self.fila('OBRA SOCIAL MEDICOS CABA', '2103'),
                2: self.fila('OBRA SOCIAL MEDICOS CABA', '2103'),
                3: self.fila('OSMEDICA', '2080')}
        nt = {pk: {'cobertura': 'OSMEDICA'} for pk in (1, 2)}
        resultado = construir_equivalencias_coberturas(self.practicas(), eges, nt, {})
        self.assertIn(clave_cobertura('OSMEDICA'), resultado['pendientes'])

    def test_un_solo_paciente_no_confirma_una_equivalencia_semantica(self):
        eges = {pk: self.fila('SANCOR SALUD (C)', '1967') for pk in (1, 2)}
        nt = {pk: {'cobertura': 'ASOCIACION MUTUAL SANCOR SALUD'} for pk in (1, 2)}
        practicas = self.practicas()
        for item in practicas:
            item['fila']['paciente_clave'] = 'mismo_paciente'
        resultado = construir_equivalencias_coberturas(practicas, eges, nt, {})
        self.assertTrue(resultado['pendientes'])
