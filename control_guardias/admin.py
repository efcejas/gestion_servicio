from django.contrib import admin
from .models import Guardia, MedicoGuardia

@admin.register(MedicoGuardia)
class MedicoGuardiaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'apellido', 'dni', 'matricula')
    search_fields = ('nombre', 'apellido', 'dni', 'matricula')

class GuardiaAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'franja_horaria', 'cubierta', 'medico')
    list_filter = ('fecha', 'franja_horaria', 'cubierta')
    search_fields = ('medico',)

admin.site.register(Guardia, GuardiaAdmin)