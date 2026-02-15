"""
Configuración del panel de administración para pedidos de estudios.
"""
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from .models import (
    PacienteEstudio,
    TipoEstudio,
    PedidoEstudio,
    AdjuntoEmail,
    LogProcesamientoEmail,
    MedicoGuardia
)


@admin.register(PacienteEstudio)
class PacienteEstudioAdmin(admin.ModelAdmin):
    list_display = [
        'nombre_completo', 'dni', 'historia_clinica', 
        'habitacion', 'cama', 'fecha_creacion'
    ]
    list_filter = ['piso', 'fecha_creacion']
    search_fields = [
        'nombre_completo', 'dni', 'historia_clinica', 
        'telefono', 'email'
    ]
    readonly_fields = ['fecha_creacion', 'fecha_modificacion']
    
    fieldsets = (
        ('Identificación', {
            'fields': ('nombre_completo', 'dni', 'historia_clinica')
        }),
        ('Contacto', {
            'fields': ('telefono', 'email')
        }),
        ('Datos Clínicos', {
            'fields': ('fecha_nacimiento', 'obra_social', 'numero_afiliado')
        }),
        ('Ubicación', {
            'fields': ('piso', 'habitacion', 'cama')
        }),
        ('Metadata', {
            'fields': ('fecha_creacion', 'fecha_modificacion'),
            'classes': ('collapse',)
        }),
    )


class AdjuntoEmailInline(admin.TabularInline):
    model = AdjuntoEmail
    extra = 0
    readonly_fields = ['nombre_archivo', 'tipo_mime', 'tamaño', 'fecha_subida']
    can_delete = False


@admin.register(TipoEstudio)
class TipoEstudioAdmin(admin.ModelAdmin):
    list_display = [
        'nombre', 'modalidad', 'medico_responsable', 
        'tiempo_estimado', 'activo'
    ]
    list_filter = ['modalidad', 'activo', 'requiere_preparacion']
    search_fields = ['nombre', 'descripcion', 'codigo_interno']
    readonly_fields = ['fecha_creacion', 'fecha_modificacion']
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('nombre', 'modalidad', 'descripcion', 'codigo_interno')
        }),
        ('Responsables', {
            'fields': ('medico_responsable', 'email_notificacion')
        }),
        ('Configuración', {
            'fields': ('requiere_preparacion', 'tiempo_estimado', 'activo')
        }),
        ('Metadata', {
            'fields': ('fecha_creacion', 'fecha_modificacion'),
            'classes': ('collapse',)
        }),
    )


