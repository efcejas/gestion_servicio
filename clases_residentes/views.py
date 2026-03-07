from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.utils import timezone
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from django.db.models import Q, Count
from django.http import JsonResponse, HttpResponseForbidden
from accounts.decorators import profile_required
from .models import ClaseResidente, ComentarioClase, FavoritoClase
from .forms import ClaseResidenteForm, ComentarioClaseForm, BuscarClaseForm


class ClaseListView(LoginRequiredMixin, ListView):
    """
    Vista para listar todas las clases disponibles según el rol del usuario.
    """
    model = ClaseResidente
    template_name = 'clases_residentes/lista_clases.html'
    context_object_name = 'clases'
    paginate_by = 12
    
    def get_queryset(self):
        from django.db import connection
        queryset = ClaseResidente.objects.filter(activa=True).select_related('autor')
        user = self.request.user

        # Detectar si estamos en SQLite
        is_sqlite = connection.vendor == 'sqlite'

        # Filtrar según permisos del usuario
        if user.rol == 'medico_residente' and user.anio_residencia:
            if is_sqlite:
                # Filtrar en Python
                queryset = [c for c in queryset if not c.anios_dirigidos or user.anio_residencia in c.anios_dirigidos]
            else:
                queryset = queryset.filter(
                    Q(anios_dirigidos=[]) |
                    Q(anios_dirigidos__contains=[user.anio_residencia])
                )

        # Búsqueda y filtros
        form = BuscarClaseForm(self.request.GET)
        if form.is_valid():
            q = form.cleaned_data.get('q')
            if q:
                if is_sqlite:
                    queryset = [c for c in queryset if q.lower() in (c.titulo or '').lower() or q.lower() in (c.descripcion or '').lower() or q.lower() in (c.tags or '').lower()]
                else:
                    queryset = queryset.filter(
                        Q(titulo__icontains=q) |
                        Q(descripcion__icontains=q) |
                        Q(tags__icontains=q)
                    )

            categoria = form.cleaned_data.get('categoria')
            if categoria:
                if is_sqlite:
                    queryset = [c for c in queryset if c.categoria == categoria]
                else:
                    queryset = queryset.filter(categoria=categoria)

            anio = form.cleaned_data.get('anio')
            if anio:
                if is_sqlite:
                    queryset = [c for c in queryset if anio in (c.anios_dirigidos or [])]
                else:
                    queryset = queryset.filter(anios_dirigidos__contains=[anio])

            if form.cleaned_data.get('solo_destacadas'):
                if is_sqlite:
                    queryset = [c for c in queryset if c.es_destacada]
                else:
                    queryset = queryset.filter(es_destacada=True)

        # Si es SQLite, queryset es lista, si no, es queryset
        if is_sqlite:
            # Simular annotate para comentarios (opcional, si usas en template)
            for c in queryset:
                c.num_comentarios = getattr(c, 'comentarios', []).count() if hasattr(c, 'comentarios') else 0
            return queryset
        else:
            return queryset.annotate(num_comentarios=Count('comentarios'))
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_busqueda'] = BuscarClaseForm(self.request.GET)
        context['total_clases'] = len(self.get_queryset())
        context['categorias'] = ClaseResidente.CATEGORIA_CHOICES
        
        # Estadísticas adicionales
        if self.request.user.rol in ['jefe_residentes', 'instructor_residentes', 'jefe_servicio']:
            context['puede_gestionar'] = True
            context['clases_pendientes'] = ClaseResidente.objects.filter(activa=False).count()
        
        return context


