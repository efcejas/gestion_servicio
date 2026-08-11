from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from unittest.mock import patch

from .models import Preinforme, Region, RevisionPreinforme, TipoEstudio


User = get_user_model()


class BusquedaContenidoBancoTest(TestCase):
    def setUp(self):
        self.residente = User.objects.create_user(
            username='res_busqueda_banco',
            password='pass123',
            rol='medico_residente',
            perfil_completo=True,
        )
        self.revisor = User.objects.create_user(
            username='staff_busqueda_banco',
            password='pass123',
            rol='medico_staff',
            perfil_completo=True,
        )
        self.tipo = TipoEstudio.objects.create(nombre='TC Tórax búsqueda')
        self.region = Region.objects.create(nombre='Tórax búsqueda')
        self.preinforme = Preinforme.objects.create(
            residente=self.residente,
            numero_estudio='BUSQ-001',
            tipo_estudio=self.tipo,
            region=self.region,
            informe_html='<p>Texto original que no debe determinar el resultado.</p>',
            estado='finalizado',
            fecha_finalizacion=timezone.now(),
        )
        self.revision = RevisionPreinforme.objects.create(
            preinforme=self.preinforme,
            revisor=self.revisor,
            informe_final_html=(
                '<p>Se observa una neumonía <strong>redonda</strong> en el lóbulo inferior.</p>'
            ),
        )
        self.client.login(username='res_busqueda_banco', password='pass123')
        self.url = reverse('preinformes:lista_banco_informes')

    def test_indexa_texto_plano_normalizado_al_guardar(self):
        self.assertEqual(
            self.revision.informe_final_texto,
            'Se observa una neumonía redonda en el lóbulo inferior.',
        )
        self.assertIn('neumonia redonda', self.revision.informe_final_busqueda)

    def test_busca_frase_sin_tildes_a_traves_del_html(self):
        response = self.client.get(self.url, {'contenido': 'neumonia redonda'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'BUSQ-001')
        self.assertContains(response, 'Coincidencia en el informe definitivo')
        self.assertContains(response, 'neumonía redonda')

    def test_no_busca_en_el_borrador_del_residente(self):
        response = self.client.get(self.url, {'contenido': 'texto original'})

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'BUSQ-001')

    def test_actualiza_indice_al_corregir_el_informe_final(self):
        self.revision.informe_final_html = '<p>Nuevo hallazgo de consolidación basal.</p>'
        self.revision.save(update_fields=['informe_final_html'])
        self.revision.refresh_from_db()

        self.assertIn('consolidacion basal', self.revision.informe_final_busqueda)
        self.assertNotIn('neumonia redonda', self.revision.informe_final_busqueda)

    @patch('preinformes.buscador_casos_service.BuscadorCasosIA.interpretar')
    def test_busqueda_ia_expande_consulta_y_muestra_interpretacion(self, interpretar):
        caso_colon = Preinforme.objects.create(
            residente=self.residente,
            numero_estudio='BUSQ-COLON',
            tipo_estudio=self.tipo,
            region=self.region,
            informe_html='<p>Borrador.</p>',
            estado='finalizado',
            fecha_finalizacion=timezone.now(),
        )
        RevisionPreinforme.objects.create(
            preinforme=caso_colon,
            revisor=self.revisor,
            informe_final_html=(
                '<p>Engrosamiento compatible con adenocarcinoma de colon.</p>'
            ),
        )
        interpretar.return_value = {
            'success': True,
            'consulta_corregida': 'tumor de colon',
            'terminos': ['adenocarcinoma de colon', 'neoplasia colónica'],
            'tipo_estudio': '',
            'region': 'colon',
            'explicacion': 'Se buscarán neoplasias de colon y términos equivalentes.',
        }

        response = self.client.get(self.url, {'q_ia': 'tumro de colon'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'BUSQ-COLON')
        self.assertContains(response, 'Interpretación de la búsqueda')
        self.assertContains(response, 'adenocarcinoma de colon')
        interpretar.assert_called_once_with('tumro de colon')
