"""
Configuración del panel de administración para la app consultorios.
"""

from django.contrib import admin
from django.utils.html import format_html

from .models import (
    AccionEGES,
    AsignacionEquipoConsultorio,
    AusenciaCobertura,
    BloqueHorario,
    Consultorio,
    EstadoTareaEGES,
    ProfesionalExterno,
    SolicitudAgendaExtra,
    TareaAgendaEGES,
)


@admin.register(Consultorio)
class ConsultorioAdmin(admin.ModelAdmin):
    """Administración de consultorios."""

    list_display = [
        'nombre_con_estado',
        'ubicacion',
        'capacidad_pacientes_hora',
        'cantidad_equipos',
        'cantidad_bloques_activos',
        'fecha_creacion',
    ]
    list_filter = ['esta_activo', 'fecha_creacion']
    search_fields = ['nombre', 'ubicacion']
    readonly_fields = ['fecha_creacion', 'fecha_modificacion']

    fieldsets = (
        ('Información Básica', {
            'fields': ('nombre', 'ubicacion', 'esta_activo')
        }),
        ('Configuración', {
            'fields': ('capacidad_pacientes_hora', 'observaciones')
        }),
        ('Metadatos', {
            'fields': ('fecha_creacion', 'fecha_modificacion'),
            'classes': ('collapse',),
        }),
    )

    def nombre_con_estado(self, obj):
        if obj.esta_activo:
            return format_html('<span style="color: green;">●</span> {}', obj.nombre)
        return format_html(
            '<span style="color: red;">●</span> <span style="color: #999;">{}</span>',
            obj.nombre,
        )

    nombre_con_estado.short_description = 'Consultorio'
    nombre_con_estado.admin_order_field = 'nombre'

    def cantidad_equipos(self, obj):
        count = obj.equipos_asignados().count()
        if count > 0:
            return format_html('<strong>{}</strong> equipo(s)', count)
        return format_html('<span style="color: #999;">Sin equipos</span>')

    cantidad_equipos.short_description = 'Equipos'

    def cantidad_bloques_activos(self, obj):
        count = obj.bloques_horarios.filter(estado='ACTIVO').count()
        if count > 0:
            return format_html('<strong style="color: green;">{}</strong> bloque(s)', count)
        return format_html('<span style="color: #999;">Sin bloques</span>')

    cantidad_bloques_activos.short_description = 'Bloques Activos'


@admin.register(ProfesionalExterno)
class ProfesionalExternoAdmin(admin.ModelAdmin):
    """Administración de profesionales externos."""

    list_display = [
        'nombre_completo_con_estado',
        'categoria',
        'matricula',
        'especialidad',
        'telefono',
        'email',
        'cantidad_bloques',
        'fecha_creacion',
    ]
    list_filter = ['esta_activo', 'categoria', 'especialidad', 'fecha_creacion']
    search_fields = ['nombre', 'apellido', 'matricula', 'email']
    readonly_fields = ['fecha_creacion', 'fecha_modificacion']

    fieldsets = (
        ('Información Personal', {
            'fields': ('nombre', 'apellido', 'matricula', 'esta_activo')
        }),
        ('Información Profesional', {
            'fields': ('categoria', 'especialidad')
        }),
        ('Contacto', {
            'fields': ('telefono', 'email')
        }),
        ('Notas', {
            'fields': ('observaciones',)
        }),
        ('Metadatos', {
            'fields': ('fecha_creacion', 'fecha_modificacion'),
            'classes': ('collapse',),
        }),
    )

    def nombre_completo_con_estado(self, obj):
        if obj.esta_activo:
            return format_html(
                '<span style="color: green;">●</span> Dr./Dra. {}, {}',
                obj.apellido,
                obj.nombre,
            )
        return format_html(
            '<span style="color: red;">●</span> <span style="color: #999;">Dr./Dra. {}, {}</span>',
            obj.apellido,
            obj.nombre,
        )

    nombre_completo_con_estado.short_description = 'Profesional'
    nombre_completo_con_estado.admin_order_field = 'apellido'

    def cantidad_bloques(self, obj):
        count = obj.bloques_horarios.filter(estado='ACTIVO').count()
        if count > 0:
            return format_html('<strong>{}</strong> bloque(s)', count)
        return format_html('<span style="color: #999;">Sin bloques</span>')

    cantidad_bloques.short_description = 'Bloques Activos'


