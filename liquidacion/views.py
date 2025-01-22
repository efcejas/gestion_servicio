from django.shortcuts import render
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, TemplateView
from django.contrib.messages.views import SuccessMessageMixin
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Sum
from .models import Medico, Estudios, RegistroEstudiosPorMedico
from .forms import RegistroEstudiosPorMedicoCreateViewForm, MedicoCreateViewForm

class MedicoCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = Medico
    form_class = MedicoCreateViewForm
    template_name = 'liquidacion/medico_form.html'
    success_url = reverse_lazy('medico_list')  # Usa reverse_lazy para resolver el nombre de la URL
    # success_message = "El médico fue registrado exitosamente"  # Mensaje de éxito

class MedicoListView(LoginRequiredMixin, ListView):
    model = Medico
    template_name = 'liquidacion/medico_list.html'
    context_object_name = 'medicos'  # Asegúrate de usar el nombre correcto en la plantilla

class EstudiosCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = Estudios
    fields = ['nombre', 'tipo', 'conteo_regiones']
    template_name = 'liquidacion/estudios_form.html'
    success_url = reverse_lazy('estudios_list')  # Usa reverse_lazy para resolver el nombre de la URL
    success_message = "El estudio fue registrado exitosamente"  # Mensaje de éxito

class EstudiosListView(LoginRequiredMixin, ListView):
    model = Estudios
    template_name = 'liquidacion/estudios_list.html'
    context_object_name = 'estudios'  # Asegúrate de usar el nombre correcto en la plantilla

class RegistroEstudiosPorMedicoCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = RegistroEstudiosPorMedico
    form_class = RegistroEstudiosPorMedicoCreateViewForm
    template_name = 'liquidacion/registroestudios_form.html'
    success_url = reverse_lazy('registroestudios_nuevo')  # Redirigir a la misma vista por defecto
    success_message = "Registro realizado exitosamente"  # Mensaje de éxito

class RegistroEstudiosPorMedicoListView(LoginRequiredMixin, TemplateView):
    template_name = 'liquidacion/registroestudios_list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Obtener todos los médicos
        medicos = Medico.objects.all()

        # Calcular datos por médico
        medico_data = []
        for medico in medicos:
            registros = RegistroEstudiosPorMedico.objects.filter(medico=medico).prefetch_related('estudio')

            # Calcular el total de regiones para el médico
            total_regiones = registros.aggregate(
                total=Sum('estudio__conteo_regiones')
            )['total'] or 0

            # Reunir información en un diccionario por médico
            medico_data.append({
                'medico': medico,
                'registros': registros,
                'total_regiones': total_regiones,
            })

        # Agregar información al contexto
        context['medico_data'] = medico_data
        return context
