from datetime import date

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.http import JsonResponse
from django.db import OperationalError
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.generic import ListView, TemplateView
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.http import HttpResponse
import openpyxl
from openpyxl.styles import Alignment, Font
from django.contrib.auth import get_user_model

from .forms import FiltroGuardiasPorMedicoForm, FiltroMisGuardiasForm, GuardiaForm
from .models import Guardia

# Redirige a la nueva URL del portal público
class GuardiaListView(View):
    """
    Vista heredada que redirige a la nueva URL del portal público.
    Mantiene compatibilidad con enlaces antiguos.
    """
    def get(self, request, *args, **kwargs):
        return redirect('control_guardias:portal_coberturas_semanal', permanent=True)


class ResumenGuardiasView(TemplateView):
    template_name = 'control_guardias/resumen_guardias.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        form = FiltroGuardiasPorMedicoForm(self.request.GET or None)
        context['form'] = form

        if form.is_valid():
            medico = form.cleaned_data.get('medico')
            mes = form.cleaned_data.get('mes')
            año = form.cleaned_data.get('año')

            guardias = Guardia.objects.filter(cubierta=True, fecha__lte=timezone.now())
            if medico:
                guardias = guardias.filter(medico=medico)
            if mes and año:
                guardias = guardias.filter(fecha__year=año, fecha__month=mes)

            franja_horaria_horas = {
                'NOCHE': 12, 'DIA_COMPLETO': 24, 'DIA': 12,
                'NOCHE_FIN_SEMANA': 12, 'DIA_FIN_SEMANA': 12
            }
            resumen_guardias = {}
            for guardia in guardias:
                medico_obj = guardia.medico
                horas = franja_horaria_horas.get(guardia.franja_horaria, 0)

                if medico_obj not in resumen_guardias:
                    resumen_guardias[medico_obj] = {
                        'total_guardias': 0,
                        'total_horas': 0,
                        'detalles': []
                    }

                resumen_guardias[medico_obj]['total_guardias'] += 1
                resumen_guardias[medico_obj]['total_horas'] += horas
                resumen_guardias[medico_obj]['detalles'].append({
                    'fecha': guardia.fecha,
                    'franja_horaria': guardia.get_franja_horaria_display(),
                    'horas': horas
                })

            for medico_data in resumen_guardias.values():
                medico_data['detalles'].sort(key=lambda x: x['fecha'])

            context['resumen_guardias'] = resumen_guardias

        return context

# Quiero crear la vista que le permita ver a cada usuario que hace guardias, las que tiene asignadas y las que ha hecho


class MisGuardiasView(LoginRequiredMixin, ListView):
    model = Guardia
    template_name = 'control_guardias/mis_guardias.html'
    context_object_name = 'mis_guardias'
    login_url = 'login'

    def get_queryset(self):
        return Guardia.objects.filter(medico__user=self.request.user).order_by('fecha')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        hoy = timezone.now().date()
        queryset = self.get_queryset()

        # Procesar el formulario de filtro
        form = FiltroMisGuardiasForm(self.request.GET or None)
        if form.is_valid():
            mes = form.cleaned_data.get('mes') or hoy.month
            año = form.cleaned_data.get('año') or hoy.year
        else:
            mes = hoy.month
            año = hoy.year

        # Guardias pasadas del mes/año seleccionado
        guardias_mes = queryset.filter(
            fecha__lt=hoy,
            fecha__month=mes,
            fecha__year=año
        ).order_by('-fecha')

        context['guardias_mes'] = guardias_mes
        context['mes_actual'] = int(mes)
        context['año_actual'] = int(año)
        context['filtro_form'] = form

        # Próximas guardias (sin filtro)
        context['proximas_guardias'] = queryset.filter(fecha__gte=hoy)

        return context

# Esto es de uso exclusivo de los administradores


class TailwindCalendarView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'control_guardias/fullcalendar_tw.html'
    login_url = 'login'
    
    def test_func(self):
        """Solo permite acceso a superusuarios"""
        return self.request.user.is_superuser


