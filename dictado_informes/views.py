from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse_lazy
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.db.models import Q, Count, Avg
from django.views.decorators.http import require_POST, require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.core.files.base import ContentFile
from .models import (
    Informe, PlantillaInforme, AudioTranscripcion, TipoEstudio, 
    EstadoInforme, TerminoMedico, CorreccionAprendizaje, MetricaDictado,
    PlantillaEstructurada, FeedbackCalidadDictado
)
from .forms import TerminoMedicoForm, PlantillaEstructuradaForm
from .ai_services import ai_service
import json
import base64
import logging
import time  # 🚀 FASE 4: Para medir tiempos
import difflib

logger = logging.getLogger(__name__)


def user_can_access_dictado_module(user):
    return user.is_authenticated and getattr(user, 'puede_acceder_dictado_ia', lambda: False)()


def get_plantillas_estructuradas_visibles(user, solo_activas=False):
    return PlantillaEstructurada.visibles_para_usuario(user, solo_activas=solo_activas)


def _calcular_metricas_edicion(texto_ia, texto_final):
    """Calcula edición manual aproximada con ratio de similitud de caracteres."""
    texto_ia = (texto_ia or '').strip()
    texto_final = (texto_final or '').strip()

    if not texto_ia and not texto_final:
        return {
            'longitud_texto_ia': 0,
            'longitud_texto_final': 0,
            'caracteres_editados': 0,
            'porcentaje_edicion': 0.0,
            'tuvo_edicion': False,
        }

    ratio = difflib.SequenceMatcher(None, texto_ia, texto_final).ratio()
    base = max(len(texto_ia), len(texto_final), 1)
    caracteres_editados = max(0, int(round((1.0 - ratio) * base)))
    porcentaje_edicion = round((caracteres_editados / base) * 100, 2)

    return {
        'longitud_texto_ia': len(texto_ia),
        'longitud_texto_final': len(texto_final),
        'caracteres_editados': caracteres_editados,
        'porcentaje_edicion': porcentaje_edicion,
        'tuvo_edicion': caracteres_editados > 0,
    }


class SuperuserRequiredMixin(UserPassesTestMixin):
    """Mixin para restringir acceso solo a superusuarios"""
    def test_func(self):
        return self.request.user.is_superuser
    
    def handle_no_permission(self):
        messages.warning(self.request, "⚠️ No tienes permiso para acceder a esta sección.")
        return redirect('home')


class DictadoModuleAccessMixin(UserPassesTestMixin):
    """Acceso restringido al piloto de dictado y superusuarios."""

    def test_func(self):
        return user_can_access_dictado_module(self.request.user)

    def handle_no_permission(self):
        messages.warning(self.request, "⚠️ No tienes permiso para acceder a Dictado IA.")
        return redirect('home')


class DashboardDictadoView(LoginRequiredMixin, SuperuserRequiredMixin, TemplateView):
    """Vista principal del módulo de dictado de informes"""
    template_name = 'dictado_informes/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Estadísticas generales
        context['total_informes'] = Informe.objects.count()
        context['informes_pendientes'] = Informe.objects.filter(
            estado__in=[EstadoInforme.BORRADOR, EstadoInforme.EN_REVISION]
        ).count()
        context['informes_finalizados'] = Informe.objects.filter(
            estado=EstadoInforme.FINALIZADO
        ).count()
        context['informes_firmados'] = Informe.objects.filter(
            estado=EstadoInforme.FIRMADO
        ).count()
        
        # Informes recientes
        context['informes_recientes'] = Informe.objects.select_related(
            'medico', 'plantilla_usada'
        ).order_by('-fecha_creacion')[:10]
        
        # Total de plantillas activas
        context['total_plantillas'] = PlantillaInforme.objects.filter(activa=True).count()
        
        # Informes por tipo de estudio
        context['informes_por_tipo'] = Informe.objects.values(
            'tipo_estudio'
        ).annotate(total=Count('id')).order_by('-total')
        
        # Información de API de IA
        context['api_info'] = ai_service.get_api_info()
        
        return context


class DictadoRapidoView(LoginRequiredMixin, DictadoModuleAccessMixin, TemplateView):
    """Vista simplificada para dictado rápido sin guardar - solo dictar, mejorar y copiar"""
    template_name = 'dictado_informes/dictado_rapido_whisper.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        plantillas_visibles = list(get_plantillas_estructuradas_visibles(
            self.request.user,
            solo_activas=True,
        ).values(
            'codigo',
            'nombre',
            'creada_por_id',
            'creada_por__username',
            'compartida',
        ).order_by('codigo'))

        plantillas_propias = [
            p for p in plantillas_visibles
            if p['creada_por_id'] == self.request.user.id
        ]
        plantillas_biblioteca = [
            p for p in plantillas_visibles
            if p['creada_por_id'] != self.request.user.id
        ]

        default_codigo = None
        if plantillas_propias:
            default_codigo = plantillas_propias[0]['codigo']
        elif plantillas_biblioteca:
            default_codigo = plantillas_biblioteca[0]['codigo']

        context['plantillas_estructuradas'] = plantillas_visibles
        context['plantillas_propias'] = plantillas_propias
        context['plantillas_biblioteca'] = plantillas_biblioteca
        context['plantillas_default_codigo'] = default_codigo
        context['plantillas_total_visibles'] = len(plantillas_visibles)
        return context


