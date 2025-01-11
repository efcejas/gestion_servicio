from django.contrib import admin
from .models import Medicos

@admin.register(Medicos)
class MedicosAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'apellido', 'dni', 'matricula', 'email', 'telefono')
    search_fields = ('nombre', 'apellido', 'dni', 'matricula', 'email', 'telefono')