class ClaseDetailView(LoginRequiredMixin, DetailView):
    """
    Vista de detalle de una clase con comentarios.
    """
    model = ClaseResidente
    template_name = 'clases_residentes/detalle_clase.html'
    context_object_name = 'clase'
    
    def get_queryset(self):
        return ClaseResidente.objects.select_related('autor').prefetch_related('comentarios__autor')
    
    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        # Verificar permisos de visualización
        if not self.object.puede_ver(request.user):
            messages.error(request, 'No tienes permiso para ver esta clase.')
            return redirect('clases_residentes:lista')

        # Control de visitas por sesión: solo cuenta si no vio hoy o pasaron 6h
        session_key = f'clase_vista_{self.object.pk}'
        now = timezone.now()
        ultima_vista = request.session.get(session_key)
        debe_sumar = False
        if ultima_vista:
            try:
                from django.utils.dateparse import parse_datetime
                ultima_vista_dt = parse_datetime(ultima_vista)
                if ultima_vista_dt is not None:
                    # Si es otro día o pasaron más de 6 horas
                    if ultima_vista_dt.date() != now.date() or (now - ultima_vista_dt).total_seconds() > 21600:
                        debe_sumar = True
                else:
                    debe_sumar = True
            except Exception:
                debe_sumar = True
        else:
            debe_sumar = True

        if debe_sumar:
            self.object.incrementar_visitas()
            request.session[session_key] = now.isoformat()

        context = self.get_context_data(object=self.object)
        return self.render_to_response(context)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_comentario'] = ComentarioClaseForm()
        context['puede_editar'] = self.object.puede_editar(self.request.user)
        context['es_favorita'] = FavoritoClase.objects.filter(
            usuario=self.request.user,
            clase=self.object
        ).exists()
        return context


class ClaseCreateView(LoginRequiredMixin, CreateView):
    """
    Vista para crear una nueva clase.
    """
    model = ClaseResidente
    form_class = ClaseResidenteForm
    template_name = 'clases_residentes/crear_clase.html'
    success_url = reverse_lazy('clases_residentes:lista')
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['usuario'] = self.request.user
        return kwargs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from django.conf import settings
        context['CLOUDINARY_CLOUD_NAME'] = settings.CLOUDINARY_STORAGE.get('CLOUD_NAME', '')
        return context
    
    def form_valid(self, form):
        form.instance.autor = self.request.user
        messages.success(self.request, '✓ Clase creada exitosamente.')
        return super().form_valid(form)
    
    def form_invalid(self, form):
        messages.error(self.request, 'Error al crear la clase. Verifica los campos.')
        return super().form_invalid(form)


class ClaseUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """
    Vista para editar una clase existente.
    """
    model = ClaseResidente
    form_class = ClaseResidenteForm
    template_name = 'clases_residentes/crear_clase.html'  # Usa mismo template que crear (tiene tabs + Cloudinary)
    
    def test_func(self):
        clase = self.get_object()
        return clase.puede_editar(self.request.user)
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['usuario'] = self.request.user
        kwargs['request'] = self.request
        return kwargs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from django.conf import settings
        context['CLOUDINARY_CLOUD_NAME'] = settings.CLOUDINARY_STORAGE.get('CLOUD_NAME', '')
        return context
    
    def get_success_url(self):
        return reverse_lazy('clases_residentes:detalle', kwargs={'pk': self.object.pk})
    
    def form_valid(self, form):
        messages.success(self.request, '✓ Clase actualizada exitosamente.')
        return super().form_valid(form)


class ClaseDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """
    Vista para eliminar una clase.
    """
    model = ClaseResidente
    template_name = 'clases_residentes/eliminar_clase.html'
    success_url = reverse_lazy('clases_residentes:lista')
    
    def test_func(self):
        clase = self.get_object()
        return clase.puede_editar(self.request.user)
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, '✓ Clase eliminada exitosamente.')
        return super().delete(request, *args, **kwargs)


@login_required
def agregar_comentario(request, pk):
    """
    Vista para agregar comentarios a una clase (AJAX).
    """
    if request.method == 'POST':
        clase = get_object_or_404(ClaseResidente, pk=pk)
        # Verificar permisos
        if not clase.puede_ver(request.user):
            return JsonResponse({'success': False, 'error': 'No tienes permiso'}, status=403)

        # Soportar JSON y POST clásico
        import json
        if request.content_type == 'application/json':
            try:
                data = json.loads(request.body.decode('utf-8'))
            except Exception:
                data = {}
            form = ComentarioClaseForm(data)
        else:
            form = ComentarioClaseForm(request.POST)

        if form.is_valid():
            comentario = form.save(commit=False)
            comentario.clase = clase
            comentario.autor = request.user
            comentario.save()
            return JsonResponse({
                'success': True,
                'comentario': {
                    'autor': comentario.autor.get_full_name() or comentario.autor.username,
                    'contenido': comentario.contenido,
                    'fecha': comentario.fecha_creacion.strftime('%d/%m/%Y %H:%M')
                }
            })
        return JsonResponse({'success': False, 'error': 'Formulario inválido'}, status=400)
    return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)


