from django.urls import path
from .views import ListaTareasView, TareasImportantesView

app_name = 'tasks'

urlpatterns = [
    path('lista/', ListaTareasView.as_view(), name='lista_tareas'),
    path('importantes/', TareasImportantesView.as_view(), name='tareas_importantes'),
]
