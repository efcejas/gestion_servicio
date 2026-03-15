from django.contrib import admin
from .models import ImportBatch, EgesRow, DirectorToken, NombreObraSocial


@admin.register(ImportBatch)
class ImportBatchAdmin(admin.ModelAdmin):
    list_display = ['id', 'archivo_nombre', 'usuario', 'fecha_importacion', 'total_filas', 'total_estudios_finalizados']
    list_filter = ['fecha_importacion', 'usuario']
    search_fields = ['archivo_nombre']
    readonly_fields = [
        'fecha_importacion', 'total_filas', 'total_ingresos_unicos',
        'total_estudios_candidatos', 'total_estudios_finalizados',
        'total_tc', 'total_rm', 'total_rx', 'total_dx', 'total_mam', 'total_eco', 'total_otros'
    ]
    fieldsets = (
        ('Información del Lote', {
            'fields': ('usuario', 'archivo_nombre', 'fecha_importacion')
        }),
        ('Métricas Generales', {
            'fields': ('total_filas', 'total_ingresos_unicos', 'total_estudios_candidatos', 'total_estudios_finalizados')
        }),
        ('Métricas por Modalidad', {
            'fields': ('total_tc', 'total_rm', 'total_rx', 'total_dx', 'total_mam', 'total_eco', 'total_otros')
        }),
    )


@admin.register(EgesRow)
class EgesRowAdmin(admin.ModelAdmin):
    list_display = ['id', 'batch', 'historia_clinica', 'apellido_nombre', 'fecha_turno',
                    'practica', 'obra_social', 'modalidad', 'sub_modalidad', 'medico_informante',
                    'estado_turno', 'es_insumo']
    list_filter = ['modalidad', 'sub_modalidad', 'es_insumo', 'estado_turno', 'batch']
    search_fields = ['historia_clinica', 'apellido_nombre', 'practica', 'servicio',
                     'medico_informante', 'obra_social']


@admin.register(NombreObraSocial)
class NombreObraSocialAdmin(admin.ModelAdmin):
    list_display = ['codigo', 'nombre']
    search_fields = ['codigo', 'nombre']
    ordering = ['nombre']


@admin.register(DirectorToken)
class DirectorTokenAdmin(admin.ModelAdmin):
    list_display = ['nombre_etiqueta', 'token', 'activo', 'fecha_creacion', 'fecha_ultimo_acceso']
    list_editable = ['activo']
    list_filter = ['activo']
    search_fields = ['nombre_etiqueta']
    readonly_fields = ['token', 'fecha_creacion', 'fecha_ultimo_acceso']
