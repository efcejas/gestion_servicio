"""
Configuración del Django Admin para gestión de equipos.
"""

from django.contrib import admin
from .models import EquipoImagen


@admin.register(EquipoImagen)
class EquipoImagenAdmin(admin.ModelAdmin):
    """Administración de equipos de imágenes en el admin."""
    
    # Columnas visibles en la lista
    list_display = [
        'nombre',
        'area',
        'fabricante',
        'modelo',
        'ubicacion',
        'en_servicio',
        'ultimo_mantenimiento',
    ]
    
    # Filtros laterales
    list_filter = [
        'area',
        'en_servicio',
        'fabricante',
        'fecha_instalacion',
    ]
    
    # Búsqueda por texto
    search_fields = [
        'nombre',
        'fabricante',
        'modelo',
        'numero_serie',
        'ubicacion',
    ]
    
    # Organización de campos en el formulario
    fieldsets = (
        ('Información Básica', {
            'fields': ('nombre', 'area', 'en_servicio')
        }),
        ('Información Técnica', {
            'fields': ('fabricante', 'modelo', 'numero_serie'),
            'classes': ('collapse',),  # Colapsable
        }),
        ('Ubicación y Fechas', {
            'fields': ('ubicacion', 'fecha_instalacion', 'ultimo_mantenimiento'),
            'classes': ('collapse',),
        }),
        ('Observaciones', {
            'fields': ('observaciones',),
            'classes': ('collapse',),
        }),
        ('Metadatos', {
            'fields': ('fecha_creacion', 'fecha_modificacion'),
            'classes': ('collapse',),
        }),
    )
    
    # Campos de solo lectura
    readonly_fields = ['fecha_creacion', 'fecha_modificacion']
    
    # Acciones masivas personalizadas
    actions = ['marcar_en_servicio', 'marcar_fuera_servicio']
    
    @admin.action(description='Marcar equipos seleccionados como EN SERVICIO')
    def marcar_en_servicio(self, request, queryset):
        """Marca equipos como en servicio."""
        updated = queryset.update(en_servicio=True)
        self.message_user(request, f'{updated} equipo(s) marcado(s) como EN SERVICIO.')
    
    @admin.action(description='Marcar equipos seleccionados como FUERA DE SERVICIO')
    def marcar_fuera_servicio(self, request, queryset):
        """Marca equipos como fuera de servicio."""
        updated = queryset.update(en_servicio=False)
        self.message_user(request, f'{updated} equipo(s) marcado(s) como FUERA DE SERVICIO.')