class DemoPresentacionIAView(TemplateView):
    """Pantalla de demo para charla clinica (sin logica de negocio)."""
    template_name = 'dictado_informes/demo_presentacion_ia.html'


def demo_segmentos_reales_api(request):
    """Métricas agregadas para incrustar segmentos reales en la demo de presentación."""
    data = {
        'dictado': {
            'informes_total': 0,
            'informes_finalizados': 0,
            'correcciones_aprendizaje': 0,
            'tiempo_promedio_segundos': 0,
        },
        'preinformes': {
            'total': 0,
            'pendiente_revision': 0,
            'finalizado': 0,
            'revisiones': 0,
        },
        'docencia': {
            'clases_activas': 0,
            'conversaciones_bot': 0,
            'mensajes_bot': 0,
        }
    }

    # Segmento real de Dictado IA
    data['dictado']['informes_total'] = Informe.objects.count()
    data['dictado']['informes_finalizados'] = Informe.objects.filter(
        estado=EstadoInforme.FINALIZADO
    ).count()
    data['dictado']['correcciones_aprendizaje'] = CorreccionAprendizaje.objects.count()

    promedio_ms = MetricaDictado.objects.filter(
        tiempo_total_ms__isnull=False
    ).aggregate(promedio=Avg('tiempo_total_ms'))['promedio']
    if promedio_ms:
        data['dictado']['tiempo_promedio_segundos'] = round(float(promedio_ms) / 1000, 1)

    # Segmento real de Preinformes (residencia)
    try:
        from preinformes.models import Preinforme, RevisionPreinforme

        data['preinformes']['total'] = Preinforme.objects.count()
        data['preinformes']['pendiente_revision'] = Preinforme.objects.filter(
            estado='pendiente_revision'
        ).count()
        data['preinformes']['finalizado'] = Preinforme.objects.filter(
            estado='finalizado'
        ).count()
        data['preinformes']['revisiones'] = RevisionPreinforme.objects.count()
    except Exception as exc:
        logger.warning("No se pudieron cargar métricas de preinformes para demo: %s", exc)

    # Segmento real de Docencia
    try:
        from clases_residentes.models import ClaseResidente, ConversacionBot, MensajeBot

        data['docencia']['clases_activas'] = ClaseResidente.objects.filter(activa=True).count()
        data['docencia']['conversaciones_bot'] = ConversacionBot.objects.count()
        data['docencia']['mensajes_bot'] = MensajeBot.objects.count()
    except Exception as exc:
        logger.warning("No se pudieron cargar métricas de docencia para demo: %s", exc)

    return JsonResponse(
        {
            'ok': True,
            'actualizado': timezone.now().strftime('%d/%m/%Y %H:%M'),
            'data': data,
        }
    )


class InformeListView(LoginRequiredMixin, SuperuserRequiredMixin, ListView):
    """Lista de todos los informes"""
    model = Informe
    template_name = 'dictado_informes/informe_list.html'
    context_object_name = 'informes'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = super().get_queryset().select_related('medico', 'medico_firma', 'plantilla_usada')
        
        # Filtros
        tipo_estudio = self.request.GET.get('tipo_estudio')
        estado = self.request.GET.get('estado')
        search = self.request.GET.get('q')
        
        if tipo_estudio:
            queryset = queryset.filter(tipo_estudio=tipo_estudio)
        if estado:
            queryset = queryset.filter(estado=estado)
        if search:
            queryset = queryset.filter(
                Q(nombre__icontains=search) |
                Q(apellido__icontains=search) |
                Q(dni_paciente__icontains=search) |
                Q(numero_estudio__icontains=search)
            )
        
        return queryset.order_by('-fecha_creacion')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tipos_estudio'] = TipoEstudio.choices
        context['estados'] = EstadoInforme.choices
        context['tipo_estudio_seleccionado'] = self.request.GET.get('tipo_estudio', '')
        context['estado_seleccionado'] = self.request.GET.get('estado', '')
        context['search'] = self.request.GET.get('search', '')
        return context


class InformeCreateView(LoginRequiredMixin, SuperuserRequiredMixin, CreateView):
    """Crear un nuevo informe"""
    model = Informe
    template_name = 'dictado_informes/informe_form.html'
    fields = [
        'nombre_paciente', 'apellido_paciente', 'dni_paciente', 'edad_paciente',
        'fecha_nacimiento', 'tipo_estudio', 'numero_estudio', 'fecha_estudio',
        'region_anatomica', 'indicacion_clinica', 'tecnica', 'hallazgos',
        'conclusion', 'estado', 'plantilla_usada', 'notas_privadas'
    ]
    success_url = reverse_lazy('dictado_informes:lista_informes')
    
    def form_valid(self, form):
        form.instance.medico = self.request.user
        messages.success(self.request, "✅ Informe creado exitosamente")
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['plantillas'] = PlantillaInforme.objects.filter(activa=True)
        context['es_nuevo'] = True
        return context