class GuardiaEventsView(View):
    def get(self, request):
        eventos = []

        # Filtrado por rango de fechas si FullCalendar manda start/end
        start_param = request.GET.get('start')
        end_param = request.GET.get('end')
        guardias_qs = Guardia.objects.all()
        if start_param and end_param:
            # FullCalendar manda ISO con posible zona: YYYY-MM-DDTHH:MM:SS... -> nos quedamos con la fecha
            try:
                start_date = start_param.split('T')[0]
                end_date = end_param.split('T')[0]
                guardias_qs = guardias_qs.filter(fecha__gte=start_date, fecha__lte=end_date)
            except ValueError:
                pass  # si algo falla, ignoramos y devolvemos todo

        # Optimizar acceso a medico y su user
        guardias_qs = guardias_qs.select_related('medico__user')

        try:
            for g in guardias_qs:
                medico_obj = g.medico
                user_obj = getattr(medico_obj, 'user', None) if medico_obj else None
                medico_nombre = user_obj.get_full_name() if user_obj else ''

                # Una guardia realmente "cubierta" sólo si tiene bandera cubierta y un médico asociado con user
                cubierta_real = bool(g.cubierta and medico_obj and user_obj)

                base_evento = {
                    'id': str(g.pk),
                    'start': g.fecha.isoformat(),
                    'allDay': True,
                    'display': 'block',
                    'extendedProps': {
                        'cubierta': cubierta_real,
                        'medico': medico_nombre if medico_nombre else 'Sin asignar',
                        'franja': g.get_franja_horaria_display(),
                        'franja_key': g.franja_horaria,
                        'editUrl': reverse('control_guardias:editar_guardia', args=[g.pk]),
                        'deleteUrl': reverse('control_guardias:eliminar_guardia', args=[g.pk]),
                    }
                }

                if cubierta_real:
                    base_evento.update({
                        'title': f'🕒 {g.get_franja_horaria_display()}\n👨‍⚕️ {medico_nombre}',
                        'backgroundColor': '#d9eaff',
                        'borderColor': '#164569',
                        'textColor': '#000',
                    })
                else:
                    base_evento.update({
                        'title': '⚠️ Guardia no cubierta',
                        'backgroundColor': '#fff3cd',
                        'borderColor': '#ffc107',
                        'textColor': '#000',
                    })

                eventos.append(base_evento)
        except OperationalError:
            # Si hubo un problema de conexión con la BD, devolvemos lista vacía con un flag
            return JsonResponse({'error': 'db_connection', 'events': []}, status=500)

        return JsonResponse(eventos, safe=False)


class GuardiaCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = Guardia
    form_class = GuardiaForm
    template_name = 'control_guardias/crear_guardia.html'
    success_url = reverse_lazy('control_guardias:calendario_guardias_full_tw')
    success_message = "Guardia creada con éxito."

    def get_initial(self):
        initial = super().get_initial()
        fecha_param = self.request.GET.get('fecha')
        if fecha_param:
            initial['fecha'] = fecha_param
        return initial

    def form_valid(self, form):
        response = super().form_valid(form)
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return HttpResponse(status=200)
        return response

    def form_invalid(self, form):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            # Devolver el HTML con errores pero con status 400 para que el JS no cierre el modal
            return self.render_to_response(self.get_context_data(form=form), status=400)
        return super().form_invalid(form)


class GuardiaUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    model = Guardia
    form_class = GuardiaForm
    template_name = 'control_guardias/editar_guardia.html'
    success_url = reverse_lazy('control_guardias:calendario_guardias_full_tw')
    success_message = "Guardia actualizada con éxito."

    def form_invalid(self, form):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return self.render_to_response(self.get_context_data(form=form), status=400)
        return super().form_invalid(form)


class GuardiaDeleteView(LoginRequiredMixin, DeleteView):
    model = Guardia
    template_name = 'control_guardias/guardia_confirm_delete.html'
    success_url = reverse_lazy('control_guardias:calendario_guardias_full_tw')

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.delete()
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return HttpResponse(status=200)
        return super().delete(request, *args, **kwargs)


# Vista pública del portal de guardias (sin autenticación requerida)
class CoberturasSemanalesPortalView(TemplateView):
    """
    Vista pública para mostrar las coberturas de guardias semanales.
    Accesible sin autenticación para permitir que la jefa de guardia
    y otros usuarios vean quién está de guardia.
    """
    template_name = 'control_guardias/coberturas_semanal_portal.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Obtener todas las guardias futuras ordenadas por fecha
        context['guardias'] = Guardia.objects.filter(
            fecha__gte=timezone.now()
        ).select_related('medico__user').order_by('fecha')
        return context


class ResumenGuardiasPortalView(TemplateView):
    """
    Vista pública para mostrar el resumen de guardias por médico.
    Accesible desde el portal de liquidación sin autenticación.
    """
    template_name = 'control_guardias/resumen_guardias_portal.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        form = FiltroGuardiasPorMedicoForm(self.request.GET or None)
        context['form'] = form

        if form.is_valid():
            medico = form.cleaned_data.get('medico')
            mes = form.cleaned_data.get('mes')
            año = form.cleaned_data.get('año')

            guardias = Guardia.objects.filter(cubierta=True, fecha__lte=timezone.now())
            if medico:
                guardias = guardias.filter(medico=medico)
            if mes and año:
                guardias = guardias.filter(fecha__year=año, fecha__month=mes)

            franja_horaria_horas = {
                'NOCHE': 12, 'DIA_COMPLETO': 24, 'DIA': 12,
                'NOCHE_FIN_SEMANA': 12, 'DIA_FIN_SEMANA': 12
            }
            resumen_guardias = {}
            for guardia in guardias:
                medico_obj = guardia.medico
                horas = franja_horaria_horas.get(guardia.franja_horaria, 0)

                if medico_obj not in resumen_guardias:
                    resumen_guardias[medico_obj] = {
                        'total_guardias': 0,
                        'total_horas': 0,
                        'detalles': []
                    }

                resumen_guardias[medico_obj]['total_guardias'] += 1
                resumen_guardias[medico_obj]['total_horas'] += horas
                resumen_guardias[medico_obj]['detalles'].append({
                    'fecha': guardia.fecha,
                    'franja_horaria': guardia.get_franja_horaria_display(),
                    'horas': horas
                })

            for medico_data in resumen_guardias.values():
                medico_data['detalles'].sort(key=lambda x: x['fecha'])

            context['resumen_guardias'] = resumen_guardias

        return context


