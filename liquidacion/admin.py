from django.contrib import admin, messages

from .models import (
    Estudios,
    GrupoTarifario,
    GuardiaPasiva,
    ConfiguracionGuardiaPasiva,
    HistorialConfiguracionGuardiaPasiva,
    HistorialPrecioEstudio,
    HistorialRecalculoTarifaGuardiaPasiva,
    HistorialRecalculoSolicitudRevisionHorario,
    HistorialRecalculoTarifaRegistro,
    HistorialSesionContable,
    PreparacionLiquidacionRRHH,
    ControlEgesSesion,
    ResultadoControlEgesRegistro,
    CorreccionPacsRegistro,
    ReglaDescuentoResidencia,
    RegistroEstudiosPorMedico,
    RevisionAuditoriaEcoRegistro,
    RevisionCruceEgesRegistro,
    SesionContable,
    SolicitudRevisionHorarioRegistro,
    TarifaGrupoTarifario,
)
from .services_auditoria import evaluar_gate_consistencia_sesion

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


class HistorialRecalculoSolicitudRevisionHorarioInline(admin.TabularInline):
    model = HistorialRecalculoSolicitudRevisionHorario
    extra = 0
    can_delete = False
    readonly_fields = (
        'fecha_recalculo',
        'recalculado_por',
        'horario_usado',
        'monto_registro_anterior',
        'monto_aplicado_anterior',
        'monto_recalculado',
        'observacion',
        'motivo_sistema',
    )
    fields = readonly_fields

    def has_add_permission(self, request, obj=None):
        return False


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