class InformeUpdateView(LoginRequiredMixin, SuperuserRequiredMixin, UpdateView):
    """Editar un informe existente"""
    model = Informe
    template_name = 'dictado_informes/informe_form.html'
    fields = [
        'nombre_paciente', 'apellido_paciente', 'dni_paciente', 'edad_paciente',
        'fecha_nacimiento', 'tipo_estudio', 'numero_estudio', 'fecha_estudio',
        'region_anatomica', 'indicacion_clinica', 'tecnica', 'hallazgos',
        'conclusion', 'estado', 'plantilla_usada', 'notas_privadas'
    ]
    success_url = reverse_lazy('dictado_informes:informe_list')
    
    def form_valid(self, form):
        messages.success(self.request, "✅ Informe actualizado exitosamente")
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['plantillas'] = PlantillaInforme.objects.filter(activa=True)
        context['es_nuevo'] = False
        context['audios'] = self.object.audios.all()
        return context


class InformeDetailView(LoginRequiredMixin, SuperuserRequiredMixin, DetailView):
    """Ver detalle de un informe"""
    model = Informe
    template_name = 'dictado_informes/informe_detail.html'
    context_object_name = 'informe'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['audios'] = self.object.audios.all()
        return context


class InformeDeleteView(LoginRequiredMixin, SuperuserRequiredMixin, DeleteView):
    """Eliminar un informe"""
    model = Informe
    template_name = 'dictado_informes/informe_confirm_delete.html'
    success_url = reverse_lazy('dictado_informes:informe_list')
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, "🗑️ Informe eliminado exitosamente")
        return super().delete(request, *args, **kwargs)


class PlantillaListView(LoginRequiredMixin, SuperuserRequiredMixin, ListView):
    """Lista de plantillas de informes"""
    model = PlantillaInforme
    template_name = 'dictado_informes/plantilla_list.html'
    context_object_name = 'plantillas'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = super().get_queryset().select_related('creada_por')
        
        tipo_estudio = self.request.GET.get('tipo_estudio')
        if tipo_estudio:
            queryset = queryset.filter(tipo_estudio=tipo_estudio)
        
        activa = self.request.GET.get('activa')
        if activa == 'true':
            queryset = queryset.filter(activa=True)
        elif activa == 'false':
            queryset = queryset.filter(activa=False)
        
        return queryset.order_by('-fecha_creacion')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tipos_estudio'] = TipoEstudio.choices
        context['tipo_seleccionado'] = self.request.GET.get('tipo_estudio', '')
        return context


class PlantillaCreateView(LoginRequiredMixin, SuperuserRequiredMixin, CreateView):
    """Crear una nueva plantilla"""
    model = PlantillaInforme
    template_name = 'dictado_informes/plantilla_form.html'
    fields = ['nombre', 'tipo_estudio', 'contenido', 'variables', 'activa']
    success_url = reverse_lazy('dictado_informes:plantilla_list')
    
    def form_valid(self, form):
        form.instance.creada_por = self.request.user
        messages.success(self.request, "✅ Plantilla creada exitosamente")
        return super().form_valid(form)


class PlantillaUpdateView(LoginRequiredMixin, SuperuserRequiredMixin, UpdateView):
    """Editar una plantilla existente"""
    model = PlantillaInforme
    template_name = 'dictado_informes/plantilla_form.html'
    fields = ['nombre', 'tipo_estudio', 'contenido', 'variables', 'activa']
    success_url = reverse_lazy('dictado_informes:plantilla_list')
    
    def form_valid(self, form):
        messages.success(self.request, "✅ Plantilla actualizada exitosamente")
        return super().form_valid(form)


# ========================================================================
# VISTAS CRUD PARA PLANTILLAS ESTRUCTURADAS (Guardrails de IA)
# ========================================================================

class PlantillaEstructuradaListView(LoginRequiredMixin, DictadoModuleAccessMixin, ListView):
    """Lista de plantillas estructuradas para guardrails"""
    model = PlantillaEstructurada
    template_name = 'dictado_informes/plantilla_estructurada_list.html'
    context_object_name = 'plantillas'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = get_plantillas_estructuradas_visibles(self.request.user).select_related('creada_por').order_by('codigo')

        scope = self.request.GET.get('scope')
        if scope == 'mias':
            queryset = queryset.filter(creada_por=self.request.user)
        elif scope == 'biblioteca':
            queryset = queryset.filter(compartida=True).exclude(creada_por=self.request.user)
        
        activa = self.request.GET.get('activa')
        if activa == 'true':
            queryset = queryset.filter(activa=True)
        elif activa == 'false':
            queryset = queryset.filter(activa=False)
        
        origen = self.request.GET.get('origen')
        if origen:
            queryset = queryset.filter(origen=origen)

        compartida = self.request.GET.get('compartida')
        if compartida == 'true':
            queryset = queryset.filter(compartida=True)
        elif compartida == 'false':
            queryset = queryset.filter(compartida=False)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['ORIGEN_CHOICES'] = PlantillaEstructurada.ORIGEN_CHOICES
        context['origen_seleccionado'] = self.request.GET.get('origen', '')
        context['compartida_seleccionada'] = self.request.GET.get('compartida', '')
        context['scope_seleccionado'] = self.request.GET.get('scope', '')
        return context


