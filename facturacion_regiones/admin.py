from django.contrib import admin
from .models import Region, Estudio, RegistroEstudio, RegistroEstudioDetalle

@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'peso']
    search_fields = ['nombre']


@admin.register(Estudio)
class EstudioAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'modalidad']
    search_fields = ['nombre']
    list_filter = ['modalidad']


class RegistroEstudioDetalleInline(admin.TabularInline):
    model = RegistroEstudioDetalle
    extra = 1  # Número de líneas vacías para agregar detalles


@admin.register(RegistroEstudio)
class RegistroEstudioAdmin(admin.ModelAdmin):
    list_display = ['paciente_nombre', 'paciente_dni', 'fecha_estudio', 'total_regiones', 'medico']
    search_fields = ['paciente_nombre', 'paciente_dni', 'medico__username']
    list_filter = ['fecha_estudio', 'medico']
    inlines = [RegistroEstudioDetalleInline]  # Agrega detalles en línea
