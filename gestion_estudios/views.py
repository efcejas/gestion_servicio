from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, PasswordResetView
from django.core.mail import send_mail
from django.db.models import Max
from django.http import HttpResponse
from django.shortcuts import redirect
from django.views.generic import TemplateView
from django.contrib import messages
from django.utils import timezone

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

class TestFlujoTrabajoView(TemplateView):
    template_name = 'test_flujo_trabajo.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['hide_navbar'] = True

        # 📊 Datos de eventos para el dashboard
        eventos_abiertos = EventoServicio.objects.filter(estado='abierto')
        
        context['cantidad_eventos_abiertos'] = eventos_abiertos.count()
        
        # Último evento abierto para mostrar
        ultimo_evento = eventos_abiertos.order_by('-fecha_creacion').first()
        context['ultimo_evento_abierto'] = ultimo_evento

        # 📋 Últimos médicos que registraron estudios (siguiendo patrón de HomeView)
        ultimos_medicos = (
            RegistroEstudiosPorMedico.objects
            .values('medico')
            .annotate(ultima_fecha=Max('fecha_registro'))
            .order_by('-ultima_fecha')[:5]  # Los últimos 5 médicos que registraron
        )

        # Obtener los registros de esos médicos en su última fecha
        ultimos_registros_medicos = RegistroEstudiosPorMedico.objects.filter(
            medico__in=[medico['medico'] for medico in ultimos_medicos],
            fecha_registro__in=[medico['ultima_fecha'] for medico in ultimos_medicos]
        ).select_related('medico').prefetch_related('estudio').order_by('-fecha_registro')

        # Calcular totales por médico
        medicos_con_totales = []
        for medico_data in ultimos_medicos:
            medico_id = medico_data['medico']
            
            # Obtener todos los registros de este médico
            todos_registros_medico = RegistroEstudiosPorMedico.objects.filter(
                medico_id=medico_id
            ).prefetch_related('estudio')
            
            # Calcular totales
            total_estudios = sum(registro.estudio.count() for registro in todos_registros_medico)
            total_regiones = sum(registro.total_regiones() for registro in todos_registros_medico)
            
            # Obtener el último registro de este médico
            ultimo_registro = ultimos_registros_medicos.filter(medico_id=medico_id).first()
            
            if ultimo_registro:
                medicos_con_totales.append({
                    'medico': ultimo_registro.medico,
                    'ultima_fecha': medico_data['ultima_fecha'],
                    'ultimo_registro': ultimo_registro,
                    'total_estudios': total_estudios,
                    'total_regiones': total_regiones,
                    'nombre_paciente': f"{ultimo_registro.nombre_paciente} {ultimo_registro.apellido_paciente}",
                })

        context['ultimos_medicos_activos'] = medicos_con_totales

        # 📈 Estadísticas REALES del sistema de liquidación
        from datetime import timedelta
        from django.db.models import Count
        
        hoy = timezone.now().date()
        
        # Pacientes únicos activos (basado en registros de liquidación)
        total_pacientes_activos = RegistroEstudiosPorMedico.objects.values(
            'nombre_paciente', 'apellido_paciente', 'dni_paciente'
        ).distinct().count()
        
        # Estudios registrados HOY (por fecha_registro)
        estudios_hoy = RegistroEstudiosPorMedico.objects.filter(
            fecha_registro__date=hoy
        ).count()
        
        # Regiones registradas HOY
        registros_hoy = RegistroEstudiosPorMedico.objects.filter(fecha_registro__date=hoy)
        regiones_hoy = sum(registro.total_regiones() for registro in registros_hoy)
        
        # Total de regiones del MES actual
        registros_mes = RegistroEstudiosPorMedico.objects.filter(
            fecha_del_informe__year=hoy.year,
            fecha_del_informe__month=hoy.month
        )
        total_regiones_mes = sum(registro.total_regiones() for registro in registros_mes)
        
        # Médicos activos (que registraron algo en los últimos 7 días)
        fecha_hace_7_dias = hoy - timedelta(days=7)
        medicos_activos_semana = RegistroEstudiosPorMedico.objects.filter(
            fecha_registro__date__gte=fecha_hace_7_dias
        ).values('medico').distinct().count()
        
        # 👨‍⚕️ Médico de guardia hoy (del módulo control_guardias)
        medico_guardia_hoy = None
        nombre_medico_guardia = "No asignado"
        franja_horaria_guardia = ""
        
        try:
            from control_guardias.models import Guardia
            from datetime import datetime
            
            # Obtener fecha y hora actual
            ahora = timezone.now()
            fecha_hoy = ahora.date()
            hora_actual = ahora.time()
            
            # Buscar guardia activa considerando horarios que cruzan la medianoche
            guardia_activa = None
            
            # 1. Verificar guardia que empezó ayer y termina hoy (ej: 20:00 ayer - 08:00 hoy)
            from datetime import timedelta
            fecha_ayer = fecha_hoy - timedelta(days=1)
            
            guardias_ayer_noche = Guardia.objects.filter(
                fecha=fecha_ayer,
                franja_horaria__in=['NOCHE', 'NOCHE_FIN_SEMANA', 'DIA_COMPLETO'],
                cubierta=True
            ).select_related('medico')
            
            for guardia in guardias_ayer_noche:
                if guardia.franja_horaria in ['NOCHE', 'NOCHE_FIN_SEMANA']:
                    # Guardia nocturna: 20:00 - 08:00
                    if hora_actual.hour < 8:  # Antes de las 8 AM
                        guardia_activa = guardia
                        break
                elif guardia.franja_horaria == 'DIA_COMPLETO':
                    # Guardia de 24 horas que empezó ayer
                    guardia_activa = guardia
                    break
            
            # 2. Si no hay guardia activa de ayer, buscar guardia de hoy
            if not guardia_activa:
                guardias_hoy = Guardia.objects.filter(
                    fecha=fecha_hoy,
                    cubierta=True
                ).select_related('medico')
                
                for guardia in guardias_hoy:
                    if guardia.franja_horaria == 'DIA_COMPLETO':
                        # Guardia de 24 horas
                        guardia_activa = guardia
                        break
                    elif guardia.franja_horaria in ['DIA', 'DIA_FIN_SEMANA']:
                        # Guardia diurna: 08:00 - 20:00
                        if 8 <= hora_actual.hour < 20:
                            guardia_activa = guardia
                            break
                    elif guardia.franja_horaria in ['NOCHE', 'NOCHE_FIN_SEMANA']:
                        # Guardia nocturna: 20:00 - 08:00 (del día siguiente)
                        if hora_actual.hour >= 20:
                            guardia_activa = guardia
                            break
            
            # 3. Procesar resultado
            if guardia_activa and guardia_activa.medico:
                medico_guardia_hoy = guardia_activa.medico
                # Construir nombre completo del médico
                if guardia_activa.medico.user:
                    nombre_completo = guardia_activa.medico.user.get_full_name()
                    if nombre_completo.strip():
                        nombre_medico_guardia = f"Dr. {nombre_completo}"
                    else:
                        nombre_medico_guardia = f"Dr. {guardia_activa.medico.user.username}"
                else:
                    nombre_medico_guardia = f"Dr. {str(guardia_activa.medico)}"
                
                # Agregar franja horaria
                franja_horaria_guardia = guardia_activa.get_franja_horaria_display()
                
                # Agregar indicador si es guardia de ayer que continúa
                if guardia_activa.fecha == fecha_ayer:
                    franja_horaria_guardia += " (continúa)"
            else:
                # Verificar si hay guardia programada pero no cubierta
                guardias_no_cubiertas = Guardia.objects.filter(
                    fecha__in=[fecha_ayer, fecha_hoy],
                    cubierta=False
                )
                
                for guardia in guardias_no_cubiertas:
                    # Aplicar la misma lógica de horarios para guardias no cubiertas
                    es_activa = False
                    if guardia.fecha == fecha_ayer and guardia.franja_horaria in ['NOCHE', 'NOCHE_FIN_SEMANA', 'DIA_COMPLETO']:
                        if guardia.franja_horaria in ['NOCHE', 'NOCHE_FIN_SEMANA'] and hora_actual.hour < 8:
                            es_activa = True
                        elif guardia.franja_horaria == 'DIA_COMPLETO':
                            es_activa = True
                    elif guardia.fecha == fecha_hoy:
                        if guardia.franja_horaria == 'DIA_COMPLETO':
                            es_activa = True
                        elif guardia.franja_horaria in ['DIA', 'DIA_FIN_SEMANA'] and 8 <= hora_actual.hour < 20:
                            es_activa = True
                        elif guardia.franja_horaria in ['NOCHE', 'NOCHE_FIN_SEMANA'] and hora_actual.hour >= 20:
                            es_activa = True
                    
                    if es_activa:
                        nombre_medico_guardia = "⚠️ Sin cubrir"
                        franja_horaria_guardia = guardia.get_franja_horaria_display()
                        break
                
        except Exception as e:
            # Si hay algún error con el módulo de guardias, usar médico más activo del día
            medico_mas_activo_hoy = RegistroEstudiosPorMedico.objects.filter(
                fecha_registro__date=hoy
            ).values('medico').annotate(
                count=Count('id')
            ).order_by('-count').first()
            
            if medico_mas_activo_hoy:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                try:
                    medico = User.objects.get(id=medico_mas_activo_hoy['medico'])
                    nombre_completo = medico.get_full_name()
                    if nombre_completo.strip():
                        nombre_medico_guardia = f"Dr. {nombre_completo} (Más activo)"
                    else:
                        nombre_medico_guardia = f"Dr. {medico.username} (Más activo)"
                    franja_horaria_guardia = "Actividad del día"
                except:
                    pass
        
        context['total_pacientes_activos'] = total_pacientes_activos
        context['estudios_hoy'] = estudios_hoy
        context['regiones_hoy'] = regiones_hoy
        context['total_regiones_mes'] = total_regiones_mes
        context['medicos_activos_semana'] = medicos_activos_semana
        context['nombre_medico_guardia'] = nombre_medico_guardia
        context['franja_horaria_guardia'] = franja_horaria_guardia
        
        # 🔄 Próximo médico de guardia
        try:
            from control_guardias.models import Guardia
            
            # Buscar la próxima guardia después de la actual
            proxima_guardia = None
            nombre_proximo_medico = ""
            fecha_proxima_guardia = ""
            
            # Si hay guardia activa de ayer que continúa, buscar desde hoy
            # Si hay guardia de hoy, buscar la siguiente
            fecha_busqueda = hoy
            
            # Si la guardia actual es de ayer (continúa), buscar desde hoy
            if guardia_activa and guardia_activa.fecha == fecha_ayer:
                fecha_busqueda = hoy
            # Si la guardia actual es de hoy y es diurna, buscar desde hoy mismo
            elif guardia_activa and guardia_activa.fecha == hoy and guardia_activa.franja_horaria in ['DIA', 'DIA_FIN_SEMANA']:
                fecha_busqueda = hoy
            # En otros casos, buscar desde mañana
            else:
                fecha_busqueda = hoy + timedelta(days=1)
            
            # Buscar próximas guardias en los próximos 7 días
            for i in range(7):
                fecha_candidata = fecha_busqueda + timedelta(days=i)
                guardias_candidatas = Guardia.objects.filter(
                    fecha=fecha_candidata,
                    cubierta=True
                ).select_related('medico').order_by('fecha')
                
                for guardia in guardias_candidatas:
                    # Si es la misma fecha que la guardia actual, verificar que sea diferente franja
                    if guardia_activa and guardia.fecha == guardia_activa.fecha:
                        # Si guardia actual es diurna, buscar nocturna del mismo día
                        if (guardia_activa.franja_horaria in ['DIA', 'DIA_FIN_SEMANA'] and 
                            guardia.franja_horaria in ['NOCHE', 'NOCHE_FIN_SEMANA']):
                            proxima_guardia = guardia
                            break
                        # Si guardia actual es nocturna, skip guardias del mismo día
                        elif guardia_activa.franja_horaria in ['NOCHE', 'NOCHE_FIN_SEMANA']:
                            continue
                        # Si guardia actual es de 24h, skip guardias del mismo día
                        elif guardia_activa.franja_horaria == 'DIA_COMPLETO':
                            continue
                    else:
                        # Diferente fecha, tomar la primera guardia cubierta
                        proxima_guardia = guardia
                        break
                
                if proxima_guardia:
                    break
            
            # Procesar resultado
            if proxima_guardia and proxima_guardia.medico:
                if proxima_guardia.medico.user:
                    nombre_completo = proxima_guardia.medico.user.get_full_name()
                    if nombre_completo.strip():
                        nombre_proximo_medico = f"Dr. {nombre_completo}"
                    else:
                        nombre_proximo_medico = f"Dr. {proxima_guardia.medico.user.username}"
                else:
                    nombre_proximo_medico = f"Dr. {str(proxima_guardia.medico)}"
                
                # Formato de fecha más legible
                if proxima_guardia.fecha == hoy:
                    fecha_proxima_guardia = f"Hoy • {proxima_guardia.get_franja_horaria_display()}"
                elif proxima_guardia.fecha == hoy + timedelta(days=1):
                    fecha_proxima_guardia = f"Mañana • {proxima_guardia.get_franja_horaria_display()}"
                else:
                    fecha_proxima_guardia = f"{proxima_guardia.fecha.strftime('%d/%m')} • {proxima_guardia.get_franja_horaria_display()}"
            
            context['nombre_proximo_medico'] = nombre_proximo_medico
            context['fecha_proxima_guardia'] = fecha_proxima_guardia
            
        except:
            context['nombre_proximo_medico'] = ""
            context['fecha_proxima_guardia'] = ""

        return context
