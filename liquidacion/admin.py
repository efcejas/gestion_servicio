from django.contrib import admin

from .models import (
    Estudios,
    GrupoTarifario,
    GuardiaPasiva,
    HistorialPrecioEstudio,
    RegistroEstudiosPorMedico,
    SesionContable,
    TarifaGrupoTarifario,
)

# [ELIMINADO - 16 de febrero 2026]
# Import de RegistroProcedimientosIntervensionismo eliminado
# Import de DiaSinPacientes eliminado (deprecado para Colegiales)
# En Colegiales, procedimientos se registran como Estudios


# ============================================================================
# HISTORIALES Y AUDITORÍA
# ============================================================================

class HistorialPrecioEstudioInline(admin.TabularInline):
    model = HistorialPrecioEstudio
    extra = 0
    can_delete = False
    readonly_fields = (
        'precio_cober_anterior',
        'precio_otras_os_anterior',
        'precio_cober_nuevo',
        'precio_otras_os_nuevo',
        'fecha_actualizacion',
        'actualizado_por',
        'motivo_actualizacion',
        'get_variacion_cober',
        'get_variacion_otras_os',
    )
    fields = (
        'fecha_actualizacion',
        'precio_cober_anterior',
        'precio_cober_nuevo',
        'get_variacion_cober',
        'precio_otras_os_anterior',
        'precio_otras_os_nuevo',
        'get_variacion_otras_os',
        'actualizado_por',
        'motivo_actualizacion',
    )

    def get_variacion_cober(self, obj):
        return f"{obj.get_variacion_cober()}%"
    get_variacion_cober.short_description = 'Var. COBER (%)'

    def get_variacion_otras_os(self, obj):
        return f"{obj.get_variacion_otras_os()}%"
    get_variacion_otras_os.short_description = 'Var. Otras OS (%)'


@admin.register(HistorialPrecioEstudio)
class HistorialPrecioEstudioAdmin(admin.ModelAdmin):
    list_display = (
        'estudio',
        'fecha_actualizacion',
        'precio_cober_anterior',
        'precio_cober_nuevo',
        'variacion_cober_display',
        'actualizado_por'
    )
    list_filter = ('fecha_actualizacion', 'estudio__tipo', 'actualizado_por')
    search_fields = ('estudio__nombre', 'estudio__codigo', 'motivo_actualizacion')
    readonly_fields = (
        'estudio',
        'precio_cober_anterior',
        'precio_otras_os_anterior',
        'precio_cober_nuevo',
        'precio_otras_os_nuevo',
        'fecha_actualizacion',
        'actualizado_por',
    )
    date_hierarchy = 'fecha_actualizacion'
    ordering = ('-fecha_actualizacion',)

    def variacion_cober_display(self, obj):
        variacion = obj.get_variacion_cober()
        color = 'red' if variacion > 0 else 'green' if variacion < 0 else 'black'
        return f'<span style="color: {color}; font-weight: bold;">{variacion:+.2f}%</span>'
    variacion_cober_display.short_description = 'Var. COBER (%)'
    variacion_cober_display.allow_tags = True

    def has_add_permission(self, request):
        return False  # Solo se crea automáticamente desde Estudios.actualizar_precios()

    def has_delete_permission(self, request, obj=None):
        return False  # Nunca eliminar historial de precios


# ============================================================================
# GRUPOS TARIFARIOS
# ============================================================================

@admin.register(TarifaGrupoTarifario)
class TarifaGrupoTarifarioAdmin(admin.ModelAdmin):
    list_display = (
        'grupo_tarifario',
        'vigencia_desde',
        'vigencia_hasta',
        'precio_cober',
        'precio_otras_os',
        'actualizado_por',
    )
    list_filter = ('grupo_tarifario__modalidad', 'grupo_tarifario', 'vigencia_desde')
    search_fields = ('grupo_tarifario__codigo', 'grupo_tarifario__nombre', 'motivo_actualizacion')
    ordering = ('grupo_tarifario', '-vigencia_desde')


class TarifaGrupoTarifarioInline(admin.TabularInline):
    model = TarifaGrupoTarifario
    extra = 0
    fields = (
        'vigencia_desde',
        'vigencia_hasta',
        'precio_cober',
        'precio_otras_os',
        'motivo_actualizacion',
        'actualizado_por',
    )


@admin.register(GrupoTarifario)
class GrupoTarifarioAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nombre', 'modalidad', 'activo', 'fecha_modificacion')
    list_filter = ('modalidad', 'activo')
    search_fields = ('codigo', 'nombre')
    ordering = ('modalidad', 'codigo')
    inlines = [TarifaGrupoTarifarioInline]


# ============================================================================
# CATÁLOGO DE ESTUDIOS
# ============================================================================

