from datetime import date

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.http import JsonResponse
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.generic import ListView, TemplateView
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.http import HttpResponse

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


class FullCalendarView(TemplateView):
    template_name = 'control_guardias/fullcalendar_view.html'


class TailwindCalendarView(TemplateView):
    template_name = 'control_guardias/fullcalendar_tw.html'


class GuardiaEventsView(View):
    def get(self, request):
        eventos = []

        guardias = Guardia.objects.all()

        for g in guardias:
            cubierta = bool(g.cubierta)
            medico_nombre = g.medico.user.get_full_name() if getattr(g.medico, 'user', None) else 'Sin asignar'
            base_evento = {
                'id': str(g.pk),
                'start': g.fecha.isoformat(),
                'allDay': True,
                'display': 'block',
                'extendedProps': {
                    'cubierta': cubierta,
                    'medico': medico_nombre,
                    'franja': g.get_franja_horaria_display(),
                    'franja_key': g.franja_horaria,
                    'editUrl': reverse('control_guardias:editar_guardia', args=[g.pk]),
                    'deleteUrl': reverse('control_guardias:eliminar_guardia', args=[g.pk]),
                }
            }

            if cubierta and g.medico and g.medico.user:
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


class GuardiaUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    model = Guardia
    form_class = GuardiaForm
    template_name = 'control_guardias/editar_guardia.html'
    success_url = reverse_lazy('control_guardias:calendario_guardias_full_tw')
    success_message = "Guardia actualizada con éxito."


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


