from django.contrib import admin
from .models import (
    TipoEstudio, Region, PlantillaPreinforme, Preinforme, 
    RevisionPreinforme, HistorialEstudios, EtiquetaPreinforme,
    AdjuntoPreinforme, PropuestaPlantillaPreinforme,
    VersionPlantillaPreinforme, AplicacionPlantillaPreinforme,
)


@admin.register(EtiquetaPreinforme)
class EtiquetaPreinformeAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'color', 'creada_por', 'fecha_creacion', 'total_usos']
    list_filter = ['creada_por', 'fecha_creacion']
    search_fields = ['nombre']
    readonly_fields = ['fecha_creacion']
    
    def total_usos(self, obj):
        """Muestra cuántos preinformes usan esta etiqueta"""
        return obj.preinformes.count()
    total_usos.short_description = 'Usos'


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
    
    def save_model(self, request, obj, form, change):
        """Limpiar HTML antes de guardar plantilla desde el admin"""
        if obj.contenido:
            from preinformes.models import sanitize_center_alignment, normalize_html_content_soft
            from bs4 import BeautifulSoup
            
            # 1. Eliminar alineación centrada
            obj.contenido = sanitize_center_alignment(obj.contenido)
            
            # 2. Eliminar backgrounds
            soup = BeautifulSoup(obj.contenido, 'html.parser')
            for tag in soup.find_all(True):
                if tag.has_attr('style'):
                    style_parts = [s.strip() for s in tag['style'].split(';') if s.strip()]
                    cleaned_parts = [p for p in style_parts if not p.lower().startswith('background')]
                    
                    if cleaned_parts:
                        tag['style'] = '; '.join(cleaned_parts)
                    else:
                        del tag['style']
            
            obj.contenido = str(soup)
            
            # 3. Normalizar HTML de forma RESPETUOSA (preserva estructura original)
            obj.contenido = normalize_html_content_soft(obj.contenido)
        
        super().save_model(request, obj, form, change)


@admin.register(PropuestaPlantillaPreinforme)
class PropuestaPlantillaPreinformeAdmin(admin.ModelAdmin):
    list_display = [
        'estudio_especifico', 'tipo_estudio', 'region', 'tipo_solicitud',
        'estado', 'autor', 'revisor', 'fecha_creacion',
    ]
    list_filter = [
        'estado', 'tipo_solicitud', 'tipo_estudio', 'region', 'fecha_creacion',
    ]
    search_fields = [
        'estudio_especifico', 'titulo', 'autor__username', 'revisor__username',
    ]
    readonly_fields = [
        'fecha_creacion', 'fecha_modificacion', 'fecha_envio_revision',
        'fecha_inicio_revision', 'fecha_resolucion',
    ]


@admin.register(VersionPlantillaPreinforme)
class VersionPlantillaPreinformeAdmin(admin.ModelAdmin):
    list_display = [
        'plantilla', 'numero', 'vigente', 'aprobada_por', 'fecha_aprobacion',
    ]
    list_filter = ['vigente', 'fecha_aprobacion', 'plantilla__tipo_estudio']
    search_fields = [
        'plantilla__nombre', 'titulo', 'aprobada_por__username',
    ]
    readonly_fields = ['fecha_aprobacion']


@admin.register(AplicacionPlantillaPreinforme)
class AplicacionPlantillaPreinformeAdmin(admin.ModelAdmin):
    list_display = [
        'preinforme', 'plantilla', 'version', 'propuesta',
        'aplicada_por', 'fecha_aplicacion',
    ]
    list_filter = [
        'contraste_ev', 'contraste_oral', 'lateralidad', 'fecha_aplicacion',
    ]
    search_fields = [
        'preinforme__numero_estudio', 'plantilla__nombre',
        'propuesta__estudio_especifico', 'aplicada_por__username',
    ]
    readonly_fields = ['fecha_aplicacion']


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
        'es_registro_demo',
        'estado', 
        'fecha_creacion'
    ]
    list_filter = [
        'estado', 
        'tipo_estudio', 
        'region', 
        'es_registro_demo',
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


@admin.register(AdjuntoPreinforme)
class AdjuntoPreinformeAdmin(admin.ModelAdmin):
    list_display = [
        'preinforme',
        'origen',
        'subido_por',
        'fecha_creacion',
        'activo',
    ]
    list_filter = ['origen', 'activo', 'fecha_creacion']
    search_fields = [
        'preinforme__numero_estudio',
        'preinforme__apellido_paciente',
        'subido_por__username',
    ]
    readonly_fields = ['fecha_creacion']
