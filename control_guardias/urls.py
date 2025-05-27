from django.urls import path
from .views import FullCalendarView, GuardiaCreateView, GuardiaEventsView, GuardiaListView, ResumenGuardiasView, MisGuardiasView

urlpatterns = [
    path('coberturas-semanal/', GuardiaListView.as_view(), name='coberturas_semanal'),
    path('coberturas-medico/', ResumenGuardiasView.as_view(), name='coberturas_medico'),
    path('calendario-full/', FullCalendarView.as_view(), name='calendario_guardias_full'),
    path('api/guardias/', GuardiaEventsView.as_view(), name='guardias_api'),
    path('crear-guardia/', GuardiaCreateView.as_view(), name='crear_guardia'),
    path('mis-guardias/', MisGuardiasView.as_view(), name='mis_guardias'),
]
