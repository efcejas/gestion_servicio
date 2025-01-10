from django.contrib import admin
from .models import personal_medico, FranjaHoraria, Disponibilidad

class PersonalMedicoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'apellido', 'dni', 'telefono', 'email', 'matricula')
    search_fields = ('nombre', 'apellido', 'dni', 'matricula')

class FranjaHorariaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'hora_inicio', 'hora_fin')
    search_fields = ('nombre',)

class DisponibilidadAdmin(admin.ModelAdmin):
    list_display = ('medico', 'dia_semana', 'franja_horaria', 'modalidad', 'servicio')
    list_filter = ('dia_semana', 'franja_horaria', 'medico', 'modalidad', 'servicio')
    search_fields = ('medico__nombre', 'medico__apellido')

admin.site.register(personal_medico, PersonalMedicoAdmin)
admin.site.register(FranjaHoraria, FranjaHorariaAdmin)
admin.site.register(Disponibilidad, DisponibilidadAdmin)