class PlantillaEstructuradaCreateView(LoginRequiredMixin, DictadoModuleAccessMixin, CreateView):
    """Crear una nueva plantilla estructurada"""
    model = PlantillaEstructurada
    form_class = PlantillaEstructuradaForm
    template_name = 'dictado_informes/plantilla_estructurada_form.html'
    success_url = reverse_lazy('dictado_informes:plantilla_estructurada_list')
    
    def form_valid(self, form):
        form.instance.creada_por = self.request.user
        form.instance.origen = 'user'
        estado_comparticion = 'compartida' if form.instance.compartida else 'privada'
        messages.success(self.request, f"✅ Plantilla '{form.instance.nombre}' creada exitosamente como {estado_comparticion}")
        return super().form_valid(form)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['es_nueva'] = True
        context['titulo'] = 'Crear Nueva Plantilla Estructurada'
        return context


class PlantillaEstructuradaUpdateView(LoginRequiredMixin, DictadoModuleAccessMixin, UpdateView):
    """Editar una plantilla estructurada existente"""
    model = PlantillaEstructurada
    form_class = PlantillaEstructuradaForm
    template_name = 'dictado_informes/plantilla_estructurada_form.html'
    success_url = reverse_lazy('dictado_informes:plantilla_estructurada_list')
    
    def form_valid(self, form):
        messages.success(self.request, f"✅ Plantilla '{form.instance.nombre}' actualizada exitosamente")
        return super().form_valid(form)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_queryset(self):
        if self.request.user.is_superuser:
            return PlantillaEstructurada.objects.all()
        return PlantillaEstructurada.objects.filter(creada_por=self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['es_nueva'] = False
        context['titulo'] = f'Editar Plantilla: {self.object.nombre}'
        # Si es legacy, mostrar advertencia
        if self.object.origen == 'legacy':
            context['advertencia_legacy'] = 'Esta plantilla fue migrada desde hardcode. Los cambios afectarán el comportamiento de IA.'
        return context


class PlantillaEstructuradaDeleteView(LoginRequiredMixin, DictadoModuleAccessMixin, DeleteView):
    """Eliminar una plantilla estructurada (soft delete)"""
    model = PlantillaEstructurada
    template_name = 'dictado_informes/plantilla_estructurada_confirm_delete.html'
    success_url = reverse_lazy('dictado_informes:plantilla_estructurada_list')
    
    def delete(self, request, *args, **kwargs):
        plantilla = self.get_object()
        # Soft delete - solo desactivar
        plantilla.activa = False
        plantilla.save()
        messages.success(request, f"🗑️ Plantilla '{plantilla.nombre}' desactivada exitosamente")
        return redirect(self.success_url)

    def get_queryset(self):
        if self.request.user.is_superuser:
            return PlantillaEstructurada.objects.all()
        return PlantillaEstructurada.objects.filter(creada_por=self.request.user)


# Vista AJAX para obtener plantilla por ID
def obtener_plantilla(request, pk):
    """API para obtener contenido de una plantilla"""
    if not request.user.is_superuser:
        return JsonResponse({'error': 'No autorizado'}, status=403)
    
    try:
        plantilla = PlantillaInforme.objects.get(pk=pk, activa=True)
        return JsonResponse({
            'success': True,
            'contenido': plantilla.contenido,
            'variables': plantilla.variables,
            'tipo_estudio': plantilla.tipo_estudio
        })
    except PlantillaInforme.DoesNotExist:
        return JsonResponse({'error': 'Plantilla no encontrada'}, status=404)


# Vista para firmar informe
def firmar_informe(request, pk):
    """Firma un informe"""
    if not request.user.is_superuser:
        messages.error(request, "No tienes permiso para firmar informes")
        return redirect('home')
    
    informe = get_object_or_404(Informe, pk=pk)
    informe.firmar(request.user)
    messages.success(request, f"✅ Informe firmado exitosamente")
    return redirect('dictado_informes:informe_detail', pk=pk)


# ========================================================================
# NOTA: La función procesar_audio_dictado() fue eliminada el 2026-03-08
# Se reemplazó por dos APIs separadas para mejor modularidad:
#   - transcribir_audio_whisper() - Solo transcripción STT
#   - mejorar_texto_ia() - Solo mejora con LLM
# Esto permite usar cada servicio independientemente según necesidad.
# ========================================================================

# API para transcribir audio con Whisper (sin mejora IA)
@require_POST
@require_http_methods(["POST"])
@login_required
def transcribir_audio_whisper(request):
    """
    Transcribe audio usando Whisper API
    Solo transcripción, sin mejora de IA
    🚀 FASE 4: Registra métricas de performance
    
    Seguridad: CSRF protegido, requiere autenticación y superuser
    """
    if not user_can_access_dictado_module(request.user):
        return JsonResponse({'error': 'No autorizado'}, status=403)
    
    # 📊 FASE 4: Iniciar medición de tiempo
    tiempo_inicio = time.time()
    metrica = None
    tuvo_error = False
    error_detalle = ""
    
    try:
        data = json.loads(request.body)
        audio_base64 = data.get('audio')
        
        if not audio_base64:
            return JsonResponse({'error': 'No se recibió audio'}, status=400)
        
        logger.info("🎤 Transcribiendo audio con Whisper...")
        
        # Decodificar audio base64
        try:
            audio_data = base64.b64decode(audio_base64.split(',')[1] if ',' in audio_base64 else audio_base64)
            logger.info(f"Audio decodificado: {len(audio_data)} bytes")
        except Exception as e:
            logger.error(f"Error decodificando base64: {str(e)}")
            return JsonResponse({'error': 'Audio inválido'}, status=400)
        
        # Validar tamaño mínimo del audio
        MIN_AUDIO_SIZE = 500  # Mínimo 500 bytes (~0.1 segundos de audio WebM)
        if len(audio_data) < MIN_AUDIO_SIZE:
            logger.warning(f"Audio muy pequeño: {len(audio_data)} bytes (mínimo: {MIN_AUDIO_SIZE})")
            return JsonResponse({
                'success': False,
                'error': f'Audio demasiado corto ({len(audio_data)} bytes). Mantén presionado el botón por más tiempo.'
            }, status=400)
        
        # Crear archivo temporal
        audio_file = ContentFile(audio_data, name='dictado.webm')
        
        # 📊 FASE 4: Medir tiempo de transcripción
        tiempo_transcripcion_inicio = time.time()
        
        # Transcribir con Whisper
        transcripcion_result = ai_service.transcribe_audio(audio_file)
        
        # 📊 FASE 4: Calcular tiempo de transcripción
        tiempo_transcripcion_ms = int((time.time() - tiempo_transcripcion_inicio) * 1000)
        
        if transcripcion_result.get('error'):
            tuvo_error = True
            error_detalle = transcripcion_result['error']
            return JsonResponse({
                'success': False,
                'error': transcripcion_result['error']
            }, status=500)
        
        texto_transcrito = transcripcion_result.get('text', '')
        
        # 🎯 PROCESAMIENTO UNIFICADO: Comandos de voz + diccionario médico en orden correcto
        texto_procesado, correcciones = TerminoMedico.procesar_texto_completo(texto_transcrito)
        
        if correcciones:
            logger.info(f"✅ Texto procesado: {len(correcciones)} correcciones aplicadas")
            for i, corr in enumerate(correcciones[:5], 1):  # Mostrar max 5 en log
                logger.info(f"   {i}. {corr['de']} → {corr['a']}")
        
        logger.info(f"✅ Transcripción Whisper: {texto_transcrito[:100]}...")
        logger.info(f"✅ Texto procesado final: {texto_procesado[:100]}...")
        
        # 📊 FASE 4: Registrar métrica
        tiempo_total_ms = int((time.time() - tiempo_inicio) * 1000)
        
        metrica = MetricaDictado.objects.create(
            usuario=request.user,
            tiempo_transcripcion_ms=tiempo_transcripcion_ms,
            tiempo_total_ms=tiempo_total_ms,
            transcripcion_from_cache=transcripcion_result.get('from_cache', False),
            duracion_audio_segundos=transcripcion_result.get('duration'),
            tamanio_audio_kb=len(audio_data) // 1024,
            longitud_transcripcion=len(texto_procesado),
            api_transcripcion='whisper',
            tuvo_errores=False
        )
        
        logger.info(f"📊 Métrica registrada: {tiempo_total_ms}ms (transcripción: {tiempo_transcripcion_ms}ms)")
        
        return JsonResponse({
            'success': True,
            'texto_transcrito': texto_procesado,  # Enviar texto YA con comandos procesados
            'texto_original': texto_transcrito,  # Por si se necesita el original
            'correcciones': correcciones,  # 🆕 Incluir correcciones del diccionario médico
            'confianza': transcripcion_result.get('confidence', 0.95),
            'duracion': transcripcion_result.get('duration'),
            'from_cache': transcripcion_result.get('from_cache', False)
        })
    
    except Exception as e:
        tuvo_error = True
        error_detalle = str(e)
        logger.exception(f"Error en transcribir_audio_whisper: {str(e)}")
        
        # 📊 FASE 4: Registrar métrica de error
        try:
            tiempo_total_ms = int((time.time() - tiempo_inicio) * 1000)
            MetricaDictado.objects.create(
                usuario=request.user,
                tiempo_total_ms=tiempo_total_ms,
                tuvo_errores=True,
                error_detalle=error_detalle[:500],  # Limitar longitud
                api_transcripcion='whisper'
            )
        except Exception as metric_error:
            logger.error(f"Error registrando métrica: {metric_error}")
        
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)



