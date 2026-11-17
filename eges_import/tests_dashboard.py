from datetime import date
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse

from .models import ImportBatch, NettermLote, ProduccionValidada
from .services_validacion_produccion import preparar_validacion_produccion, confirmar_produccion
from .tests_produccion import FuentesSinteticasMixin


@override_settings(SECURE_SSL_REDIRECT=False, SESSION_ENGINE='django.contrib.sessions.backends.signed_cookies')
class BaseEgesDashboardTest(FuentesSinteticasMixin, TestCase):
    def aprobar(self, *, lotes=None, desde=date(2026, 10, 1), hasta=date(2026, 10, 31)):
        seleccion = dict(batch_eges_ids=[self.batch.pk], lote_netterm_ids=lotes or [self.lote.pk],
                         fecha_desde=desde, fecha_hasta=hasta)
        preparacion = preparar_validacion_produccion(**seleccion)
        return confirmar_produccion(**seleccion, usuario=self.usuario,
                                    firma_esperada=preparacion['firma'], decisiones={})

    def datos(self, incluir=False, **filtros):
        self.client.force_login(self.usuario)
        respuesta = self.client.get(reverse('eges_import:estadisticas_fuentes_data'), {
            'base_eges': 'todos', 'incluir_netterm': '1' if incluir else '0', **filtros,
        })
        self.assertEqual(respuesta.status_code, 200, respuesta.content[:500])
        return respuesta.json()

    def cargar_eco_aprobada(self):
        self.eges()
        self.netterm()
        self.netterm(pedido='extra', documento='87654321')
        return self.aprobar()

    def test_validacion_rx_anterior_pide_revision_y_conserva_base_actual(self):
        self.eges(practica='RX TORAX', codigo_practica='340301', cantidad=2)
        self.netterm(codigo='340301', practica='RX TORAX', modalidad_modelo='RX')
        with patch('eges_import.services_produccion.aplicar_unidades_rx', side_effect=lambda filas: filas):
            self.aprobar()
        datos = self.datos(True)
        self.assertEqual(datos['kpis']['practicas_realizadas'], 2)
        self.assertTrue(datos['metadatos']['advertencias_dashboard'])

    def nuevo_lote(self, nombre='nuevo.xls'):
        return ImportBatch.objects.create(usuario=self.usuario, archivo_nombre=nombre)

    def nuevo_netterm(self, huella='b'):
        return NettermLote.objects.create(archivo_nombre='nuevo.xlsx', archivo_sha256=huella * 64,
                                         importado_por=self.usuario, version_parser='QA', motivo='Prueba')

    def test_base_incluye_todos_los_lotes_y_netterm_sin_aprobar_queda_pendiente(self):
        self.eges()
        self.eges(batch=self.nuevo_lote(), dni_paciente='99999999', practica='RESONANCIA DE CEREBRO',
                  codigo_practica='341001')
        self.netterm(pedido='sin_aprobar', documento='87654321')
        self.assertEqual(self.datos()['kpis']['practicas_realizadas'], 2)
        self.assertEqual(self.datos(True)['kpis']['practicas_realizadas'], 2)
        pantalla = self.client.get(reverse('eges_import:estadisticas'))
        self.assertEqual(pantalla.status_code, 200)
        self.assertContains(pantalla, 'Base EGES completa')
        self.assertNotContains(pantalla, 'name="lotes_eges"')
        self.assertFalse(pantalla.context['netterm_activado'])

    def test_rm_nueva_del_mismo_mes_se_mantiene_al_alternar_aporte_eco(self):
        aprobada = self.cargar_eco_aprobada()
        self.eges(batch=self.nuevo_lote('rm_octubre.xls'), dni_paciente='99999999',
                  practica='RESONANCIA DE CEREBRO', codigo_practica='341001')
        base = self.datos()
        combinado = self.datos(True)
        self.assertEqual(base['kpis']['practicas_realizadas'], 2)
        self.assertEqual(base['metadatos']['aporte_netterm_disponible'], 1)
        self.assertEqual(combinado['kpis']['practicas_realizadas'], 3)
        self.assertEqual(combinado['metadatos']['aporte_netterm_aplicado'], 1)
        self.assertFalse(combinado['metadatos']['advertencias_dashboard'])
        self.assertIn('RM', combinado['modalidad']['modalidades'])
        aprobada.refresh_from_db()
        self.assertEqual(aprobada.resultado_json['total_produccion'], 2)

    def test_nuevo_lote_del_mismo_ambito_muestra_base_y_pide_revalidar_aporte(self):
        self.cargar_eco_aprobada()
        self.eges(batch=self.nuevo_lote(), dni_paciente='99999999', codigo_practica='180113')
        combinado = self.datos(True)
        self.assertEqual(combinado['kpis']['practicas_realizadas'], 2)
        self.assertEqual(combinado['metadatos']['aporte_netterm_aplicado'], 0)
        self.assertTrue(combinado['metadatos']['advertencias_dashboard'])

    def test_aprobaciones_de_dos_modalidades_se_combinan_sin_reemplazar_la_anterior(self):
        self.cargar_eco_aprobada()
        self.batch = self.nuevo_lote('rm.xls')
        self.lote = self.nuevo_netterm()
        self.eges(dni_paciente='22222222', practica='RESONANCIA DE CEREBRO', codigo_practica='341001')
        for pedido, documento in [('rm1', '22222222'), ('rm2', '33333333')]:
            self.netterm(pedido=pedido, documento=documento, codigo='341001', practica='RESONANCIA DE CEREBRO',
                         modalidad_original='RM', modalidad_modelo='RM')
        self.aprobar()
        self.assertEqual(self.datos()['kpis']['practicas_realizadas'], 2)
        self.assertEqual(self.datos(True)['kpis']['practicas_realizadas'], 4)
        self.assertEqual(self.datos(True, **{'modalidades[]': ['RM']})['kpis']['practicas_realizadas'], 2)

    def test_nueva_aprobacion_del_mismo_periodo_sustituye_la_anterior(self):
        self.cargar_eco_aprobada()
        anterior = self.lote
        self.lote = self.nuevo_netterm()
        self.netterm(pedido='tercero', documento='33333333')
        self.aprobar(lotes=[anterior.pk, self.lote.pk])
        combinado = self.datos(True)
        self.assertEqual(combinado['kpis']['practicas_realizadas'], 3)
        self.assertEqual(combinado['metadatos']['aporte_netterm_aplicado'], 2)
        self.assertEqual(ProduccionValidada.objects.count(), 2)

    def test_dashboard_precarga_datos_compartidos_al_combinar_validaciones(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        from .services_dashboard import construir_produccion_dashboard

        self.cargar_eco_aprobada()
        with CaptureQueriesContext(connection) as una_validacion:
            una = construir_produccion_dashboard(incluir_netterm=True)

        lote_anterior = self.lote
        self.lote = self.nuevo_netterm('c')
        self.netterm(pedido='otra-practica', documento='44444444')
        self.aprobar(lotes=[lote_anterior.pk, self.lote.pk])
        with CaptureQueriesContext(connection) as dos_validaciones:
            dos = construir_produccion_dashboard(incluir_netterm=True)

        consultas_una = sum(query['sql'].lstrip().upper().startswith('SELECT')
                            for query in una_validacion.captured_queries)
        consultas_dos = sum(query['sql'].lstrip().upper().startswith('SELECT')
                            for query in dos_validaciones.captured_queries)
        self.assertEqual(una['total_produccion'], 2)
        self.assertEqual(dos['total_produccion'], 3)
        self.assertLessEqual(consultas_dos, consultas_una + 2)

    def test_actualizacion_de_realizacion_traslada_aporte_entre_meses_una_sola_vez(self):
        self.cargar_eco_aprobada()
        self.lote = self.nuevo_netterm()
        self.netterm(pedido='extra', documento='87654321', fecha_realizacion=date(2026, 11, 10))
        self.aprobar(desde=date(2026, 11, 1), hasta=date(2026, 11, 30))
        combinado = self.datos(True)
        self.assertEqual(combinado['kpis']['practicas_realizadas'], 2)
        self.assertEqual(combinado['temporal']['labels'], ['10/2026', '11/2026'])

    def test_pedido_reutilizado_por_otro_paciente_conserva_ambos_estudios(self):
        self.cargar_eco_aprobada()
        self.lote = self.nuevo_netterm()
        self.netterm(pedido='extra', documento='99999999', fecha_realizacion=date(2026, 11, 10))
        self.aprobar(desde=date(2026, 11, 1), hasta=date(2026, 11, 30))
        self.assertEqual(self.datos(True)['kpis']['practicas_realizadas'], 3)

    def test_pdf_y_filtros_usan_la_misma_base_completa(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        self.cargar_eco_aprobada()
        self.datos(True)
        with CaptureQueriesContext(connection) as consultas:
            respuesta = self.client.get(reverse('eges_import:exportar_pdf_fuentes'), {
                'base_eges': 'todos', 'incluir_netterm': '1',
            })
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.content.startswith(b'%PDF-'))
        self.assertFalse(any(q['sql'].lstrip().upper().startswith(('INSERT ', 'UPDATE ', 'DELETE ')) for q in consultas))
        fuera_del_periodo = self.datos(True, fecha_desde='2026-09-01', fecha_hasta='2026-09-30')
        self.assertEqual(fuera_del_periodo['kpis']['practicas_realizadas'], 0)
        self.assertEqual(fuera_del_periodo['metadatos']['aporte_netterm_disponible'], 0)
