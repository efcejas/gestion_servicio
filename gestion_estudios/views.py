from django.contrib.auth.views import LoginView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView

from django.core.mail import send_mail
from django.http import HttpResponse
from django.db.models import Max
from liquidacion.models import RegistroEstudiosPorMedico

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
    login_url = 'login'

    def get_context_data(self, **kwargs):
        """ Muestra los últimos 3 usuarios que hicieron registros y en qué día """
        context = super().get_context_data(**kwargs)
        context['hide_navbar'] = False

        # Obtener los últimos 3 médicos que hicieron registros
        ultimos_medicos = (
            RegistroEstudiosPorMedico.objects
            .values('medico')  # Obtener solo el ID del médico
            .annotate(ultima_fecha=Max('fecha_registro'))  # Obtener la última fecha de cada médico
            .order_by('-ultima_fecha')[:4]  # Tomar los 3 más recientes
        )

        # Obtener los objetos completos de los registros usando las fechas anteriores
        ultimos_registros = RegistroEstudiosPorMedico.objects.filter(
            medico__in=[medico['medico'] for medico in ultimos_medicos],
            fecha_registro__in=[medico['ultima_fecha'] for medico in ultimos_medicos]
        ).order_by('-fecha_registro')

        context['ultimos_registros_medicos'] = ultimos_registros
        return context

