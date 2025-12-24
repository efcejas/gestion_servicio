from django.contrib import admin
from .models import ClaseResidente, ComentarioClase, FavoritoClase


@admin.register(ClaseResidente)
class ClaseResidenteAdmin(admin.ModelAdmin):
    list_display = ['titulo', 'categoria', 'autor', 'fecha_clase', 'anios_dirigidos_display', 'visitas', 'es_destacada', 'activa']
    list_filter = ['categoria', 'es_destacada', 'activa', 'fecha_clase']
    search_fields = ['titulo', 'descripcion', 'tags', 'autor__username']
    readonly_fields = ['visitas', 'fecha_creacion', 'fecha_actualizacion']
    date_hierarchy = 'fecha_clase'
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('titulo', 'descripcion', 'categoria', 'tags')
        }),
        ('Archivo', {
            'fields': ('archivo', 'archivo_thumbnail')
        }),
        ('Audiencia', {
            'fields': ('anios_dirigidos',)
        }),
        ('Autor y Fechas', {
            'fields': ('autor', 'fecha_clase', 'fecha_creacion', 'fecha_actualizacion')
        }),
        ('Estado', {
            'fields': ('activa', 'es_destacada', 'visitas')
        }),
    )
    
    def anios_dirigidos_display(self, obj):
        return obj.anios_dirigidos_display()
    anios_dirigidos_display.short_description = 'Años Dirigidos'


@admin.register(ComentarioClase)
class ComentarioClaseAdmin(admin.ModelAdmin):
    list_display = ['clase', 'autor', 'contenido_preview', 'fecha_creacion']
    list_filter = ['fecha_creacion']
    search_fields = ['contenido', 'autor__username', 'clase__titulo']
    readonly_fields = ['fecha_creacion', 'fecha_actualizacion']
    
    def contenido_preview(self, obj):
        return obj.contenido[:50] + '...' if len(obj.contenido) > 50 else obj.contenido
    contenido_preview.short_description = 'Contenido'


@admin.register(FavoritoClase)
class FavoritoClaseAdmin(admin.ModelAdmin):
    list_display = ['usuario', 'clase', 'fecha_creacion']
    list_filter = ['fecha_creacion']
    search_fields = ['usuario__username', 'clase__titulo']
    readonly_fields = ['fecha_creacion']