def exportar_excel_guardias(request):
    """
    Vista para exportar las guardias por médico a un archivo Excel.
    Aplica los mismos filtros que ResumenGuardiasPortalView.
    """
    User = get_user_model()
    
    # Obtener los filtros de la URL
    medico_id = request.GET.get('medico')
    mes = request.GET.get('mes')
    año = request.GET.get('año')
    
    # Filtrar guardias (misma lógica que en ResumenGuardiasPortalView)
    guardias = Guardia.objects.filter(cubierta=True, fecha__lte=timezone.now())
    
    if medico_id:
        guardias = guardias.filter(medico_id=medico_id)
        medico = User.objects.get(id=medico_id)
        nombre_medico = f"{medico.first_name}_{medico.last_name}"
    else:
        nombre_medico = "todos_los_medicos"
    
    if mes and año:
        guardias = guardias.filter(fecha__year=int(año), fecha__month=int(mes))
    
    # Mapeo de franjas horarias a horas
    franja_horaria_horas = {
        'NOCHE': 12, 'DIA_COMPLETO': 24, 'DIA': 12,
        'NOCHE_FIN_SEMANA': 12, 'DIA_FIN_SEMANA': 12
    }
    
    # Calcular resumen por médico
    resumen_guardias = {}
    for guardia in guardias:
        medico_obj = guardia.medico
        horas = franja_horaria_horas.get(guardia.franja_horaria, 0)
        
        if medico_obj not in resumen_guardias:
            resumen_guardias[medico_obj] = {
                'total_guardias': 0,
                'total_horas': 0,
                'detalles': []
            }
        
        resumen_guardias[medico_obj]['total_guardias'] += 1
        resumen_guardias[medico_obj]['total_horas'] += horas
        resumen_guardias[medico_obj]['detalles'].append({
            'fecha': guardia.fecha,
            'franja_horaria': guardia.get_franja_horaria_display(),
            'horas': horas
        })
    
    # Ordenar detalles por fecha
    for medico_data in resumen_guardias.values():
        medico_data['detalles'].sort(key=lambda x: x['fecha'])
    
    # Crear un libro de Excel
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Guardias por Médico"
    
    # Establecer la fila de encabezados
    headers = [
        "Médico", "Total Guardias", "Total Horas", "Fecha", "Franja Horaria", "Horas"
    ]
    ws.append(headers)
    
    # Aplicar estilo a los encabezados
    for cell in ws[1]:
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal="center", vertical="center")
    
    # Agregar los datos
    for medico_obj, data in resumen_guardias.items():
        nombre_completo = f"Dr/a. {medico_obj.user.get_full_name()}"
        total_guardias = data['total_guardias']
        total_horas = data['total_horas']
        
        # Primera fila con los totales y el primer detalle
        if data['detalles']:
            primer_detalle = data['detalles'][0]
            ws.append([
                nombre_completo,
                total_guardias,
                total_horas,
                primer_detalle['fecha'].strftime("%d/%m/%Y"),
                primer_detalle['franja_horaria'],
                primer_detalle['horas']
            ])
            
            # Filas adicionales con los demás detalles
            for detalle in data['detalles'][1:]:
                ws.append([
                    "",  # Médico (vacío en filas adicionales)
                    "",  # Total Guardias (vacío)
                    "",  # Total Horas (vacío)
                    detalle['fecha'].strftime("%d/%m/%Y"),
                    detalle['franja_horaria'],
                    detalle['horas']
                ])
    
    # Ajustar ancho de columnas automáticamente
    for column in ws.columns:
        max_length = 0
        column_letter = column[0].column_letter
        for cell in column:
            try:
                if cell.value:
                    max_length = max(max_length, len(str(cell.value)))
            except:
                pass
        adjusted_width = min(max_length + 2, 50)
        ws.column_dimensions[column_letter].width = adjusted_width
    
    # Preparar respuesta HTTP
    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = f'attachment; filename="guardias_{nombre_medico}.xlsx"'
    wb.save(response)
    return response