@admin.register(Estudios)
class EstudiosAdmin(admin.ModelAdmin):
    list_display = (
        'codigo',
        'nombre',
        'tipo',
        'grupo_tarifario',
        'precio_cober',
        'precio_otras_os',
        'precio_unico',
        'conteo_regiones_default',
        'activo',
        'fecha_actualizacion_precios'
    )
    list_filter = ('tipo', 'grupo_tarifario', 'precio_unico', 'activo')
    search_fields = ('codigo', 'nombre')
    ordering = ('codigo', 'nombre')
    readonly_fields = ('fecha_actualizacion_precios', 'actualizado_por')
    inlines = [HistorialPrecioEstudioInline]

    fieldsets = (
        ('Identificación', {
            'fields': ('codigo', 'nombre', 'tipo', 'grupo_tarifario')
        }),
        ('Precios', {
            'fields': (
                'precio_cober',
                'precio_otras_os',
                'precio_unico',
            ),
            'description': 'Si precio_unico=True, se usa precio_cober para ambas OS'
        }),
        ('Regiones', {
            'fields': ('conteo_regiones', 'conteo_regiones_default')
        }),
        ('Estado', {
            'fields': ('activo', 'fecha_actualizacion_precios', 'actualizado_por')
        }),
    )

    def save_model(self, request, obj, form, change):
        if change and ('precio_cober' in form.changed_data or 'precio_otras_os' in form.changed_data):
            obj.actualizar_precios(
                nuevo_precio_cober=obj.precio_cober,
                nuevo_precio_otras_os=obj.precio_otras_os,
                usuario=request.user,
                motivo='Actualización desde Admin'
            )
        else:
            obj.actualizado_por = request.user
            super().save_model(request, obj, form, change)

# ============================================================================
# SESIONES CONTABLES Y LIQUIDACIÓN
# ============================================================================

