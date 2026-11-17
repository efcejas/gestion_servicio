from datetime import date
from io import BytesIO

from django.test import TestCase, override_settings
from django.urls import reverse
from openpyxl import load_workbook

from .models import DirectorToken
from .services_validacion_produccion import preparar_validacion_produccion, confirmar_produccion
from .tests_produccion import FuentesSinteticasMixin


@override_settings(SECURE_SSL_REDIRECT=False)
class DirectorFuentesTest(FuentesSinteticasMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.token = DirectorToken.objects.create(nombre_etiqueta='QA director')
        self.eges(tipo_atencion='Guardia')
        self.netterm()
        self.netterm(pedido='adicional', documento='87654321')
        seleccion = dict(batch_eges_ids=[self.batch.pk], lote_netterm_ids=[self.lote.pk],
                         fecha_desde=date(2026, 10, 1), fecha_hasta=date(2026, 10, 31))
        preparacion = preparar_validacion_produccion(**seleccion)
        confirmar_produccion(usuario=self.usuario, firma_esperada=preparacion['firma'], decisiones={}, **seleccion)
        self.filtros = {'fecha_desde': '2026-10-01', 'fecha_hasta': '2026-10-31', 'incluir_netterm': '1'}

    def url(self, nombre):
        return reverse('eges_import:' + nombre, kwargs={'token': str(self.token.token)})

    def test_portal_y_admin_comparten_todos_los_agregados(self):
        respuesta = self.client.get(self.url('portal_director_fuentes'), self.filtros)
        self.assertEqual(respuesta.status_code, 200)
        director = respuesta.json()
        self.client.force_login(self.usuario)
        admin = self.client.get(reverse('eges_import:estadisticas_fuentes_data'),
                                {**self.filtros, 'base_eges': 'todos'}).json()
        for clave, datos in admin.items():
            self.assertEqual(director[clave], datos, clave)
        self.assertEqual(director['kpis']['practicas_realizadas'], 2)
        self.assertEqual(director['kpis']['pacientes_atendidos'], 2)
        self.assertEqual(director['director']['guardias']['total_guardia'], 1)
        self.assertEqual(sum(director['director']['practicas']['datasets'][0]['data']), 2)
        self.assertNotIn('87654321', respuesta.content.decode())

    def test_aporte_opcional_y_modalidades(self):
        base = self.client.get(self.url('portal_director_fuentes'), {**self.filtros, 'incluir_netterm': '0'}).json()
        self.assertEqual(base['kpis']['practicas_realizadas'], 1)
        vacio = self.client.get(self.url('portal_director_fuentes'), {**self.filtros, 'modalidades[]': 'TC'}).json()
        self.assertEqual(vacio['kpis']['practicas_realizadas'], 0)

    def test_token_inactivo_y_filtro_invalido(self):
        self.assertEqual(self.client.get(self.url('portal_director_fuentes'), {'fecha_desde': 'invalida'}).status_code, 400)
        self.token.activo = False
        self.token.save(update_fields=['activo'])
        for nombre in ('portal_director_fuentes', 'portal_director_exportar_pdf', 'portal_director_exportar_excel'):
            self.assertEqual(self.client.get(self.url(nombre), self.filtros).status_code, 403)

    def test_pantalla_de_lectura_y_pdf_usan_la_misma_fuente(self):
        pagina = self.client.get(self.url('portal_director'))
        self.assertEqual(pagina.status_code, 200)
        self.assertContains(pagina, 'fuentes-data/')
        self.assertNotContains(pagina, 'Integrar y validar Netterm')
        self.assertContains(pagina, 'Pacientes identificados')
        pdf = self.client.get(self.url('portal_director_exportar_pdf'), self.filtros)
        self.assertEqual(pdf.status_code, 200)
        self.assertTrue(pdf.content.startswith(b'%PDF'))

    def test_excel_exporta_produccion_actual(self):
        respuesta = self.client.get(self.url('portal_director_exportar_excel'), self.filtros)
        self.assertEqual(respuesta.status_code, 200)
        libro = load_workbook(BytesIO(respuesta.content), read_only=True)
        try:
            resumen = dict(list(libro['Resumen'].values)[1:])
            self.assertEqual(resumen['Prácticas realizadas'], 2)
            self.assertEqual(resumen['Pacientes identificados'], 2)
        finally:
            libro.close()