@admin.register(AsignacionEquipoConsultorio)
class AsignacionEquipoConsultorioAdmin(admin.ModelAdmin):
    """Administración de asignaciones de equipos a consultorios."""

    list_display = [
        'equipo',
        'consultorio',
        'tipo_asignacion',
        'fecha_inicio',
        'fecha_fin',
        'estado_vigencia',
        'fecha_creacion',
    ]
    list_filter = ['es_permanente', 'consultorio', 'equipo__area', 'fecha_inicio']
    search_fields = ['equipo__nombre', 'consultorio__nombre', 'observaciones']
    readonly_fields = ['fecha_creacion', 'fecha_modificacion', 'estado_vigencia']
    autocomplete_fields = ['equipo', 'consultorio']

    fieldsets = (
        ('Asignación', {
            'fields': ('consultorio', 'equipo')
        }),
        ('Período', {
            'fields': ('es_permanente', 'fecha_inicio', 'fecha_fin'),
            'description': 'Si es permanente, no necesita fecha de fin. Si es temporal, debe especificar ambas fechas.',
        }),
        ('Información Adicional', {
            'fields': ('observaciones',)
        }),
        ('Metadatos', {
            'fields': ('estado_vigencia', 'fecha_creacion', 'fecha_modificacion'),
            'classes': ('collapse',),
        }),
    )

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if not obj and 'fecha_inicio' in form.base_fields:
            from django.utils import timezone
            form.base_fields['fecha_inicio'].initial = timezone.now().date()
        return form

    def tipo_asignacion(self, obj):
        if obj.es_permanente:
            return format_html('<span style="color: blue; font-weight: bold;">PERMANENTE</span>')
        return format_html('<span style="color: orange;">TEMPORAL</span>')

    tipo_asignacion.short_description = 'Tipo'

    def estado_vigencia(self, obj):
        if not obj or not obj.pk:
            return format_html('<span style="color: #999;">-</span>')
        if obj.esta_vigente():
            return format_html('<span style="color: green; font-weight: bold;">✓ VIGENTE</span>')
        return format_html('<span style="color: red;">✗ No vigente</span>')

    estado_vigencia.short_description = 'Estado'


