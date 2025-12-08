from django.contrib import admin
from .models import AgendaItem, NotaPersonal


@admin.register(AgendaItem)
class AgendaItemAdmin(admin.ModelAdmin):
    list_display = ['titulo', 'fecha', 'hora_inicio', 'tipo', 'es_importante', 'completado']
    list_filter = ['fecha', 'tipo', 'es_importante', 'completado']
    search_fields = ['titulo', 'descripcion']
    ordering = ['fecha', 'hora_inicio', 'titulo']
    date_hierarchy = 'fecha'
    
    fieldsets = (
        ('Información Principal', {
            'fields': ('titulo', 'tipo', 'descripcion')
        }),
        ('Fecha y Hora', {
            'fields': ('fecha', 'hora_inicio', 'hora_fin')
        }),
        ('Estado', {
            'fields': ('es_importante', 'completado')
        }),
        ('Metadatos', {
            'fields': ('creado_por',),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        if not change:  # Si es un nuevo objeto
            obj.creado_por = request.user
        super().save_model(request, obj, form, change)


@admin.register(NotaPersonal)
class NotaPersonalAdmin(admin.ModelAdmin):
    list_display = ['get_titulo_display', 'fijada', 'creado_en', 'actualizado_en']
    list_filter = ['fijada', 'creado_en']
    search_fields = ['titulo', 'contenido']
    ordering = ['-fijada', '-actualizado_en']
    
    fieldsets = (
        ('Contenido', {
            'fields': ('titulo', 'contenido', 'fijada')
        }),
        ('Metadatos', {
            'fields': ('creado_por',),
            'classes': ('collapse',)
        }),
    )
    
    def get_titulo_display(self, obj):
        return obj.titulo if obj.titulo else '(Sin título)'
    get_titulo_display.short_description = 'Título'
    
    def save_model(self, request, obj, form, change):
        if not change:  # Si es un nuevo objeto
            obj.creado_por = request.user
        super().save_model(request, obj, form, change)
