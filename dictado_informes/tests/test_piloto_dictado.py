from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from dictado_informes.models import PlantillaEstructurada


User = get_user_model()


@override_settings(SECURE_SSL_REDIRECT=False, ALLOWED_HOSTS=['testserver', 'localhost'])
class DictadoPilotoAccessTests(TestCase):
    def setUp(self):
        self.piloto = User.objects.create_user(
            username='piloto_dictado',
            password='testpass123',
            rol='piloto_dictado',
            perfil_completo=True,
        )
        self.otro_piloto = User.objects.create_user(
            username='otro_piloto',
            password='testpass123',
            rol='piloto_dictado',
            perfil_completo=True,
        )
        self.staff = User.objects.create_user(
            username='staff_sin_dictado',
            password='testpass123',
            rol='medico_staff',
            perfil_completo=True,
        )
        self.superuser = User.objects.create_superuser(
            username='admin_dictado',
            email='admin@example.com',
            password='testpass123',
        )
        PlantillaEstructurada.objects.create(
            codigo='PILOTO_TEST',
            nombre='Plantilla piloto',
            titulo='RM PILOTO',
            seccion_tecnica='Técnica de prueba',
            comentarios_base=['Comentario base'],
            origen='user',
            creada_por=self.superuser,
            compartida=True,
        )
        PlantillaEstructurada.objects.create(
            codigo='PRIVADA_OTRO',
            nombre='Plantilla privada otro piloto',
            titulo='RM PRIVADA',
            seccion_tecnica='Técnica privada',
            comentarios_base=['Privada'],
            origen='user',
            creada_por=self.otro_piloto,
            compartida=False,
        )

    def test_home_redirige_piloto_a_dictado_rapido(self):
        self.client.force_login(self.piloto)

        response = self.client.get(reverse('home'))

        self.assertRedirects(response, reverse('dictado_informes:dictado_rapido'))

    def test_piloto_accede_a_dictado_rapido(self):
        self.client.force_login(self.piloto)

        response = self.client.get(reverse('dictado_informes:dictado_rapido'))

        self.assertEqual(response.status_code, 200)

    @override_settings(DICTADO_AGENTE_HABILITADO=False)
    def test_dictado_rapido_oculta_agente_si_flag_apagado(self):
        self.client.force_login(self.piloto)

        response = self.client.get(reverse('dictado_informes:dictado_rapido'))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Agente de informe')
        self.assertContains(response, 'Plantilla Estructurada')

    def test_piloto_accede_a_plantillas_estructuradas(self):
        self.client.force_login(self.piloto)

        response = self.client.get(reverse('dictado_informes:plantilla_estructurada_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Plantilla piloto')
        self.assertNotContains(response, 'Plantilla privada otro piloto')

    def test_usuario_sin_rol_dictado_no_accede_a_dictado_rapido(self):
        self.client.force_login(self.staff)

        response = self.client.get(reverse('dictado_informes:dictado_rapido'))

        self.assertRedirects(response, reverse('home'))

    def test_api_mejorar_texto_rechaza_usuario_sin_permiso(self):
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse('dictado_informes:mejorar_texto'),
            data='{"texto":"edema oseo", "modo":"FIEL", "tipo_estudio":"OTR"}',
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 403)

    def test_navbar_del_piloto_muestra_solo_dictado(self):
        self.client.force_login(self.piloto)

        response = self.client.get(reverse('dictado_informes:dictado_rapido'))

        nav_groups = response.context['nav_groups']
        self.assertEqual(len(nav_groups), 1)
        self.assertEqual(nav_groups[0]['label'], 'Dictado IA')
        labels = [item['label'] for item in nav_groups[0]['items']]
        self.assertEqual(labels, ['Dictado Rápido', 'Plantillas Estructuradas'])

    def test_superuser_ve_dictado_en_sidebar(self):
        self.client.force_login(self.superuser)

        response = self.client.get(reverse('dictado_informes:dictado_rapido'))

        nav_groups = response.context['nav_groups']
        group = next((item for item in nav_groups if item['label'] == 'Dictado IA'), None)
        self.assertIsNotNone(group)
        labels = [item['label'] for item in group['items']]
        self.assertIn('Plantillas Estructuradas', labels)

    def test_piloto_no_puede_editar_plantilla_privada_de_otro(self):
        self.client.force_login(self.piloto)
        plantilla_privada = PlantillaEstructurada.objects.get(codigo='PRIVADA_OTRO')

        response = self.client.get(reverse('dictado_informes:plantilla_estructurada_update', args=[plantilla_privada.pk]))

        self.assertEqual(response.status_code, 404)
