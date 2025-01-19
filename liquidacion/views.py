from django.shortcuts import render
from django.urls import reverse_lazy
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from .models import Medico, Estudios, RegistroEstudiosPorMedico
from django.contrib.auth.mixins import LoginRequiredMixin
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