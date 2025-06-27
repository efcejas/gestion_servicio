import calendar
from datetime import date

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.http import JsonResponse
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.generic import ListView, TemplateView
from django.views.generic.edit import CreateView

from .forms import FiltroGuardiasPorMedicoForm, FiltroMisGuardiasForm, GuardiaForm
from .models import Guardia

# Esto lo ven usuarios sin restricciones


class GuardiaListView(ListView):
    model = Guardia
    template_name = 'control_guardias/lista_guardias.html'
    context_object_name = 'guardias'
    ordering = ['fecha']

    def get_queryset(self):
        return Guardia.objects.filter(fecha__gte=timezone.now()).order_by('fecha')

# Esto lo ven usuarios sin logueo


class ResumenGuardiasView(TemplateView):
    template_name = 'control_guardias/resumen_guardias.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Instanciar el formulario con los datos GET
        form = FiltroGuardiasPorMedicoForm(self.request.GET or None)
        context['form'] = form

        if form.is_valid():
            medico = form.cleaned_data.get('medico')
            mes = form.cleaned_data.get('mes')
            año = form.cleaned_data.get('año')

            # Filtrar guardias según los criterios del formulario
            guardias = Guardia.objects.filter(
                cubierta=True, fecha__lte=timezone.now())
            if medico:
                guardias = guardias.filter(medico=medico)
            if mes and año:
                guardias = guardias.filter(fecha__year=año, fecha__month=mes)

            # Calcular el resumen por médico
            franja_horaria_horas = {
                'NOCHE': 12, 'DIA_COMPLETO': 24, 'DIA': 12,
                'NOCHE_FIN_SEMANA': 12, 'DIA_FIN_SEMANA': 12
            }
            resumen_guardias = {}
            for guardia in guardias:
                medico = guardia.medico
                horas = franja_horaria_horas.get(guardia.franja_horaria, 0)

                if medico not in resumen_guardias:
                    resumen_guardias[medico] = {
                        'total_guardias': 0,
                        'total_horas': 0,
                        'detalles': []
                    }

                resumen_guardias[medico]['total_guardias'] += 1
                resumen_guardias[medico]['total_horas'] += horas
                resumen_guardias[medico]['detalles'].append({
                    'fecha': guardia.fecha,
                    'franja_horaria': guardia.get_franja_horaria_display(),
                    'horas': horas
                })

            # Ordenar los detalles por fecha en cada médico
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


class FullCalendarView(TemplateView):
    template_name = 'control_guardias/fullcalendar_view.html'


@method_decorator(login_required, name='dispatch')
class GuardiaEventsView(View):
    def get(self, request):
        eventos = []

        guardias = Guardia.objects.all()

        for g in guardias:
            if g.cubierta and g.medico and g.medico.user:
                eventos.append({
                    'title': f'🕒 {g.get_franja_horaria_display()}\n👨‍⚕️ {g.medico.user.get_full_name()}',
                    'start': g.fecha.isoformat(),
                    'backgroundColor': '#d9eaff',
                    'borderColor': '#164569',
                    'textColor': '#000',
                    'display': 'block',
                })
            else:
                eventos.append({
                    'title': '⚠️ Guardia no cubierta',
                    'start': g.fecha.isoformat(),
                    'backgroundColor': '#fff3cd',
                    'borderColor': '#ffc107',
                    'textColor': '#000',
                    'display': 'block',
                })

        return JsonResponse(eventos, safe=False)


class GuardiaCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = Guardia
    form_class = GuardiaForm
    template_name = 'control_guardias/crear_guardia.html'
    success_url = reverse_lazy('calendario_guardias_full')
    success_message = "Guardia creada con éxito."

    def get_initial(self):
        initial = super().get_initial()
        fecha_param = self.request.GET.get('fecha')
        if fecha_param:
            initial['fecha'] = fecha_param
        return initial

# control_guardias/views.py


class CalendarioGuardiasView(TemplateView):
    template_name = 'control_guardias/calendario_guardias.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Obtener año y mes desde la URL o usar actuales
        year = int(self.request.GET.get('year', timezone.now().year))
        month = int(self.request.GET.get('month', timezone.now().month))

        # Calcular mes anterior y siguiente
        if month == 1:
            prev_month = 12
            prev_year = year - 1
        else:
            prev_month = month - 1
            prev_year = year

        if month == 12:
            next_month = 1
            next_year = year + 1
        else:
            next_month = month + 1
            next_year = year

        # Generar los días del calendario
        cal = calendar.Calendar(firstweekday=0)  # lunes=0
        dias_mes = list(cal.itermonthdates(year, month))

        # Obtener guardias del mes
        guardias = Guardia.objects.filter(fecha__year=year, fecha__month=month)

        # Agrupar guardias por día
        guardias_por_dia = {}
        for g in guardias:
            guardias_por_dia.setdefault(g.fecha, []).append(g)

        context.update({
            'dias_mes': dias_mes,
            'guardias_por_dia': guardias_por_dia,
            'year': year,
            'month': month,
            'prev_year': prev_year,
            'prev_month': prev_month,
            'next_year': next_year,
            'next_month': next_month,
        })
        return context
