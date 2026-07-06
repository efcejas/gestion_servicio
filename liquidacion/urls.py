from django.urls import path
from .views import (
    EstudiosCreateView,
    EstudiosListView,
    EstudiosUpdateView,
    SolicitudRevisionHorarioRegistroCreateView,
    RegistroEstudiosPorMedicoCreateView,
    RegistroEstudiosPorMedicoAdminDetailView,
    RegistroEstudiosPorMedicoListView,
    RegistroEstudiosPorMedicoUpdateView,
    RegistroEstudiosPorMedicoDeleteView,
    generar_pdf_liquidacion,
    LiquidacionPorMedicoPorMesListView,  # [NUEVO v3.0] Vista unificada
    exportar_excel_liquidacion,  # [NUEVO v3.0] Exportación unificada
    exportar_excel_liquidacion_definitiva,
    exportar_excel_mis_registros,
    # RegistrarDiaSinPacientesView,  # [DEPRECADO] No se usa en Colegiales
    RegistrarGuardiaPasivaView,  # [NUEVO v2.0]
    GuardiaPasivaUpdateView,  # [NUEVO v3.2]
    GuardiaPasivaDeleteView,  # [NUEVO v3.2]
    CargaMasivaView,
    PortalLiquidacionInicioView,
    SolicitudRevisionHorarioAdminListView,
    SolicitudRevisionHorarioAdminDetailView,
    SolicitudRevisionHorarioResolverView,
    SolicitudRevisionHorarioBulkActionView,
    SolicitudRevisionHorarioAplicarView,
    SolicitudRevisionHorarioRecalcularAplicacionView,
    AuditoriaEcoSesionView,
    AuditoriaEcoRegistroResolverView,
    AuditoriaEcoRegistroCorregirView,
    AuditoriaEcoCorreccionPacsBulkView,
    GruposTarifariosListView,
    GrupoTarifarioDetalleView,
    GrupoTarifarioTarifaNuevaView,
    SesionContableListView,       # [NUEVO Fase B] Gestión del ciclo contable
    PreparacionLiquidacionRRHHPreviewView,
    sesion_contable_transicion,   # [NUEVO Fase B] Transición de estado
)

# [ELIMINADO - 16 de feb 2026] 
# ProcedimientosIntervensionismoListCreateView, ProcedimientosIntervensionismoListView, 
# ProcedimientosIntervensionismoUpdateView, ProcedimientosIntervensionismoDeleteView,
# ProcedimientosPorMedicoPorMesListView, exportar_excel_procedimientos
# Razón: En Colegiales, procedimientos se registran como estudios

app_name = 'liquidacion'

