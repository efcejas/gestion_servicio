from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView, View
from django.utils import timezone
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from django.db.models import Q, Count
from django.http import JsonResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from accounts.decorators import profile_required
from .models import ClaseResidente, ComentarioClase, FavoritoClase, EjemploVisualizacion, AccesoGuiaPresentaciones, ConversacionBot, MensajeBot
from .forms import ClaseResidenteForm, ComentarioClaseForm, BuscarClaseForm
import json
import logging

logger = logging.getLogger(__name__)


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


class GuiaPresentacionesView(LoginRequiredMixin, TemplateView):
    """
    Vista informativa sobre buenas prácticas para elaborar presentaciones de ateneos y clases.
    Incluye normas de citación, recursos recomendados, tips de diseño y presentación oral.
    """
    template_name = 'clases_residentes/guia_presentaciones.html'
    
    def get(self, request, *args, **kwargs):
        """Registrar el acceso del usuario a la guía"""
        try:
            user_agent = request.META.get('HTTP_USER_AGENT', '')[:255]
            AccesoGuiaPresentaciones.objects.create(
                usuario=request.user,
                user_agent=user_agent
            )
        except Exception as e:
            # No interrumpir el acceso a la guía si falla el registro
            pass
        
        return super().get(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Consultar ejemplos visuales activos, agrupados por categoría
        context['ejemplos'] = EjemploVisualizacion.objects.filter(activo=True).order_by('orden')
        
        # Estructura de Ateneo (Caso Clínico)
        context['estructura_ateneo'] = {
            'titulo': 'Ateneo de Caso Clínico',
            'descripcion': 'Presentación estructurada de un caso clínico real con análisis diagnóstico',
            'secciones': [
                {'nombre': 'Portada', 'contenido': 'Título del caso, tu nombre, fecha, institución'},
                {'nombre': 'Caso Clínico', 'contenido': 'Motivo de consulta, antecedentes, examen físico'},
                {'nombre': 'Estudios Complementarios', 'contenido': 'Análisis de laboratorio e imágenes con los hallazgos principales'},
                {'nombre': 'Diagnósticos Diferenciales', 'contenido': 'Lista razonada de posibles diagnósticos'},
                {'nombre': 'Diagnóstico Final', 'contenido': 'Diagnóstico definitivo con su justificación'},
                {'nombre': 'Discusión', 'contenido': 'Revisión bibliográfica del tema, particularidades del caso'},
                {'nombre': 'Bibliografía', 'contenido': 'Referencias en formato Vancouver'},
            ],
            'tips': [
                'Guardá el suspenso diagnóstico hasta la discusión',
                'Andá mostrando las imágenes de forma progresiva',
                'Incluí tanto los hallazgos positivos como los negativos relevantes',
            ]
        }
        
        # Estructura de Clase Teórica
        context['estructura_clase'] = {
            'titulo': 'Clase Teórica/Revisión',
            'descripcion': 'Presentación educativa sobre un tema específico',
            'secciones': [
                {'nombre': 'Portada', 'contenido': 'Título, tu nombre, fecha, institución'},
                {'nombre': 'Objetivos', 'contenido': 'Qué va a aprender la audiencia al finalizar'},
                {'nombre': 'Introducción', 'contenido': 'Contexto y relevancia del tema'},
                {'nombre': 'Desarrollo', 'contenido': 'Contenido principal organizado en subtemas'},
                {'nombre': 'Casos Ilustrativos', 'contenido': 'Ejemplos clínicos que refuercen los conceptos'},
                {'nombre': 'Conclusiones', 'contenido': 'Puntos clave para llevarse'},
                {'nombre': 'Bibliografía', 'contenido': 'Referencias en formato Vancouver'},
            ],
            'tips': [
                'Dividí el contenido en secciones bien claras',
                'Usá casos reales para ilustrar los conceptos teóricos',
                'Incluí preguntas de repaso al final de cada sección',
            ]
        }
        
        # Citación de imágenes con ayudas mnemotécnicas
        context['citacion_imagenes'] = {
            'vancouver': {
                'formato': 'Autor(es). Título de la imagen [Tipo de medio]. En: Fuente; Año. Disponible en: URL',
                'ejemplo': 'Smith J, Johnson M. Tomografía de tórax con neumonía COVID-19 [Imagen TC]. En: Radiopaedia; 2023. Disponible en: https://radiopaedia.org/cases/12345',
                'explicacion': 'Este formato asegura la trazabilidad de la imagen. El autor es quien tomó o publicó la imagen, no necesariamente el paciente.',
                'tip_memoria': '💡 Acordate: ATE-FUA (Autor, Título, En, Fuente, URL, Año)',
                'cuando_usar': 'Siempre que uses imágenes de libros, artículos, bases de datos o sitios web especializados',
            },
            'imagen_propia': {
                'formato': 'Fuente: Archivo personal [o nombre de la institución]',
                'ejemplo': 'Fuente: Archivo personal del Servicio de Diagnóstico por Imágenes, Hospital Sanatorio Colegiales',
                'explicacion': 'Para imágenes de tus casos propios o de la institución, indicá claramente el origen.',
                'tip_memoria': '💡 Simple: "Fuente: [De dónde sale]"',
                'cuando_usar': 'Para casos de tu institución o imágenes que sacaste vos',
            },
            'dominio_publico': {
                'formato': 'Imagen de dominio público / Creative Commons. Fuente: [Nombre del sitio]',
                'ejemplo': 'Imagen de dominio público. Fuente: Wikimedia Commons',
                'explicacion': 'Aunque sean de dominio público, siempre indicá la fuente por ética académica.',
                'tip_memoria': '💡 Aunque sea gratis, citá la fuente igual',
                'cuando_usar': 'Imágenes de Wikimedia, bancos de imágenes gratuitos, recursos educativos abiertos',
            },
        }
        
        # Bibliografía con ayudas mnemotécnicas
        context['citacion_bibliografia'] = {
            'articulo_revista': {
                'formato': 'Autor(es). Título del artículo. Nombre de la Revista. Año;Volumen(Número):páginas.',
                'ejemplo': 'Doe J, Smith A, Johnson M. COVID-19 imaging findings in severe cases. Radiology. 2023;308(2):234-245.',
                'explicacion': 'El orden refleja: QUIÉN escribió, QUÉ escribió, DÓNDE se publicó, CUÁNDO y EN QUÉ PÁGINAS.',
                'tip_memoria': '💡 ATR-AVP: Autor, Título, Revista, Año, Volumen, Páginas',
                'elementos': {
                    'Autor': 'Hasta 6 autores (si son más, los primeros 3 + et al.)',
                    'Título': 'Del artículo, sin comillas, con punto final',
                    'Revista': 'Abreviatura oficial (ej: Radiology, AJNR, Eur Radiol)',
                    'Año': 'De publicación',
                    'Volumen': 'Número de volumen en negrita (opcional)',
                    'Páginas': 'Rango completo (234-245, no 234-45)',
                },
            },
            'libro': {
                'formato': 'Autor(es). Título del Libro. Edición. Ciudad: Editorial; Año.',
                'ejemplo': 'Dähnert W. Radiology Review Manual. 8th ed. Philadelphia: Wolters Kluwer; 2017.',
                'explicacion': 'Similar al artículo pero incluye editorial y ciudad. La edición se indica solo si no es la primera.',
                'tip_memoria': '💡 A-T-E-C-E-A: Autor, Título, Edición, Ciudad, Editorial, Año',
                'elementos': {
                    'Autor': 'Apellido e inicial(es) del nombre',
                    'Título': 'En cursiva o normal según formato',
                    'Edición': 'Si es 2da o posterior (2nd ed., 3rd ed.)',
                    'Ciudad': 'Donde se publicó',
                    'Editorial': 'Nombre completo',
                    'Año': 'De publicación',
                },
            },
            'sitio_web': {
                'formato': 'Autor/Institución. Título de la página [Internet]. Ciudad: Editor; Año [citado Fecha]. Disponible en: URL',
                'ejemplo': 'Radiopaedia. CT pulmonary angiogram protocol [Internet]. Melbourne: Radiopaedia.org; 2023 [citado 2026 Mar 5]. Disponible en: https://radiopaedia.org/articles/ct-pulmonary-angiogram',
                'explicacion': 'Para recursos web, incluí [Internet] y la fecha en que accediste (puede cambiar con el tiempo).',
                'tip_memoria': '💡 Agregá [Internet] y fecha de [citado AAAA Mes Día], después la URL',
                'cuando_usar': 'UpToDate, Radiopaedia, sitios de sociedades médicas, protocolos online',
            },
        }
        
        # Recursos recomendados
        context['recursos_recomendados'] = [
            {
                'nombre': 'PubMed',
                'url': 'https://pubmed.ncbi.nlm.nih.gov/',
                'descripcion': 'Base de datos de literatura biomédica. Buscá artículos científicos revisados por pares.',
                'icono': 'fa-book-medical',
                'color': 'blue',
            },
            {
                'nombre': 'Radiopaedia',
                'url': 'https://radiopaedia.org/',
                'descripcion': 'Enciclopedia colaborativa de radiología con casos, artículos y protocolos.',
                'icono': 'fa-x-ray',
                'color': 'purple',
            },
            {
                'nombre': 'UpToDate',
                'url': 'https://www.uptodate.com/',
                'descripcion': 'Recurso clínico basado en evidencia con guías de práctica actualizadas.',
                'icono': 'fa-stethoscope',
                'color': 'green',
            },
            {
                'nombre': 'Google Scholar',
                'url': 'https://scholar.google.com/',
                'descripcion': 'Buscador académico para encontrar artículos, tesis y libros especializados.',
                'icono': 'fa-graduation-cap',
                'color': 'red',
            },
            {
                'nombre': 'RSNA RadiologyInfo',
                'url': 'https://www.radiologyinfo.org/',
                'descripcion': 'Información sobre procedimientos radiológicos para pacientes y profesionales.',
                'icono': 'fa-hospital',
                'color': 'orange',
            },
        ]
        
        # Tips de diseño visual
        context['tips_diseno'] = {
            'regla_6x6': {
                'titulo': 'Regla 6×6',
                'descripcion': 'No más de 6 líneas por diapositiva, no más de 6 palabras por línea',
                'razon': 'Mantiene la atención en vos como presentador, no en leer la diapo',
                'tip_memoria': '💡 Si la audiencia está leyendo, no te está escuchando',
            },
            'fuentes': {
                'titulo': 'Tipografía Legible',
                'descripcion': 'Usá fuentes sans-serif (Arial, Calibri, Helvetica) tamaño mínimo 24pt',
                'razon': 'Las fuentes sin serifa se leen mejor en pantallas y proyecciones',
                'tip_memoria': '💡 Si no se lee desde la última fila, el tamaño no sirve',
            },
            'colores': {
                'titulo': 'Contraste Alto',
                'descripcion': 'Fondo oscuro con texto claro, o fondo claro con texto oscuro. Evitá combinaciones de bajo contraste.',
                'razon': 'Mejora la legibilidad en diferentes condiciones de iluminación',
                'tip_memoria': '💡 Probá tu presentación en modo proyector antes del ateneo',
            },
            'imagenes': {
                'titulo': 'Imágenes de Alta Resolución',
                'descripcion': 'Usá imágenes de al menos 1024×768 px. Evitá imágenes pixeladas o borrosas.',
                'razon': 'La calidad de las imágenes refleja tu profesionalismo',
                'tip_memoria': '💡 Una imagen borrosa es peor que no poner nada',
            },
            'animaciones': {
                'titulo': 'Animaciones Moderadas',
                'descripcion': 'Usá transiciones simples y solo cuando agreguen valor (revelar información progresivamente)',
                'razon': 'Las animaciones excesivas distraen del contenido',
                'tip_memoria': '💡 Si gira, rebota o hace ruido, probablemente sobra',
            },
        }
        
        # Tips de presentación oral
        context['tips_presentacion'] = [
            {
                'categoria': 'Antes de Presentar',
                'tips': [
                    'Practicá al menos 3 veces completo. Medí el tiempo.',
                    'Conocé el equipo: proyector, puntero, micrófono.',
                    'Llegá 15 minutos antes para cargar tu presentación.',
                    'Tené un plan B: USB de respaldo, presentación en la nube.',
                ]
            },
            {
                'categoria': 'Durante la Presentación',
                'tips': [
                    'Contacto visual: mirá a diferentes personas de la audiencia, no a la pantalla.',
                    'Hablá claro y pausado. Proyectá la voz aunque uses micrófono.',
                    'Usá el puntero láser con moderación. No lo muevas nerviosamente.',
                    'Explicá las imágenes: no asumas que todos ven lo mismo que vos.',
                ]
            },
            {
                'categoria': 'Manejo del Tiempo',
                'tips': [
                    'Respetá el tiempo asignado. Mejor terminar 2 minutos antes que pasarte.',
                    'Tené marcadores mentales: "A los 10 min tengo que estar en la sección X".',
                    'Si te quedás sin tiempo, andá directo a conclusiones, no aceleres todo.',
                ]
            },
            {
                'categoria': 'Manejo de Preguntas',
                'tips': [
                    'Escuchá la pregunta completa antes de responder.',
                    'Si no sabés, admitilo: "Excelente pregunta, voy a tener que investigarlo".',
                    'Reformulá preguntas confusas: "Si entiendo bien, me estás preguntando...".',
                    'No te pongas a la defensiva. Las preguntas son oportunidades de aprendizaje.',
                ]
            },
        ]
        
        return context


class BotChatView(LoginRequiredMixin, View):
    """
    Vista API para el chatbot de asistencia en presentaciones.
    Recibe mensajes del usuario y retorna respuestas del bot.
    """
    
    def post(self, request):
        """Procesa un mensaje del usuario y retorna la respuesta del bot"""
        try:
            # Parsear JSON del request
            data = json.loads(request.body)
            mensaje = data.get('mensaje', '').strip()
            conversacion_id = data.get('conversacion_id')
            
            # Validar mensaje
            if not mensaje:
                return JsonResponse({
                    'success': False,
                    'error': 'El mensaje no puede estar vacío'
                }, status=400)
            
            if len(mensaje) > 500:
                return JsonResponse({
                    'success': False,
                    'error': 'El mensaje es demasiado largo (máximo 500 caracteres)'
                }, status=400)
            
            # Rate limiting básico: máximo 20 mensajes por hora
            from django.core.cache import cache
            cache_key = f'bot_rate_limit_{request.user.id}'
            mensajes_enviados = cache.get(cache_key, 0)
            
            if mensajes_enviados >= 20:
                return JsonResponse({
                    'success': False,
                    'error': 'Has alcanzado el límite de 20 mensajes por hora. Intentá más tarde.'
                }, status=429)
            
            # Llamar al servicio del bot
            from .bot_service import PresentacionesBot
            bot = PresentacionesBot()
            resultado = bot.chat(
                usuario=request.user,
                mensaje=mensaje,
                conversacion_id=conversacion_id
            )
            
            # Incrementar contador de rate limiting
            cache.set(cache_key, mensajes_enviados + 1, 3600)  # 1 hora
            
            if resultado['success']:
                return JsonResponse({
                    'success': True,
                    'respuesta': resultado['respuesta'],
                    'conversacion_id': resultado['conversacion_id'],
                    'mensaje_id': resultado.get('mensaje_id'),
                    'from_cache': resultado.get('from_cache', False)
                })
            else:
                return JsonResponse({
                    'success': False,
                    'error': resultado['error']
                }, status=500)
                
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'JSON inválido'
            }, status=400)
        except Exception as e:
            logger.error(f"Error en BotChatView: {e}")
            return JsonResponse({
                'success': False,
                'error': 'Error interno del servidor'
            }, status=500)
    
    def get(self, request):
        """Método GET no permitido"""
        return JsonResponse({
            'success': False,
            'error': 'Método no permitido. Usar POST.'
        }, status=405)


