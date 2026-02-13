# Importaciones de bibliotecas estándar de Python
import logging
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
from django.core.mail import send_mail
from django.conf import settings

# Variables globales
User = get_user_model()
logger = logging.getLogger(__name__)


class EventoServicioCreateView(LoginRequiredMixin, CreateView):
    model = EventoServicio
    form_class = EventoServicioForm
    template_name = 'gestion_eventos/crear_evento_tailwind.html'
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

        response = super().form_valid(form)
        
        # Mensaje informativo sobre el evento creado
        tipo_evento_display = self.object.get_tipo_evento_display()
        paciente_info = f" - Paciente: {self.object.nombre_paciente}" if self.object.nombre_paciente else ""
        servicio_info = f" ({self.object.get_servicio_origen_evento_display()})" if self.object.servicio_origen_evento else ""
        
        messages.success(
            self.request, 
            f'✓ Evento creado exitosamente: "{tipo_evento_display}"{servicio_info}{paciente_info}'
        )

        # Enviar email de notificación, tanto para evento nuevo como para nota agregada
        try:
            subject = f"Nuevo evento creado: {tipo_evento_display}"
            message = f"Se ha creado un nuevo evento.\n\nTipo: {tipo_evento_display}\n{servicio_info}\n{paciente_info}\nDescripción: {self.object.descripcion}"
            from_email = settings.DEFAULT_FROM_EMAIL
            recipient_list = ["ecejas@sanatoriocolegiales.com.ar"]
            send_mail(subject, message, from_email, recipient_list, fail_silently=False)
            logger.info(f"Email de notificación enviado para evento {self.object.id}")
        except Exception as e:
            logger.error(f"Error enviando email de notificación: {e}", exc_info=True)
        
        return response


class EventoServicioListView(ListView, LoginRequiredMixin):
    model = EventoServicio
    template_name = 'gestion_eventos/lista_eventos.html'
    context_object_name = 'eventos'
    
    def get_queryset(self):
        user = self.request.user

        # Filtro base según el grupo del usuario
        if user.groups.filter(name="Técnicos de tomografía").exists():
            queryset = EventoServicio.objects.filter(
                estado__in=['abierto', 'en_revision'],
                servicio_origen_evento='tomografia'
            )
        elif user.groups.filter(name="Técnicos de resonancia").exists():
            queryset = EventoServicio.objects.filter(
                estado__in=['abierto', 'en_revision'],
                servicio_origen_evento='resonancia'
            )
        else:
            queryset = EventoServicio.objects.filter(
                estado__in=['abierto', 'en_revision']
            )
        
        # Aplicar filtros de búsqueda
        q = self.request.GET.get('q')
        if q:
            queryset = queryset.filter(
                Q(nombre_paciente__icontains=q) |
                Q(dni_paciente__icontains=q)
            )
        
        estado = self.request.GET.get('estado')
        if estado:
            queryset = queryset.filter(estado=estado)
        
        tipo_evento = self.request.GET.get('tipo_evento')
        if tipo_evento:
            queryset = queryset.filter(tipo_evento=tipo_evento)
        
        sector = self.request.GET.get('sector')
        if sector:
            queryset = queryset.filter(sector_de_pedido__icontains=sector)
        
        return queryset.order_by('-fecha_creacion')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Filtro base según el usuario
        if user.groups.filter(name="Técnicos de tomografía").exists():
            base_filter = {'servicio_origen_evento': 'tomografia'}
        elif user.groups.filter(name="Técnicos de resonancia").exists():
            base_filter = {'servicio_origen_evento': 'resonancia'}
        else:
            base_filter = {}
        
        # Métricas para el header
        context['eventos_abiertos'] = EventoServicio.objects.filter(
            estado='abierto', **base_filter
        ).count()
        context['eventos_en_revision'] = EventoServicio.objects.filter(
            estado='en_revision', **base_filter
        ).count()
        context['eventos_con_notas'] = EventoServicio.objects.filter(
            estado__in=['abierto', 'en_revision'],
            notas__isnull=False,
            **base_filter
        ).distinct().count()
        
        return context

