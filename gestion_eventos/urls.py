from django.urls import path
from .views import EventoServicioCreateView, EventoServicioDetailView, EventoServicioListView

app_name = 'gestion_eventos'

urlpatterns = [
    path('nuevo/', EventoServicioCreateView.as_view(), name='evento_nuevo'),
    path('eventos/', EventoServicioListView.as_view(), name='lista_eventos'),
    path('evento/<int:pk>/', EventoServicioDetailView.as_view(), name='detalle_evento'),
]