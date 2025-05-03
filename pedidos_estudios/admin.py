from django.contrib import admin
from .models import PedidoEstudio, PedidoEstudioNota, HistorialPedidoEstudio

class PedidoEstudioNotaInline(admin.TabularInline):
    model = PedidoEstudioNota
    extra = 1
    readonly_fields = ('creado_por', 'fecha')
    fields = ('comentario', 'creado_por', 'fecha')
    can_delete = False

    def has_change_permission(self, request, obj=None):
        return False

@admin.register(PedidoEstudio)
class PedidoEstudioAdmin(admin.ModelAdmin):
    list_display = ('nombre_paciente', 'dni_paciente', 'tipo_estudio', 'sector_solicitante', 'estado', 'fecha_creacion')
    list_filter = ('estado', 'sector_solicitante', 'modalidad', 'prioridad')
    search_fields = ('nombre_paciente', 'dni_paciente', 'tipo_estudio', 'sector_solicitante', 'medico_solicitante', 'modalidad', 'prioridad')
    ordering = ('-fecha_creacion',)
    readonly_fields = ('fecha_creacion',)
    inlines = [PedidoEstudioNotaInline]

@admin.register(PedidoEstudioNota)
class PedidoEstudioNotaAdmin(admin.ModelAdmin):
    list_display = ('pedido', 'creado_por', 'fecha')
    search_fields = ('comentario',)
    list_filter = ('creado_por', 'fecha')
    ordering = ('-fecha',)

@admin.register(HistorialPedidoEstudio)
class HistorialPedidoEstudioAdmin(admin.ModelAdmin):
    list_display = ('pedido', 'usuario', 'cambio', 'fecha', 'es_visualizacion')
    list_filter = ('cambio', 'es_visualizacion', 'fecha', 'usuario')
    search_fields = ('pedido__nombre_paciente', 'usuario__username', 'valor_anterior', 'valor_nuevo')
    ordering = ('-fecha',)
    readonly_fields = ('pedido', 'usuario', 'fecha', 'cambio', 'valor_anterior', 'valor_nuevo', 'es_visualizacion')