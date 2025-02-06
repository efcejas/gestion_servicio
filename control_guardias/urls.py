from django.urls import path
from .views import GuardiaListView, ResumenGuardiasView

urlpatterns = [
    path('coberturas-semanal/', GuardiaListView.as_view(), name='coberturas_semanal'),
    path('coberturas-medico/', ResumenGuardiasView.as_view(), name='coberturas_medico'),
]
