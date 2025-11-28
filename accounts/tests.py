from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from .models import CustomUser
from .forms import CustomUserCreationForm

User = get_user_model()


class CustomUserModelTest(TestCase):
    """Pruebas para el modelo CustomUser"""

    def setUp(self):
        """Configuración inicial para cada prueba"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User',
            cargo='médico',
            telefono='1234567890'
        )

    def test_crear_usuario(self):
        """Verifica que se puede crear un usuario correctamente"""
        self.assertEqual(self.user.username, 'testuser')
        self.assertEqual(self.user.email, 'test@example.com')
        self.assertEqual(self.user.cargo, 'médico')
        self.assertTrue(self.user.check_password('testpass123'))

    def test_usuario_str(self):
        """Verifica la representación en string del usuario"""
        expected = f"{self.user.username} - Médico"
        self.assertEqual(str(self.user), expected)

    def test_usuario_sin_cargo(self):
        """Verifica el string de un usuario sin cargo"""
        user_sin_cargo = User.objects.create_user(
            username='nocargo',
            password='testpass123'
        )
        expected = f"{user_sin_cargo.username} - Sin cargo"
        self.assertEqual(str(user_sin_cargo), expected)

    def test_opciones_cargo(self):
        """Verifica que las opciones de cargo están definidas"""
        opciones_cargo = [choice[0] for choice in CustomUser.CARGO]
        self.assertIn('médico', opciones_cargo)
        self.assertIn('jefe', opciones_cargo)
        self.assertIn('técnico radiólogo', opciones_cargo)


class CustomUserCreationFormTest(TestCase):
    """Pruebas para el formulario de creación de usuarios"""

    def test_formulario_valido(self):
        """Verifica que el formulario acepta datos válidos"""
        form_data = {
            'username': 'newuser',
            'email': 'new@example.com',
            'first_name': 'New',
            'last_name': 'User',
            'cargo': 'médico',
            'telefono': '1234567890',
            'password1': 'StrongPass123!',
            'password2': 'StrongPass123!',
        }
        form = CustomUserCreationForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_formulario_contrasenas_no_coinciden(self):
        """Verifica que el formulario rechaza contraseñas diferentes"""
        form_data = {
            'username': 'newuser',
            'email': 'new@example.com',
            'password1': 'StrongPass123!',
            'password2': 'DifferentPass123!',
        }
        form = CustomUserCreationForm(data=form_data)
        self.assertFalse(form.is_valid())

    def test_formulario_username_duplicado(self):
        """Verifica que el formulario rechaza usernames duplicados"""
        User.objects.create_user(username='duplicate', password='testpass123')
        form_data = {
            'username': 'duplicate',
            'email': 'new@example.com',
            'password1': 'StrongPass123!',
            'password2': 'StrongPass123!',
        }
        form = CustomUserCreationForm(data=form_data)
        self.assertFalse(form.is_valid())


class UserRegisterViewTest(TestCase):
    """Pruebas para la vista de registro de usuarios"""

    def setUp(self):
        """Configuración inicial para cada prueba"""
        self.client = Client()
        self.register_url = reverse('register')

    def test_registro_get(self):
        """Verifica que la página de registro se carga correctamente"""
        response = self.client.get(self.register_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'registration/register.html')
        self.assertContains(response, 'username')

    def test_registro_post_valido(self):
        """Verifica que se puede registrar un usuario correctamente"""
        form_data = {
            'username': 'newuser',
            'email': 'new@example.com',
            'first_name': 'New',
            'last_name': 'User',
            'cargo': 'médico',
            'telefono': '1234567890',
            'password1': 'StrongPass123!',
            'password2': 'StrongPass123!',
        }
        response = self.client.post(self.register_url, data=form_data)
        
        # Verifica que redirige al login
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('login'))
        
        # Verifica que el usuario fue creado
        self.assertTrue(User.objects.filter(username='newuser').exists())

    def test_registro_hide_navbar(self):
        """Verifica que el contexto incluye hide_navbar"""
        response = self.client.get(self.register_url)
        self.assertTrue(response.context.get('hide_navbar'))


class UserAuthenticationTest(TestCase):
    """Pruebas para autenticación de usuarios"""

    def setUp(self):
        """Configuración inicial para cada prueba"""
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.login_url = reverse('login')

    def test_login_exitoso(self):
        """Verifica que un usuario puede iniciar sesión"""
        login_exitoso = self.client.login(
            username='testuser',
            password='testpass123'
        )
        self.assertTrue(login_exitoso)

    def test_login_fallido(self):
        """Verifica que un login con credenciales incorrectas falla"""
        login_exitoso = self.client.login(
            username='testuser',
            password='wrongpassword'
        )
        self.assertFalse(login_exitoso)

    def test_acceso_pagina_protegida_sin_login(self):
        """Verifica que páginas protegidas redirigen al login"""
        protected_url = reverse('home')
        response = self.client.get(protected_url)
        # Debe redirigir al login
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith('/accounts/login/'))
