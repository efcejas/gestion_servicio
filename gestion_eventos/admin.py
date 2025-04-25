from django.contrib import admin
from .models import EventoServicio, NotaEvento

@admin.register(EventoServicio)
class EventoServicioAdmin(admin.ModelAdmin):
    list_display = ('id', 'tipo_evento', 'estado', 'creado_por', 'fecha_creacion', 'sector_de_pedido', 'nombre_paciente', 'estudio_relacionado')
    list_filter = ('tipo_evento', 'estado', 'fecha_creacion')
    search_fields = ('descripcion', 'nombre_paciente', 'estudio_relacionado', 'creado_por__username')
    date_hierarchy = 'fecha_creacion'
    ordering = ['-fecha_creacion']

@admin.register(NotaEvento)
class NotaEventoAdmin(admin.ModelAdmin):
    list_display = ('id', 'evento', 'creado_por', 'fecha')
    list_filter = ('fecha',)
    search_fields = ('comentario', 'evento__descripcion', 'creado_por__username')
    date_hierarchy = 'fecha'
    ordering = ['-fecha']
