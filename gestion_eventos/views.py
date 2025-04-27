from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils.timezone import now
from django.views.generic import DetailView
from django.views.generic.edit import CreateView
from django.views.generic.list import ListView
from django.core.paginator import Paginator

from .forms import EventoServicioForm, NotaEventoForm, ActualizarEstadoEventoForm
from .models import EventoServicio, NotaEvento

class EventoServicioCreateView(LoginRequiredMixin, CreateView):
    model = EventoServicio
    form_class = EventoServicioForm
    template_name = 'gestion_eventos/crear_evento.html'
    success_url = reverse_lazy('gestion_eventos:lista_eventos')

    def form_valid(self, form):
        form.instance.creado_por = self.request.user
        return super().form_valid(form)

class EventoServicioListView(ListView):
    model = EventoServicio
    template_name = 'gestion_eventos/lista_eventos.html'
    context_object_name = 'eventos'
    
    def get_queryset(self):
        return EventoServicio.objects.filter(
            estado__in=['abierto', 'pendiente']
        ).order_by('-fecha_creacion')
        
class HistorialEventoListView(ListView):
    model = EventoServicio
    template_name = 'gestion_eventos/historial_eventos.html'
    context_object_name = 'eventos'
    paginate_by = 4

    def get_queryset(self):
        return EventoServicio.objects.filter(
            estado__in=['resuelto', 'cancelado']
        ).order_by('-fecha_creacion')

class EventoServicioDetailView(LoginRequiredMixin, DetailView):
    model = EventoServicio
    template_name = 'gestion_eventos/detalle_evento.html'
    context_object_name = 'evento'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['notas'] = self.object.notas.order_by('fecha')
        context['nota_form'] = NotaEventoForm()
        context['estado_form'] = ActualizarEstadoEventoForm(initial={'estado': self.object.estado})
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        if 'comentario' in request.POST:
            nota_form = NotaEventoForm(request.POST)
            if nota_form.is_valid():
                nota = nota_form.save(commit=False)
                nota.evento = self.object
                nota.creado_por = request.user
                nota.save()
        elif 'estado' in request.POST:
            estado_form = ActualizarEstadoEventoForm(request.POST)
            if estado_form.is_valid():
                self.object.estado = estado_form.cleaned_data['estado']
                self.object.save()
        return redirect(reverse('gestion_eventos:detalle_evento', kwargs={'pk': self.object.pk}))