@admin.register(PreparacionLiquidacionRRHH)
class PreparacionLiquidacionRRHHAdmin(admin.ModelAdmin):
    list_display = (
        'sesion_contable',
        'version',
        'estado',
        'creado_por',
        'fecha_creacion',
        'snapshot_hash',
    )
    list_filter = ('estado', 'sesion_contable__año', 'sesion_contable__mes')
    search_fields = ('asunto', 'snapshot_hash', 'creado_por__username')
    readonly_fields = (
        'sesion_contable',
        'version',
        'estado',
        'destinatarios_json',
        'cc_json',
        'asunto',
        'cuerpo',
        'resumen_json',
        'snapshot_hash',
        'creado_por',
        'fecha_creacion',
        'actualizado_por',
        'fecha_actualizacion',
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


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


@admin.register(ReglaDescuentoResidencia)
class ReglaDescuentoResidenciaAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'estudio',
        'grupo_tarifario',
        'activo',
        'vigencia_desde',
        'vigencia_hasta',
        'aplica_medico_residente',
        'aplica_jefe_residentes',
        'aplica_instructor_residentes',
    )
    list_filter = (
        'activo',
        'vigencia_desde',
        'vigencia_hasta',
        'aplica_medico_residente',
        'aplica_jefe_residentes',
        'aplica_instructor_residentes',
    )
    search_fields = (
        'estudio__nombre',
        'estudio__codigo',
        'grupo_tarifario__codigo',
        'grupo_tarifario__nombre',
        'observacion',
    )
    readonly_fields = ('fecha_creacion', 'fecha_actualizacion', 'creado_por', 'actualizado_por')
    ordering = ('-vigencia_desde', '-id')
    fieldsets = (
        ('Entidad', {
            'fields': ('estudio', 'grupo_tarifario', 'activo'),
            'description': 'Definir una regla por estudio o por grupo tarifario, no ambas.',
        }),
        ('Roles residencia', {
            'fields': (
                'aplica_medico_residente',
                'aplica_jefe_residentes',
                'aplica_instructor_residentes',
            ),
        }),
        ('Vigencia', {
            'fields': ('vigencia_desde', 'vigencia_hasta'),
        }),
        ('Auditoria', {
            'fields': ('observacion', 'creado_por', 'actualizado_por', 'fecha_creacion', 'fecha_actualizacion'),
            'classes': ('collapse',),
        }),
    )

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.creado_por = request.user
        obj.actualizado_por = request.user
        obj.full_clean()
        super().save_model(request, obj, form, change)


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
    readonly_fields = ('estado', 'fecha_apertura', 'fecha_cierre', 'fecha_facturacion', 'fecha_pago')
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

    def _puede_transicionar_hasta_cerrada(self, user):
        return user.is_superuser or user.rol in ['administrativo', 'jefe_servicio']

    def _puede_transicionar_financiera(self, user):
        return user.is_superuser or user.rol == 'administrativo'
    
    def pasar_a_revision(self, request, queryset):
        if not self._puede_transicionar_hasta_cerrada(request.user):
            self.message_user(request, 'No tienes permisos para pasar sesiones a REVISIÓN.', level=messages.ERROR)
            return
        updated = 0
        advertencias = 0
        for sesion in queryset.filter(estado='ABIERTA'):
            gate = evaluar_gate_consistencia_sesion(sesion, 'REVISION')
            if gate['advertencias']:
                advertencias += len(gate['advertencias'])
            estado_anterior = sesion.estado
            sesion.estado = 'REVISION'
            sesion.save(update_fields=['estado'])
            HistorialSesionContable.objects.create(
                sesion_contable=sesion,
                estado_anterior=estado_anterior,
                estado_nuevo=sesion.estado,
                usuario=request.user,
                origen=HistorialSesionContable.ORIGEN_ADMIN,
                observacion_sistema='Accion admin: pasar a revision',
            )
            updated += 1
        msg = f"{updated} sesiones pasadas a REVISIÓN"
        if advertencias:
            msg += f" (con {advertencias} advertencia(s) de consistencia)"
        self.message_user(request, msg)
    pasar_a_revision.short_description = "Pasar a REVISIÓN"
    
    def cerrar_sesion(self, request, queryset):
        if not self._puede_transicionar_hasta_cerrada(request.user):
            self.message_user(request, 'No tienes permisos para cerrar sesiones.', level=messages.ERROR)
            return
        from django.utils import timezone
        cerradas = 0
        bloqueadas = 0
        for sesion in queryset.filter(estado='REVISION'):
            gate = evaluar_gate_consistencia_sesion(sesion, 'CERRADA')
            if gate['bloqueantes']:
                bloqueadas += 1
                continue
            estado_anterior = sesion.estado
            sesion.estado = 'CERRADA'
            sesion.fecha_cierre = timezone.now()
            sesion.cerrada_por = request.user
            sesion.save()
            HistorialSesionContable.objects.create(
                sesion_contable=sesion,
                estado_anterior=estado_anterior,
                estado_nuevo=sesion.estado,
                usuario=request.user,
                origen=HistorialSesionContable.ORIGEN_ADMIN,
                observacion_sistema='Accion admin: cerrar sesion',
            )
            cerradas += 1
        msg = f"{cerradas} sesiones CERRADAS"
        if bloqueadas:
            msg += f" | {bloqueadas} bloqueadas por inconsistencias"
        self.message_user(request, msg)
    cerrar_sesion.short_description = "Cerrar sesiones"

    def marcar_facturada(self, request, queryset):
        self.message_user(
            request,
            'Transicion financiera deshabilitada en acciones admin. Usa el portal administrativo de liquidacion.',
            level=messages.WARNING,
        )
    marcar_facturada.short_description = "Marcar como FACTURADA"

    def marcar_pagada(self, request, queryset):
        self.message_user(
            request,
            'Transicion financiera deshabilitada en acciones admin. Usa el portal administrativo de liquidacion.',
            level=messages.WARNING,
        )
    marcar_pagada.short_description = "Marcar como PAGADA"


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
    readonly_fields = ('sesion_contable', 'fecha_registro', 'monto')
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


class HistorialConfiguracionGuardiaPasivaInline(admin.TabularInline):
    model = HistorialConfiguracionGuardiaPasiva
    extra = 0
    can_delete = False
    fields = (
        'fecha_cambio',
        'monto_anterior',
        'monto_nuevo',
        'vigente_desde_anterior',
        'vigente_desde_nueva',
        'motivo_actualizacion',
        'actualizado_por',
    )
    readonly_fields = fields
    ordering = ('-fecha_cambio',)


@admin.register(ConfiguracionGuardiaPasiva)
class ConfiguracionGuardiaPasivaAdmin(admin.ModelAdmin):
    list_display = ('monto_vigente', 'vigente_desde', 'vigente_hasta', 'actualizado_por', 'fecha_actualizacion')
    list_filter = ('vigente_desde', 'vigente_hasta')
    search_fields = ('motivo_actualizacion',)
    readonly_fields = ('fecha_actualizacion',)
    inlines = [HistorialConfiguracionGuardiaPasivaInline]

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(HistorialConfiguracionGuardiaPasiva)
class HistorialConfiguracionGuardiaPasivaAdmin(admin.ModelAdmin):
    list_display = (
        'fecha_cambio',
        'monto_anterior',
        'monto_nuevo',
        'vigente_desde_anterior',
        'vigente_desde_nueva',
        'actualizado_por',
    )
    list_filter = ('fecha_cambio', 'actualizado_por')
    readonly_fields = (
        'configuracion',
        'monto_anterior',
        'monto_nuevo',
        'vigente_desde_anterior',
        'vigente_desde_nueva',
        'motivo_actualizacion',
        'actualizado_por',
        'fecha_cambio',
    )
    date_hierarchy = 'fecha_cambio'

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


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


