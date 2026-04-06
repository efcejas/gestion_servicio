from django.contrib import admin

from .models import (
    AsignacionGuardia,
    AusenciaResidente,
    ConfiguracionTipoGuardia,
    CuotaMensualGuardia,
    Feriado,
    NotificacionGuardia,
    SolicitudCambioGuardia,
)


@admin.register(ConfiguracionTipoGuardia)
class ConfiguracionTipoGuardiaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'hora_inicio', 'hora_fin', 'dias_semana', 'aplica_feriados', 'activo')
    list_filter = ('activo', 'aplica_feriados')
    search_fields = ('nombre',)


@admin.register(Feriado)
class FeriadoAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'descripcion')
    ordering = ('fecha',)


@admin.register(CuotaMensualGuardia)
class CuotaMensualGuardiaAdmin(admin.ModelAdmin):
    list_display = ('anio_residencia', 'guardias_por_mes', 'atenuante_porcentaje', 'guardias_efectivas')
    ordering = ('anio_residencia',)

    def guardias_efectivas(self, obj):
        return obj.guardias_efectivas
    guardias_efectivas.short_description = 'Cuota efectiva'


@admin.register(AsignacionGuardia)
class AsignacionGuardiaAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'get_residente', 'tipo_guardia', 'estado', 'es_feriado')
    list_filter = ('estado', 'es_feriado', 'tipo_guardia')
    search_fields = ('residente__first_name', 'residente__last_name')
    date_hierarchy = 'fecha'
    raw_id_fields = ('residente', 'creada_por')

    def get_residente(self, obj):
        return obj.residente.get_full_name()
    get_residente.short_description = 'Residente'


@admin.register(AusenciaResidente)
class AusenciaResidenteAdmin(admin.ModelAdmin):
    list_display = ('get_residente', 'motivo', 'fecha_inicio', 'fecha_fin', 'estado')
    list_filter = ('motivo', 'estado')
    search_fields = ('residente__first_name', 'residente__last_name')

    def get_residente(self, obj):
        return obj.residente.get_full_name()
    get_residente.short_description = 'Residente'


@admin.register(SolicitudCambioGuardia)
class SolicitudCambioGuardiaAdmin(admin.ModelAdmin):
    list_display = ('get_solicitante', 'get_receptor', 'estado', 'fecha_solicitud')
    list_filter = ('estado',)

    def get_solicitante(self, obj):
        return obj.solicitante.get_full_name()
    get_solicitante.short_description = 'Solicitante'

    def get_receptor(self, obj):
        return obj.receptor.get_full_name()
    get_receptor.short_description = 'Receptor'


@admin.register(NotificacionGuardia)
class NotificacionGuardiaAdmin(admin.ModelAdmin):
    list_display = ('get_destinatario', 'tipo', 'leida', 'fecha')
    list_filter = ('tipo', 'leida')
    search_fields = ('destinatario__first_name', 'destinatario__last_name')

    def get_destinatario(self, obj):
        return obj.destinatario.get_full_name()
    get_destinatario.short_description = 'Destinatario'
