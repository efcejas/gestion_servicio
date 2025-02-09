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
    ProcedimientosPorMedicoPorMesListView
)

urlpatterns = [
    path('medico/nuevo/', MedicoCreateView.as_view(), name='medico_nuevo'),
    path('medico/', MedicoListView.as_view(), name='medico_list'),
    path('estudios/nuevo/', EstudiosCreateView.as_view(), name='estudios_nuevo'),
    path('estudios/', EstudiosListView.as_view(), name='estudios_list'),
    path('registro_estudios_por_medico/nuevo/', RegistroEstudiosPorMedicoCreateView.as_view(), name='registroestudios_nuevo'),
    path('registro_estudios_por_medico/', RegistroEstudiosPorMedicoListView.as_view(), name='registroestudios_list'),
    path('editar/<int:pk>/', RegistroEstudiosPorMedicoUpdateView.as_view(), name='registroestudios_edit'),
    path('eliminar/<int:pk>/', RegistroEstudiosPorMedicoDeleteView.as_view(), name='registroestudios_delete'),
    path('generar-pdf/', generar_pdf_liquidacion, name='generar_pdf_liquidacion'),
    path('informados-por-medico-por-mes/', InformadosPorMedicoPorMesListView.as_view(), name='informados_por_medico_por_mes'),
    path('procedimientos-intervensionismo/', ProcedimientosIntervensionismoListCreateView.as_view(), name='procedimientos_intervensionismo'),
    path('mis-procedimientos/', ProcedimientosIntervensionismoListView.as_view(), name='mis_procedimientos'),
    path('procedimientos-por-medico-por-mes/', ProcedimientosPorMedicoPorMesListView.as_view(), name='procedimientos_por_medico_por_mes'),
]