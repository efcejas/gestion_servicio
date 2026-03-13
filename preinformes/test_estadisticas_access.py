from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


User = get_user_model()


class PreinformesEstadisticasAccessTest(TestCase):
    def setUp(self):
        self.jefe = User.objects.create_user(
            username='jefe_stats',
            password='testpass123',
            rol='jefe_residentes',
            perfil_completo=True,
        )
        self.instructor = User.objects.create_user(
            username='instructor_stats',
            password='testpass123',
            rol='instructor_residentes',
            perfil_completo=True,
        )
        self.staff = User.objects.create_user(
            username='staff_stats',
            password='testpass123',
            rol='medico_staff',
            perfil_completo=True,
        )

    def test_jefe_residentes_puede_acceder_a_estadisticas(self):
        self.client.force_login(self.jefe)
        response = self.client.get(reverse('preinformes:estadisticas'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Estadísticas del Sistema')

    def test_instructor_residentes_puede_acceder_a_estadisticas(self):
        self.client.force_login(self.instructor)
        response = self.client.get(reverse('preinformes:estadisticas'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Estadísticas del Sistema')

    def test_medico_staff_no_puede_acceder_a_estadisticas(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse('preinformes:estadisticas'))

        self.assertEqual(response.status_code, 302)