@admin.register(BloqueHorario)
class BloqueHorarioAdmin(admin.ModelAdmin):
    """Administración de bloques horarios."""

    list_display = [
        'consultorio',
        'profesional_display',
        'tipo_titular',
        'dia_semana_display',
        'horario_display',
        'tipo_actividad',
        'tipo_lista',
        'permite_cobertura_residente',
        'estado_display',
        'vigencia_display',
    ]
    list_filter = [
        'estado',
        'dia_semana',
        'tipo_titular',
        'tipo_actividad',
        'tipo_lista',
        'permite_cobertura_residente',
        'consultorio',
        'fecha_inicio_vigencia',
    ]
    search_fields = [
        'consultorio__nombre',
        'profesional_asignado_temporal__username',
        'profesional_asignado_temporal__first_name',
        'profesional_asignado_temporal__last_name',
        'profesional_interno__username',
        'profesional_interno__first_name',
        'profesional_interno__last_name',
        'profesional_externo__nombre',
        'profesional_externo__apellido',
        'observaciones',
        'competencia_requerida',
    ]
    readonly_fields = ['fecha_creacion', 'fecha_modificacion', 'creado_por', 'duracion_display']
    autocomplete_fields = ['consultorio', 'equipo']

    fieldsets = (
        ('Ubicación', {
            'fields': ('consultorio', 'equipo')
        }),
        ('Profesional', {
            'fields': ('tipo_titular', 'profesional_asignado_temporal', 'profesional_interno', 'profesional_externo'),
            'description': 'Titular nominal: complete interno o externo. Titular genérico: use R2/R3/Jefes y opcionalmente nombre asignado.',
        }),
        ('Horario', {
            'fields': ('dia_semana', 'hora_inicio', 'hora_fin', 'duracion_display')
        }),
        ('Vigencia', {
            'fields': ('fecha_inicio_vigencia', 'fecha_fin_vigencia')
        }),
        ('Configuración Operativa', {
            'fields': (
                'tipo_actividad',
                'tipo_lista',
                ('permite_cobertura_residente', 'prioridad_cobertura'),
                'competencia_requerida',
                'estado',
            )
        }),
        ('Información Adicional', {
            'fields': ('observaciones',)
        }),
        ('Metadatos', {
            'fields': ('creado_por', 'fecha_creacion', 'fecha_modificacion'),
            'classes': ('collapse',),
        }),
    )

    def save_model(self, request, obj, form, change):
        if not change:
            obj.creado_por = request.user
        super().save_model(request, obj, form, change)

    def profesional_display(self, obj):
        nombre = obj.nombre_profesional()
        if obj.tipo_titular != 'NOMINAL':
            return format_html('<span style="color: #6b21a8;">🧩 {}</span>', nombre)
        if obj.profesional_interno:
            return format_html('<span style="color: blue;">👤 {}</span>', nombre)
        if obj.profesional_externo:
            return format_html('<span style="color: green;">👨‍⚕️ {}</span>', nombre)
        return format_html('<span style="color: #999;">Sin asignar</span>')

    profesional_display.short_description = 'Profesional'

    def dia_semana_display(self, obj):
        return obj.get_dia_semana_display()

    dia_semana_display.short_description = 'Día'
    dia_semana_display.admin_order_field = 'dia_semana'

    def horario_display(self, obj):
        if not obj.hora_inicio or not obj.hora_fin:
            return '-'
        return format_html(
            '<strong>{}</strong> - <strong>{}</strong>',
            obj.hora_inicio.strftime('%H:%M'),
            obj.hora_fin.strftime('%H:%M'),
        )

    horario_display.short_description = 'Horario'

    def estado_display(self, obj):
        colores = {
            'ACTIVO': 'green',
            'PAUSADO': 'orange',
            'FINALIZADO': 'red',
        }
        color = colores.get(obj.estado, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_estado_display(),
        )

    estado_display.short_description = 'Estado'
    estado_display.admin_order_field = 'estado'

    def vigencia_display(self, obj):
        if not obj.fecha_inicio_vigencia:
            return '-'
        if obj.fecha_fin_vigencia:
            return format_html(
                '{}<br/><small style="color: #999;">hasta {}</small>',
                obj.fecha_inicio_vigencia.strftime('%d/%m/%Y'),
                obj.fecha_fin_vigencia.strftime('%d/%m/%Y'),
            )
        return format_html(
            '{}<br/><small style="color: green;">Indefinido</small>',
            obj.fecha_inicio_vigencia.strftime('%d/%m/%Y'),
        )

    vigencia_display.short_description = 'Vigencia'

    def duracion_display(self, obj):
        if not obj.hora_inicio or not obj.hora_fin:
            return '-'
        horas = obj.duracion_horas()
        if horas == 0:
            return '-'
        return format_html('<strong>{:.1f}</strong> hora(s)', horas)

    duracion_display.short_description = 'Duración'


@admin.register(AusenciaCobertura)
class AusenciaCoberturaAdmin(admin.ModelAdmin):
    """Administración de ausencias y coberturas de bloques."""

    list_display = [
        'fecha_ausencia',
        'bloque',
        'profesional_ausente_display',
        'residente_sugerido',
        'residente_asignado',
        'estado',
        'reportado_por',
    ]
    list_filter = ['estado', 'motivo', 'fecha_ausencia', 'bloque__consultorio']
    search_fields = [
        'bloque__consultorio__nombre',
        'profesional_ausente_interno__username',
        'profesional_ausente_interno__first_name',
        'profesional_ausente_interno__last_name',
        'profesional_ausente_externo__nombre',
        'profesional_ausente_externo__apellido',
        'residente_asignado__username',
        'observaciones',
    ]
    autocomplete_fields = [
        'bloque',
        'profesional_ausente_interno',
        'profesional_ausente_externo',
        'residente_sugerido',
        'residente_asignado',
        'reportado_por',
    ]
    readonly_fields = ['fecha_creacion', 'fecha_modificacion']

    fieldsets = (
        ('Evento', {
            'fields': ('bloque', 'fecha_ausencia', 'estado', 'motivo', 'detalle_motivo')
        }),
        ('Profesional Ausente', {
            'fields': ('profesional_ausente_interno', 'profesional_ausente_externo')
        }),
        ('Cobertura', {
            'fields': ('residente_sugerido', 'residente_asignado', 'observaciones')
        }),
        ('Auditoría', {
            'fields': ('reportado_por', 'fecha_creacion', 'fecha_modificacion'),
            'classes': ('collapse',),
        }),
    )

    def profesional_ausente_display(self, obj):
        return obj.nombre_profesional_ausente()

    profesional_ausente_display.short_description = 'Ausente'


