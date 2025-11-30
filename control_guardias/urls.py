from django.urls import path
from .views import exportar_excel_guardias

app_name = 'control_guardias'
from .views import (
    TailwindCalendarView,
    GuardiaCreateView,
    GuardiaUpdateView,
    GuardiaDeleteView,
    GuardiaEventsView,
    GuardiaListView,
    ResumenGuardiasView,
    MisGuardiasView,
    CoberturasSemanalesPortalView,
    ResumenGuardiasPortalView,
)

urlpatterns = [
    # Portal público (sin autenticación requerida)
    path('portal/coberturas-semanal/', CoberturasSemanalesPortalView.as_view(), name='portal_coberturas_semanal'),
    path('portal/resumen-guardias/', ResumenGuardiasPortalView.as_view(), name='portal_resumen_guardias'),
    path('exportar-excel-guardias/', exportar_excel_guardias, name='exportar_excel_guardias'),
    
    # Vistas con autenticación
    path('coberturas-semanal/', GuardiaListView.as_view(), name='coberturas_semanal'),
    path('coberturas-medico/', ResumenGuardiasView.as_view(), name='coberturas_medico'),
    path('calendario-full-tw/', TailwindCalendarView.as_view(), name='calendario_guardias_full_tw'),
    path('api/guardias/', GuardiaEventsView.as_view(), name='guardias_api'),
    path('crear-guardia/', GuardiaCreateView.as_view(), name='crear_guardia'),
    path('editar-guardia/<int:pk>/', GuardiaUpdateView.as_view(), name='editar_guardia'),
    path('eliminar-guardia/<int:pk>/', GuardiaDeleteView.as_view(), name='eliminar_guardia'),
    path('mis-guardias/', MisGuardiasView.as_view(), name='mis_guardias'),
]
