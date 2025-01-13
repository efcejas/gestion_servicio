from django.urls import path
from .views import RegistroDiarioCreateView

urlpatterns = [
    path('registro-diario/nuevo/', RegistroDiarioCreateView.as_view(), name='registro_diario_crear'),
]
