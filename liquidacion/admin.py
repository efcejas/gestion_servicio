from django.contrib import admin
from .models import Medico, Estudios, RegistroEstudiosPorMedico, RegistroProcedimientosIntervensionismo

@admin.register(Medico)
class MedicoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'apellido', 'matricula')
    search_fields = ('nombre', 'apellido', 'matricula')
    list_filter = ('nombre', 'apellido', 'matricula')
    ordering = ('nombre', 'apellido', 'matricula')

@admin.register(Estudios)
class EstudiosAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'tipo', 'conteo_regiones')
    search_fields = ('nombre', 'tipo', 'conteo_regiones')
    list_filter = ('nombre', 'tipo', 'conteo_regiones')
    ordering = ('nombre', 'tipo', 'conteo_regiones')

class EstudiosAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'tipo', 'conteo_regiones')
    search_fields = ('nombre', 'tipo', 'conteo_regiones')
    list_filter = ('nombre', 'tipo', 'conteo_regiones')
    ordering = ('nombre', 'tipo', 'conteo_regiones')

@admin.register(RegistroEstudiosPorMedico)
class RegistroEstudiosPorMedicoAdmin(admin.ModelAdmin):
    list_display = ('medico', 'nombre_paciente', 'apellido_paciente', 'dni_paciente', 
                    'fecha_registro', 'fecha_del_informe', 'mostrar_total_regiones')
    search_fields = ('medico__nombre', 'medico__apellido', 'nombre_paciente', 
                     'apellido_paciente', 'dni_paciente', 'fecha_registro', 'fecha_del_informe')
    list_filter = ('medico', 'fecha_registro', 'fecha_del_informe', 'estudio')
    ordering = ('medico', 'fecha_registro', 'fecha_del_informe')

    def mostrar_total_regiones(self, obj):
        """
        Muestra el total de regiones en el admin.
        """
        return obj.total_regiones()

    mostrar_total_regiones.short_description = 'Total de regiones'

@admin.register(RegistroProcedimientosIntervensionismo)
class RegistroProcedimientosIntervensionismoAdmin(admin.ModelAdmin):
    list_display = ('medico', 'nombre_paciente', 'apellido_paciente', 'dni_paciente', 'fecha_registro', 'fecha_del_procedimiento', 'procedimiento')
    search_fields = ('nombre_paciente', 'apellido_paciente', 'dni_paciente', 'procedimiento')
    list_filter = ('fecha_registro', 'fecha_del_procedimiento', 'medico')
