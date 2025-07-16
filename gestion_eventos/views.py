# Importaciones de bibliotecas estándar de Python
from datetime import datetime

# Importaciones de Django (ordenadas alfabéticamente)
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db import models
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.template.loader import render_to_string
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.timezone import now
from django.views.generic import DetailView
from django.views.generic.edit import CreateView
from django.views.generic.list import ListView

# Importaciones locales de la aplicación
from .forms import (
    ActualizarEstadoEventoForm,
    ActualizarTipoEventoForm,
    EventoServicioForm,
    FiltroEventoForm,
    NotaEventoForm,
)
from .models import EventoServicio

# Variables globales
User = get_user_model()


class EventoServicioCreateView(LoginRequiredMixin, CreateView):
    model = EventoServicio
    form_class = EventoServicioForm
    template_name = 'gestion_eventos/crear_evento.html'
    success_url = reverse_lazy('gestion_eventos:lista_eventos')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user  # Pasa el usuario al formulario
        return kwargs

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form._user = self.request.user  # Pasar usuario para validación anti-duplicados
        return form

    def form_valid(self, form):
        user = self.request.user
        form.instance.creado_por = user

        # Si es técnico, asigna el área automáticamente
        if user.groups.filter(name="Técnicos de tomografía").exists():
            form.instance.servicio_origen_evento = 'tomografia'
        elif user.groups.filter(name="Técnicos de resonancia").exists():
            form.instance.servicio_origen_evento = 'resonancia'
        # Si es médico, administrativo, etc., deja lo que venga del formulario

        return super().form_valid(form)


class EventoServicioListView(ListView, LoginRequiredMixin):
    model = EventoServicio
    template_name = 'gestion_eventos/lista_eventos.html'
    context_object_name = 'eventos'
    
    def get_queryset(self):
        user = self.request.user

        if user.groups.filter(name="Técnicos de tomografía").exists():
            # Solo eventos de tomografía
            return EventoServicio.objects.filter(
                estado__in=['abierto', 'en_revision'],
                servicio_origen_evento='tomografia'
            ).order_by('-fecha_creacion')

        elif user.groups.filter(name="Técnicos de resonancia").exists():
            # Solo eventos de resonancia
            return EventoServicio.objects.filter(
                estado__in=['abierto', 'en_revision'],
                servicio_origen_evento='resonancia'
            ).order_by('-fecha_creacion')

        else:
            # Médicos, administrativos, etc. ven todo
            return EventoServicio.objects.filter(
                estado__in=['abierto', 'en_revision']
            ).order_by('-fecha_creacion')

class HistorialEventoListView(ListView, LoginRequiredMixin):
    model = EventoServicio
    template_name = 'gestion_eventos/historial_eventos.html'
    context_object_name = 'eventos'
    paginate_by = 4

    def get_queryset(self):
        user = self.request.user

        if user.groups.filter(name="Técnicos de tomografía").exists():
            queryset = EventoServicio.objects.filter(
                estado='resuelto',
                servicio_origen_evento='tomografia'
            ).order_by('-fecha_creacion')
        elif user.groups.filter(name="Técnicos de resonancia").exists():
            queryset = EventoServicio.objects.filter(
                estado='resuelto',
                servicio_origen_evento='resonancia'
            ).order_by('-fecha_creacion')
        else:
            queryset = EventoServicio.objects.filter(
                estado='resuelto'
            ).order_by('-fecha_creacion')

        # Filtros adicionales (búsqueda, fechas, etc.)
        self.form = FiltroEventoForm(self.request.GET)
        q = self.request.GET.get('q')
        if q:
            queryset = queryset.filter(
                models.Q(nombre_paciente__icontains=q) |
                models.Q(dni_paciente__icontains=q)
            )
        if self.form.is_valid():
            tipo_evento = self.form.cleaned_data.get('tipo_evento')
            fecha_inicio = self.form.cleaned_data.get('fecha_inicio')
            fecha_fin = self.form.cleaned_data.get('fecha_fin')
            if tipo_evento:
                queryset = queryset.filter(tipo_evento=tipo_evento)
            if fecha_inicio:
                queryset = queryset.filter(fecha_creacion__gte=fecha_inicio)
            if fecha_fin:
                queryset = queryset.filter(fecha_creacion__lte=fecha_fin)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        eventos = self.get_queryset()
        paginator = Paginator(eventos, self.paginate_by)
        page = self.request.GET.get('page')
        try:
            eventos_paginados = paginator.page(page)
        except PageNotAnInteger:
            eventos_paginados = paginator.page(1)
        except EmptyPage:
            eventos_paginados = paginator.page(paginator.num_pages)
        context['eventos'] = eventos_paginados
        context['form'] = self.form
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
    
# Vista para mostrar los eventos al personal administrativo de piso con permisos 

class EventosAdministrativosListView(LoginRequiredMixin, ListView):
    model = EventoServicio
    template_name = 'gestion_eventos/control_administrativo_eventos.html'
    context_object_name = 'eventos'
    paginate_by = 10
    login_url = 'login'

    def get_queryset(self):
    
        # Filtrar solo eventos del mes actual
        ahora = timezone.now()
        inicio_mes = ahora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        queryset = EventoServicio.objects.filter(
            fecha_creacion__gte=inicio_mes
        ).order_by('-fecha_creacion')
        
        search_query = self.request.GET.get('search')
        if search_query:
            queryset = queryset.filter(
                Q(nombre_paciente__icontains=search_query) |
                Q(dni_paciente__icontains=search_query)
            )
        return queryset

class EventoServicioAdminDetailView(LoginRequiredMixin, DetailView):
    model = EventoServicio
    template_name = 'gestion_eventos/detalle_evento_administrativo.html'
    context_object_name = 'evento'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['notas'] = self.object.notas.order_by('-fecha')
        context['historial'] = self.object.historial.order_by('-fecha')
        return context

