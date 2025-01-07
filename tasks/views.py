from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic.list import ListView
from .models import Tarea
from django.utils import timezone


class ListaTareasView(LoginRequiredMixin, ListView):
    model = Tarea
    template_name = 'tasks/lista_tareas.html'
    context_object_name = 'tareas'

    def get_queryset(self):
        return Tarea.objects.filter(usuario=self.request.user).order_by('estado', 'prioridad')


class TareasImportantesView(LoginRequiredMixin, ListView):
    model = Tarea
    template_name = 'home.html'  # Archivo HTML para renderizar
    context_object_name = 'tareas_importantes'  # Nombre que se usará en el template

    def get_queryset(self):
        # Consulta para obtener las tareas importantes
        return Tarea.objects.filter(
            usuario=self.request.user,
            estado='pendiente',
            fecha_limite__gte=timezone.now()
        ).order_by('fecha_limite')[:5]
