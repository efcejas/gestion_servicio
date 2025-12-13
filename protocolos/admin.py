from django.contrib import admin
from .models import Modalidad, RegionAnatomica, Tag, Protocolo, FaseAdquisicion


@admin.register(Modalidad)
class ModalidadAdmin(admin.ModelAdmin):
    list_display = ['codigo', 'nombre']
    search_fields = ['codigo', 'nombre']


@admin.register(RegionAnatomica)
class RegionAnatomicaAdmin(admin.ModelAdmin):
    list_display = ['codigo', 'nombre']
    search_fields = ['codigo', 'nombre']


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'slug']
    search_fields = ['nombre']
    prepopulated_fields = {'slug': ('nombre',)}


class FaseAdquisicionInline(admin.TabularInline):
    model = FaseAdquisicion
    fields = ['orden', 'nombre', 'tipo_fase', 'region', 'delay_segundos']
    extra = 1
    autocomplete_fields = ['region']


@admin.register(Protocolo)
class ProtocoloAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'modalidad', 'region', 'es_activo']
    list_filter = ['modalidad', 'region', 'es_activo', 'tags']
    search_fields = ['nombre', 'descripcion']
    filter_horizontal = ['tags']
    autocomplete_fields = ['modalidad', 'region']
    inlines = [FaseAdquisicionInline]
    
    fieldsets = (
        ('Clasificación', {
            'fields': ('modalidad', 'region', 'nombre', 'descripcion', 'tags')
        }),
        ('Contraste', {
            'fields': ('requiere_contraste_ev', 'requiere_contraste_oral', 'requiere_ayuno')
        }),
        ('Preparación del paciente', {
            'fields': ('calibre_via_minimo', 'sitio_via_preferido', 'preparacion_paciente')
        }),
        ('Cobertura y notas', {
            'fields': ('cobertura_global', 'notas_docentes')
        }),
        ('Estado', {
            'fields': ('es_activo',)
        }),
    )


@admin.register(FaseAdquisicion)
class FaseAdquisicionAdmin(admin.ModelAdmin):
    list_display = ['protocolo', 'orden', 'nombre', 'tipo_fase', 'region']
    list_filter = ['tipo_fase', 'region']
    search_fields = ['nombre', 'protocolo__nombre']
    autocomplete_fields = ['protocolo', 'region']