@admin.register(TareaAgendaEGES)
class TareaAgendaEGESAdmin(admin.ModelAdmin):
    """Administración de tareas EGES para administrativas."""

    list_display = [
        'accion_display',
        'consultorio',
        'profesional_display',
        'fecha_afectada',
        'origen',
        'estado_display',
        'creado_por',
        'fecha_creacion',
    ]
    list_filter = ['estado', 'accion', 'origen', 'consultorio', 'fecha_creacion']
    search_fields = [
        'consultorio__nombre',
        'profesional_interno__first_name',
        'profesional_interno__last_name',
        'profesional_externo__nombre',
        'profesional_externo__apellido',
        'notas',
    ]
    readonly_fields = ['fecha_creacion', 'fecha_ejecucion', 'ejecutado_por']

    fieldsets = (
        ('Tarea', {
            'fields': ('accion', 'origen', 'consultorio', 'notas')
        }),
        ('Profesional', {
            'fields': ('profesional_interno', 'profesional_externo')
        }),
        ('Fecha/Horario', {
            'fields': ('fecha_afectada', 'fecha_desde', 'fecha_hasta', 'hora_inicio', 'hora_fin')
        }),
        ('Estado', {
            'fields': ('estado',)
        }),
        ('Ejecución', {
            'fields': ('ejecutado_por', 'fecha_ejecucion', 'notas_ejecucion'),
            'classes': ('collapse',),
        }),
        ('Auditoría', {
            'fields': ('creado_por', 'fecha_creacion'),
            'classes': ('collapse',),
        }),
    )

    def accion_display(self, obj):
        colores = {
            AccionEGES.HABILITAR: 'green',
            AccionEGES.DESHABILITAR: 'red',
            AccionEGES.REASIGNAR: 'orange',
        }
        color = colores.get(obj.accion, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_accion_display(),
        )

    accion_display.short_description = 'Acción'
    accion_display.admin_order_field = 'accion'

    def profesional_display(self, obj):
        return obj.nombre_profesional()

    profesional_display.short_description = 'Profesional'

    def estado_display(self, obj):
        colores = {
            EstadoTareaEGES.PENDIENTE: 'orange',
            EstadoTareaEGES.EJECUTADO: 'green',
        }
        color = colores.get(obj.estado, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_estado_display(),
        )

    estado_display.short_description = 'Estado'
    estado_display.admin_order_field = 'estado'


@admin.register(SolicitudAgendaExtra)
class SolicitudAgendaExtraAdmin(admin.ModelAdmin):
    """Administración de solicitudes de agenda extra."""

    list_display = [
        'fecha_solicitada',
        'consultorio',
        'profesional_display',
        'horario_display',
        'tipo_actividad',
        'estado',
        'solicitante',
        'resuelto_por',
    ]
    list_filter = ['estado', 'tipo_actividad', 'consultorio', 'fecha_solicitada']
    search_fields = [
        'consultorio__nombre',
        'profesional_interno__first_name',
        'profesional_interno__last_name',
        'profesional_externo__nombre',
        'profesional_externo__apellido',
        'motivo',
    ]
    readonly_fields = ['fecha_creacion', 'fecha_modificacion', 'fecha_resolucion', 'resuelto_por', 'tarea_eges']

    fieldsets = (
        ('Solicitud', {
            'fields': ('solicitante', 'consultorio', 'fecha_solicitada', 'hora_inicio', 'hora_fin', 'tipo_actividad', 'motivo')
        }),
        ('Profesional', {
            'fields': ('profesional_interno', 'profesional_externo')
        }),
        ('Resolución', {
            'fields': ('estado', 'resuelto_por', 'fecha_resolucion', 'observaciones_resolucion', 'tarea_eges'),
            'classes': ('collapse',),
        }),
        ('Metadatos', {
            'fields': ('fecha_creacion', 'fecha_modificacion'),
            'classes': ('collapse',),
        }),
    )

    def profesional_display(self, obj):
        return obj.nombre_profesional()

    profesional_display.short_description = 'Profesional'

    def horario_display(self, obj):
        if not obj.hora_inicio or not obj.hora_fin:
            return '-'
        return format_html(
            '<strong>{}</strong> - <strong>{}</strong>',
            obj.hora_inicio.strftime('%H:%M'),
            obj.hora_fin.strftime('%H:%M'),
        )

    horario_display.short_description = 'Horario'
