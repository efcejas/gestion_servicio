from django.contrib import admin
from .models import Paciente, OrdenMedica, RegistroAtencion, Estudio

@admin.register(Paciente)
class PacienteAdmin(admin.ModelAdmin):
    list_display = ['apellido', 'nombre', 'dni', 'telefono']
    search_fields = ['apellido', 'dni']

@admin.register(Estudio)
class EstudioAdmin(admin.ModelAdmin):
    list_display = ['nombre']
    search_fields = ['nombre']


@admin.register(OrdenMedica)
class OrdenMedicaAdmin(admin.ModelAdmin):
    list_display = ['paciente', 'fecha_emision']
    search_fields = ['paciente__apellido', 'fecha_emision']


@admin.register(RegistroAtencion)
class RegistroAtencionAdmin(admin.ModelAdmin):
    list_display = ['paciente', 'medico', 'fecha_atencion']
    search_fields = ['paciente__apellido', 'medico__username', 'fecha_atencion']
