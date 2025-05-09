from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils.timezone import now
from django.views.generic import DetailView
from django.views.generic.edit import CreateView
from django.views.generic.list import ListView
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.contrib import messages

from .forms import ActualizarTipoEventoForm, EventoServicioForm, NotaEventoForm, ActualizarEstadoEventoForm
from .models import EventoServicio, NotaEvento

class EventoServicioCreateView(LoginRequiredMixin, CreateView):
    model = EventoServicio
    form_class = EventoServicioForm
    template_name = 'gestion_eventos/crear_evento.html'
    success_url = reverse_lazy('gestion_eventos:lista_eventos')

    def form_valid(self, form):
        form.instance.creado_por = self.request.user
        return super().form_valid(form)

# Lista de eventos activos (abiertos o pendientes)
class EventoServicioListView(ListView):
    model = EventoServicio
    template_name = 'gestion_eventos/lista_eventos.html'
    context_object_name = 'eventos'
    
    def get_queryset(self):
        return EventoServicio.objects.filter(
            estado__in=['abierto', 'en_revision'],  # 🚨 Cambiado de 'abierto' a 'en_revision'
        ).order_by('-fecha_creacion')

# Lista del historial (eventos resueltos)
class HistorialEventoListView(ListView):
    model = EventoServicio
    template_name = 'gestion_eventos/historial_eventos.html'
    context_object_name = 'eventos'
    paginate_by = 4

    def get_queryset(self):
        return EventoServicio.objects.filter(
            estado='resuelto'  # 🚨 Ahora sólo los resueltos
        ).order_by('-fecha_creacion')
        
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        eventos = self.get_queryset()
        paginator = Paginator(eventos, self.paginate_by)

        page = self.request.GET.get('page')
        try:
            eventos_paginados = paginator.page(page)
        except PageNotAnInteger:
            eventos_paginados = paginator.page(1)  # 🚨 Si no es número, mostrar la página 1
        except EmptyPage:
            eventos_paginados = paginator.page(paginator.num_pages)

        context['eventos'] = eventos_paginados
        return context

# Vista detalle de evento, para agregar notas o cambiar estado
class EventoServicioDetailView(LoginRequiredMixin, DetailView):
    model = EventoServicio
    template_name = 'gestion_eventos/detalle_evento.html'
    context_object_name = 'evento'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['notas'] = self.object.notas.order_by('-fecha')
        context['nota_form'] = NotaEventoForm()
        context['estado_form'] = ActualizarEstadoEventoForm(initial={'estado': self.object.estado})
        context['tipo_evento_form'] = ActualizarTipoEventoForm(initial={'tipo_evento': self.object.tipo_evento})
        context['historial'] = self.object.historial.order_by('-fecha')
        return context

    def post(self, request, *args, **kwargs):
        print(request.POST)
        self.object = self.get_object()

        if 'guardar_nota' in request.POST:  # Cambiado de 'comentario' a 'guardar_nota'
            nota_form = NotaEventoForm(request.POST)
            if nota_form.is_valid():
                nota = nota_form.save(commit=False)
                nota.evento = self.object
                nota.creado_por = request.user
                nota.save()
            else:
                print(nota_form.errors)  # Muestra los errores del formulario

        elif 'estado' in request.POST:
            estado_form = ActualizarEstadoEventoForm(request.POST, instance=self.object)
            if estado_form.is_valid():
                estado_form.save(usuario=request.user)  # 👈 importante

        elif 'actualizar_tipo_evento' in request.POST:
            tipo_evento_form = ActualizarTipoEventoForm(request.POST, instance=self.object)
            if tipo_evento_form.is_valid():
                tipo_evento_form.save(usuario=request.user)
            else:
                print(tipo_evento_form.errors)  # Muestra los errores del formulario
                
        return redirect(reverse('gestion_eventos:detalle_evento', kwargs={'pk': self.object.pk}))