# API para mejorar texto existente
@require_POST
def mejorar_texto_ia(request):
    """
    Mejora un texto ya escrito usando IA
    Útil para mejorar borradores sin dictado
    Soporta modo plantilla para respetar estructuras predefinidas
    🚀 FASE 4: Registra métricas de performance
    """
    if not user_can_access_dictado_module(request.user):
        return JsonResponse({'error': 'No autorizado'}, status=403)
    
    # 📊 FASE 4: Iniciar medición de tiempo
    tiempo_inicio = time.time()
    tuvo_error = False
    error_detalle = ""
    
    try:
        data = json.loads(request.body)
        # Aceptar tanto 'texto' como 'texto_original' para compatibilidad
        texto = data.get('texto_original') or data.get('texto', '')
        tipo_estudio = data.get('tipo_estudio', 'OTR')
        modo = data.get('modo', 'LIBRE')
        tipo_plantilla = data.get('tipo_plantilla', 'RODILLA')  # Nuevo campo
        plantilla = data.get('plantilla', None)
        field_name = data.get('field_name', None)  # Campo específico para contexto
        
        if not texto or texto.strip() == '':
            logger.warning("⚠️ mejorar_texto_ia: No se recibió texto válido")
            return JsonResponse({'error': 'No se recibió texto para mejorar'}, status=400)
        
        logger.info(f"📝 Mejorando texto ({len(texto)} caracteres) en modo {modo} para campo '{field_name}'")
        
        # Inicializar correcciones como lista vacía
        correcciones = []
        
        # El texto ya viene con diccionario médico aplicado desde la transcripción
        # Si viene de edición manual, aplicar diccionario ahora
        if data.get('from_manual_edit', False):
            texto_procesado, correcciones = TerminoMedico.aplicar_correcciones(texto)
            if correcciones:
                logger.info(f"✅ Diccionario aplicado (edición manual): {len(correcciones)} correcciones")
        else:
            # Ya viene procesado de transcripción
            texto_procesado = texto
        
        # Construir contexto con modo y campo específico
        contexto = {
            'modo': modo,  # 'FIEL' = solo corregir, 'AUTO' = detectar, 'ESTRUCTURADO' = crear secciones
            'field_name': field_name  # Para mejor contexto del campo específico
        }
        
        # Solo agregar tipo_plantilla si NO es modo FIEL
        if modo != 'FIEL':
            contexto['tipo_plantilla'] = tipo_plantilla
            logger.info(f"📋 Tipo de plantilla: {tipo_plantilla}")
        else:
            logger.info(f"✏️ Modo FIEL - sin plantilla, solo corrección")
        
        # Solo agregar plantilla si NO es modo FIEL
        if plantilla and modo != 'FIEL':
            contexto['plantilla'] = plantilla
            logger.info(f"🎯 Usando plantilla: {plantilla.get('nombre', 'sin nombre')}")
        
        # 📊 FASE 4: Medir tiempo de mejora con IA
        tiempo_mejora_inicio = time.time()
        
        # 3. MEJORAR CON IA
        result = ai_service.improve_medical_text(
            texto_procesado, 
            tipo_estudio, 
            contexto,
            usuario=request.user if request.user.is_authenticated else None
        )
        
        # 📊 FASE 4: Calcular tiempo de mejora
        tiempo_mejora_ms = int((time.time() - tiempo_mejora_inicio) * 1000)
        tiempo_total_ms = int((time.time() - tiempo_inicio) * 1000)
        
        texto_mejorado = result.get('texto_mejorado', texto_procesado)
        
        logger.info(f"✅ Texto mejorado en modo final: {result.get('modo', modo)}")
        
        # 📊 FASE 4: Registrar métrica
        try:
            MetricaDictado.objects.create(
                usuario=request.user,
                tiempo_mejora_ms=tiempo_mejora_ms,
                tiempo_total_ms=tiempo_total_ms,
                mejora_from_cache=result.get('from_cache', False),
                longitud_transcripcion=len(texto),  # Texto original
                longitud_mejora=len(texto_mejorado),  # Texto mejorado
                api_mejora=result.get('api_used', 'gpt'),
                modo_mejora=modo,
                tipo_estudio=tipo_estudio,
                tuvo_errores=False
            )
            logger.info(f"📊 Métrica registrada: {tiempo_total_ms}ms (mejora: {tiempo_mejora_ms}ms)")
        except Exception as metric_error:
            logger.error(f"Error registrando métrica: {metric_error}")
        
        return JsonResponse({
            'success': True,
            'texto_mejorado': texto_mejorado,
            'confianza': result.get('confianza', 0.0),
            'sugerencias': result.get('sugerencias', []),
            'correcciones_aplicadas': correcciones,  # Enviar correcciones al frontend
            'modo': result.get('modo', modo),  # Retornar modo usado por la IA
            'score_confianza': result.get('score_confianza', 1.0),
            'requiere_confirmacion': result.get('requiere_confirmacion', False),
            'motivo_confianza': result.get('motivo_confianza', ''),
            'guardrails_aplicados': result.get('guardrails_aplicados', []),
            'posible_invencion': result.get('posible_invencion', False),
            'terminos_sospechosos': result.get('terminos_sospechosos', [])
        })
    
    except json.JSONDecodeError as e:
        tuvo_error = True
        error_detalle = f"JSON decode error: {str(e)}"
        logger.error(f"❌ Error decodificando JSON: {str(e)}")
        return JsonResponse({'error': 'Datos inválidos en la solicitud'}, status=400)
    except Exception as e:
        tuvo_error = True
        error_detalle = str(e)
        logger.error(f"❌ Error en mejorar_texto_ia: {str(e)}", exc_info=True)
        
        # 📊 FASE 4: Registrar métrica de error
        try:
            tiempo_total_ms = int((time.time() - tiempo_inicio) * 1000)
            MetricaDictado.objects.create(
                usuario=request.user,
                tiempo_total_ms=tiempo_total_ms,
                tipo_estudio=data.get('tipo_estudio', 'OTR') if 'data' in locals() else 'OTR',
                modo_mejora=data.get('modo', 'LIBRE') if 'data' in locals() else 'LIBRE',
                tuvo_errores=True,
                error_detalle=error_detalle[:500],  # Limitar longitud
                api_mejora='gpt'
            )
        except Exception as metric_error:
            logger.error(f"Error registrando métrica: {metric_error}")
        
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)