@admin.register(SesionContable)
class SesionContableAdmin(admin.ModelAdmin):
    list_display = (
        'mes_año_display',
        'estado',
        'count_practicas',
        'count_guardias',
        'fecha_apertura',
        'fecha_cierre',
        'cerrada_por'
    )
    list_filter = ('estado', 'año', 'mes')
    search_fields = ('observaciones',)
    readonly_fields = ('fecha_apertura', 'fecha_cierre', 'fecha_facturacion', 'fecha_pago')
    ordering = ('-año', '-mes')
    
    fieldsets = (
        ('Período', {
            'fields': ('mes', 'año')
        }),
        ('Estado', {
            'fields': ('estado', 'observaciones')
        }),
        ('Fechas', {
            'fields': ('fecha_apertura', 'fecha_cierre', 'fecha_facturacion', 'fecha_pago'),
            'classes': ('collapse',)
        }),
        ('Auditoría', {
            'fields': ('cerrada_por',),
            'classes': ('collapse',)
        }),
    )
    
    def mes_año_display(self, obj):
        meses = ['', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
                'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
        return f"{meses[obj.mes]} {obj.año}"
    mes_año_display.short_description = 'Período'
    mes_año_display.admin_order_field = 'mes'
    
    def count_practicas(self, obj):
        count = obj.practicas.count()
        return f"{count} prácticas"
    count_practicas.short_description = 'Prácticas'
    
    def count_guardias(self, obj):
        count = obj.guardias_pasivas.count()
        return f"{count} guardias"
    count_guardias.short_description = 'Guardias'
    
    actions = ['pasar_a_revision', 'cerrar_sesion']
    
    def pasar_a_revision(self, request, queryset):
        updated = queryset.filter(estado='ABIERTA').update(estado='REVISION')
        self.message_user(request, f"{updated} sesiones pasadas a REVISIÓN")
    pasar_a_revision.short_description = "Pasar a REVISIÓN"
    
    def cerrar_sesion(self, request, queryset):
        from django.utils import timezone
        for sesion in queryset.filter(estado='REVISION'):
            sesion.estado = 'CERRADA'
            sesion.fecha_cierre = timezone.now()
            sesion.cerrada_por = request.user
            sesion.save()
        self.message_user(request, f"{queryset.count()} sesiones CERRADAS")
    cerrar_sesion.short_description = "Cerrar sesiones"


@admin.register(GuardiaPasiva)
class GuardiaPasivaAdmin(admin.ModelAdmin):
    list_display = (
        'medico',
        'fecha_guardia',
        'tipo_guardia',
        'monto',
        'sesion_contable'
    )
    list_filter = ('tipo_guardia', 'sesion_contable__año', 'sesion_contable__mes')
    search_fields = ('medico__first_name', 'medico__last_name', 'observaciones')
    readonly_fields = ('sesion_contable', 'fecha_registro')
    date_hierarchy = 'fecha_guardia'
    ordering = ('-fecha_guardia',)
    
    fieldsets = (
        ('Guardia', {
            'fields': ('medico', 'fecha_guardia', 'tipo_guardia', 'monto')
        }),
        ('Observaciones', {
            'fields': ('observaciones',),
            'classes': ('collapse',)
        }),
        ('Sistema', {
            'fields': ('sesion_contable', 'fecha_registro'),
            'classes': ('collapse',)
        }),
    )


# ============================================================================
# PRÁCTICAS (RegistroEstudiosPorMedico)
# ============================================================================

@admin.register(RegistroEstudiosPorMedico)
class RegistroEstudiosPorMedicoAdmin(admin.ModelAdmin):
    list_display = (
        'medico',
        'fecha_del_informe',
        'paciente_display',
        'estudio_display',
        'tipo_obra_social',
        'horario',
        'cantidad_regiones',
        'monto_calculado',
        'sesion_contable'
    )
    list_filter = (
        'sesion_contable__año',
        'sesion_contable__mes',
        'tipo_obra_social',
        'horario',
        'medico',
        # 'estudio' removido - ahora es M2M through
    )
    search_fields = (
        'nombre_paciente',
        'apellido_paciente',
        'dni_paciente',
        'medico__first_name',
        'medico__last_name'
    )
    readonly_fields = (
        'sesion_contable',
        'monto_calculado',
        'fecha_registro',
        'modificado_por',
        'fecha_modificacion',
        'desglose_monto_display'
    )
    date_hierarchy = 'fecha_del_informe'
    ordering = ('-fecha_del_informe', '-fecha_registro')
    
    fieldsets = (
        ('Médico y Sesión', {
            'fields': ('medico', 'sesion_contable', 'fecha_del_informe')
        }),
        ('Paciente', {
            'fields': ('nombre_paciente', 'apellido_paciente', 'dni_paciente')
        }),
        ('Estudio', {
            'fields': (
                'cantidad_regiones',
            ),
            'description': 'Los estudios se gestionan desde la tabla intermedia RegistroEstudio'
        }),
        ('Facturación', {
            'fields': (
                'tipo_obra_social',
                'horario',
                'monto_calculado',
                'desglose_monto_display',
            )
        }),
        ('Bonus Urgencia (solo RM remoto)', {
            'fields': (
                'paciente_internado',
                'fecha_hora_solicitud',
                'fecha_hora_informe'
            ),
            'classes': ('collapse',)
        }),
        ('Auditoría', {
            'fields': (
                'fecha_registro',
                'modificado_por',
                'fecha_modificacion',
                'motivo_modificacion'
            ),
            'classes': ('collapse',)
        }),
    )
    
    def paciente_display(self, obj):
        return f"{obj.apellido_paciente}, {obj.nombre_paciente}"
    paciente_display.short_description = 'Paciente'
    
    def estudio_display(self, obj):
        estudios_lista = obj.estudio.all()
        if not estudios_lista.exists():
            return '-'
        nombres = [e.nombre for e in estudios_lista]
        return ", ".join(nombres) if len(nombres) <= 2 else f"{nombres[0]}, {nombres[1]} +{len(nombres)-2} más"
    estudio_display.short_description = 'Estudios'
    
    def desglose_monto_display(self, obj):
        desglose = obj.get_desglose_monto()
        if not desglose:
            return '<div>Sin estudios</div>'
        html = f"""<div style='font-family: monospace;'>
        <strong>Estudios:</strong> {desglose['estudios']}<br>
        <strong>Cantidad:</strong> {desglose['cantidad_estudios']} estudio(s)<br>
        <strong>Precio total ({desglose['tipo_os']}):</strong> ${desglose['precio_total']}<br>
        <strong>Regiones:</strong> {desglose['regiones']}<br>
        <strong>Horario:</strong> {desglose['horario']} ({desglose['porcentaje']})<br>
        """
        if desglose.get('bonus_urgencia'):
            html += f"<strong style='color: green;'>Bonus Urgencia:</strong> {desglose['bonus_urgencia']} (Tiempo: {desglose['tiempo_respuesta']})<br>"
        html += f"<strong style='font-size: 14px;'>MONTO FINAL:</strong> <span style='font-size: 14px; color: blue;'>${desglose['monto_final']}</span></div>"
        return html
    desglose_monto_display.short_description = 'Desglose del Monto'
    desglose_monto_display.allow_tags = True


# ============================================================================
# MODELOS DEPRECADOS
# ============================================================================

# DiaSinPacientes [DEPRECADO - No se usa en Colegiales]
# Admin eliminado - Modelo mantenido solo para compatibilidad legacy

# RegistroProcedimientosIntervensionismo [ELIMINADO - 16 de febrero 2026]
# Razón: En Colegiales no se usa, se registra como Estudios
# Ver liquidacion_backup_completo_2026-02-16.json para datos históricos
