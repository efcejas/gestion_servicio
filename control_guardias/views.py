from django.shortcuts import render
from django.views.generic import ListView, TemplateView
from .models import Guardia, MedicoGuardia
from django.utils import timezone
from django.db.models import Count, Sum
from .forms import FiltroGuardiasPorMedicoForm

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

        # Instanciar el formulario con los datos GET
        form = FiltroGuardiasPorMedicoForm(self.request.GET or None)
        context['form'] = form

        if form.is_valid():
            medico = form.cleaned_data.get('medico')
            mes = form.cleaned_data.get('mes')
            año = form.cleaned_data.get('año')

            # Filtrar guardias según los criterios del formulario
            guardias = Guardia.objects.filter(cubierta=True)
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
