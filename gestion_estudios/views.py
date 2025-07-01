from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, PasswordResetView
from django.core.mail import send_mail
from django.db.models import Max
from django.http import HttpResponse
from django.shortcuts import redirect
from django.views.generic import TemplateView
from django.contrib import messages

from gestion_eventos.models import EventoServicio
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

class CustomPasswordResetView(PasswordResetView):
    html_email_template_name = 'registration/password_reset_email.html'  # Plantilla HTML
    subject_template_name = 'registration/password_reset_subject.txt'  # Plantilla para el asunto del correo

# Vista personalizada para la página de login
class CustomLoginView(LoginView):
    template_name = 'registration/login.html'
    redirect_authenticated_user = True  # Si el usuario ya está autenticado, redirigir a la página de inicio

    def get_context_data(self, **kwargs):
        """ Agrega la lógica para ocultar la barra de navegación """
        context = super().get_context_data(**kwargs)
        context['hide_navbar'] = True  # Ocultar la barra de navegación en la página de login
        return context

from gestion_eventos.models import EventoServicio

class HomeView(LoginRequiredMixin, TemplateView):
    template_name = 'home.html'
    login_url = 'login'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['hide_navbar'] = False

        # Últimos registros médicos
        ultimos_medicos = (
            RegistroEstudiosPorMedico.objects
            .values('medico')
            .annotate(ultima_fecha=Max('fecha_registro'))
            .order_by('-ultima_fecha')[:4]
        )

        ultimos_registros = RegistroEstudiosPorMedico.objects.filter(
            medico__in=[medico['medico'] for medico in ultimos_medicos],
            fecha_registro__in=[medico['ultima_fecha'] for medico in ultimos_medicos]
        ).order_by('-fecha_registro')

        context['ultimos_registros_medicos'] = ultimos_registros

        # 🚀 Datos de eventos actuales
        eventos_abiertos = EventoServicio.objects.filter(estado__in=['abierto', 'pendiente'])
        context['cantidad_eventos_abiertos'] = eventos_abiertos.count()

        ultima_actualizacion = None
        for evento in eventos_abiertos:
            if evento.ultima_nota:
                if not ultima_actualizacion or evento.ultima_nota.fecha > ultima_actualizacion:
                    ultima_actualizacion = evento.ultima_nota.fecha
        
        context['ultima_actualizacion_evento'] = ultima_actualizacion

        return context

# Vista para probar Flowbite
class FlowbiteTestView(TemplateView):
    template_name = 'flowbite_test.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['hide_navbar'] = True  # Ocultar navbar de Bootstrap para esta prueba
        return context

# Vista para prueba simple de Tailwind
class SimpleTailwindTestView(TemplateView):
    template_name = 'simple_tailwind_test.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['hide_navbar'] = True  # Ocultar navbar de Bootstrap para esta prueba
        return context

# Vista para debug de Tailwind CSS
class DebugTailwindView(TemplateView):
    template_name = 'debug_tailwind.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['hide_navbar'] = True  # Ocultar navbar de Bootstrap para esta prueba
        return context
