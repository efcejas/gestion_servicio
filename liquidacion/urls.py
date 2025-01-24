from django.urls import path
from .views import MedicoCreateView, EstudiosCreateView, EstudiosListView, RegistroEstudiosPorMedicoCreateView, MedicoListView, RegistroEstudiosPorMedicoListView, """ generar_pdf_liquidacion """

urlpatterns = [
    path('medico/nuevo/', MedicoCreateView.as_view(), name='medico_nuevo'),
    path('medico/', MedicoListView.as_view(), name='medico_list'),
    path('estudios/nuevo/', EstudiosCreateView.as_view(), name='estudios_nuevo'),
    path('estudios/', EstudiosListView.as_view(), name='estudios_list'),
    path('registro_estudios_por_medico/nuevo/', RegistroEstudiosPorMedicoCreateView.as_view(), name='registroestudios_nuevo'),
    path('registro_estudios_por_medico/', RegistroEstudiosPorMedicoListView.as_view(), name='registroestudios_list'),
    # path('generar-pdf/', generar_pdf_liquidacion, name='generar_pdf_liquidacion'),
]