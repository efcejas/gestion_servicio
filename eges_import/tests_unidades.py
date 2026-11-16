from datetime import date

from django.test import TestCase

from .tests_produccion import FuentesSinteticasMixin
from .services_produccion import construir_preview_produccion
from .services_unidades import aplicar_unidades_rx
from .services_estadisticas import construir_estadisticas_fuentes


class UnidadesRadiologicasTest(FuentesSinteticasMixin, TestCase):
    def seleccion(self):
        return dict(batch_eges_ids=[self.batch.pk], lote_netterm_ids=[self.lote.pk])

    def torax(self, cantidad=2):
        return self.eges(practica='RX TORAX', codigo_practica='340301', cantidad=cantidad)

    def proyeccion(self, codigo, pedido='1'):
        return self.netterm(pedido=pedido, codigo=codigo,
                            practica='RX TORAX' if codigo == '340301' else 'RX SUBSIG. TORAX',
                            modalidad_original='RX', modalidad_modelo='RX')

    def test_cantidad_rx_alimenta_indicadores_y_graficos(self):
        self.torax()
        datos = construir_estadisticas_fuentes(**self.seleccion())
        self.assertEqual(datos['kpis']['practicas_realizadas'], 2)
        self.assertEqual(datos['kpis']['pacientes_atendidos'], 1)
        self.assertEqual(datos['kpis']['practicas_por_paciente'], 2)

    def test_dos_proyecciones_mismo_pedido_no_se_suman_a_cantidad_dos(self):
        self.torax()
        self.proyeccion('340301')
        secundaria = self.proyeccion('340302')
        resultado = construir_preview_produccion(**self.seleccion(), incluir_practicas=True)
        self.assertEqual(resultado['total_produccion'], 2)
        self.assertEqual(resultado['aporte_netterm'], 0)
        self.assertEqual(resultado['practicas'][0]['componentes_rx_netterm'], [secundaria.pk])

    def test_cantidad_uno_conserva_aporte_subsiguiente(self):
        self.torax(cantidad=1)
        self.proyeccion('340301')
        self.proyeccion('340302')
        resultado = construir_preview_produccion(**self.seleccion())
        self.assertEqual(resultado['total_produccion'], 2)
        self.assertEqual(resultado['aporte_netterm'], 1)

    def test_otro_pedido_conserva_estudio_independiente(self):
        self.torax()
        self.proyeccion('340301')
        self.proyeccion('340302', pedido='2')
        self.assertEqual(construir_preview_produccion(**self.seleccion())['total_produccion'], 3)

    def test_mamografia_y_axilar_suman_dos_con_cantidad_bilateral(self):
        self.eges(practica='MAMOGRAFIA SENOGRAFIA', codigo_practica='340601', cantidad=2)
        self.eges(practica='MAMOGRAFIA PROYECCION AXILAR', codigo_practica='340602', cantidad=2)
        datos = construir_estadisticas_fuentes(**self.seleccion())
        self.assertEqual(datos['kpis']['practicas_realizadas'], 2)
        self.assertEqual(datos['kpis']['pacientes_atendidos'], 1)

    def test_densitometria_varias_posiciones_cuenta_una(self):
        self.eges(practica='DENSITOMETRIA OSEA (2 O MAS POSICIONES)',
                  codigo_practica='900095', cantidad=2)
        self.assertEqual(construir_preview_produccion(**self.seleccion())['total_produccion'], 1)

    def test_cantidad_cero_conserva_practica_clinica(self):
        self.torax(cantidad=0)
        self.assertEqual(construir_preview_produccion(**self.seleccion())['total_produccion'], 1)

    def test_adicional_independiente_confirmado_se_conserva(self):
        self.torax()
        self.proyeccion('340301')
        self.proyeccion('340302', pedido='2')
        resultado = construir_preview_produccion(**self.seleccion(), incluir_practicas=True)
        adicional = next(item for item in resultado['practicas'] if 'fecha_turno' not in item['fila'])
        adicional['fila'].update(pedido='1', adicional_independiente=True)
        self.assertEqual(len(aplicar_unidades_rx(resultado['practicas'])), 2)
