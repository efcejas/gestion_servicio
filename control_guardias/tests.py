from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import datetime, timedelta
from .models import MedicoGuardia, Guardia

User = get_user_model()


class MedicoGuardiaModelTest(TestCase):
    """Pruebas para el modelo MedicoGuardia"""

    def setUp(self):
        """Configuración inicial para cada prueba"""
        self.user = User.objects.create_user(
            username='drsmith',
            password='testpass123',
            first_name='John',
            last_name='Smith',
            cargo='médico'
        )
        self.medico = MedicoGuardia.objects.create(
            dni='12345678',
            matricula='123456',
            user=self.user
        )

    def test_crear_medico_guardia(self):
        """Verifica que se puede crear un médico de guardia"""
        self.assertEqual(self.medico.dni, '12345678')
        self.assertEqual(self.medico.matricula, '123456')
        self.assertEqual(self.medico.user, self.user)

    def test_medico_guardia_str(self):
        """Verifica la representación en string del médico"""
        expected = f"{self.user.get_full_name()} - {self.medico.dni} - {self.medico.matricula}"
        self.assertEqual(str(self.medico), expected)

    def test_medico_sin_usuario(self):
        """Verifica el string de un médico sin usuario asociado"""
        medico_sin_user = MedicoGuardia.objects.create(
            dni='87654321',
            matricula='654321'
        )
        expected = f"{medico_sin_user.dni} - {medico_sin_user.matricula}"
        self.assertEqual(str(medico_sin_user), expected)

    def test_dni_unico(self):
        """Verifica que el DNI debe ser único"""
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            MedicoGuardia.objects.create(
                dni='12345678',  # DNI duplicado
                matricula='999999'
            )

    def test_matricula_unica(self):
        """Verifica que la matrícula debe ser única"""
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            MedicoGuardia.objects.create(
                dni='99999999',
                matricula='123456'  # Matrícula duplicada
            )


class GuardiaModelTest(TestCase):
    """Pruebas para el modelo Guardia"""

    def setUp(self):
        """Configuración inicial para cada prueba"""
        self.user = User.objects.create_user(
            username='drsmith',
            password='testpass123',
            first_name='John',
            last_name='Smith'
        )
        self.medico = MedicoGuardia.objects.create(
            dni='12345678',
            matricula='123456',
            user=self.user
        )
        self.fecha_guardia = timezone.now().date()

    def test_crear_guardia_cubierta(self):
        """Verifica que se puede crear una guardia cubierta"""
        guardia = Guardia.objects.create(
            franja_horaria='NOCHE',
            cubierta=True,
            medico=self.medico,
            fecha=self.fecha_guardia
        )
        self.assertEqual(guardia.franja_horaria, 'NOCHE')
        self.assertTrue(guardia.cubierta)
        self.assertEqual(guardia.medico, self.medico)

    def test_crear_guardia_no_cubierta(self):
        """Verifica que se puede crear una guardia sin cubrir"""
        guardia = Guardia.objects.create(
            franja_horaria='DIA',
            cubierta=False,
            fecha=self.fecha_guardia
        )
        self.assertFalse(guardia.cubierta)
        self.assertIsNone(guardia.medico)

    def test_guardia_str(self):
        """Verifica la representación en string de la guardia"""
        guardia = Guardia.objects.create(
            franja_horaria='NOCHE',
            cubierta=True,
            medico=self.medico,
            fecha=self.fecha_guardia
        )
        str_guardia = str(guardia)
        self.assertIn('Cubierta', str_guardia)

    def test_opciones_franja_horaria(self):
        """Verifica que todas las franjas horarias están disponibles"""
        franjas = [choice[0] for choice in Guardia.FRANJA_HORARIA_CHOICES]
        self.assertIn('NOCHE', franjas)
        self.assertIn('DIA', franjas)
        self.assertIn('DIA_COMPLETO', franjas)

    def test_guardia_default_cubierta(self):
        """Verifica que el valor por defecto de cubierta es True"""
        guardia = Guardia.objects.create(
            franja_horaria='NOCHE',
            medico=self.medico,
            fecha=self.fecha_guardia
        )
        self.assertTrue(guardia.cubierta)


class GuardiaViewsTest(TestCase):
    """Pruebas para las vistas de control de guardias"""

    def setUp(self):
        """Configuración inicial para cada prueba"""
        self.client = Client()
        self.user = User.objects.create_user(
            username='drsmith',
            password='testpass123',
            is_staff=True
        )
        self.medico = MedicoGuardia.objects.create(
            dni='12345678',
            matricula='123456',
            user=self.user
        )
        self.client.login(username='drsmith', password='testpass123')

    def test_acceso_sin_autenticacion(self):
        """Verifica que las vistas requieren autenticación"""
        self.client.logout()
        response = self.client.get(reverse('control_guardias:coberturas_semanal'))
        self.assertEqual(response.status_code, 302)  # Redirige al login

    def test_coberturas_semanal_view(self):
        """Verifica que la vista de coberturas semanales funciona"""
        response = self.client.get(reverse('control_guardias:coberturas_semanal'))
        self.assertEqual(response.status_code, 200)

    def test_crear_guardia_semana_actual(self):
        """Verifica que se pueden crear guardias para la semana actual"""
        hoy = timezone.now().date()
        guardia = Guardia.objects.create(
            franja_horaria='NOCHE',
            cubierta=True,
            medico=self.medico,
            fecha=hoy
        )
        self.assertEqual(Guardia.objects.count(), 1)
        self.assertEqual(guardia.fecha, hoy)
