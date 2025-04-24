from django.urls import path
from .views import EventoServicioCreateView

app_name = 'gestion_eventos'

urlpatterns = [
    path('nuevo/', EventoServicioCreateView.as_view(), name='evento_nuevo'),
]