# ========================================
# VISTAS PARA DICCIONARIO MÉDICO
# ========================================

class TerminoMedicoListView(LoginRequiredMixin, SuperuserRequiredMixin, ListView):
    """Lista de términos médicos del diccionario"""
    model = TerminoMedico
    template_name = 'dictado_informes/termino_list.html'
    context_object_name = 'terminos'
    paginate_by = 50
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filtros
        categoria = self.request.GET.get('categoria')
        activo = self.request.GET.get('activo')
        search = self.request.GET.get('q')
        
        if categoria:
            queryset = queryset.filter(categoria=categoria)
        if activo == 'si':
            queryset = queryset.filter(activo=True)
        elif activo == 'no':
            queryset = queryset.filter(activo=False)
        if search:
            queryset = queryset.filter(
                Q(termino_incorrecto__icontains=search) |
                Q(termino_correcto__icontains=search) |
                Q(notas__icontains=search)
            )
        
        return queryset.order_by('-frecuencia_uso', 'termino_incorrecto')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_terminos'] = TerminoMedico.objects.count()
        context['terminos_activos'] = TerminoMedico.objects.filter(activo=True).count()
        context['mas_usados'] = TerminoMedico.objects.filter(activo=True).order_by('-frecuencia_uso')[:5]
        return context


