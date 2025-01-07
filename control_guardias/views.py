from django.shortcuts import render
from django.views.generic import ListView
from .models import Guardia
from django.utils import timezone

class GuardiaListView(ListView):
    model = Guardia
    template_name = 'control_guardias/lista_guardias.html'
    context_object_name = 'guardias'
    ordering = ['fecha']

    def get_queryset(self):
        return Guardia.objects.filter(fecha__gte=timezone.now()).order_by('fecha')