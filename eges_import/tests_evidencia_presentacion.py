from datetime import date, time
from django.test import SimpleTestCase, TestCase
from django.template.loader import render_to_string
from .services_evidencia_presentacion import detalle_netterm, detalle_eges, enriquecer_evidencias
from .tests_produccion import FuentesSinteticasMixin


class FechasEvidenciaTest(SimpleTestCase):
    def test_eventos_separados_sin_usar_pedido_como_realizacion(self):
        detalle = detalle_netterm({'fecha_pedido':'2026-10-01','hora_pedido':'13:30:00',
            'fecha_realizacion':'2026-10-02','hora_realizacion':'14:20:00',
            'fecha_informe':'2026-10-03','hora_informe':'15:10:00',
            'sector':'CONSULTORIOS EXTERNOS','informante':'PROFESIONAL DEMO'})
        self.assertEqual(detalle['fecha_pedido'], date(2026,10,1))
        self.assertEqual(detalle['fecha_realizacion'], date(2026,10,2))
        self.assertEqual(detalle['hora_informe'], time(15,10))
        html = render_to_string('eges_import/includes/detalle_evidencia.html', {'detalle':detalle})
        for etiqueta in ('Pedido','Realización','Informe','Sector','CONSULTORIOS EXTERNOS'):
            self.assertIn(etiqueta, html)

    def test_fecha_ausente_o_invalida_no_se_sustituye_por_otra(self):
        detalle = detalle_netterm({'fecha_pedido':'2026-10-01','hora_pedido':'13:30:00',
                                  'fecha_realizacion':'no válida','hora_realizacion':None})
        self.assertIsNone(detalle['fecha_realizacion'])
        self.assertIsNone(detalle['hora_informe'])
        html = render_to_string('eges_import/includes/detalle_evidencia.html', {'detalle':detalle})
        self.assertIn('Fecha no disponible', html)
        self.assertIn('Hora no disponible', html)

    def test_eges_muestra_turno_sin_inventar_fechas_de_realizacion_e_informe(self):
        detalle = detalle_eges({'fecha_turno':date(2026,10,1),'hora_turno':time(13,30),
                               'tipo_atencion':'Ambulatorio','medico_informante':'DEMO'})
        self.assertNotIn('fecha_realizacion', detalle)
        self.assertNotIn('fecha_informe', detalle)
        html = render_to_string('eges_import/includes/detalle_evidencia.html', {'detalle':detalle})
        self.assertIn('Turno / ingreso', html)
        self.assertIn('Sin fecha y hora separadas en este Excel.', html)


class EvidenciaGruposTest(FuentesSinteticasMixin, TestCase):
    def test_enriquecer_no_modifica_originales_y_solo_consulta_eges_una_vez(self):
        fila = self.eges(medico_informante='PROFESIONAL DEMO',tipo_atencion='Ambulatorio')
        grupos = [{'filas':[{'id':fila.pk,'fuente':'EGES'}, {'id':123,'fuente':'Netterm'}]}]
        originales = {123:{'fecha_pedido':'2026-10-01','hora_pedido':'13:30:00',
                          'sector':'CONSULTORIOS EXTERNOS'}}
        with self.assertNumQueries(1):
            enriquecer_evidencias(grupos, originales)
        self.assertEqual(grupos[0]['filas'][0]['detalle']['profesional'], 'PROFESIONAL DEMO')
        self.assertEqual(grupos[0]['filas'][1]['detalle']['sector'], 'CONSULTORIOS EXTERNOS')
        self.assertEqual(originales[123]['fecha_pedido'], '2026-10-01')
        fila.refresh_from_db()
        self.assertEqual(fila.tipo_atencion, 'Ambulatorio')
