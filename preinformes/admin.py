from django.contrib import admin
from .models import TipoEstudio, Region, PlantillaPreinforme, Preinforme, RevisionPreinforme, HistorialEstudios


@admin.register(TipoEstudio)
class TipoEstudioAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'activo']
    list_filter = ['activo']
    search_fields = ['nombre']


@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'activo']
    list_filter = ['activo']
    search_fields = ['nombre']


@admin.register(PlantillaPreinforme)
class PlantillaPreinformeAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'tipo_estudio', 'region', 'sistema_destino', 'estado', 'activa', 'creada_por']
    list_filter = ['tipo_estudio', 'region', 'sistema_destino', 'estado', 'activa', 'fecha_creacion']
    search_fields = ['nombre', 'tipo_estudio__nombre', 'region__nombre']
    readonly_fields = ['fecha_creacion', 'fecha_modificacion']
    
    fieldsets = (
        ('Información General', {
            'fields': ('nombre', 'tipo_estudio', 'region', 'sistema_destino', 'estado', 'activa', 'creada_por')
        }),
        ('Contenido de la Plantilla', {
            'fields': ('contenido',),
            'description': 'Contenido completo de la plantilla. Pega directamente desde Word con formato.'
        }),
        ('LEGACY - Campos Separados (Obsoleto)', {
            'fields': ('tecnica_template', 'hallazgos_template', 'conclusion_template'),
            'description': 'Campos legacy para compatibilidad con plantillas antiguas. NO usar para plantillas nuevas.',
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('fecha_creacion', 'fecha_modificacion'),
            'classes': ('collapse',)
        }),
    )


class RevisionPreinformeInline(admin.StackedInline):
    model = RevisionPreinforme
    extra = 0


@admin.register(Preinforme)
class PreinformeAdmin(admin.ModelAdmin):
    list_display = [
        'numero_estudio', 
        'apellido_paciente', 
        'nombre_paciente', 
        'residente', 
        'tipo_estudio', 
        'region', 
        'estado', 
        'fecha_creacion'
    ]
    list_filter = [
        'estado', 
        'tipo_estudio', 
        'region', 
        'fecha_creacion',
        'residente__username'
    ]
    search_fields = [
        'numero_estudio', 
        'apellido_paciente', 
        'nombre_paciente',
        'residente__username'
    ]
    readonly_fields = [
        'fecha_creacion', 
        'fecha_envio_revision', 
        'fecha_inicio_revision', 
        'fecha_finalizacion'
    ]
    inlines = [RevisionPreinformeInline]


@admin.register(RevisionPreinforme)
class RevisionPreinformeAdmin(admin.ModelAdmin):
    list_display = [
        'preinforme', 
        'revisor', 
        'puntuacion', 
        'fecha_creacion'
    ]
    list_filter = ['puntuacion', 'fecha_creacion', 'revisor']
    search_fields = [
        'preinforme__numero_estudio',
        'preinforme__apellido_paciente',
        'revisor__username'
    ]


@admin.register(HistorialEstudios)
class HistorialEstudiosAdmin(admin.ModelAdmin):
    list_display = [
        'residente', 
        'total_preinformes', 
        'preinformes_finalizados', 
        'promedio_puntuacion',
        'fecha_ultimo_preinforme'
    ]
    readonly_fields = [
        'total_preinformes',
        'preinformes_finalizados', 
        'promedio_puntuacion',
        'fecha_ultimo_preinforme'
    ]
    actions = ['actualizar_estadisticas']
    
    def actualizar_estadisticas(self, request, queryset):
        for historial in queryset:
            historial.actualizar_estadisticas()
        self.message_user(request, f'Se actualizaron {queryset.count()} historiales.')
    actualizar_estadisticas.short_description = 'Actualizar estadísticas'