class TerminoMedicoCreateView(LoginRequiredMixin, SuperuserRequiredMixin, CreateView):
    """Crear nuevo término médico"""
    model = TerminoMedico
    form_class = TerminoMedicoForm
    template_name = 'dictado_informes/termino_form.html'
    success_url = reverse_lazy('dictado_informes:termino_list')
    
    def form_valid(self, form):
        messages.success(self.request, f"✅ Término '{form.instance.termino_correcto}' agregado al diccionario")
        return super().form_valid(form)


class TerminoMedicoUpdateView(LoginRequiredMixin, SuperuserRequiredMixin, UpdateView):
    """Editar término médico existente"""
    model = TerminoMedico
    form_class = TerminoMedicoForm
    template_name = 'dictado_informes/termino_form.html'
    success_url = reverse_lazy('dictado_informes:termino_list')
    
    def form_valid(self, form):
        messages.success(self.request, f"✅ Término '{form.instance.termino_correcto}' actualizado")
        return super().form_valid(form)


class TerminoMedicoDeleteView(LoginRequiredMixin, SuperuserRequiredMixin, DeleteView):
    """Eliminar término médico"""
    model = TerminoMedico
    template_name = 'dictado_informes/termino_confirm_delete.html'
    success_url = reverse_lazy('dictado_informes:termino_list')
    
    def delete(self, request, *args, **kwargs):
        termino = self.get_object()
        messages.success(request, f"🗑️ Término '{termino.termino_correcto}' eliminado del diccionario")
        return super().delete(request, *args, **kwargs)


@require_POST
def toggle_termino_activo(request, pk):
    """Toggle estado activo/inactivo de un término"""
    termino = get_object_or_404(TerminoMedico, pk=pk)
    termino.activo = not termino.activo
    termino.save()
    
    estado = "activado" if termino.activo else "desactivado"
    return JsonResponse({
        'success': True,
        'activo': termino.activo,
        'message': f"Término '{termino.termino_correcto}' {estado}"
    })


