from django.urls import path
from .views import EventoServicioCreateView, EventoServicioDetailView, EventoServicioListView, HistorialEventoListView, EventosAdministrativosListView, EventoDetalleAjaxView

app_name = 'gestion_eventos'

urlpatterns = [
    path('nuevo/', EventoServicioCreateView.as_view(), name='evento_nuevo'),
    path('eventos/', EventoServicioListView.as_view(), name='lista_eventos'),
    path('historial/', HistorialEventoListView.as_view(), name='historial_eventos'),
    path('evento/<int:pk>/', EventoServicioDetailView.as_view(), name='detalle_evento'),
    path('evento/<int:pk>/ajax/', EventoDetalleAjaxView.as_view(), name='evento_detalle_ajax'),
    path('administrativos/', EventosAdministrativosListView.as_view(), name='eventos_administrativos'),
]