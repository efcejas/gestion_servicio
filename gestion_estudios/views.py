from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.views import LoginView, PasswordResetView
from django.core.mail import send_mail
from functools import wraps
from django.db.models import Count, Max
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.generic import TemplateView, RedirectView

from control_guardias.models import Guardia, MedicoGuardia
from gestion_eventos.models import EventoServicio
from liquidacion.models import RegistroEstudiosPorMedico


def superuser_required(view_func):
    """
    Decorador que requiere que el usuario sea superusuario.
    - Si no está autenticado: redirige a login
    - Si está autenticado pero no es superusuario: devuelve 403 Forbidden
    - Si es superusuario: permite el acceso
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            from django.contrib.auth.views import redirect_to_login
            return redirect_to_login(request.get_full_path())
        
        if not request.user.is_superuser:
            from django.http import HttpResponseForbidden
            return HttpResponseForbidden("Acceso denegado: Se requieren permisos de superusuario.")
        
        return view_func(request, *args, **kwargs)
    return _wrapped_view


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



# Vista de redirección para admin-dashboard (reemplaza el dashboard simple eliminado)
class AdminDashboardView(LoginRequiredMixin, UserPassesTestMixin, RedirectView):
    """Redirige a la página principal - el dashboard simple fue eliminado"""
    pattern_name = 'home'
    permanent = False
    
    def test_func(self):
        """Solo permite acceso a superusuarios"""
        return self.request.user.is_superuser

@superuser_required
def eventos_modal(request):
    """Vista para mostrar eventos filtrados por estado en el modal"""
    # Obtener el filtro de estado (por defecto: abierto)
    estado_filtro = request.GET.get('estado', 'abierto')
    
    # Filtrar eventos según el estado
    if estado_filtro == 'todos':
        eventos = EventoServicio.objects.all()
    elif estado_filtro == 'resuelto':
        # Para resueltos, mostrar solo los últimos 7 días
        hace_7_dias = timezone.now() - timedelta(days=7)
        eventos = EventoServicio.objects.filter(
            estado='resuelto',
            fecha_creacion__gte=hace_7_dias
        )
    else:
        eventos = EventoServicio.objects.filter(estado=estado_filtro)
    
    eventos = eventos.prefetch_related('notas__creado_por').order_by('-fecha_creacion')
    
    # Obtener conteos para cada estado
    conteos = {
        'abierto': EventoServicio.objects.filter(estado='abierto').count(),
        'en_revision': EventoServicio.objects.filter(estado='en_revision').count(),
        'resuelto': EventoServicio.objects.filter(
            estado='resuelto',
            fecha_creacion__gte=timezone.now() - timedelta(days=7)
        ).count(),
        'todos': EventoServicio.objects.count(),
    }
    
    context = {
        'eventos': eventos,
        'total_eventos': eventos.count(),
        'estado_actual': estado_filtro,
        'conteos': conteos,
    }
    
    return render(request, 'dashboard/eventos_modal.html', context)

@superuser_required
def cambiar_estado_evento(request, evento_id):
    """Vista para cambiar el estado de un evento"""
    if request.method == 'POST':
        try:
            evento = EventoServicio.objects.get(id=evento_id)
            nuevo_estado = request.POST.get('estado')
            
            # Validar que el estado sea válido
            estados_validos = [choice[0] for choice in EventoServicio.ESTADO_CHOICES]
            if nuevo_estado not in estados_validos:
                return JsonResponse({'success': False, 'error': 'Estado no válido'})
            
            # Cambiar el estado
            evento.estado = nuevo_estado
            evento.save(usuario=request.user)
            
            return JsonResponse({
                'success': True, 
                'message': f'Estado cambiado a {evento.get_estado_display()}',
                'nuevo_estado': nuevo_estado,
                'nuevo_estado_display': evento.get_estado_display()
            })
            
        except EventoServicio.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Evento no encontrado'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Método no permitido'})


class HomeTailwindView(LoginRequiredMixin, TemplateView):
    """
    Dashboard principal - personalizado según tipo de usuario
    Superusuarios ven admin_dashboard.html con sidebar, calendario y carga masiva
    Otros usuarios ven home.html con sus secciones específicas
    """
    login_url = 'login'

    def get_template_names(self):
        """Retorna template diferente para superusuarios"""
        if self.request.user.is_superuser:
            return ['admin_dashboard.html']  # Dashboard con sidebar
        return ['home.html']  # Dashboard normal

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['hide_navbar'] = False
        
        # Agregar contexto específico para dashboard de administrador
        if self.request.user.is_superuser:
            context.update(self.get_admin_dashboard_context())

        return context
    
    def get_admin_dashboard_context(self):
        """Contexto para el dashboard administrativo"""
        from gestion_eventos.models import EventoServicio
        from control_guardias.models import Guardia
        from liquidacion.models import RegistroEstudiosPorMedico
        from django.db.models import Max
        
        hoy = timezone.now().date()
        fecha_hace_7_dias = hoy - timedelta(days=7)
        
        # Eventos
        eventos_abiertos = EventoServicio.objects.filter(estado='abierto')
        eventos_en_revision = EventoServicio.objects.filter(estado='en_revision')
        eventos_resueltos_hoy = EventoServicio.objects.filter(
            estado='resuelto',
            fecha_creacion__date=hoy
        )
        
        # Guardias
        guardias_hoy = Guardia.objects.filter(fecha=hoy, cubierta=True)
        guardias_proximas = Guardia.objects.filter(
            fecha__gte=hoy,
            cubierta=True,
            medico__isnull=False
        ).select_related('medico').order_by('fecha', 'franja_horaria')[:5]
        
        # Obtener guardia actual (hoy) y próxima
        guardia_hoy = guardias_hoy.select_related('medico').first()
        if guardia_hoy and guardia_hoy.medico:
            nombre_medico_guardia = self.formatear_nombre_medico(guardia_hoy.medico)
            franja_horaria_guardia = guardia_hoy.get_franja_horaria_display()
        else:
            nombre_medico_guardia = "Sin cubrir"
            franja_horaria_guardia = "No hay guardia asignada"
        
        # Próxima guardia (después de hoy)
        proxima_guardia = Guardia.objects.filter(
            fecha__gt=hoy,
            cubierta=True,
            medico__isnull=False
        ).select_related('medico').order_by('fecha', 'franja_horaria').first()
        
        if proxima_guardia and proxima_guardia.medico:
            nombre_proximo_medico = self.formatear_nombre_medico(proxima_guardia.medico)
            fecha_proxima_guardia = f"{proxima_guardia.fecha.strftime('%d/%m/%Y')} • {proxima_guardia.get_franja_horaria_display()}"
        else:
            nombre_proximo_medico = "No programado"
            fecha_proxima_guardia = "Sin guardias futuras"
        
        # Estudios
        registros_hoy = RegistroEstudiosPorMedico.objects.filter(fecha_registro__date=hoy)
        registros_mes = RegistroEstudiosPorMedico.objects.filter(
            fecha_del_informe__year=hoy.year,
            fecha_del_informe__month=hoy.month
        )
        
        # Últimos médicos activos
        ultimos_medicos = (
            RegistroEstudiosPorMedico.objects
            .values('medico')
            .annotate(ultima_fecha=Max('fecha_registro'))
            .order_by('-ultima_fecha')[:5]
        )
        
        medicos_activos_data = []
        for m in ultimos_medicos:
            medico_id = m['medico']
            fecha = m['ultima_fecha']
            
            registros_del_dia = RegistroEstudiosPorMedico.objects.filter(
                medico_id=medico_id,
                fecha_registro__date=fecha.date()
            ).select_related('medico').prefetch_related('estudio')
            
            if registros_del_dia.exists():
                medico = registros_del_dia.first().medico
                ultimo_registro = registros_del_dia.order_by('-fecha_registro').first()
                
                total_estudios = sum(
                    r.estudio.count() * (r.cantidad_estudio or 1) 
                    for r in registros_del_dia
                )
                total_regiones = sum(r.total_regiones() for r in registros_del_dia)
                
                medicos_activos_data.append({
                    'medico': medico,
                    'ultima_fecha': fecha,
                    'ultimo_registro': ultimo_registro,
                    'total_estudios': total_estudios,
                    'total_regiones': total_regiones,
                    'nombre_paciente': f"{ultimo_registro.nombre_paciente} {ultimo_registro.apellido_paciente}",
                })
        
        return {
            'cantidad_eventos_abiertos': eventos_abiertos.count(),
            'cantidad_eventos_en_revision': eventos_en_revision.count(),
            'cantidad_eventos_resueltos_hoy': eventos_resueltos_hoy.count(),
            'ultimo_evento_abierto': eventos_abiertos.order_by('-fecha_creacion').first(),
            'guardias_hoy': guardias_hoy,
            'guardias_proximas': guardias_proximas,
            'nombre_medico_guardia': nombre_medico_guardia,
            'franja_horaria_guardia': franja_horaria_guardia,
            'nombre_proximo_medico': nombre_proximo_medico,
            'fecha_proxima_guardia': fecha_proxima_guardia,
            'estudios_hoy': registros_hoy.count(),
            'total_estudios_mes': registros_mes.count(),
            'total_regiones_mes': sum(r.total_regiones() for r in registros_mes),
            'total_pacientes_activos': RegistroEstudiosPorMedico.objects.values(
                'nombre_paciente', 'apellido_paciente', 'dni_paciente'
            ).distinct().count(),
            'medicos_activos_semana': RegistroEstudiosPorMedico.objects.filter(
                fecha_registro__date__gte=fecha_hace_7_dias
            ).values('medico').distinct().count(),
            'ultimos_medicos_activos': medicos_activos_data,
        }
    
    def formatear_nombre_medico(self, medico_obj):
        """Formatea el nombre del médico para mostrar"""
        if hasattr(medico_obj, 'user') and medico_obj.user:
            nombre = medico_obj.user.get_full_name()
            if nombre.strip():
                return f"Dr. {nombre}"
            return f"Dr. {medico_obj.user.username}"
        elif hasattr(medico_obj, 'get_full_name'):
            nombre = medico_obj.get_full_name()
            if nombre.strip():
                return f"Dr. {nombre}"
            return f"Dr. {medico_obj.username}"
        return f"Dr. {str(medico_obj)}"
