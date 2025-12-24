from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.views import LoginView, PasswordResetView
from django.contrib.auth.views import (
    PasswordResetDoneView,
    PasswordResetConfirmView, 
    PasswordResetCompleteView,
    PasswordChangeView,
    PasswordChangeDoneView
)
from django.core.mail import send_mail
from functools import wraps
from django.db.models import Count, Max
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.generic import TemplateView

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

    def get_context_data(self, **kwargs):
        """ Agrega la lógica para ocultar la barra de navegación """
        context = super().get_context_data(**kwargs)
        context['hide_navbar'] = True  # Ocultar la barra de navegación en la página de reset
        return context


class CustomPasswordResetDoneView(PasswordResetDoneView):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['hide_navbar'] = True
        return context


class CustomPasswordResetConfirmView(PasswordResetConfirmView):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['hide_navbar'] = True
        return context


class CustomPasswordResetCompleteView(PasswordResetCompleteView):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['hide_navbar'] = True
        return context


class CustomPasswordChangeView(PasswordChangeView):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['hide_navbar'] = True
        return context


class CustomPasswordChangeDoneView(PasswordChangeDoneView):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['hide_navbar'] = True
        return context

# Vista personalizada para la página de login
class CustomLoginView(LoginView):
    template_name = 'registration/login_tailwind.html'
    redirect_authenticated_user = True  # Si el usuario ya está autenticado, redirigir a la página de inicio

    def get_context_data(self, **kwargs):
        """ Agrega la lógica para ocultar la barra de navegación """
        context = super().get_context_data(**kwargs)
        context['hide_navbar'] = True  # Ocultar la barra de navegación en la página de login
        return context

class HomeView(LoginRequiredMixin, TemplateView):
    template_name = 'home_tailwind.html'
    login_url = 'login'

    def dispatch(self, request, *args, **kwargs):
        """Redirigir superusuarios al dashboard de admin"""
        if request.user.is_authenticated and request.user.is_superuser:
            return redirect('admin_dashboard')
        return super().dispatch(request, *args, **kwargs)

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

class AdminDashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'admin_dashboard.html'
    login_url = 'login'  # Redirigir a login si no está autenticado
    
    def test_func(self):
        """Solo permite acceso a superusuarios"""
        return self.request.user.is_superuser

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['hide_navbar'] = True

        # Obtener la fecha actual local (sin zona horaria para simplificar)
        ahora_local = datetime.now()
        hoy = ahora_local.date()
        hora_actual = ahora_local.time()

        try:
            context.update(self.get_eventos_context())
        except Exception as e:
            print(f"❌ Error en eventos: {e}")
            context.update({'cantidad_eventos_abiertos': 0, 'ultimo_evento_abierto': None})

        try:
            context.update(self.get_medicos_context())
        except Exception as e:
            print(f"❌ Error en médicos: {e}")
            context.update({'ultimos_medicos_activos': []})

        try:
            context.update(self.get_estadisticas_context(hoy))
        except Exception as e:
            print(f"❌ Error en estadísticas: {e}")
            context.update({
                'total_pacientes_activos': 0,
                'estudios_hoy': 0,
                'regiones_hoy': 0,
                'total_regiones_mes': 0,
                'medicos_activos_semana': 0,
            })

        try:
            context.update(self.get_guardias_context(hoy))
        except Exception as e:
            print(f"❌ Error en guardias: {e}")
            context.update({
                'nombre_medico_guardia': "Error al cargar",
                'franja_horaria_guardia': f"Error: {str(e)}",
                'nombre_proximo_medico': "",
                'fecha_proxima_guardia': "",
            })

        return context

    # ------------------------ EVENTOS ------------------------

    def get_eventos_context(self):
        # Contar eventos por estado
        eventos_abiertos = EventoServicio.objects.filter(estado='abierto')
        eventos_en_revision = EventoServicio.objects.filter(estado='en_revision')
        
        # Para resueltos, contar solo los de hoy
        hoy = timezone.now().date()
        eventos_resueltos_hoy = EventoServicio.objects.filter(
            estado='resuelto',
            fecha_creacion__date=hoy
        )
        
        return {
            'cantidad_eventos_abiertos': eventos_abiertos.count(),
            'cantidad_eventos_en_revision': eventos_en_revision.count(),
            'cantidad_eventos_resueltos_hoy': eventos_resueltos_hoy.count(),
            'ultimo_evento_abierto': eventos_abiertos.order_by('-fecha_creacion').first(),
        }

    # ------------------------ MÉDICOS ------------------------

    def get_medicos_context(self):
        # Obtener los últimos 5 médicos únicos por fecha más reciente
        ultimos_medicos = (
            RegistroEstudiosPorMedico.objects
            .values('medico')
            .annotate(ultima_fecha=Max('fecha_registro'))
            .order_by('-ultima_fecha')[:10]  # Obtener más para asegurar variedad
        )

        resultados = []
        count = 0
        
        for m in ultimos_medicos:
            if count >= 5:  # Limitar a 5 resultados
                break
                
            medico_id = m['medico']
            fecha = m['ultima_fecha']

            # Obtener todos los registros de este médico en su día más reciente
            registros_del_dia = RegistroEstudiosPorMedico.objects.filter(
                medico_id=medico_id,
                fecha_registro__date=fecha.date()
            ).select_related('medico').prefetch_related('estudio')

            if not registros_del_dia.exists():
                continue

            # Obtener el médico y el registro más reciente de ese día
            medico = registros_del_dia.first().medico
            ultimo_registro = registros_del_dia.order_by('-fecha_registro').first()

            # Calcular total de estudios para este día
            total_estudios = 0
            for r in registros_del_dia:
                cantidad = r.cantidad_estudio or 1
                total_estudios += r.estudio.count() * cantidad
            
            # Calcular total de regiones para este día
            total_regiones = sum(r.total_regiones() for r in registros_del_dia)

            resultados.append({
                'medico': medico,
                'ultima_fecha': fecha,
                'ultimo_registro': ultimo_registro,
                'total_estudios': total_estudios,
                'total_regiones': total_regiones,
                'nombre_paciente': f"{ultimo_registro.nombre_paciente} {ultimo_registro.apellido_paciente}",
            })
            
            count += 1

        return {'ultimos_medicos_activos': resultados}

    # ------------------------ ESTADÍSTICAS ------------------------

    def get_estadisticas_context(self, hoy):
        registros_hoy = RegistroEstudiosPorMedico.objects.filter(fecha_registro__date=hoy)
        registros_mes = RegistroEstudiosPorMedico.objects.filter(
            fecha_del_informe__year=hoy.year,
            fecha_del_informe__month=hoy.month
        )

        fecha_hace_7_dias = hoy - timedelta(days=7)

        return {
            'total_pacientes_activos': RegistroEstudiosPorMedico.objects.values(
                'nombre_paciente', 'apellido_paciente', 'dni_paciente'
            ).distinct().count(),
            'estudios_hoy': registros_hoy.count(),
            'regiones_hoy': sum(r.total_regiones() for r in registros_hoy),
            'total_regiones_mes': sum(r.total_regiones() for r in registros_mes),
            'medicos_activos_semana': RegistroEstudiosPorMedico.objects.filter(
                fecha_registro__date__gte=fecha_hace_7_dias
            ).values('medico').distinct().count(),
        }

    # ------------------------ GUARDIAS ------------------------

    def get_guardias_context(self, fecha_hoy):
        """Versión simplificada: obtiene las 2 guardias más próximas desde hoy hacia el futuro."""
        
        # Obtener las 2 guardias más próximas (desde hoy hacia el futuro)
        guardias_proximas = Guardia.objects.filter(
            fecha__gte=fecha_hoy,  # Desde hoy en adelante
            cubierta=True,
            medico__isnull=False
        ).select_related('medico').order_by('fecha', 'franja_horaria')[:2]
        
        # Si hay guardias, tomar la primera como "actual" y la segunda como "próxima"
        if guardias_proximas:
            guardia_actual = guardias_proximas[0]
            nombre_guardia = self.formatear_nombre_medico(guardia_actual.medico)
            franja_guardia = guardia_actual.get_franja_horaria_display()
            
            # Si hay una segunda guardia, usarla como "próxima"
            if len(guardias_proximas) > 1:
                guardia_proxima = guardias_proximas[1]
                nombre_proximo = self.formatear_nombre_medico(guardia_proxima.medico)
                fecha_proxima = f"{guardia_proxima.fecha.strftime('%d/%m')} • {guardia_proxima.get_franja_horaria_display()}"
            else:
                nombre_proximo = "No programado"
                fecha_proxima = "Sin más guardias"
        else:
            nombre_guardia = "No asignado"
            franja_guardia = "Sin guardia programada"
            nombre_proximo = "No programado"
            fecha_proxima = "Sin guardias futuras"

        return {
            'nombre_medico_guardia': nombre_guardia,
            'franja_horaria_guardia': franja_guardia,
            'nombre_proximo_medico': nombre_proximo,
            'fecha_proxima_guardia': fecha_proxima,
            'guardias_proximas': guardias_proximas,  # Para usar en el template si quieres
            'total_guardias': Guardia.objects.filter(cubierta=True).count(),
        }

    def formatear_nombre_medico(self, medico_obj):
        # Si es un MedicoGuardia
        if hasattr(medico_obj, 'user') and medico_obj.user:
            nombre = medico_obj.user.get_full_name()
            if nombre.strip():
                return f"Dr. {nombre}"
            else:
                return f"Dr. {medico_obj.user.username}"
        # Si es un User directamente
        elif hasattr(medico_obj, 'get_full_name'):
            nombre = medico_obj.get_full_name()
            if nombre.strip():
                return f"Dr. {nombre}"
            else:
                return f"Dr. {medico_obj.username}"
        # Fallback
        else:
            return f"Dr. {str(medico_obj)}"

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
