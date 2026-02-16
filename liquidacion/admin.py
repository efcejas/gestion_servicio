from django.contrib import admin
from .models import Estudios, RegistroEstudiosPorMedico, DiaSinPacientes

# [ELIMINADO - 16 de febrero 2026]
# Import de RegistroProcedimientosIntervensionismo eliminado
# En Colegiales, procedimientos se registran como Estudios

@admin.register(Estudios)
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
    
@admin.register(DiaSinPacientes)
class DiaSinPacientesAdmin(admin.ModelAdmin):
    list_display = ('medico', 'fecha', 'fecha_creacion')
    list_filter = ('fecha', 'medico')
    search_fields = ('medico__first_name', 'medico__last_name', 'fecha')

# [ANULADO - 16 de febrero 2026]
# RegistroProcedimientosIntervensionismoAdmin eliminado
# Razón: En Colegiales no se usa, se registra como Estudios
# Ver liquidacion_backup_completo_2026-02-16.json para datos históricos
