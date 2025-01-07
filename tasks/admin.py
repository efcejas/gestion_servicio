from django.contrib import admin
from .models import Tarea

@admin.register(Tarea)
class TareaAdmin(admin.ModelAdmin):
    list_display = ['titulo', 'usuario', 'estado', 'prioridad', 'fecha_limite']
    list_filter = ['estado', 'prioridad', 'usuario']
    search_fields = ['titulo', 'descripcion']