@admin.register(PedidoEstudio)
class PedidoEstudioAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'paciente_nombre', 'tipo_estudio_display', 
        'estado_badge', 'prioridad_badge', 
        'fecha_solicitud', 'requiere_revision_badge'
    ]
    list_filter = [
        'estado', 'prioridad', 'requiere_revision', 
        'procesado_automaticamente', 'notificacion_enviada',
        'fecha_solicitud'
    ]
    search_fields = [
        'paciente__nombre_completo', 'medico_solicitante',
        'descripcion_estudio', 'email_asunto'
    ]
    readonly_fields = [
        'fecha_creacion', 'fecha_modificacion', 
        'email_message_id', 'datos_raw',
        'ver_email_original'
    ]
    
    date_hierarchy = 'fecha_solicitud'
    inlines = [AdjuntoEmailInline]
    
    fieldsets = (
        ('Información del Paciente', {
            'fields': ('paciente',)
        }),
        ('Estudio Solicitado', {
            'fields': (
                'tipo_estudio', 'descripcion_estudio', 
                'indicacion_clinica', 'observaciones'
            )
        }),
        ('Médicos', {
            'fields': ('medico_solicitante', 'medico_asignado')
        }),
        ('Estado y Prioridad', {
            'fields': ('estado', 'prioridad')
        }),
        ('Fechas', {
            'fields': (
                'fecha_solicitud', 'fecha_programada', 'fecha_realizacion'
            )
        }),
        ('Email Original', {
            'fields': (
                'email_message_id', 'email_asunto', 'email_remitente',
                'email_fecha', 'ver_email_original', 'datos_raw'
            ),
            'classes': ('collapse',)
        }),
        ('Control de Procesamiento', {
            'fields': (
                'procesado_automaticamente', 'requiere_revision',
                'revisado_por', 'fecha_revision'
            ),
            'classes': ('collapse',)
        }),
        ('Notificaciones', {
            'fields': ('notificacion_enviada', 'fecha_notificacion'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('fecha_creacion', 'fecha_modificacion', 'creado_por'),
            'classes': ('collapse',)
        }),
    )
    
    actions = [
        'marcar_como_procesado',
        'enviar_notificaciones',
        'marcar_como_urgente'
    ]
    
    def paciente_nombre(self, obj):
        return obj.paciente.nombre_completo
    paciente_nombre.short_description = 'Paciente'
    
    def tipo_estudio_display(self, obj):
        return obj.tipo_estudio or "Sin especificar"
    tipo_estudio_display.short_description = 'Tipo de Estudio'
    
    def estado_badge(self, obj):
        colors = {
            'PENDIENTE': '#ffc107',
            'PROCESANDO': '#17a2b8',
            'PROGRAMADO': '#007bff',
            'REALIZADO': '#28a745',
            'CANCELADO': '#6c757d',
            'ERROR': '#dc3545',
        }
        color = colors.get(obj.estado, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; '
            'padding: 3px 10px; border-radius: 3px; font-weight: bold;">{}</span>',
            color, obj.get_estado_display()
        )
    estado_badge.short_description = 'Estado'
    
    def prioridad_badge(self, obj):
        colors = {
            'URGENTE': '#dc3545',
            'ALTA': '#fd7e14',
            'NORMAL': '#28a745',
            'BAJA': '#6c757d',
        }
        color = colors.get(obj.prioridad, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; '
            'padding: 3px 10px; border-radius: 3px;">{}</span>',
            color, obj.get_prioridad_display()
        )
    prioridad_badge.short_description = 'Prioridad'
    
    def requiere_revision_badge(self, obj):
        if obj.requiere_revision:
            return format_html(
                '<span style="color: #dc3545; font-weight: bold;">⚠ Sí</span>'
            )
        return format_html('<span style="color: #28a745;">✓ No</span>')
    requiere_revision_badge.short_description = 'Revisión'
    
    def ver_email_original(self, obj):
        if obj.datos_raw:
            return format_html('<pre>{}</pre>', str(obj.datos_raw))
        return "No disponible"
    ver_email_original.short_description = 'Datos del Email'
    
    @admin.action(description='Marcar como procesado')
    def marcar_como_procesado(self, request, queryset):
        updated = 0
        for pedido in queryset:
            pedido.marcar_como_procesado(usuario=request.user)
            updated += 1
        self.message_user(request, f'{updated} pedidos marcados como procesados.')
    
    @admin.action(description='Enviar notificaciones pendientes')
    def enviar_notificaciones(self, request, queryset):
        from .services.notificador import NotificadorPedidos
        
        notificador = NotificadorPedidos()
        enviados = 0
        
        for pedido in queryset.filter(notificacion_enviada=False):
            if notificador.notificar_pedido(pedido):
                enviados += 1
        
        self.message_user(request, f'{enviados} notificaciones enviadas.')
    
    @admin.action(description='Marcar como URGENTE')
    def marcar_como_urgente(self, request, queryset):
        updated = queryset.update(prioridad='URGENTE')
        self.message_user(request, f'{updated} pedidos marcados como urgentes.')


@admin.register(AdjuntoEmail)
class AdjuntoEmailAdmin(admin.ModelAdmin):
    list_display = ['nombre_archivo', 'pedido', 'tipo_mime', 'tamaño_kb', 'fecha_subida']
    list_filter = ['tipo_mime', 'fecha_subida']
    search_fields = ['nombre_archivo', 'pedido__paciente__nombre_completo']
    readonly_fields = ['fecha_subida']
    
    def tamaño_kb(self, obj):
        return f"{obj.tamaño / 1024:.2f} KB"
    tamaño_kb.short_description = 'Tamaño'


@admin.register(LogProcesamientoEmail)
class LogProcesamientoEmailAdmin(admin.ModelAdmin):
    list_display = [
        'email_asunto', 'email_remitente', 'resultado_badge',
        'pedido_creado', 'fecha_procesamiento', 'tiempo_procesamiento'
    ]
    list_filter = ['resultado', 'fecha_procesamiento']
    search_fields = [
        'email_asunto', 'email_remitente', 
        'email_message_id', 'mensaje'
    ]
    readonly_fields = [
        'email_message_id', 'email_asunto', 'email_remitente',
        'email_fecha', 'resultado', 'pedido_creado', 'mensaje',
        'datos_extraidos', 'errores', 'fecha_procesamiento',
        'tiempo_procesamiento'
    ]
    
    date_hierarchy = 'fecha_procesamiento'
    
    def resultado_badge(self, obj):
        colors = {
            'EXITO': '#28a745',
            'ERROR': '#dc3545',
            'PARCIAL': '#ffc107',
            'DUPLICADO': '#6c757d',
        }
        color = colors.get(obj.resultado, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; '
            'padding: 3px 10px; border-radius: 3px;">{}</span>',
            color, obj.get_resultado_display()
        )
    resultado_badge.short_description = 'Resultado'
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False


@admin.register(MedicoGuardia)
class MedicoGuardiaAdmin(admin.ModelAdmin):
    list_display = [
        'nombre_completo', 'especialidad_badge', 'activo_badge',
        'email_display', 'orden_rotacion'
    ]
    list_filter = ['especialidad', 'activo', 'fecha_creacion']
    search_fields = ['nombre_completo', 'email', 'matricula', 'telefono']
    readonly_fields = ['fecha_creacion', 'fecha_modificacion']
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('usuario', 'nombre_completo', 'matricula')
        }),
        ('Especialidad y Disponibilidad', {
            'fields': ('especialidad', 'activo', 'orden_rotacion')
        }),
        ('Contacto', {
            'fields': ('email', 'telefono', 'whatsapp')
        }),
        ('Notas', {
            'fields': ('notas',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('fecha_creacion', 'fecha_modificacion'),
            'classes': ('collapse',)
        }),
    )
    
    def especialidad_badge(self, obj):
        colors = {
            'DOPPLER': '#17a2b8',
            'ECOCARDIO': '#28a745',
            'AMBOS': '#6f42c1',
        }
        color = colors.get(obj.especialidad, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; '
            'padding: 3px 10px; border-radius: 3px;">{}</span>',
            color, obj.get_especialidad_display()
        )
    especialidad_badge.short_description = 'Especialidad'
    
    def activo_badge(self, obj):
        if obj.activo:
            return format_html(
                '<span style="color: #28a745; font-weight: bold;">✓ Activo</span>'
            )
        return format_html(
            '<span style="color: #dc3545; font-weight: bold;">✗ Inactivo</span>'
        )
    activo_badge.short_description = 'Estado'
    
    def email_display(self, obj):
        email = obj.get_email_contacto()
        if obj.usuario:
            return format_html(
                '{} <small>(usuario del sistema)</small>',
                email
            )
        return email
    email_display.short_description = 'Email'
