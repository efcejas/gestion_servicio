from django.contrib import admin
from .models import Medico, Estudios

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