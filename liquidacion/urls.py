from django.urls import path
from .views import (
    EstudiosCreateView,
    EstudiosListView,
    RegistroEstudiosPorMedicoCreateView,
    RegistroEstudiosPorMedicoListView,
    RegistroEstudiosPorMedicoUpdateView,
    RegistroEstudiosPorMedicoDeleteView,
    generar_pdf_liquidacion,
    InformadosPorMedicoPorMesListView,  # [DEPRECADO v3.0] - Usar LiquidacionPorMedicoPorMesListView
    EcografiasPorMedicoPorMesListView,  # [DEPRECADO v3.0] - Usar LiquidacionPorMedicoPorMesListView
    LiquidacionPorMedicoPorMesListView,  # [NUEVO v3.0] Vista unificada
    exportar_excel_informes,  # [DEPRECADO v3.0] - Usar exportar_excel_liquidacion
    exportar_excel_ecografias,  # [DEPRECADO v3.0] - Usar exportar_excel_liquidacion
    exportar_excel_liquidacion,  # [NUEVO v3.0] Exportación unificada
    # RegistrarDiaSinPacientesView,  # [DEPRECADO] No se usa en Colegiales
    RegistrarGuardiaPasivaView,  # [NUEVO v2.0]
    CargaMasivaView,
    PortalLiquidacionInicioView
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
    
    # [NUEVO v3.0 - VISTA UNIFICADA RECOMENDADA]
    path('liquidacion-mensual/', LiquidacionPorMedicoPorMesListView.as_view(), name='liquidacion_mensual'),
    path('exportar_excel_liquidacion/', exportar_excel_liquidacion, name='exportar_excel_liquidacion'),
    
    # [Mantenidas por compatibilidad - Considerar deprecar]
    path('informados-por-medico-por-mes/', InformadosPorMedicoPorMesListView.as_view(), name='informados_por_medico_por_mes'),
    path('ecografias-por-medico-por-mes/', EcografiasPorMedicoPorMesListView.as_view(), name='ecografias_por_medico_por_mes'),
    # [ELIMINADO - 16 feb 2026] path('procedimientos-por-medico-por-mes/', ProcedimientosPorMedicoPorMesListView.as_view(), ...),
    path('exportar_excel_informes/', exportar_excel_informes, name='exportar_excel_informes'),
    path('exportar_excel_ecografias/', exportar_excel_ecografias, name='exportar_excel_ecografias'),
    # [ELIMINADO - 16 feb 2026] path('exportar_excel_procedimientos/', exportar_excel_procedimientos, ...),

    # ===== RUTAS INTERNAS (Requieren Login) =====
    path('estudios/nuevo/', EstudiosCreateView.as_view(), name='estudios_nuevo'),
    path('estudios/', EstudiosListView.as_view(), name='estudios_list'),

    # Rutas para Registro de Estudios por Medico
    path('registro_estudios_por_medico/nuevo/', RegistroEstudiosPorMedicoCreateView.as_view(), name='registroestudios_nuevo'),
    path('registro_estudios_por_medico/', RegistroEstudiosPorMedicoListView.as_view(), name='registroestudios_list'),
    path('editar/<int:pk>/', RegistroEstudiosPorMedicoUpdateView.as_view(), name='registroestudios_edit'),
    path('eliminar/<int:pk>/', RegistroEstudiosPorMedicoDeleteView.as_view(), name='registroestudios_delete'),
    # path('registrar-dia-sin-pacientes/', RegistrarDiaSinPacientesView.as_view(), name='registrar_dia_sin_pacientes'),  # [DEPRECADO]

    # Rutas nuevas v2.0
    path('guardia-pasiva/nuevo/', RegistrarGuardiaPasivaView.as_view(), name='registrar_guardia_pasiva'),

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
]