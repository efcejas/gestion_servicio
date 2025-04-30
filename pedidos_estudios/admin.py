from django.contrib import admin
from .models import PedidoEstudio, PedidoEstudioNota

class PedidoEstudioNotaInline(admin.TabularInline):
    model = PedidoEstudioNota
    extra = 1  # Muestra un campo vacío adicional para agregar nuevas notas
    readonly_fields = ('creado_por', 'fecha')
    fields = ('comentario', 'creado_por', 'fecha')
    can_delete = False  # Opcional: si querés que no puedan borrarse notas desde el admin

    def has_change_permission(self, request, obj=None):
        # Opcional: para que una vez creada la nota no pueda editarse desde el admin
        return False

@admin.register(PedidoEstudio)
class PedidoEstudioAdmin(admin.ModelAdmin):
    list_display = ('nombre_paciente', 'dni_paciente', 'tipo_estudio', 'sector_solicitante', 'estado', 'fecha_creacion')
    list_filter = ('estado', 'sector_solicitante')
    search_fields = ('nombre_paciente', 'dni_paciente', 'tipo_estudio', 'sector_solicitante', 'medico_solicitante')
    ordering = ('-fecha_creacion',)
    inlines = [PedidoEstudioNotaInline]

@admin.register(PedidoEstudioNota)
class PedidoEstudioNotaAdmin(admin.ModelAdmin):
    list_display = ('pedido', 'creado_por', 'fecha')
    search_fields = ('comentario',)
    ordering = ('-fecha',)
