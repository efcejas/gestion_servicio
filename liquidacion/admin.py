from django.contrib import admin
from .models import Medico, Estudio, RegistroDiario, DetalleRegistro, TarifaEstudio, Paciente

@admin.register(Medico)
class MedicoAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'apellido', 'dni', 'matricula']

@admin.register(Estudio)
class EstudioAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'modalidad', 'regiones', 'valor']

class DetalleRegistroInline(admin.TabularInline):
    model = DetalleRegistro
    extra = 1

@admin.register(Paciente)
class PacienteAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'apellido', 'dni']
    search_fields = ['nombre', 'apellido', 'dni']


@admin.register(RegistroDiario)
class RegistroDiarioAdmin(admin.ModelAdmin):
    list_display = ['medico', 'paciente', 'fecha', 'total_regiones']
    inlines = [DetalleRegistroInline]
    search_fields = ['paciente__nombre', 'paciente__apellido', 'medico__nombre']
    list_filter = ['fecha']

@admin.register(TarifaEstudio)
class TarifaEstudioAdmin(admin.ModelAdmin):
    list_display = ['modalidad', 'valor_por_region']
