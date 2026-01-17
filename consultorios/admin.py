"""
Configuración del panel de administración para la app consultorios.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import (
    Consultorio,
    ProfesionalExterno,
    AsignacionEquipoConsultorio,
    BloqueHorario
)


@admin.register(Consultorio)
class ConsultorioAdmin(admin.ModelAdmin):
    """Administración de consultorios"""
    
    list_display = [
        'nombre_con_estado',
        'ubicacion',
        'capacidad_pacientes_hora',
        'cantidad_equipos',
        'cantidad_bloques_activos',
        'fecha_creacion'
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
            'classes': ('collapse',)
        }),
    )
    
    def nombre_con_estado(self, obj):
        """Muestra el nombre con indicador visual de estado"""
        if obj.esta_activo:
            return format_html(
                '<span style="color: green;">●</span> {}',
                obj.nombre
            )
        return format_html(
            '<span style="color: red;">●</span> <span style="color: #999;">{}</span>',
            obj.nombre
        )
    nombre_con_estado.short_description = 'Consultorio'
    nombre_con_estado.admin_order_field = 'nombre'
    
    def cantidad_equipos(self, obj):
        """Cuenta equipos asignados actualmente"""
        count = obj.equipos_asignados().count()
        if count > 0:
            return format_html('<strong>{}</strong> equipo(s)', count)
        return format_html('<span style="color: #999;">Sin equipos</span>')
    cantidad_equipos.short_description = 'Equipos'
    
    def cantidad_bloques_activos(self, obj):
        """Cuenta bloques horarios activos"""
        count = obj.bloques_horarios.filter(estado='ACTIVO').count()
        if count > 0:
            return format_html('<strong style="color: green;">{}</strong> bloque(s)', count)
        return format_html('<span style="color: #999;">Sin bloques</span>')
    cantidad_bloques_activos.short_description = 'Bloques Activos'


@admin.register(ProfesionalExterno)
class ProfesionalExternoAdmin(admin.ModelAdmin):
    """Administración de profesionales externos"""
    
    list_display = [
        'nombre_completo_con_estado',
        'matricula',
        'especialidad',
        'telefono',
        'email',
        'cantidad_bloques',
        'fecha_creacion'
    ]
    
    list_filter = ['esta_activo', 'especialidad', 'fecha_creacion']
    
    search_fields = ['nombre', 'apellido', 'matricula', 'email']
    
    readonly_fields = ['fecha_creacion', 'fecha_modificacion']
    
    fieldsets = (
        ('Información Personal', {
            'fields': ('nombre', 'apellido', 'matricula', 'esta_activo')
        }),
        ('Información Profesional', {
            'fields': ('especialidad',)
        }),
        ('Contacto', {
            'fields': ('telefono', 'email')
        }),
        ('Notas', {
            'fields': ('observaciones',)
        }),
        ('Metadatos', {
            'fields': ('fecha_creacion', 'fecha_modificacion'),
            'classes': ('collapse',)
        }),
    )
    
    def nombre_completo_con_estado(self, obj):
        """Muestra el nombre completo con indicador de estado"""
        if obj.esta_activo:
            return format_html(
                '<span style="color: green;">●</span> Dr./Dra. {}, {}',
                obj.apellido,
                obj.nombre
            )
        return format_html(
            '<span style="color: red;">●</span> <span style="color: #999;">Dr./Dra. {}, {}</span>',
            obj.apellido,
            obj.nombre
        )
    nombre_completo_con_estado.short_description = 'Profesional'
    nombre_completo_con_estado.admin_order_field = 'apellido'
    
    def cantidad_bloques(self, obj):
        """Cuenta bloques horarios asignados"""
        count = obj.bloques_horarios.filter(estado='ACTIVO').count()
        if count > 0:
            return format_html('<strong>{}</strong> bloque(s)', count)
        return format_html('<span style="color: #999;">Sin bloques</span>')
    cantidad_bloques.short_description = 'Bloques Activos'


@admin.register(AsignacionEquipoConsultorio)
class AsignacionEquipoConsultorioAdmin(admin.ModelAdmin):
    """Administración de asignaciones de equipos a consultorios"""
    
    list_display = [
        'equipo',
        'consultorio',
        'tipo_asignacion',
        'fecha_inicio',
        'fecha_fin',
        'estado_vigencia',
        'fecha_creacion'
    ]
    
    list_filter = [
        'es_permanente',
        'consultorio',
        'equipo__area',
        'fecha_inicio'
    ]
    
    search_fields = [
        'equipo__nombre',
        'consultorio__nombre',
        'observaciones'
    ]
    
    readonly_fields = ['fecha_creacion', 'fecha_modificacion', 'estado_vigencia']
    
    autocomplete_fields = ['equipo', 'consultorio']
    
    fieldsets = (
        ('Asignación', {
            'fields': ('consultorio', 'equipo')
        }),
        ('Período', {
            'fields': ('es_permanente', 'fecha_inicio', 'fecha_fin'),
            'description': 'Si es permanente, no necesita fecha de fin. Si es temporal, debe especificar ambas fechas.'
        }),
        ('Información Adicional', {
            'fields': ('observaciones',)
        }),
        ('Metadatos', {
            'fields': ('estado_vigencia', 'fecha_creacion', 'fecha_modificacion'),
            'classes': ('collapse',)
        }),
    )
    
    def get_form(self, request, obj=None, **kwargs):
        """Personalizar el formulario del admin"""
        form = super().get_form(request, obj, **kwargs)
        
        # Establecer fecha de inicio por defecto como hoy
        if not obj and 'fecha_inicio' in form.base_fields:
            from django.utils import timezone
            form.base_fields['fecha_inicio'].initial = timezone.now().date()
        
        # Ayuda contextual para el campo es_permanente
        if 'es_permanente' in form.base_fields:
            form.base_fields['es_permanente'].help_text = (
                "Marca esto si el equipo estará asignado indefinidamente. "
                "Si NO es permanente, debes especificar una fecha de fin."
            )
        
        return form
    
    def tipo_asignacion(self, obj):
        """Muestra el tipo de asignación"""
        if obj.es_permanente:
            return format_html('<span style="color: blue; font-weight: bold;">PERMANENTE</span>')
        return format_html('<span style="color: orange;">TEMPORAL</span>')
    tipo_asignacion.short_description = 'Tipo'
    
    def estado_vigencia(self, obj):
        """Muestra si la asignación está vigente"""
        if obj.esta_vigente():
            return format_html('<span style="color: green; font-weight: bold;">✓ VIGENTE</span>')
        return format_html('<span style="color: red;">✗ No vigente</span>')
    estado_vigencia.short_description = 'Estado'


@admin.register(BloqueHorario)
class BloqueHorarioAdmin(admin.ModelAdmin):
    """Administración de bloques horarios"""
    
    list_display = [
        'consultorio',
        'profesional_display',
        'dia_semana_display',
        'horario_display',
        'tipo_actividad',
        'estado_display',
        'vigencia_display'
    ]
    
    list_filter = [
        'estado',
        'dia_semana',
        'tipo_actividad',
        'consultorio',
        'fecha_inicio_vigencia'
    ]
    
    search_fields = [
        'consultorio__nombre',
        'profesional_interno__username',
        'profesional_interno__first_name',
        'profesional_interno__last_name',
        'profesional_externo__nombre',
        'profesional_externo__apellido',
        'observaciones'
    ]
    
    readonly_fields = [
        'fecha_creacion',
        'fecha_modificacion',
        'creado_por',
        'duracion_display'
    ]
    
    autocomplete_fields = ['consultorio', 'equipo']
    
    fieldsets = (
        ('Ubicación', {
            'fields': ('consultorio', 'equipo')
        }),
        ('Profesional', {
            'fields': ('profesional_interno', 'profesional_externo'),
            'description': 'Seleccione UN profesional (interno O externo, no ambos)'
        }),
        ('Horario', {
            'fields': (
                'dia_semana',
                'hora_inicio',
                'hora_fin',
                'duracion_display'
            )
        }),
        ('Vigencia', {
            'fields': ('fecha_inicio_vigencia', 'fecha_fin_vigencia')
        }),
        ('Configuración', {
            'fields': ('tipo_actividad', 'estado')
        }),
        ('Información Adicional', {
            'fields': ('observaciones',)
        }),
        ('Metadatos', {
            'fields': ('creado_por', 'fecha_creacion', 'fecha_modificacion'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        """Guarda el modelo y registra quién lo creó"""
        if not change:  # Si es un nuevo objeto
            obj.creado_por = request.user
        super().save_model(request, obj, form, change)
    
    def profesional_display(self, obj):
        """Muestra el profesional (interno o externo)"""
        nombre = obj.nombre_profesional()
        if obj.profesional_interno:
            return format_html('<span style="color: blue;">👤 {}</span>', nombre)
        elif obj.profesional_externo:
            return format_html('<span style="color: green;">👨‍⚕️ {}</span>', nombre)
        return format_html('<span style="color: #999;">Sin asignar</span>')
    profesional_display.short_description = 'Profesional'
    
    def dia_semana_display(self, obj):
        """Muestra el día de la semana"""
        return obj.get_dia_semana_display()
    dia_semana_display.short_description = 'Día'
    dia_semana_display.admin_order_field = 'dia_semana'
    
    def horario_display(self, obj):
        """Muestra el horario en formato legible"""
        if not obj.hora_inicio or not obj.hora_fin:
            return '-'
        
        return format_html(
            '<strong>{}</strong> - <strong>{}</strong>',
            obj.hora_inicio.strftime('%H:%M'),
            obj.hora_fin.strftime('%H:%M')
        )
    horario_display.short_description = 'Horario'
    
    def estado_display(self, obj):
        """Muestra el estado con color"""
        colores = {
            'ACTIVO': 'green',
            'PAUSADO': 'orange',
            'FINALIZADO': 'red'
        }
        color = colores.get(obj.estado, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_estado_display()
        )
    estado_display.short_description = 'Estado'
    estado_display.admin_order_field = 'estado'
    
    def vigencia_display(self, obj):
        """Muestra el período de vigencia"""
        if not obj.fecha_inicio_vigencia:
            return '-'
        
        if obj.fecha_fin_vigencia:
            return format_html(
                '{}<br/><small style="color: #999;">hasta {}</small>',
                obj.fecha_inicio_vigencia.strftime('%d/%m/%Y'),
                obj.fecha_fin_vigencia.strftime('%d/%m/%Y')
            )
        return format_html(
            '{}<br/><small style="color: green;">Indefinido</small>',
            obj.fecha_inicio_vigencia.strftime('%d/%m/%Y')
        )
    vigencia_display.short_description = 'Vigencia'
    
    def duracion_display(self, obj):
        """Muestra la duración del bloque"""
        if not obj.hora_inicio or not obj.hora_fin:
            return '-'
        
        horas = obj.duracion_horas()
        if horas == 0:
            return '-'
        
        return format_html('<strong>{:.1f}</strong> hora(s)', horas)
    duracion_display.short_description = 'Duración'