class HistorialEventoListView(ListView, LoginRequiredMixin):
    model = EventoServicio
    template_name = 'gestion_eventos/historial_eventos_tailwind.html'
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
        
        # Métricas para el header
        user = self.request.user
        if user.groups.filter(name="Técnicos de tomografía").exists():
            base_filter = {'servicio_origen_evento': 'tomografia'}
        elif user.groups.filter(name="Técnicos de resonancia").exists():
            base_filter = {'servicio_origen_evento': 'resonancia'}
        else:
            base_filter = {}
        
        # Total de eventos resueltos (sin filtros de búsqueda)
        context['total_resueltos'] = EventoServicio.objects.filter(
            estado='resuelto', **base_filter
        ).count()
        
        # Eventos resueltos este mes
        hoy = timezone.now()
        inicio_mes = hoy.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        context['resueltos_este_mes'] = EventoServicio.objects.filter(
            estado='resuelto',
            fecha_creacion__gte=inicio_mes,
            **base_filter
        ).count()
        
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
        
        # Contexto de navegación inteligente basado en el estado del evento
        context['is_from_historial'] = self.object.estado == 'resuelto'
        
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        
        print(f"POST request received: {dict(request.POST)}")

        if 'guardar_nota' in request.POST:
            nota_form = NotaEventoForm(request.POST)
            if nota_form.is_valid():
                nota = nota_form.save(commit=False)
                nota.evento = self.object
                nota.creado_por = request.user
                nota.save()
                # Enviar email de notificación por nueva nota
                try:
                    subject = f"Nueva nota agregada al evento: {self.object.get_tipo_evento_display()}"
                    paciente_info = f"Paciente: {self.object.nombre_paciente}" if self.object.nombre_paciente else ""
                    servicio_info = f"Servicio: {self.object.get_servicio_origen_evento_display()}" if self.object.servicio_origen_evento else ""
                    message = (
                        f"Se ha agregado una nueva nota al evento.\n\n"
                        f"Tipo: {self.object.get_tipo_evento_display()}\n"
                        f"{servicio_info}\n"
                        f"{paciente_info}\n"
                        f"Descripción: {self.object.descripcion}\n\n"
                        f"Nota: {nota.comentario}\n"
                        f"Autor de la nota: {nota.creado_por.get_full_name()}"
                    )
                    from_email = settings.DEFAULT_FROM_EMAIL
                    recipient_list = ["ecejas@sanatoriocolegiales.com.ar"]
                    send_mail(subject, message, from_email, recipient_list, fail_silently=False)
                    logger.info(f"Email de notificación enviado para nota en evento {self.object.id}")
                except Exception as e:
                    logger.error(f"Error enviando email de notificación de nota: {e}", exc_info=True)
                
                # Mensaje contextual con información del evento
                paciente_info = f" para {self.object.nombre_paciente}" if self.object.nombre_paciente else ""
                messages.success(
                    request, 
                    f'✓ Nota agregada al evento{paciente_info}. Total de notas: {self.object.notas.count()}'
                )
            else:
                messages.error(request, '✗ No se pudo agregar la nota. Por favor, verifica el contenido.')

        elif 'actualizar_estado' in request.POST:
            estado_form = ActualizarEstadoEventoForm(request.POST, instance=self.object)
            if estado_form.is_valid():
                estado_anterior = self.object.estado
                estado_form.save(usuario=request.user)
                estado_nuevo = self.object.estado
                
                # Diccionario de nombres legibles para estados
                estados_display = {
                    'abierto': 'Abierto',
                    'en_revision': 'En Revisión',
                    'resuelto': 'Resuelto'
                }
                
                # Mensajes contextuales según el cambio de estado
                if estado_nuevo == 'resuelto':
                    tipo_evento_display = self.object.get_tipo_evento_display()
                    messages.success(
                        request, 
                        f'✓ Evento "{tipo_evento_display}" marcado como RESUELTO. El evento se ha archivado correctamente.'
                    )
                elif estado_nuevo == 'en_revision':
                    messages.info(
                        request, 
                        f'📋 Estado cambiado de "{estados_display.get(estado_anterior)}" a "En Revisión". El evento requiere supervisión.'
                    )
                elif estado_nuevo == 'abierto' and estado_anterior == 'en_revision':
                    messages.warning(
                        request, 
                        f'⚠ Evento reabierto desde "En Revisión" a "Abierto". Requiere atención inmediata.'
                    )
                else:
                    messages.success(
                        request, 
                        f'✓ Estado actualizado: {estados_display.get(estado_anterior)} → {estados_display.get(estado_nuevo)}'
                    )
            else:
                messages.error(request, '✗ No se pudo actualizar el estado. Intenta nuevamente.')

        elif 'actualizar_tipo_evento' in request.POST:
            tipo_evento_form = ActualizarTipoEventoForm(request.POST, instance=self.object)
            if tipo_evento_form.is_valid():
                tipo_anterior = self.object.tipo_evento
                tipo_evento_form.save(usuario=request.user)
                tipo_nuevo = self.object.tipo_evento
                
                # Obtener nombres legibles
                tipo_anterior_display = dict(self.object.TIPO_EVENTO_CHOICES).get(tipo_anterior)
                tipo_nuevo_display = self.object.get_tipo_evento_display()
                
                messages.success(
                    request, 
                    f'✓ Tipo de evento reclasificado: "{tipo_anterior_display}" → "{tipo_nuevo_display}"'
                )
            else:
                messages.error(request, '✗ No se pudo actualizar el tipo de evento. Verifica la selección.')
                
        return redirect(reverse('gestion_eventos:detalle_evento', kwargs={'pk': self.object.pk}))
    
# Vista Dashboard de Eventos con lógica de permisos
class EventosDashboardView(LoginRequiredMixin, ListView):
    model = EventoServicio
    template_name = 'gestion_eventos/dashboard_eventos.html'
    context_object_name = 'eventos_recientes'
    
    def get_queryset(self):
        user = self.request.user
        
        if user.groups.filter(name="Técnicos de tomografía").exists():
            return EventoServicio.objects.filter(
                servicio_origen_evento='tomografia'
            ).order_by('-fecha_creacion')[:5]
        elif user.groups.filter(name="Técnicos de resonancia").exists():
            return EventoServicio.objects.filter(
                servicio_origen_evento='resonancia'
            ).order_by('-fecha_creacion')[:5]
        else:
            return EventoServicio.objects.all().order_by('-fecha_creacion')[:5]
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Filtros según el grupo del usuario
        if user.groups.filter(name="Técnicos de tomografía").exists():
            base_filter = {'servicio_origen_evento': 'tomografia'}
        elif user.groups.filter(name="Técnicos de resonancia").exists():
            base_filter = {'servicio_origen_evento': 'resonancia'}
        else:
            base_filter = {}
        
        # Métricas filtradas por grupo
        context['eventos_activos'] = EventoServicio.objects.filter(
            estado__in=['abierto', 'en_revision'], **base_filter
        ).count()
        context['eventos_resueltos_hoy'] = EventoServicio.objects.filter(
            estado='resuelto',
            fecha_creacion__date=timezone.now().date(),
            **base_filter
        ).count()
        context['eventos_pendientes'] = EventoServicio.objects.filter(
            estado='abierto', **base_filter
        ).count()
        
        return context

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