@admin.register(SolicitudRevisionHorarioRegistro)
class SolicitudRevisionHorarioRegistroAdmin(admin.ModelAdmin):
    inlines = [HistorialRecalculoSolicitudRevisionHorarioInline]
    list_display = (
        'id',
        'estado',
        'fecha_solicitud',
        'registro_id',
        'solicitado_por',
        'revisado_por',
        'fecha_revision',
        'aplicado_por',
        'fecha_aplicacion',
        'horario_solicitado',
        'fecha_hora_real_declarada',
    )
    list_filter = ('estado', 'horario_solicitado', 'fecha_solicitud', 'solicitado_por')
    search_fields = (
        'id',
        'registro__id',
        'registro__dni_paciente',
        'registro__apellido_paciente',
        'registro__nombre_paciente',
        'solicitado_por__first_name',
        'solicitado_por__last_name',
    )
    readonly_fields = (
        'registro',
        'solicitado_por',
        'fecha_solicitud',
        'horario_solicitado',
        'fecha_hora_real_declarada',
        'motivo_solicitud',
        'estado',
        'revisado_por',
        'fecha_revision',
        'observacion_revision',
        'aplicado_por',
        'fecha_aplicacion',
        'horario_anterior',
        'horario_aplicado',
        'monto_anterior',
        'monto_aplicado',
        'observacion_aplicacion',
    )
    ordering = ('-fecha_solicitud',)
    date_hierarchy = 'fecha_solicitud'

    fieldsets = (
        ('Solicitud', {
            'fields': (
                'registro',
                'solicitado_por',
                'fecha_solicitud',
                'estado',
            )
        }),
        ('Detalle declarado', {
            'fields': (
                'horario_solicitado',
                'fecha_hora_real_declarada',
                'motivo_solicitud',
            )
        }),
        ('Resolucion administrativa', {
            'fields': (
                'revisado_por',
                'fecha_revision',
                'observacion_revision',
            )
        }),
        ('Aplicacion economica', {
            'fields': (
                'aplicado_por',
                'fecha_aplicacion',
                'horario_anterior',
                'horario_aplicado',
                'monto_anterior',
                'monto_aplicado',
                'observacion_aplicacion',
            )
        }),
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(HistorialRecalculoSolicitudRevisionHorario)
class HistorialRecalculoSolicitudRevisionHorarioAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'solicitud',
        'registro',
        'recalculado_por',
        'fecha_recalculo',
        'horario_usado',
        'monto_registro_anterior',
        'monto_recalculado',
    )
    list_filter = ('fecha_recalculo', 'horario_usado', 'recalculado_por')
    search_fields = ('solicitud__id', 'registro__id')
    readonly_fields = (
        'solicitud',
        'registro',
        'recalculado_por',
        'fecha_recalculo',
        'horario_usado',
        'monto_registro_anterior',
        'monto_aplicado_anterior',
        'monto_recalculado',
        'observacion',
        'motivo_sistema',
    )
    ordering = ('-fecha_recalculo',)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(HistorialRecalculoTarifaRegistro)
class HistorialRecalculoTarifaRegistroAdmin(admin.ModelAdmin):
    list_display = (
        'registro',
        'sesion_contable',
        'fecha_desde',
        'fecha_hasta',
        'monto_anterior',
        'monto_nuevo',
        'diferencia',
        'recalculado_por',
        'fecha_recalculo',
    )
    list_filter = ('sesion_contable', 'fecha_desde', 'fecha_recalculo')
    search_fields = (
        'registro__nombre_paciente',
        'registro__apellido_paciente',
        'registro__dni_paciente',
        'motivo',
    )
    readonly_fields = (
        'sesion_contable',
        'registro',
        'fecha_desde',
        'fecha_hasta',
        'monto_anterior',
        'monto_nuevo',
        'diferencia',
        'motivo',
        'recalculado_por',
        'fecha_recalculo',
    )
    date_hierarchy = 'fecha_recalculo'
    ordering = ('-fecha_recalculo',)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(HistorialRecalculoTarifaGuardiaPasiva)