@require_POST
def guardar_correccion_aprendizaje(request):
    """
    Guarda una corrección manual del usuario para entrenar la IA.
    Se llama cuando el usuario edita el texto mejorado y lo guarda.
    """
    if not user_can_access_dictado_module(request.user):
        return JsonResponse({'error': 'No autorizado'}, status=403)
    
    try:
        data = json.loads(request.body)
        texto_original = data.get('texto_original', '')  # Transcripción Whisper
        texto_ia = data.get('texto_ia', '')              # Texto mejorado por IA
        texto_final = data.get('texto_final', '')        # Texto editado por usuario
        tipo_estudio = data.get('tipo_estudio', '')
        
        if not texto_original or not texto_ia or not texto_final:
            return JsonResponse({'error': 'Faltan textos requeridos'}, status=400)
        
        # Solo guardar si el usuario hizo cambios
        if texto_ia.strip() == texto_final.strip():
            return JsonResponse({
                'success': True,
                'message': 'No hay cambios para guardar',
                'guardado': False
            })
        
        # Crear registro de aprendizaje
        correccion = CorreccionAprendizaje.objects.create(
            texto_original=texto_original,
            texto_ia=texto_ia,
            texto_final=texto_final,
            usuario=request.user,
            tipo_estudio=tipo_estudio if tipo_estudio in dict(TipoEstudio.choices) else ''
        )

        apta_para_prompt = CorreccionAprendizaje.es_apta_para_prompt(correccion)
        estado_aprendizaje = "apta" if apta_para_prompt else "descartada_para_prompt"
        
        logger.info(f"✅ Corrección de aprendizaje guardada ID={correccion.id} por {request.user}")
        logger.info(f"   Cambios detectados: {len(correccion.cambios_detectados)}")
        logger.info(f"   Estado aprendizaje automático: {estado_aprendizaje}")

        if apta_para_prompt:
            mensaje = f"✅ Corrección guardada! {len(correccion.cambios_detectados)} cambios detectados"
        else:
            mensaje = (
                "✅ Corrección guardada en historial, pero no se usará automáticamente "
                "porque parece una edición atípica."
            )
        
        return JsonResponse({
            'success': True,
            'message': mensaje,
            'guardado': True,
            'id': correccion.id,
            'cambios': correccion.cambios_detectados,
            'apta_para_prompt': apta_para_prompt,
            'estado_aprendizaje': estado_aprendizaje,
        })
        
    except Exception as e:
        logger.error(f"❌ Error guardando corrección: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_POST
def registrar_feedback_calidad(request):
    """Registra feedback binario de calidad y magnitud de edición manual."""
    if not user_can_access_dictado_module(request.user):
        return JsonResponse({'error': 'No autorizado'}, status=403)

    try:
        data = json.loads(request.body)
        estado_feedback = data.get('estado_feedback', '').strip()
        texto_ia = data.get('texto_ia', '')
        texto_final = data.get('texto_final', '')
        modo_dictado = data.get('modo_dictado', FeedbackCalidadDictado.ModoDictado.FIEL)
        tipo_estudio = data.get('tipo_estudio', '')
        tipo_plantilla = data.get('tipo_plantilla', '')

        estados_validos = {e[0] for e in FeedbackCalidadDictado.EstadoFeedback.choices}
        if estado_feedback not in estados_validos:
            return JsonResponse({'error': 'estado_feedback inválido'}, status=400)

        modos_validos = {m[0] for m in FeedbackCalidadDictado.ModoDictado.choices}
        if modo_dictado not in modos_validos:
            modo_dictado = FeedbackCalidadDictado.ModoDictado.FIEL

        if tipo_estudio not in dict(TipoEstudio.choices):
            tipo_estudio = ''

        metricas = _calcular_metricas_edicion(texto_ia, texto_final)

        feedback = FeedbackCalidadDictado.objects.create(
            usuario=request.user,
            estado_feedback=estado_feedback,
            modo_dictado=modo_dictado,
            tipo_estudio=tipo_estudio,
            tipo_plantilla=(tipo_plantilla or '')[:50],
            **metricas,
        )

        return JsonResponse({
            'success': True,
            'id': feedback.id,
            'porcentaje_edicion': feedback.porcentaje_edicion,
            'caracteres_editados': feedback.caracteres_editados,
            'tuvo_edicion': feedback.tuvo_edicion,
        })
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Datos inválidos en la solicitud'}, status=400)
    except Exception as e:
        logger.exception(f"Error registrando feedback de calidad: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@require_http_methods(["GET"])
def info_aprendizaje(request):
    """
    Endpoint para obtener información sobre el sistema de aprendizaje activo
    """
    try:
        from .models import CorreccionAprendizaje
        
        # Obtener ejemplos para el usuario actual
        usuario = request.user if request.user.is_authenticated else None
        ejemplos = CorreccionAprendizaje.obtener_ejemplos_aprendizaje(usuario=usuario, limite=10)
        
        # Contar líneas de ejemplos (cada línea es una corrección)
        cantidad = len(ejemplos.split('\n')) if ejemplos else 0
        
        logger.info(f"📊 Info aprendizaje: usuario={usuario}, cantidad={cantidad}")
        
        return JsonResponse({
            'success': True,
            'cantidad': cantidad,
            'tiene_ejemplos': cantidad > 0
        })
        
    except Exception as e:
        logger.error(f"❌ Error obteniendo info aprendizaje: {str(e)}")
        return JsonResponse({
            'success': False,
            'cantidad': 0,
            'tiene_ejemplos': False
        })
    except Exception as e:
        logger.exception(f"Error guardando corrección de aprendizaje: {str(e)}")
        return JsonResponse({
            'error': str(e)
        }, status=500)

