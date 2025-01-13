from django.contrib import admin
from .models import Estudio, RegistroDiario, DetalleRegistro, Medico, Paciente

@admin.register(Medico)
class MedicoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'apellido', 'dni', 'matricula')
    search_fields = ('nombre', 'apellido', 'dni', 'matricula')

@admin.register(Paciente)
class PacienteAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'apellido', 'dni')
    search_fields = ('nombre', 'apellido', 'dni')

@admin.register(Estudio)
class EstudioAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'regiones')
    search_fields = ('nombre',)


@admin.register(RegistroDiario)
class RegistroDiarioAdmin(admin.ModelAdmin):
    list_display = ('medico', 'paciente', 'fecha', 'total_regiones')
    list_filter = ('fecha',)
    search_fields = ('medico__usuario__first_name', 'paciente__nombre')

class DetalleRegistroInline(admin.TabularInline):
    model = DetalleRegistro
    extra = 1

@admin.register(DetalleRegistro)
class DetalleRegistroAdmin(admin.ModelAdmin):
    list_display = ('registro', 'estudio', 'cantidad')

