from django.contrib import admin

from .models import CorreoResumen, CorreoSincronizacion


@admin.register(CorreoResumen)
class CorreoResumenAdmin(admin.ModelAdmin):
    list_display = (
        'fecha_email',
        'remitente_visible',
        'asunto',
        'prioridad_sugerida',
        'categoria',
        'score_importancia',
        'leido',
    )
    list_filter = ('prioridad_sugerida', 'categoria', 'leido', 'requiere_accion', 'proveedor')
    search_fields = ('asunto', 'remitente', 'remitente_nombre', 'snippet')
    ordering = ('-fecha_email',)


@admin.register(CorreoSincronizacion)
class CorreoSincronizacionAdmin(admin.ModelAdmin):
    list_display = ('iniciado_en', 'cuenta', 'proveedor', 'estado', 'correos_leidos', 'correos_nuevos')
    list_filter = ('estado', 'proveedor')
    ordering = ('-iniciado_en',)
