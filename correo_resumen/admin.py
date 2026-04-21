from django.contrib import admin

from .models import CorreoResumen, CorreoSincronizacion, CorreoHilo


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


@admin.register(CorreoHilo)
class CorreoHiloAdmin(admin.ModelAdmin):
    list_display = (
        'asunto_normalizado',
        'cuenta',
        'cantidad_correos',
        'prioridad_hilo',
        'estado_hilo',
        'requiere_respuesta',
        'fecha_compromiso',
        'fecha_ultimo_email',
    )
    list_filter = ('estado_hilo', 'prioridad_hilo', 'requiere_respuesta', 'cuenta')
    search_fields = ('asunto_normalizado',)
    readonly_fields = (
        'asunto_normalizado',
        'participantes',
        'fecha_primer_email',
        'fecha_ultimo_email',
        'resumen_hilo',
        'creado_en',
        'actualizado_en',
    )
    filter_horizontal = ('correos',)
    ordering = ('-fecha_ultimo_email',)
