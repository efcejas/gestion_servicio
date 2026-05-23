from django.urls import path
from .views import (
    EstudiosCreateView,
    EstudiosListView,
    RegistroEstudiosPorMedicoCreateView,
    RegistroEstudiosPorMedicoListView,
    RegistroEstudiosPorMedicoUpdateView,
    RegistroEstudiosPorMedicoDeleteView,
    generar_pdf_liquidacion,
    LiquidacionPorMedicoPorMesListView,  # [NUEVO v3.0] Vista unificada
    exportar_excel_liquidacion,  # [NUEVO v3.0] Exportación unificada
    # RegistrarDiaSinPacientesView,  # [DEPRECADO] No se usa en Colegiales
    RegistrarGuardiaPasivaView,  # [NUEVO v2.0]
    GuardiaPasivaUpdateView,  # [NUEVO v3.2]
    GuardiaPasivaDeleteView,  # [NUEVO v3.2]
    CargaMasivaView,
    PortalLiquidacionInicioView,
    SesionContableListView,       # [NUEVO Fase B] Gestión del ciclo contable
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
    
    # [NUEVO v3.0 - VISTA UNIFICADA RECOMENDADA]
    path('liquidacion-mensual/', LiquidacionPorMedicoPorMesListView.as_view(), name='liquidacion_mensual'),
    path('exportar_excel_liquidacion/', exportar_excel_liquidacion, name='exportar_excel_liquidacion'),

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
    path('sesiones/<int:pk>/transicion/', sesion_contable_transicion, name='sesion_transicion'),
]