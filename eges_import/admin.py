from django.contrib import admin
from .models import ImportBatch, EgesRow


@admin.register(ImportBatch)
class ImportBatchAdmin(admin.ModelAdmin):
    list_display = ['id', 'archivo_nombre', 'usuario', 'fecha_importacion', 'total_filas', 'total_estudios_finalizados']
    list_filter = ['fecha_importacion', 'usuario']
    search_fields = ['archivo_nombre']
    readonly_fields = [
        'fecha_importacion', 'total_filas', 'total_ingresos_unicos',
        'total_estudios_candidatos', 'total_estudios_finalizados',
        'total_tc', 'total_rm', 'total_rx', 'total_eco', 'total_otros'
    ]
    fieldsets = (
        ('Información del Lote', {
            'fields': ('usuario', 'archivo_nombre', 'fecha_importacion')
        }),
        ('Métricas Generales', {
            'fields': ('total_filas', 'total_ingresos_unicos', 'total_estudios_candidatos', 'total_estudios_finalizados')
        }),
        ('Métricas por Modalidad', {
            'fields': ('total_tc', 'total_rm', 'total_rx', 'total_eco', 'total_otros')
        }),
    )


@admin.register(EgesRow)
class EgesRowAdmin(admin.ModelAdmin):
    list_display = ['id', 'batch', 'historia_clinica', 'apellido_nombre', 'fecha_turno', 'servicio', 'modalidad', 'estado_turno', 'es_insumo']
    list_filter = ['batch', 'modalidad', 'estado_turno', 'es_insumo']
    search_fields = ['historia_clinica', 'apellido_nombre', 'servicio']
    readonly_fields = ['fecha_creacion', 'modalidad', 'es_insumo']
    date_hierarchy = 'fecha_turno'
    
    fieldsets = (
        ('Lote', {
            'fields': ('batch',)
        }),
        ('Identificación del Turno', {
            'fields': ('numero_turno', 'fecha_turno', 'hora_turno', 'centro_atencion')
        }),
        ('Paciente', {
            'fields': ('historia_clinica', 'apellido_nombre')
        }),
        ('Estudio', {
            'fields': ('servicio', 'equipo', 'estado_turno')
        }),
        ('Clasificación', {
            'fields': ('es_insumo', 'modalidad', 'fecha_creacion')
        }),
    )
