from django.shortcuts import render
from django.urls import reverse_lazy
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.messages.views import SuccessMessageMixin
from .models import Medico, Estudios
from django.contrib.auth.mixins import LoginRequiredMixin

class MedicoCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = Medico
    fields = ['nombre', 'apellido', 'matricula']
    template_name = 'liquidacion/medico_form.html'
    success_url = '/'
    # success_message = "El médico fue registrado exitosamente"  # Mensaje de éxito

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