class HistorialRecalculoTarifaGuardiaPasivaAdmin(admin.ModelAdmin):
    list_display = (
        'fecha_recalculo',
        'sesion_contable',
        'guardia',
        'monto_anterior',
        'monto_nuevo',
        'diferencia',
        'recalculado_por',
    )
    list_filter = ('sesion_contable', 'fecha_recalculo', 'recalculado_por')
    readonly_fields = (
        'sesion_contable',
        'guardia',
        'fecha_desde',
        'fecha_hasta',
        'monto_anterior',
        'monto_nuevo',
        'diferencia',
        'motivo',
        'recalculado_por',
        'fecha_recalculo',
    )
    date_hierarchy = 'fecha_recalculo'

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(RevisionAuditoriaEcoRegistro)
class RevisionAuditoriaEcoRegistroAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'sesion_contable',
        'registro',
        'estado',
        'revisado_por',
        'fecha_revision',
    )
    list_filter = ('estado', 'sesion_contable__año', 'sesion_contable__mes', 'fecha_revision')
    search_fields = (
        'registro__id',
        'registro__apellido_paciente',
        'registro__nombre_paciente',
        'registro__dni_paciente',
        'observacion',
    )
    readonly_fields = (
        'sesion_contable',
        'registro',
        'estado',
        'motivos_json',
        'observacion',
        'revisado_por',
        'fecha_revision',
    )
    ordering = ('-fecha_revision',)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(RevisionCruceEgesRegistro)
class RevisionCruceEgesRegistroAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'sesion_contable',
        'registro',
        'batch_eges',
        'estado',
        'revisado_por',
        'fecha_revision',
    )
    list_filter = ('estado', 'sesion_contable', 'fecha_revision')
    search_fields = (
        'registro__id',
        'registro__apellido_paciente',
        'registro__nombre_paciente',
        'registro__dni_paciente',
        'batch_eges__archivo_nombre',
        'observacion',
    )
    readonly_fields = (
        'sesion_contable',
        'registro',
        'batch_eges',
        'estado',
        'motivos_json',
        'snapshot_json',
        'observacion',
        'revisado_por',
        'fecha_revision',
    )
    ordering = ('-fecha_revision',)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ControlEgesSesion)
class ControlEgesSesionAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'sesion_contable',
        'version',
        'batch_eges',
        'total_registros',
        'total_ok',
        'total_advertencias',
        'total_manuales',
        'procesado_por',
        'fecha_procesamiento',
    )
    list_filter = ('sesion_contable', 'fecha_procesamiento')
    readonly_fields = (
        'sesion_contable',
        'batch_eges',
        'version',
        'total_registros',
        'total_ok',
        'total_advertencias',
        'total_manuales',
        'procesado_por',
        'fecha_procesamiento',
    )
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ResultadoControlEgesRegistro)
class ResultadoControlEgesRegistroAdmin(admin.ModelAdmin):
    list_display = ('id', 'control', 'registro', 'estado')
    list_filter = ('estado', 'control__sesion_contable')
    search_fields = (
        'registro__id',
        'registro__apellido_paciente',
        'registro__nombre_paciente',
        'registro__dni_paciente',
    )
    readonly_fields = ('control', 'registro', 'estado', 'motivos_json', 'snapshot_json')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(CorreccionPacsRegistro)
class CorreccionPacsRegistroAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'sesion_contable',
        'registro',
        'tipo_correccion',
        'horario_anterior',
        'horario_nuevo',
        'hora_pacs',
        'monto_anterior',
        'monto_nuevo',
        'corregido_por',
        'fecha_correccion',
    )
    list_filter = ('sesion_contable', 'fecha_correccion')
    search_fields = (
        'registro__id',
        'registro__apellido_paciente',
        'registro__nombre_paciente',
        'registro__dni_paciente',
        'observacion',
    )
    readonly_fields = (
        'sesion_contable',
        'registro',
        'revision_auditoria_eco',
        'tipo_correccion',
        'horario_anterior',
        'horario_nuevo',
        'hora_pacs',
        'monto_anterior',
        'monto_nuevo',
        'observacion',
        'corregido_por',
        'fecha_correccion',
    )
    ordering = ('-fecha_correccion',)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


# ============================================================================
# MODELOS DEPRECADOS
# ============================================================================

# DiaSinPacientes [DEPRECADO - No se usa en Colegiales]
# Admin eliminado - Modelo mantenido solo para compatibilidad legacy

# RegistroProcedimientosIntervensionismo [ELIMINADO - 16 de febrero 2026]
# Razón: En Colegiales no se usa, se registra como Estudios
# Ver liquidacion_backup_completo_2026-02-16.json para datos históricos
