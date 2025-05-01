from django.contrib import admin
from .models import EventoServicio, NotaEvento, HistorialEvento

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

@admin.register(HistorialEvento)
class HistorialEventoAdmin(admin.ModelAdmin):
    list_display = ('id', 'evento', 'usuario', 'fecha', 'cambio', 'valor_anterior', 'valor_nuevo')
    list_filter = ('cambio', 'fecha', 'usuario')
    search_fields = ('evento__descripcion', 'usuario__username', 'valor_anterior', 'valor_nuevo')
    date_hierarchy = 'fecha'
    ordering = ['-fecha']