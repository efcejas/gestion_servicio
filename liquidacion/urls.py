from django.urls import path
from .views import MedicoCreateView, EstudiosCreateView, EstudiosListView

urlpatterns = [
    path('medico/nuevo/', MedicoCreateView.as_view(), name='medico_nuevo'),
    path('estudios/nuevo/', EstudiosCreateView.as_view(), name='estudios_nuevo'),
    path('estudios/', EstudiosListView.as_view(), name='estudios_list'),
]