@login_required
def toggle_favorito(request, pk):
    """
    Vista para marcar/desmarcar una clase como favorita (AJAX).
    """
    if request.method == 'POST':
        clase = get_object_or_404(ClaseResidente, pk=pk)
        
        favorito, created = FavoritoClase.objects.get_or_create(
            usuario=request.user,
            clase=clase
        )
        
        if not created:
            favorito.delete()
            return JsonResponse({'success': True, 'es_favorita': False})
        
        return JsonResponse({'success': True, 'es_favorita': True})
    
    return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)


@login_required
def mis_clases(request):
    """
    Vista para mostrar las clases creadas por el usuario actual.
    """
    clases = ClaseResidente.objects.filter(
        autor=request.user
    ).annotate(
        num_comentarios=Count('comentarios'),
        num_favoritos=Count('favoritos')
    ).order_by('-fecha_creacion')
    
    context = {
        'clases': clases,
        'total_clases': clases.count(),
        'total_visitas': sum(c.visitas for c in clases),
        'total_comentarios': sum(c.num_comentarios for c in clases),
        'total_favoritos': sum(c.num_favoritos for c in clases),
    }
    
    return render(request, 'clases_residentes/mis_clases.html', context)


@login_required
def favoritos(request):
    """
    Vista para mostrar las clases marcadas como favoritas.
    """
    favoritos = FavoritoClase.objects.filter(
        usuario=request.user
    ).select_related('clase__autor')
    
    clases = [f.clase for f in favoritos]
    
    context = {
        'clases': clases,
        'favoritos': favoritos,
    }
    
    return render(request, 'clases_residentes/favoritos.html', context)


@login_required
def gestionar_clases(request):
    """
    Vista para jefes e instructores para gestionar todas las clases.
    Solo accesible para roles con permisos.
    """
    if request.user.rol not in ['jefe_residentes', 'instructor_residentes', 'jefe_servicio']:
        return HttpResponseForbidden('No tienes permiso para acceder a esta página.')
    
    clases = ClaseResidente.objects.select_related('autor').annotate(
        num_comentarios=Count('comentarios')
    ).order_by('-fecha_creacion')
    
    # Filtros
    filtro = request.GET.get('filtro', 'todas')
    if filtro == 'activas':
        clases = clases.filter(activa=True)
    elif filtro == 'inactivas':
        clases = clases.filter(activa=False)
    elif filtro == 'destacadas':
        clases = clases.filter(es_destacada=True)
    
    context = {
        'clases': clases,
        'categorias': ClaseResidente.CATEGORIA_CHOICES,
        'filtro': filtro,
        'total_clases': ClaseResidente.objects.count(),
        'activas': ClaseResidente.objects.filter(activa=True).count(),
        'inactivas': ClaseResidente.objects.filter(activa=False).count(),
        'destacadas': ClaseResidente.objects.filter(es_destacada=True).count(),
        'total_visitas': sum(c.visitas for c in ClaseResidente.objects.all()),
    }
    
    return render(request, 'clases_residentes/gestionar_clases.html', context)


@login_required
def cambiar_estado_clase(request, pk):
    """
    Vista AJAX para cambiar el estado (activa/inactiva) de una clase.
    Solo para jefes e instructores.
    """
    if request.method == 'POST' and request.user.rol in ['jefe_residentes', 'instructor_residentes', 'jefe_servicio']:
        clase = get_object_or_404(ClaseResidente, pk=pk)
        clase.activa = not clase.activa
        clase.save()
        
        return JsonResponse({
            'success': True,
            'activa': clase.activa,
            'mensaje': f'Clase {"activada" if clase.activa else "desactivada"} exitosamente'
        })
    
    return JsonResponse({'success': False, 'error': 'No autorizado'}, status=403)
