from django.urls import path
from .views import (
    EventoServicioCreateView, EventoServicioDetailView, EventoServicioListView, 
    HistorialEventoListView, EventosAdministrativosListView, EventoServicioAdminDetailView,
    EventosDashboardView
)

app_name = 'gestion_eventos'

urlpatterns = [
    path('', EventosDashboardView.as_view(), name='dashboard_eventos'),
    path('nuevo/', EventoServicioCreateView.as_view(), name='evento_nuevo'),
    path('eventos/', EventoServicioListView.as_view(), name='lista_eventos'),
    path('historial/', HistorialEventoListView.as_view(), name='historial_eventos'),
    path('evento/<int:pk>/', EventoServicioDetailView.as_view(), name='detalle_evento'),
    path('administrativos/', EventosAdministrativosListView.as_view(), name='eventos_administrativos'),
    path('evento-admin/<int:pk>/', EventoServicioAdminDetailView.as_view(), name='detalle_evento_admin'),
]