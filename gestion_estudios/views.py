from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, PasswordResetView
from django.core.mail import send_mail
from django.db.models import Count, Max
from django.http import HttpResponse
from django.shortcuts import redirect
from django.utils import timezone
from django.views.generic import TemplateView

from control_guardias.models import Guardia, MedicoGuardia
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

        hoy = timezone.now().date()
        hora_actual = timezone.now().time()

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
            context.update(self.get_guardias_context(hoy, hora_actual))
        except Exception as e:
            print(f"❌ Error en guardias: {e}")
            import traceback
            traceback.print_exc()
            context.update({
                'nombre_medico_guardia': "Error al cargar",
                'franja_horaria_guardia': f"Error: {str(e)}",
                'nombre_proximo_medico': "",
                'fecha_proxima_guardia': "",
            })

        return context

    # ------------------------ EVENTOS ------------------------

    def get_eventos_context(self):
        eventos_abiertos = EventoServicio.objects.filter(estado='abierto')
        return {
            'cantidad_eventos_abiertos': eventos_abiertos.count(),
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

    def get_guardias_context(self, fecha_hoy, hora_actual):
        # Buscar guardia activa
        guardia_activa = self.buscar_guardia_activa(fecha_hoy, hora_actual, cubierta=True)

        if guardia_activa and guardia_activa.medico:
            nombre_guardia = self.formatear_nombre_medico(guardia_activa.medico)
            franja = guardia_activa.get_franja_horaria_display()
            if guardia_activa.fecha == fecha_hoy - timedelta(days=1):
                franja += " (continúa)"
        else:
            # Buscar guardia sin cubrir
            guardia_activa = self.buscar_guardia_activa(fecha_hoy, hora_actual, cubierta=False)
            if guardia_activa:
                nombre_guardia = "⚠️ Sin cubrir"
                franja = guardia_activa.get_franja_horaria_display()
            else:
                # Fallback: médico más activo del día
                fallback = RegistroEstudiosPorMedico.objects.filter(
                    fecha_registro__date=fecha_hoy
                ).values('medico').annotate(count=Count('id')).order_by('-count').first()
                
                nombre_guardia = "No asignado"
                franja = ""
                
                if fallback:
                    try:
                        user = get_user_model().objects.get(id=fallback['medico'])
                        if hasattr(user, 'user') and user.user:
                            nombre_guardia = self.formatear_nombre_medico(user, " (Más activo)")
                        else:
                            nombre_completo = user.get_full_name() if user.get_full_name() else user.username
                            nombre_guardia = f"Dr. {nombre_completo} (Más activo)"
                        franja = "Actividad del día"
                    except Exception:
                        pass

        # Próxima guardia
        proxima = self.buscar_proxima_guardia(guardia_activa, fecha_hoy)
        if proxima and proxima.medico:
            nombre_proximo = self.formatear_nombre_medico(proxima.medico)
            fecha_proxima = self.formatear_fecha_guardia(proxima, fecha_hoy)
        else:
            nombre_proximo = ""
            fecha_proxima = ""

        return {
            'nombre_medico_guardia': nombre_guardia,
            'franja_horaria_guardia': franja,
            'nombre_proximo_medico': nombre_proximo,
            'fecha_proxima_guardia': fecha_proxima,
        }

    def esta_guardia_activa(self, g, hora, fecha):
        if g.franja_horaria == 'DIA_COMPLETO':
            return True
        elif g.franja_horaria in ['DIA', 'DIA_FIN_SEMANA']:
            return 8 <= hora.hour < 20
        elif g.franja_horaria in ['NOCHE', 'NOCHE_FIN_SEMANA']:
            # Guardia de hoy: activa desde las 20:00
            if g.fecha == fecha:
                return hora.hour >= 20
            # Guardia de ayer: activa hasta las 08:00
            else:
                return hora.hour < 8
        return False

    def buscar_guardia_activa(self, fecha, hora, cubierta=True):
        fecha_ayer = fecha - timedelta(days=1)
        guardias = Guardia.objects.filter(fecha__in=[fecha, fecha_ayer], cubierta=cubierta).select_related('medico')
        
        for g in guardias:
            if self.esta_guardia_activa(g, hora, fecha):
                return g
        
        return None

    def buscar_proxima_guardia(self, actual, fecha):
        inicio = actual.fecha + timedelta(days=1) if actual else fecha
        for i in range(7):
            dia = inicio + timedelta(days=i)
            guardias = Guardia.objects.filter(fecha=dia, cubierta=True).select_related('medico')
            for g in guardias:
                if not actual or g.fecha != actual.fecha or g.franja_horaria != actual.franja_horaria:
                    return g
        return None

    def formatear_nombre_medico(self, medico_obj, sufijo=""):
        # Si es un MedicoGuardia
        if hasattr(medico_obj, 'user') and medico_obj.user:
            nombre = medico_obj.user.get_full_name()
            if nombre.strip():
                return f"Dr. {nombre}{sufijo}"
            else:
                return f"Dr. {medico_obj.user.username}{sufijo}"
        # Si es un User directamente
        elif hasattr(medico_obj, 'get_full_name'):
            nombre = medico_obj.get_full_name()
            if nombre.strip():
                return f"Dr. {nombre}{sufijo}"
            else:
                return f"Dr. {medico_obj.username}{sufijo}"
        # Fallback
        else:
            return f"Dr. {str(medico_obj)}{sufijo}"

    def formatear_fecha_guardia(self, guardia, hoy):
        if guardia.fecha == hoy:
            return f"Hoy • {guardia.get_franja_horaria_display()}"
        elif guardia.fecha == hoy + timedelta(days=1):
            return f"Mañana • {guardia.get_franja_horaria_display()}"
        return f"{guardia.fecha.strftime('%d/%m')} • {guardia.get_franja_horaria_display()}"

    def crear_guardias_prueba(self, fecha_hoy):
        """Crea guardias de prueba si no existen"""
        try:
            from accounts.models import CustomUser
            
            # Verificar si ya hay guardias para hoy
            if Guardia.objects.filter(fecha=fecha_hoy).exists():
                return
            
            # Buscar o crear un médico de prueba
            usuario_admin = CustomUser.objects.filter(is_superuser=True).first()
            if not usuario_admin:
                return
                
            medico_prueba, created = MedicoGuardia.objects.get_or_create(
                user=usuario_admin,
                defaults={
                    'dni': '12345678',
                    'matricula': '123456'
                }
            )
            
            # Crear guardia de día para hoy
            Guardia.objects.create(
                fecha=fecha_hoy,
                franja_horaria='DIA',
                cubierta=True,
                medico=medico_prueba
            )
            
            # Crear guardia nocturna para hoy
            Guardia.objects.create(
                fecha=fecha_hoy,
                franja_horaria='NOCHE',
                cubierta=True,
                medico=medico_prueba
            )
            
        except Exception:
            pass
