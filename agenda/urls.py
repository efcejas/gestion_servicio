from django.urls import path
from .views import (
    AgendaItemCreateView,
    AgendaItemUpdateView,
    NotaPersonalCreateView,
    NotaPersonalUpdateView,
)

app_name = 'agenda'

urlpatterns = [
    # Agenda Items
    path('agenda/nuevo/', AgendaItemCreateView.as_view(), name='agenda_nuevo'),
    path('agenda/<int:pk>/editar/', AgendaItemUpdateView.as_view(), name='agenda_editar'),
    
    # Notas Personales
    path('notas/nueva/', NotaPersonalCreateView.as_view(), name='nota_nueva'),
    path('notas/<int:pk>/editar/', NotaPersonalUpdateView.as_view(), name='nota_editar'),
]