urlpatterns = [

    # ===== PORTAL ADMINISTRATIVO (Sin Login) =====
    path('portal/', PortalLiquidacionInicioView.as_view(), name='portal_inicio'),
    path('grupos-tarifarios/', GruposTarifariosListView.as_view(), name='grupos_tarifarios_list'),
    path('grupos-tarifarios/<int:pk>/', GrupoTarifarioDetalleView.as_view(), name='grupo_tarifario_detalle'),
    path(
        'solicitudes-revision-horario/',
        SolicitudRevisionHorarioAdminListView.as_view(),
        name='solicitudes_revision_horario_list',
    ),
    path(
        'solicitudes-revision-horario/<int:pk>/',
        SolicitudRevisionHorarioAdminDetailView.as_view(),
        name='solicitudes_revision_horario_detalle',
    ),
    path(
        'solicitudes-revision-horario/<int:pk>/resolver/',
        SolicitudRevisionHorarioResolverView.as_view(),
        name='solicitud_revision_horario_resolver',
    ),
    path(
        'solicitudes-revision-horario/accion-masiva/',
        SolicitudRevisionHorarioBulkActionView.as_view(),
        name='solicitudes_revision_horario_accion_masiva',
    ),
    path(
        'solicitudes-revision-horario/<int:pk>/aplicar/',
        SolicitudRevisionHorarioAplicarView.as_view(),
        name='solicitud_revision_horario_aplicar',
    ),
    path(
        'solicitudes-revision-horario/<int:pk>/recalcular-aplicacion/',
        SolicitudRevisionHorarioRecalcularAplicacionView.as_view(),
        name='solicitud_revision_horario_recalcular_aplicacion',
    ),
    path(
        'sesiones/<int:pk>/auditoria-eco/',
        AuditoriaEcoSesionView.as_view(),
        name='auditoria_eco_sesion',
    ),
    path(
        'sesiones/<int:pk>/auditoria-eco/<int:registro_pk>/resolver/',
        AuditoriaEcoRegistroResolverView.as_view(),
        name='auditoria_eco_registro_resolver',
    ),
    path(
        'sesiones/<int:pk>/auditoria-eco/<int:registro_pk>/corregir/',
        AuditoriaEcoRegistroCorregirView.as_view(),
        name='auditoria_eco_registro_corregir',
    ),
    path(
        'sesiones/<int:pk>/auditoria-eco/corregir-ajustes-masivo/',
        AuditoriaEcoCorreccionPacsBulkView.as_view(),
        name='auditoria_eco_correccion_pacs_masiva',
    ),
    path(
        'grupos-tarifarios/<int:grupo_pk>/tarifas/nueva/',
        GrupoTarifarioTarifaNuevaView.as_view(),
        name='grupo_tarifario_tarifa_nueva',
    ),
    
    # [NUEVO v3.0 - VISTA UNIFICADA RECOMENDADA]
    path('liquidacion-mensual/', LiquidacionPorMedicoPorMesListView.as_view(), name='liquidacion_mensual'),
    path('exportar_excel_liquidacion/', exportar_excel_liquidacion, name='exportar_excel_liquidacion'),
    path(
        'exportar_excel_liquidacion_definitiva/',
        exportar_excel_liquidacion_definitiva,
        name='exportar_excel_liquidacion_definitiva',
    ),

    # ===== RUTAS INTERNAS (Requieren Login) =====
    path('estudios/nuevo/', EstudiosCreateView.as_view(), name='estudios_nuevo'),
    path('estudios/', EstudiosListView.as_view(), name='estudios_list'),
    path('estudios/<int:pk>/editar/', EstudiosUpdateView.as_view(), name='estudios_edit'),

    # Rutas para Registro de Estudios por Medico
    path('registro_estudios_por_medico/nuevo/', RegistroEstudiosPorMedicoCreateView.as_view(), name='registroestudios_nuevo'),
    path('registro_estudios_por_medico/', RegistroEstudiosPorMedicoListView.as_view(), name='registroestudios_list'),
    path('registro_estudios_por_medico/exportar-excel/', exportar_excel_mis_registros, name='exportar_excel_mis_registros'),
    path('registro_estudios_por_medico/<int:pk>/inspeccionar/', RegistroEstudiosPorMedicoAdminDetailView.as_view(), name='registroestudios_admin_detalle'),
    path(
        'registro_estudios_por_medico/<int:registro_pk>/solicitar-revision/',
        SolicitudRevisionHorarioRegistroCreateView.as_view(),
        name='solicitud_revision_horario_nueva',
    ),
    path('editar/<int:pk>/', RegistroEstudiosPorMedicoUpdateView.as_view(), name='registroestudios_edit'),
    path('eliminar/<int:pk>/', RegistroEstudiosPorMedicoDeleteView.as_view(), name='registroestudios_delete'),
    # path('registrar-dia-sin-pacientes/', RegistrarDiaSinPacientesView.as_view(), name='registrar_dia_sin_pacientes'),  # [DEPRECADO]

    # Rutas nuevas v2.0
    path('guardia-pasiva/nuevo/', RegistrarGuardiaPasivaView.as_view(), name='registrar_guardia_pasiva'),
    path('guardia-pasiva/editar/<int:pk>/', GuardiaPasivaUpdateView.as_view(), name='editar_guardia_pasiva'),
    path('guardia-pasiva/eliminar/<int:pk>/', GuardiaPasivaDeleteView.as_view(), name='eliminar_guardia_pasiva'),

    # Ruta para generar PDF
    path('generar-pdf/', generar_pdf_liquidacion, name='generar_pdf_liquidacion'),

    # [ELIMINADO - 16 de febrero 2026]
    # Rutas de procedimientos intervensionismo eliminadas:
    # - path('procedimientos-intervensionismo/', ...)
    # - path('procedimientos_intervensionismo/<int:pk>/editar/', ...)
    # - path('procedimientos_intervensionismo/<int:pk>/eliminar/', ...)
    # - path('mis-procedimientos/', ...)
    # Razón: En Colegiales se usa RegistroEstudios para todo

    # Ruta para la carga masiva de estudios (solo admin)
    path('carga-excel/', CargaMasivaView.as_view(), name='carga-masiva'),

    # ===== GESTIÓN DE SESIONES CONTABLES (Fase B) =====
    path('sesiones/', SesionContableListView.as_view(), name='sesiones_list'),
    path('sesiones/<int:pk>/rrhh/preview/', PreparacionLiquidacionRRHHPreviewView.as_view(), name='preparacion_rrhh_preview'),
    path('sesiones/<int:pk>/transicion/', sesion_contable_transicion, name='sesion_transicion'),
]
