from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.views import LoginView, PasswordResetView
from django.core.mail import send_mail
from functools import wraps
from django.db.models import Count, Max

from agenda.models import AgendaItem, NotaPersonal
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
        from equipos.models import EquipoImagen
        from django.db.models import Max
        from datetime import datetime
        import pytz
        
        # Usar timezone de Argentina
        tz_argentina = pytz.timezone('America/Argentina/Buenos_Aires')
        ahora = timezone.now().astimezone(tz_argentina)
        hoy = ahora.date()
        hora_actual = ahora.time()
        fecha_hace_7_dias = hoy - timedelta(days=7)
        
        # Eventos
        eventos_abiertos = EventoServicio.objects.filter(estado='abierto')
        eventos_en_revision = EventoServicio.objects.filter(estado='en_revision')
        eventos_resueltos_hoy = EventoServicio.objects.filter(
            estado='resuelto',
            fecha_creacion__date=hoy
        )
        
        # GUARDIA ACTUAL: Determinar qué guardia está activa AHORA según la hora ARGENTINA
        guardias_hoy = Guardia.objects.filter(fecha=hoy, cubierta=True).select_related('medico')
        
        # Determinar franja actual según la hora ARGENTINA
        # DIA: 08:00 - 20:00
        # NOCHE: 20:00 - 08:00 (siguiente día)
        hora_minutos = hora_actual.hour * 60 + hora_actual.minute
        hora_08_00 = 8 * 60  # 480 minutos
        hora_20_00 = 20 * 60  # 1200 minutos
        
        # Guardia actual según hora
        guardia_actual = None
        if hora_minutos >= hora_08_00 and hora_minutos < hora_20_00:
            # Estamos en horario DIA (08:00 - 20:00)
            guardia_actual = guardias_hoy.filter(
                franja_horaria__in=['DIA', 'DIA_COMPLETO', 'DIA_FIN_SEMANA']
            ).first()
            franja_actual_texto = "DIA (08:00 - 20:00)"
        else:
            # Estamos en horario NOCHE (20:00 - 08:00)
            # Si es antes de las 08:00, buscamos la guardia de noche de AYER
            if hora_minutos < hora_08_00:
                ayer = hoy - timedelta(days=1)
                guardias_ayer = Guardia.objects.filter(fecha=ayer, cubierta=True).select_related('medico')
                guardia_actual = guardias_ayer.filter(
                    franja_horaria__in=['NOCHE', 'DIA_COMPLETO', 'NOCHE_FIN_SEMANA']
                ).first()
                franja_actual_texto = f"NOCHE (desde {ayer.strftime('%d/%m')} 20:00)"
            else:
                # Es después de las 20:00 de hoy
                guardia_actual = guardias_hoy.filter(
                    franja_horaria__in=['NOCHE', 'DIA_COMPLETO', 'NOCHE_FIN_SEMANA']
                ).first()
                franja_actual_texto = "NOCHE (20:00 - 08:00)"
        
        # Formatear información de guardia actual
        if guardia_actual and guardia_actual.medico:
            nombre_medico_guardia = self.formatear_nombre_medico(guardia_actual.medico)
            franja_horaria_guardia = f"{franja_actual_texto} • Ahora: {ahora.strftime('%H:%M')} hs"
        else:
            nombre_medico_guardia = "Sin cubrir"
            franja_horaria_guardia = f"{franja_actual_texto} • Ahora: {ahora.strftime('%H:%M')} hs • Sin asignar"
        
        # Próxima guardia (siguiente turno o día)
        guardias_proximas = Guardia.objects.filter(
            fecha__gte=hoy,
            cubierta=True,
            medico__isnull=False
        ).select_related('medico').order_by('fecha', 'franja_horaria')
        
        # Excluir la guardia actual de las próximas
        proxima_guardia = None
        for g in guardias_proximas:
            if guardia_actual and g.id == guardia_actual.id:
                continue  # Saltar la guardia actual
            proxima_guardia = g
            break
        
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
        
        # Calcular regiones del mes
        total_regiones_mes = sum(r.total_regiones() for r in registros_mes)
        total_estudios_mes_count = registros_mes.count()
        
        # DEBUG: Log para ver qué está pasando
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"=== DASHBOARD DEBUG ===")
        logger.info(f"Fecha hoy (Argentina): {hoy}")
        logger.info(f"Hora actual (Argentina): {ahora.strftime('%H:%M:%S')}")
        logger.info(f"Total registros con fecha_registro hoy: {registros_hoy.count()}")
        logger.info(f"Total registros mes (fecha_del_informe): {total_estudios_mes_count}")
        logger.info(f"Total regiones mes: {total_regiones_mes}")
        
        # Desglose de regiones por tipo de estudio (para debugging)
        if total_estudios_mes_count > 0:
            tipos_estudios = {}
            for r in registros_mes:
                for est in r.estudio.all():
                    tipo = est.get_tipo_display()
                    if tipo not in tipos_estudios:
                        tipos_estudios[tipo] = {'cantidad': 0, 'regiones': 0}
                    cant = r.cantidad_estudio or 1
                    tipos_estudios[tipo]['cantidad'] += cant
                    tipos_estudios[tipo]['regiones'] += est.conteo_regiones * cant
            
            logger.info(f"Desglose por tipo de estudio:")
            for tipo, data in tipos_estudios.items():
                logger.info(f"  - {tipo}: {data['cantidad']} estudios, {data['regiones']} regiones")
        
        # Últimos médicos activos - CORREGIDO: Usar timezone aware comparison
        ultimos_medicos_hoy = (
            RegistroEstudiosPorMedico.objects
            .filter(fecha_registro__date=hoy)
            .values('medico')
            .annotate(ultima_fecha=Max('fecha_registro'))
            .order_by('-ultima_fecha')[:5]
        )
        
        logger.info(f"Médicos que registraron hoy: {ultimos_medicos_hoy.count()}")
        for m in ultimos_medicos_hoy:
            logger.info(f"  - Médico ID {m['medico']}: {m['ultima_fecha']}")
        
        # Si no hay suficientes médicos de hoy, completar con médicos de los últimos días
        medicos_ids_hoy = [m['medico'] for m in ultimos_medicos_hoy]
        cant_faltantes = 5 - len(medicos_ids_hoy)
        
        ultimos_medicos_adicionales = []
        if cant_faltantes > 0:
            ultimos_medicos_adicionales = (
                RegistroEstudiosPorMedico.objects
                .filter(fecha_registro__date__lt=hoy, fecha_registro__date__gte=fecha_hace_7_dias)
                .exclude(medico__in=medicos_ids_hoy)
                .values('medico')
                .annotate(ultima_fecha=Max('fecha_registro'))
                .order_by('-ultima_fecha')[:cant_faltantes]
            )
            logger.info(f"Médicos adicionales (días anteriores): {ultimos_medicos_adicionales.count()}")
        
        # Combinar ambos querysets
        ultimos_medicos = list(ultimos_medicos_hoy) + list(ultimos_medicos_adicionales)
        
        medicos_activos_data = []
        for m in ultimos_medicos:
            medico_id = m['medico']
            fecha = m['ultima_fecha']
            
            # Convertir fecha a timezone Argentina para comparación correcta
            if timezone.is_aware(fecha):
                fecha_argentina = fecha.astimezone(tz_argentina)
            else:
                fecha_argentina = tz_argentina.localize(fecha)
            
            fecha_date = fecha_argentina.date()
            
            registros_del_dia = RegistroEstudiosPorMedico.objects.filter(
                medico_id=medico_id,
                fecha_registro__date=fecha_date
            ).select_related('medico').prefetch_related('estudio')
            
            if registros_del_dia.exists():
                medico = registros_del_dia.first().medico
                ultimo_registro = registros_del_dia.order_by('-fecha_registro').first()
                
                total_estudios = sum(
                    r.estudio.count() * (r.cantidad_estudio or 1) 
                    for r in registros_del_dia
                )
                total_regiones = sum(r.total_regiones() for r in registros_del_dia)
                
                # Indicar si el registro fue hoy (fecha Argentina)
                es_hoy = fecha_date == hoy
                
                logger.info(f"Médico {medico.get_full_name()}: fecha={fecha_date}, hoy={hoy}, es_hoy={es_hoy}")
                
                medicos_activos_data.append({
                    'medico': medico,
                    'ultima_fecha': fecha_argentina,
                    'ultimo_registro': ultimo_registro,
                    'total_estudios': total_estudios,
                    'total_regiones': total_regiones,
                    'nombre_paciente': f"{ultimo_registro.nombre_paciente} {ultimo_registro.apellido_paciente}",
                    'es_hoy': es_hoy,
                })
        
        logger.info(f"Total médicos en tabla: {len(medicos_activos_data)}")
        logger.info(f"=== FIN DASHBOARD DEBUG ===")
        
        # Estadísticas de Equipos de Imágenes
        equipos_total = EquipoImagen.objects.count()
        equipos_en_servicio = EquipoImagen.objects.filter(en_servicio=True).count()
        equipos_fuera_servicio = EquipoImagen.objects.filter(en_servicio=False).count()
        
        # Equipos por área
        from collections import Counter
        equipos_por_area_raw = EquipoImagen.objects.filter(en_servicio=True).values_list('area', flat=True)
        equipos_por_area_count = Counter(equipos_por_area_raw)
        equipos_por_area = [
            {'area': area, 'area_display': dict(EquipoImagen._meta.get_field('area').choices)[area], 'cantidad': count}
            for area, count in equipos_por_area_count.items()
        ]
        
        # Últimos 5 equipos agregados
        equipos_recientes = EquipoImagen.objects.order_by('-fecha_creacion')[:5]
        
        # ========================================
        # AGENDA Y NOTAS (para jefatura)
        # ========================================
        # Agenda del usuario actual
        agenda_hoy = AgendaItem.objects.filter(
            fecha=hoy,
            creado_por=self.request.user
        ).order_by('hora_inicio', 'titulo')
        
        # Próximos eventos (hoy + 7 días)
        fecha_limite = hoy + timedelta(days=7)
        agenda_proximos = AgendaItem.objects.filter(
            fecha__gt=hoy,
            fecha__lte=fecha_limite,
            creado_por=self.request.user
        ).order_by('fecha', 'hora_inicio')[:10]
        
        # Notas fijadas
        notas_fijadas = NotaPersonal.objects.filter(
            fijada=True,
            creado_por=self.request.user
        ).order_by('-actualizado_en')[:5]
        
        # Notas recientes (no fijadas)
        notas_recientes = NotaPersonal.objects.filter(
            fijada=False,
            creado_por=self.request.user
        ).order_by('-actualizado_en')[:5]
        
        return {
            'cantidad_eventos_abiertos': eventos_abiertos.count(),
            'cantidad_eventos_en_revision': eventos_en_revision.count(),
            'cantidad_eventos_resueltos_hoy': eventos_resueltos_hoy.count(),
            'ultimo_evento_abierto': eventos_abiertos.order_by('-fecha_creacion').first(),
            'guardias_hoy': guardias_hoy,
            'guardias_proximas': guardias_proximas[:5],
            'guardia_actual': guardia_actual,
            'nombre_medico_guardia': nombre_medico_guardia,
            'franja_horaria_guardia': franja_horaria_guardia,
            'nombre_proximo_medico': nombre_proximo_medico,
            'fecha_proxima_guardia': fecha_proxima_guardia,
            'hora_actual': ahora.strftime('%H:%M'),
            'fecha_actual': hoy.strftime('%d/%m/%Y'),
            'estudios_hoy': registros_hoy.count(),
            'total_estudios_mes': total_estudios_mes_count,
            'total_regiones_mes': total_regiones_mes,
            'total_pacientes_activos': RegistroEstudiosPorMedico.objects.values(
                'nombre_paciente', 'apellido_paciente', 'dni_paciente'
            ).distinct().count(),
            'medicos_activos_semana': RegistroEstudiosPorMedico.objects.filter(
                fecha_registro__date__gte=fecha_hace_7_dias
            ).values('medico').distinct().count(),
            'ultimos_medicos_activos': medicos_activos_data,
            'mes_actual': self._traducir_mes(hoy),  # Para mostrar "Diciembre 2025"
            # Datos de equipos
            'equipos_total': equipos_total,
            'equipos_en_servicio': equipos_en_servicio,
            'equipos_fuera_servicio': equipos_fuera_servicio,
            'equipos_por_area': equipos_por_area,
            'equipos_recientes': equipos_recientes,
            # Agenda y notas
            'agenda_hoy': agenda_hoy,
            'agenda_proximos': agenda_proximos,
            'notas_fijadas': notas_fijadas,
            'notas_recientes': notas_recientes,
        }
    
    def _traducir_mes(self, fecha):
        """Traduce el mes al español"""
        meses = {
            1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
            5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
            9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'
        }
        return f"{meses[fecha.month]} {fecha.year}"
    
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
