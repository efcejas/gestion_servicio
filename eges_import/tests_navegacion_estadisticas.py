from html.parser import HTMLParser
import re
from django.test import TestCase, override_settings
from django.urls import reverse
from .tests_produccion import FuentesSinteticasMixin


class EnlacesHTML(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.enlaces = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.enlaces.append(dict(attrs))


@override_settings(SECURE_SSL_REDIRECT=False, SESSION_ENGINE='django.contrib.sessions.backends.signed_cookies')
class RecorridoEstadisticasTest(FuentesSinteticasMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.usuario)

    def test_modulos_comparten_recorrido_y_un_solo_acceso_de_consolidacion_para_el_dashboard(self):
        for nombre in ('estadisticas', 'importar', 'preview_netterm', 'lista_batches', 'lista_lotes_netterm', 'validar_produccion'):
            with self.subTest(pantalla=nombre):
                pagina = self.client.get(reverse('eges_import:' + nombre))
                self.assertEqual(pagina.status_code, 200)
                enlaces = EnlacesHTML(pagina.content.decode()).enlaces
                consolidar = [e for e in enlaces if e.get('id') == 'validar-produccion-fuentes']
                self.assertEqual(len(consolidar), 1)
                self.assertEqual(consolidar[0]['href'], reverse('eges_import:validar_produccion'))
                self.assertContains(pagina, 'aria-label="Módulos de estadísticas"')
                self.assertNotContains(pagina, 'EGES: Lotes e importación')
                self.assertNotContains(pagina, 'Importar mes EGES')

    def test_diagnostico_no_es_un_paso_obligatorio_ni_un_acceso_de_carga(self):
        importar = self.client.get(reverse('eges_import:importar'))
        enlaces = EnlacesHTML(importar.content.decode()).enlaces
        self.assertNotIn(reverse('eges_import:preview_conciliacion'), [e.get('href') for e in enlaces])
        self.assertNotIn(reverse('eges_import:produccion_consolidada'), [e.get('href') for e in enlaces])
        dashboard = self.client.get(reverse('eges_import:estadisticas'))
        self.assertContains(dashboard, 'Diagnóstico de fuentes · opcional')
        diagnostico = self.client.get(reverse('eges_import:preview_conciliacion'))
        self.assertEqual(diagnostico.status_code, 200)
        self.assertContains(diagnostico, 'Esta consulta es opcional.')

    def test_resultado_eges_orienta_hacia_carga_netterm_sin_cambiar_datos(self):
        self.eges()
        pagina = self.client.get(reverse('eges_import:detalle_batch', args=[self.batch.pk]))
        self.assertEqual(pagina.status_code, 200)
        self.assertContains(pagina, 'Continuar a cargar Netterm')
        enlaces = EnlacesHTML(pagina.content.decode()).enlaces
        self.assertIn(reverse('eges_import:preview_netterm'), [e.get('href') for e in enlaces])

    def test_filtros_compactos_conservan_controles_y_selecciones(self):
        pagina = self.client.get(reverse('eges_import:estadisticas'))
        self.assertEqual(pagina.status_code, 200)
        html = pagina.content.decode()
        for identificador in ('fecha-desde','fecha-hasta','incluir-netterm-dashboard',
                              'btn-todas-modalidades','btn-aplicar-filtros','btn-limpiar-filtros',
                              'btn-exportar-pdf','filtro-resumen','aporte-netterm-resumen','avisos-aporte-netterm'):
            self.assertEqual(html.count(f'id="{identificador}"'), 1, identificador)
        self.assertEqual(set(re.findall(r'data-periodo="([^"]+)"',html)),
                         {'ultimo-cargado','tres-meses','todo','mes-actual','mes-anterior','90-dias'})
        self.assertEqual(set(re.findall(r'value="([^"]+)" class="modalidad-check',html)),
                         {'TC','RM','RX','ECO','DX','MAM','SERIE'})
