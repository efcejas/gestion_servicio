from django.contrib.auth.views import LoginView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView

from django.core.mail import send_mail
from django.http import HttpResponse

def send_test_email(request):
    send_mail(
        'Correo de prueba',
        'Este es un correo de prueba enviado desde Django usando Gmail.',
        'ensofermincejas@gmail.com',
        ['efccejas@hotmail.com'],
        fail_silently=False,
    )
    return HttpResponse("Correo enviado exitosamente")

# Vista personalizada para la página de login
class CustomLoginView(LoginView):
    template_name = 'registration/login.html'
    redirect_authenticated_user = True  # Si el usuario ya está autenticado, redirigir a la página de inicio

    def get_context_data(self, **kwargs):
        """ Agrega la lógica para ocultar la barra de navegación """
        context = super().get_context_data(**kwargs)
        context['hide_navbar'] = True  # Ocultar la barra de navegación en la página de login
        return context

# Vista personalizada para la página de inicio (requiere autenticación)
class HomeView(LoginRequiredMixin, TemplateView):
    template_name = 'home.html'
    login_url = 'login'  # Redirigir al login si el usuario no está autenticado

    def get_context_data(self, **kwargs):
        """ Agrega la lógica para mostrar la barra de navegación """
        context = super().get_context_data(**kwargs)
        context['hide_navbar'] = False  # Mostrar la barra de navegación en la página de inicio
        return context
