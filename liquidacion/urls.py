from django.urls import path
from .views import (
    MedicoCreateView,
    MedicoListView,
    EstudiosCreateView,
    EstudiosListView,
    RegistroEstudiosPorMedicoCreateView,
    RegistroEstudiosPorMedicoListView,
    RegistroEstudiosPorMedicoUpdateView,
    RegistroEstudiosPorMedicoDeleteView,
    generar_pdf_liquidacion,
    InformadosPorMedicoPorMesListView,
    ProcedimientosIntervensionismoListCreateView,
    ProcedimientosIntervensionismoListView,
    ProcedimientosIntervensionismoUpdateView,
    ProcedimientosIntervensionismoDeleteView,
    ProcedimientosPorMedicoPorMesListView,
    EcografiasPorMedicoPorMesListView,
    exportar_excel_informes,
    exportar_excel_ecografias,
    exportar_excel_procedimientos,
    RegistrarDiaSinPacientesView
)

urlpatterns = [
    # Rutas para Medico
    path('medico/nuevo/', MedicoCreateView.as_view(), name='medico_nuevo'),
    path('medico/', MedicoListView.as_view(), name='medico_list'),

    # Rutas para Estudios
    path('estudios/nuevo/', EstudiosCreateView.as_view(), name='estudios_nuevo'),
    path('estudios/', EstudiosListView.as_view(), name='estudios_list'),

    # Rutas para Registro de Estudios por Medico
    path('registro_estudios_por_medico/nuevo/', RegistroEstudiosPorMedicoCreateView.as_view(), name='registroestudios_nuevo'),
    path('registro_estudios_por_medico/', RegistroEstudiosPorMedicoListView.as_view(), name='registroestudios_list'),
    path('editar/<int:pk>/', RegistroEstudiosPorMedicoUpdateView.as_view(), name='registroestudios_edit'),
    path('eliminar/<int:pk>/', RegistroEstudiosPorMedicoDeleteView.as_view(), name='registroestudios_delete'),
    path('registrar-dia-sin-pacientes/', RegistrarDiaSinPacientesView.as_view(), name='registrar_dia_sin_pacientes'),

    # Rutas para Informes por Medico por Mes
    path('informados-por-medico-por-mes/', InformadosPorMedicoPorMesListView.as_view(), name='informados_por_medico_por_mes'),

    # Ruta para generar PDF
    path('generar-pdf/', generar_pdf_liquidacion, name='generar_pdf_liquidacion'),

    # Ruta para exportar a Excel
    path('exportar_excel_informes/', exportar_excel_informes, name='exportar_excel_informes'),
    path('exportar_excel_ecografias/', exportar_excel_ecografias, name='exportar_excel_ecografias'),
    path('exportar_excel_procedimientos/', exportar_excel_procedimientos, name='exportar_excel_procedimientos'),

    # Rutas para Procedimientos de Intervensionismo
    path('procedimientos-intervensionismo/', ProcedimientosIntervensionismoListCreateView.as_view(), name='procedimientos_intervensionismo'),
    path('procedimientos_intervensionismo/<int:pk>/editar/', ProcedimientosIntervensionismoUpdateView.as_view(), name='editar_procedimiento'),
    path('procedimientos_intervensionismo/<int:pk>/eliminar/', ProcedimientosIntervensionismoDeleteView.as_view(), name='eliminar_procedimiento'),
    path('mis-procedimientos/', ProcedimientosIntervensionismoListView.as_view(), name='mis_procedimientos'),

    # Rutas para Procedimientos por Medico por Mes
    path('procedimientos-por-medico-por-mes/', ProcedimientosPorMedicoPorMesListView.as_view(), name='procedimientos_por_medico_por_mes'),

    # Rutas para Ecografias por Medico por Mes
    path('ecografias-por-medico-por-mes/', EcografiasPorMedicoPorMesListView.as_view(), name='ecografias_por_medico_por_mes'),
]