class BotFeedbackView(LoginRequiredMixin, View):
    """
    Vista API para registrar feedback (positivo/negativo) de mensajes del bot.
    """
    
    def post(self, request):
        """Registra feedback de un mensaje"""
        try:
            data = json.loads(request.body)
            mensaje_id = data.get('mensaje_id')
            feedback = data.get('feedback')  # 'positivo' o 'negativo'
            
            # Validar datos
            if not mensaje_id or not feedback:
                return JsonResponse({
                    'success': False,
                    'error': 'mensaje_id y feedback son requeridos'
                }, status=400)
            
            if feedback not in ['positivo', 'negativo']:
                return JsonResponse({
                    'success': False,
                    'error': 'feedback debe ser "positivo" o "negativo"'
                }, status=400)
            
            # Obtener mensaje y verificar que pertenece al usuario
            mensaje = get_object_or_404(MensajeBot, id=mensaje_id)
            
            if mensaje.conversacion.usuario != request.user:
                return JsonResponse({
                    'success': False,
                    'error': 'No tienes permiso para valorar este mensaje'
                }, status=403)
            
            # Solo se puede dar feedback a mensajes del bot
            if mensaje.rol != 'assistant':
                return JsonResponse({
                    'success': False,
                    'error': 'Solo se puede dar feedback a respuestas del bot'
                }, status=400)
            
            # Actualizar feedback
            mensaje.feedback = feedback
            mensaje.save(update_fields=['feedback'])
            
            logger.info(f"Feedback {feedback} registrado para mensaje {mensaje_id} por {request.user}")
            
            return JsonResponse({
                'success': True,
                'mensaje': f'Feedback {feedback} registrado correctamente'
            })
            
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'JSON inválido'
            }, status=400)
        except Exception as e:
            logger.error(f"Error en BotFeedbackView: {e}")
            return JsonResponse({
                'success': False,
                'error': 'Error interno del servidor'
            }, status=500)
