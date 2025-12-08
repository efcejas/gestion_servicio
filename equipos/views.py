from django.shortcuts import render
from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from .models import EquipoImagen


class EquiposListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """
    Vista de solo lectura para listar todos los equipos de imágenes.
    Solo accesible para usuarios staff o superusuarios.
    """
    model = EquipoImagen
    template_name = 'equipos/equipos_list.html'
    context_object_name = 'equipos'
    ordering = ['area', 'nombre']
    
    def test_func(self):
        """Solo permite acceso a usuarios staff o superusuarios"""
        return self.request.user.is_staff or self.request.user.is_superuser
    
    def get_queryset(self):
        """
        Devuelve el queryset de equipos.
        Opcionalmente filtra solo equipos en servicio si viene ?solo_activos=1
        """
        queryset = super().get_queryset()
        
        # Filtro opcional por equipos activos
        solo_activos = self.request.GET.get('solo_activos', None)
        if solo_activos == '1':
            queryset = queryset.filter(en_servicio=True)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        """Agrega contexto adicional para el template"""
        context = super().get_context_data(**kwargs)
        
        # Estadísticas rápidas
        context['total_equipos'] = EquipoImagen.objects.count()
        context['equipos_activos'] = EquipoImagen.objects.filter(en_servicio=True).count()
        context['equipos_inactivos'] = EquipoImagen.objects.filter(en_servicio=False).count()
        
        # Parámetro de filtro actual
        context['solo_activos'] = self.request.GET.get('solo_activos', '') == '1'
        
        return context
