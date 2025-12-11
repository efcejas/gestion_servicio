from django.urls import path
from .views import (
    AgendaItemCreateView,
    AgendaItemUpdateView,
    AgendaItemToggleCompletoView,
    NotaPersonalCreateView,
    NotaPersonalUpdateView,
    NotaPersonalToggleFijadaView,
)

app_name = 'agenda'

urlpatterns = [
    # Agenda
    path('agenda/nuevo/', AgendaItemCreateView.as_view(), name='agenda_nuevo'),
    path('agenda/<int:pk>/editar/', AgendaItemUpdateView.as_view(), name='agenda_editar'),
    path('agenda/<int:pk>/toggle-completado/', AgendaItemToggleCompletoView.as_view(), name='agenda_toggle_completado'),
    
    # Notas
    path('notas/nueva/', NotaPersonalCreateView.as_view(), name='nota_nueva'),
    path('notas/<int:pk>/editar/', NotaPersonalUpdateView.as_view(), name='nota_editar'),
    path('notas/<int:pk>/toggle-fijada/', NotaPersonalToggleFijadaView.as_view(), name='nota_toggle_fijada'),
]
