from django.contrib import admin
from .models import MedicoGuardia, Guardia

@admin.register(MedicoGuardia)
class MedicoGuardiaAdmin(admin.ModelAdmin):
    list_display = ('get_nombre_completo', 'dni', 'matricula', 'user')
    search_fields = ('user__first_name', 'user__last_name', 'dni', 'matricula')
    list_filter = ('user',)

    def get_nombre_completo(self, obj):
        return obj.user.get_full_name() if obj.user else "Sin usuario"
    get_nombre_completo.short_description = 'Nombre completo'

@admin.register(Guardia)
class GuardiaAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'franja_horaria', 'cubierta', 'get_medico')
    search_fields = ('medico__user__first_name', 'medico__user__last_name')
    list_filter = ('franja_horaria', 'cubierta')

    def get_medico(self, obj):
        return obj.medico.user.get_full_name() if obj.medico and obj.medico.user else "Sin usuario"
    get_medico.short_description = 'Médico'