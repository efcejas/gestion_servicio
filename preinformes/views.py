from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import models, IntegrityError, transaction
from django.http import JsonResponse, HttpResponse
from django.urls import reverse
from django.utils import timezone
from django.core.paginator import Paginator
from django.core.files.uploadedfile import UploadedFile
from django.core.cache import cache
from django.db.models import Q, Count, Avg
from django.contrib.auth import get_user_model
from django.views.decorators.http import require_http_methods
import json
import logging
import os

from accounts.decorators import role_required
from .models import (
    Preinforme, TipoEstudio, Region, PlantillaPreinforme, 
    RevisionPreinforme, HistorialEstudios, EtiquetaPreinforme,
    AdjuntoPreinforme,
    EncuestaResidente
)
from .forms import (
    PreinformeForm, FiltroPreinformesForm, 
    RevisionPreinformeForm, PlantillaPreinformeForm,
    NuevaPlantillaResidenteForm
)

User = get_user_model()
logger = logging.getLogger(__name__)

MAX_ADJUNTOS_POR_ORIGEN = 3
MAX_ADJUNTO_SIZE_MB = 5
ALLOWED_ADJUNTO_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}

from .services import evaluar_sesion_mentor as _autoevaluar_sesion_mentor_al_enviar
from .selectors import get_asignados_de, get_pendientes_sin_revisor


def _guardar_adjuntos_preinforme(preinforme, archivos, subido_por, origen):
    """Valida y guarda adjuntos de imágenes para un preinforme."""
    if not archivos:
        return 0, None

    existentes = AdjuntoPreinforme.objects.filter(
        preinforme=preinforme,
        origen=origen,
        activo=True,
    ).count()

    if existentes + len(archivos) > MAX_ADJUNTOS_POR_ORIGEN:
        disponibles = max(0, MAX_ADJUNTOS_POR_ORIGEN - existentes)
        return 0, f'Solo puedes subir {MAX_ADJUNTOS_POR_ORIGEN} imágenes por rol. Te quedan {disponibles} disponibles.'

    archivos_validos = []
    for archivo in archivos:
        if not isinstance(archivo, UploadedFile):
            return 0, 'Archivo inválido recibido.'

        extension = os.path.splitext(archivo.name)[1].lower()
        if extension not in ALLOWED_ADJUNTO_EXTENSIONS:
            return 0, 'Formato no permitido. Usa JPG, PNG o WEBP.'

        if archivo.size > MAX_ADJUNTO_SIZE_MB * 1024 * 1024:
            return 0, f'Cada imagen debe ser menor a {MAX_ADJUNTO_SIZE_MB} MB.'

        archivos_validos.append(archivo)

    creados = []
    try:
        with transaction.atomic():
            for archivo in archivos_validos:
                creado = AdjuntoPreinforme.objects.create(
                    preinforme=preinforme,
                    imagen=archivo,
                    subido_por=subido_por,
                    origen=origen,
                    descripcion_corta='',
                    activo=True,
                )
                creados.append(creado)
    except Exception:
        return 0, 'No se pudieron guardar las imágenes. Inténtalo nuevamente.'

    return len(creados), None


def _eliminar_adjuntos_residente(preinforme, adjunto_ids, usuario):
    """Elimina adjuntos activos del residente para un preinforme editable."""
    if not adjunto_ids:
        return 0

    ids_validos = []
    for adjunto_id in adjunto_ids:
        try:
            ids_validos.append(int(adjunto_id))
        except (TypeError, ValueError):
            continue

    if not ids_validos:
        return 0

    adjuntos = AdjuntoPreinforme.objects.filter(
        id__in=ids_validos,
        preinforme=preinforme,
        origen='residente',
        subido_por=usuario,
        activo=True,
    )

    eliminados = 0
    for adjunto in adjuntos:
        if adjunto.imagen:
            adjunto.imagen.delete(save=False)
        adjunto.delete()
        eliminados += 1

    return eliminados


# === VISTAS PARA RESIDENTES ===

@login_required
@role_required('medico_residente', 'jefe_residentes', 'instructor_residentes')
def dashboard_residente(request):
    """Dashboard principal para residentes"""
    # Obtener o crear historial del residente
    historial, created = HistorialEstudios.objects.get_or_create(residente=request.user)
    if created:
        historial.actualizar_estadisticas()
    
    # Estadísticas rápidas
    preinformes_pendientes = Preinforme.objects.filter(
        residente=request.user,
        estado__in=['borrador', 'pendiente_revision']
    ).count()
    
    preinformes_en_revision = Preinforme.objects.filter(
        residente=request.user,
        estado='en_revision'
    ).count()
    
    # Últimos preinformes
    ultimos_preinformes = Preinforme.objects.filter(
        residente=request.user
    ).order_by('-fecha_creacion')[:5]
    
    # Preinformes en edición activa (por cualquier residente)
    tiempo_limite = timezone.now() - timezone.timedelta(minutes=15)
    preinformes_en_edicion = Preinforme.objects.filter(
        en_edicion_por__isnull=False,
        ultima_actividad_edicion__gt=tiempo_limite,
        estado__in=['borrador', 'pendiente_revision', 'en_revision']
    ).exclude(
        en_edicion_por=request.user
    ).select_related('en_edicion_por', 'tipo_estudio', 'revisor').order_by('-ultima_actividad_edicion')

    encuesta_completada = EncuestaResidente.objects.filter(residente=request.user).exists()

    context = {
        'historial': historial,
        'preinformes_pendientes': preinformes_pendientes,
        'preinformes_en_revision': preinformes_en_revision,
        'ultimos_preinformes': ultimos_preinformes,
        'preinformes_en_edicion': preinformes_en_edicion,
        'encuesta_completada': encuesta_completada,
    }
    
    return render(request, 'preinformes/dashboard_residente.html', context)


@login_required
@role_required('medico_residente', 'jefe_residentes', 'instructor_residentes')
def crear_preinforme(request):
    """Crear un nuevo preinforme"""
    if request.method == 'POST':
        # Guardar datos del formulario en sesión antes de procesar
        if 'crear_plantilla' in request.POST:
            # Usuario quiere crear una plantilla nueva
            request.session['preinforme_form_data'] = request.POST.dict()
            tipo_estudio = request.POST.get('tipo_estudio', '').strip()
            region = request.POST.get('region', '').strip()
            
            # Validar que tipo_estudio y region sean valores válidos
            if not tipo_estudio or not region or tipo_estudio in ['None', 'null', ''] or region in ['None', 'null', '']:
                messages.error(request, 'Debes seleccionar primero el tipo de estudio y región antes de crear una plantilla.')
                return redirect('preinformes:crear_preinforme')
            
            return redirect(f"{reverse('preinformes:crear_plantilla_residente')}?tipo_estudio={tipo_estudio}&region={region}")
        
        form = PreinformeForm(request.POST, user=request.user)
        if form.is_valid():
            preinforme = form.save(commit=False)
            preinforme.residente = request.user
            preinforme.save()

            archivos = request.FILES.getlist('imagenes_residente')
            cantidad_adjuntos, error_adjuntos = _guardar_adjuntos_preinforme(
                preinforme=preinforme,
                archivos=archivos,
                subido_por=request.user,
                origen='residente',
            )
            if error_adjuntos:
                messages.warning(request, f'Preinforme creado, pero hubo un problema al subir imágenes: {error_adjuntos}')
            elif cantidad_adjuntos:
                messages.success(request, f'Se adjuntaron {cantidad_adjuntos} imagen(es) al preinforme.')
            
            # Limpiar datos guardados en sesión
            if 'preinforme_form_data' in request.session:
                del request.session['preinforme_form_data']
            
            # Actualizar historial
            historial, created = HistorialEstudios.objects.get_or_create(residente=request.user)
            historial.actualizar_estadisticas()
            
            messages.success(request, 'Preinforme creado exitosamente.')
            
            if 'guardar_y_continuar' in request.POST:
                return redirect('preinformes:editar_preinforme', pk=preinforme.pk)
            elif 'guardar_y_enviar' in request.POST:
                preinforme.enviar_a_revision()
                _autoevaluar_sesion_mentor_al_enviar(
                    preinforme,
                    request.POST.get('asistente_conversacion_id') or None,
                )
                messages.success(request, 'Preinforme enviado para revisión.')
                return redirect('preinformes:dashboard_residente')
            else:
                return redirect('preinformes:dashboard_residente')
    else:
        # GET: Restaurar datos del formulario si existen en sesión
        initial_data = {}
        if 'preinforme_form_data' in request.session:
            saved_data = request.session['preinforme_form_data']
            # Restaurar solo los campos que queremos preservar
            fields_to_restore = [
                'numero_estudio', 'tipo_estudio', 'region', 'sistema_destino',
                'apellido_paciente', 'nombre_paciente', 'dni_paciente',
                'edad_paciente', 'sexo_paciente', 'fecha_estudio'
            ]
            for field in fields_to_restore:
                if field in saved_data and saved_data[field]:
                    initial_data[field] = saved_data[field]
        
        # Si viene de crear plantilla, cargar la plantilla en el formulario
        plantilla_id = request.GET.get('plantilla_id')
        if plantilla_id:
            try:
                plantilla = PlantillaPreinforme.objects.get(id=plantilla_id)
                initial_data['plantilla'] = plantilla.id
                messages.success(request, f'Plantilla "{plantilla.nombre}" cargada exitosamente.')
            except PlantillaPreinforme.DoesNotExist:
                pass
        
        form = PreinformeForm(initial=initial_data if initial_data else None, user=request.user)
    
    context = {
        'form': form,
        'adjuntos_residente': [],
        'adjuntos_revisor': [],
        'title': 'Nuevo Preinforme'
    }
    
    return render(request, 'preinformes/form_preinforme.html', context)


@login_required
@role_required('medico_residente', 'jefe_residentes', 'instructor_residentes')
def editar_preinforme(request, pk):
    """Editar preinforme existente (solo si está pendiente de revisión y es el creador)"""
    preinforme = get_object_or_404(Preinforme, pk=pk)
    if preinforme.residente != request.user:
        messages.error(request, 'No tiene permiso para editar este preinforme.')
        return redirect('preinformes:mis_preinformes')
    if preinforme.estado not in ['borrador', 'pendiente_revision']:
        messages.error(request, 'Solo puede editar preinformes en borrador o pendientes de revisión.')
        return redirect('preinformes:mis_preinformes')

    # Marcar como en edición al abrir el formulario
    if request.method == 'GET':
        preinforme.marcar_en_edicion(request.user)

    if request.method == 'POST':
        form = PreinformeForm(request.POST, instance=preinforme, user=request.user)
        if form.is_valid():
            form.save()

            ids_adjuntos_eliminar = request.POST.getlist('eliminar_adjuntos_residente')
            eliminados = _eliminar_adjuntos_residente(
                preinforme=preinforme,
                adjunto_ids=ids_adjuntos_eliminar,
                usuario=request.user,
            )
            if eliminados:
                messages.success(request, f'Se eliminaron {eliminados} imagen(es) cargadas previamente.')

            archivos = request.FILES.getlist('imagenes_residente')
            cantidad_adjuntos, error_adjuntos = _guardar_adjuntos_preinforme(
                preinforme=preinforme,
                archivos=archivos,
                subido_por=request.user,
                origen='residente',
            )

            if error_adjuntos:
                messages.warning(request, f'Preinforme actualizado, pero hubo un problema al subir imágenes: {error_adjuntos}')
            elif cantidad_adjuntos:
                messages.success(request, f'Se adjuntaron {cantidad_adjuntos} imagen(es).')

            messages.success(request, 'Preinforme actualizado exitosamente.')

            if 'guardar_y_continuar' in request.POST:
                preinforme.marcar_en_edicion(request.user)
                return redirect('preinformes:editar_preinforme', pk=preinforme.pk)
            elif 'guardar_y_enviar' in request.POST:
                preinforme.enviar_a_revision()
                _autoevaluar_sesion_mentor_al_enviar(
                    preinforme,
                    request.POST.get('asistente_conversacion_id') or None,
                )
                preinforme.liberar_edicion()
                messages.success(request, 'Preinforme enviado para revisión.')
                return redirect('preinformes:dashboard_residente')
            else:
                preinforme.liberar_edicion()
                return redirect('preinformes:dashboard_residente')
    else:
        form = PreinformeForm(instance=preinforme, user=request.user)

    context = {
        'form': form,
        'preinforme': preinforme,
        'adjuntos_residente': preinforme.adjuntos.filter(origen='residente', activo=True),
        'adjuntos_revisor': preinforme.adjuntos.filter(origen='revisor', activo=True),
        'title': 'Editar Preinforme'
    }

    return render(request, 'preinformes/form_preinforme.html', context)


@login_required
@role_required('medico_residente', 'jefe_residentes', 'instructor_residentes')
def mis_preinformes(request):
    """Lista de preinformes del residente"""
    form = FiltroPreinformesForm(request.GET)
    preinformes = Preinforme.objects.filter(residente=request.user)
    
    # Aplicar filtros
    if form.is_valid():
        if form.cleaned_data['estado']:
            preinformes = preinformes.filter(estado=form.cleaned_data['estado'])
        if form.cleaned_data['tipo_estudio']:
            preinformes = preinformes.filter(tipo_estudio=form.cleaned_data['tipo_estudio'])
        if form.cleaned_data['region']:
            preinformes = preinformes.filter(region=form.cleaned_data['region'])
        if form.cleaned_data['fecha_desde']:
            preinformes = preinformes.filter(fecha_creacion__date__gte=form.cleaned_data['fecha_desde'])
        if form.cleaned_data['fecha_hasta']:
            preinformes = preinformes.filter(fecha_creacion__date__lte=form.cleaned_data['fecha_hasta'])
        if form.cleaned_data['numero_estudio']:
            preinformes = preinformes.filter(numero_estudio__icontains=form.cleaned_data['numero_estudio'])
    
    # Filtro por etiquetas (parámetro GET)
    etiquetas_ids = request.GET.getlist('etiquetas')
    if etiquetas_ids:
        preinformes = preinformes.filter(etiquetas__id__in=etiquetas_ids).distinct()
    
    preinformes = preinformes.order_by('-fecha_creacion')
    
    # Paginación
    paginator = Paginator(preinformes, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Etiquetas disponibles para filtrar
    etiquetas_disponibles = EtiquetaPreinforme.objects.filter(
        preinformes__residente=request.user
    ).distinct().annotate(
        total=Count('preinformes')
    ).order_by('-total', 'nombre')
    
    context = {
        'page_obj': page_obj,
        'form': form,
        'etiquetas_disponibles': etiquetas_disponibles,
        'etiquetas_seleccionadas': [int(id) for id in etiquetas_ids],
        'title': 'Mis Preinformes'
    }
    
    return render(request, 'preinformes/mis_preinformes.html', context)


@login_required
@role_required('medico_residente', 'jefe_residentes', 'instructor_residentes')
def ver_preinforme(request, pk):
    """Ver detalle de preinforme con revisión si existe"""
    preinforme = get_object_or_404(Preinforme, pk=pk, residente=request.user)
    
    context = {
        'preinforme': preinforme,
        'adjuntos_residente': preinforme.adjuntos.filter(origen='residente', activo=True),
        'adjuntos_revisor': preinforme.adjuntos.filter(origen='revisor', activo=True),
        'title': f'Preinforme {preinforme.numero_estudio}'
    }
    
    return render(request, 'preinformes/ver_preinforme.html', context)


# === BANCO DE INFORMES (pool compartido de finalizados) ===

@login_required
@role_required('medico_residente', 'jefe_residentes', 'instructor_residentes')
def lista_banco_informes(request):
    """Lista de todos los preinformes finalizados del equipo residente.
    Permite que el residente A busque y copie el informe definitivo del residente B.
    No muestra datos de evaluación (puntuación, comentarios del revisor).
    """
    qs = Preinforme.objects.filter(
        estado='finalizado',
        residente__rol='medico_residente',
    ).select_related('residente', 'tipo_estudio', 'region', 'revision').order_by('-fecha_finalizacion')

    # Filtros GET
    q_numero = request.GET.get('numero_estudio', '').strip()
    q_paciente = request.GET.get('paciente', '').strip()
    q_tipo = request.GET.get('tipo_estudio', '')
    q_region = request.GET.get('region', '')

    if q_numero:
        qs = qs.filter(numero_estudio__icontains=q_numero)
    if q_paciente:
        qs = qs.filter(
            Q(apellido_paciente__icontains=q_paciente) |
            Q(nombre_paciente__icontains=q_paciente)
        )
    if q_tipo:
        qs = qs.filter(tipo_estudio_id=q_tipo)
    if q_region:
        qs = qs.filter(region_id=q_region)

    paginator = Paginator(qs, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    from .models import TipoEstudio, Region
    context = {
        'page_obj': page_obj,
        'tipos_estudio': TipoEstudio.objects.all().order_by('nombre'),
        'regiones': Region.objects.all().order_by('nombre'),
        'q_numero': q_numero,
        'q_paciente': q_paciente,
        'q_tipo': q_tipo,
        'q_region': q_region,
        'title': 'Banco de Informes',
    }
    return render(request, 'preinformes/lista_banco_informes.html', context)


@login_required
@role_required('medico_residente', 'jefe_residentes', 'instructor_residentes')
def ver_banco_preinforme(request, pk):
    """Vista limpia del informe final para el pool del equipo.
    Solo muestra el informe definitivo y el botón de copia.
    Sin datos de la evaluación (puntuación, comentarios al residente).
    """
    preinforme = get_object_or_404(
        Preinforme,
        pk=pk,
        estado='finalizado',
        residente__rol='medico_residente',
    )
    context = {
        'preinforme': preinforme,
        'title': f'Informe {preinforme.numero_estudio}',
    }
    return render(request, 'preinformes/ver_banco_preinforme.html', context)


# === VISTAS PARA STAFF ===

@login_required
@role_required('medico_staff', 'jefe_residentes', 'instructor_residentes', 'jefe_servicio')
def dashboard_staff(request):
    """Dashboard para médicos de staff"""
    # Preinformes asignados a mí (pendientes o en revisión)
    mis_asignados = get_asignados_de(request.user).count()
    
    # Preinformes sin asignar (pendientes de revisión sin revisor)
    pendientes_revision = get_pendientes_sin_revisor().count()
    
    # Preinformes en revisión por este usuario
    en_revision = Preinforme.objects.filter(
        estado='en_revision',
        revisor=request.user
    ).count()
    
    # Estadísticas generales
    total_preinformes_mes = Preinforme.objects.filter(
        fecha_creacion__month=timezone.now().month,
        fecha_creacion__year=timezone.now().year
    ).count()
    
    # Últimos preinformes asignados a mí
    mis_ultimos_asignados = get_asignados_de(request.user).order_by('-fecha_envio_revision')[:5]
    
    # Últimos preinformes pendientes sin asignar
    ultimos_pendientes = get_pendientes_sin_revisor().order_by('-fecha_envio_revision')[:5]
    
    context = {
        'mis_asignados': mis_asignados,
        'pendientes_revision': pendientes_revision,
        'en_revision': en_revision,
        'total_preinformes_mes': total_preinformes_mes,
        'mis_ultimos_asignados': mis_ultimos_asignados,
        'ultimos_pendientes': ultimos_pendientes,
    }
    
    return render(request, 'preinformes/dashboard_staff.html', context)


@login_required
@role_required('medico_staff', 'jefe_residentes', 'instructor_residentes', 'jefe_servicio')
def lista_revision(request):
    """Lista de preinformes para revisar"""
    form = FiltroPreinformesForm(request.GET)
    
    # Filtro para mostrar diferentes categorías
    mostrar = request.GET.get('mostrar', 'asignados')  # 'asignados', 'sin_asignar', 'compartidos', 'todos', 'finalizados'
    
    if mostrar == 'asignados':
        # Solo mis preinformes asignados
        preinformes = Preinforme.objects.filter(
            Q(revisor=request.user) & Q(estado__in=['pendiente_revision', 'en_revision'])
        )
    elif mostrar == 'sin_asignar':
        # Preinformes sin revisor asignado (excluir compartidos)
        preinformes = Preinforme.objects.filter(
            estado__in=['pendiente_revision', 'en_revision'],
            revisor__isnull=True,
            asignacion_compartida=False
        )
    elif mostrar == 'compartidos':
        # Pool compartido para jefes/instructores
        if request.user.rol in ['jefe_residentes', 'instructor_residentes']:
            preinformes = Preinforme.objects.filter(
                asignacion_compartida=True,
                revisor__isnull=True,
                estado__in=['pendiente_revision', 'en_revision']
            )
        else:
            # Si no tiene el rol adecuado, mostrar lista vacía
            preinformes = Preinforme.objects.none()
    elif mostrar == 'finalizados':
        # Preinformes que ya revisé y están finalizados (solo lectura)
        preinformes = Preinforme.objects.filter(
            revisor=request.user,
            estado='finalizado',
        ).select_related('revision', 'residente', 'tipo_estudio', 'region')
    else:
        # Todos: pendientes/en_revision sin asignar (excluir compartidos para staff), o asignados a mí
        base_filter = Q(estado__in=['pendiente_revision', 'en_revision'], revisor=request.user)
        
        # Para estudios sin asignar, depende del rol
        if request.user.rol in ['jefe_residentes', 'instructor_residentes']:
            # Jefes e instructores ven todos los sin asignar (incluidos compartidos)
            base_filter |= Q(estado__in=['pendiente_revision', 'en_revision'], revisor__isnull=True)
        else:
            # Staff solo ve sin asignar que NO sean compartidos
            base_filter |= Q(
                estado__in=['pendiente_revision', 'en_revision'], 
                revisor__isnull=True,
                asignacion_compartida=False
            )
        
        preinformes = Preinforme.objects.filter(base_filter)
    
    # Aplicar filtros
    if form.is_valid():
        if form.cleaned_data.get('estado'):
            preinformes = preinformes.filter(estado=form.cleaned_data['estado'])
        if form.cleaned_data.get('tipo_estudio'):
            preinformes = preinformes.filter(tipo_estudio=form.cleaned_data['tipo_estudio'])
        if form.cleaned_data.get('region'):
            preinformes = preinformes.filter(region=form.cleaned_data['region'])
        if form.cleaned_data.get('residente'):
            preinformes = preinformes.filter(residente=form.cleaned_data['residente'])
        if form.cleaned_data.get('fecha_desde'):
            preinformes = preinformes.filter(fecha_envio_revision__date__gte=form.cleaned_data['fecha_desde'])
        if form.cleaned_data.get('fecha_hasta'):
            preinformes = preinformes.filter(fecha_envio_revision__date__lte=form.cleaned_data['fecha_hasta'])
        if form.cleaned_data.get('numero_estudio'):
            preinformes = preinformes.filter(numero_estudio__icontains=form.cleaned_data['numero_estudio'])
    
    preinformes = preinformes.order_by('-fecha_envio_revision')
    
    # Paginación
    paginator = Paginator(preinformes, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'form': form,
        'title': 'Preinformes para Revisar',
        'mostrar': mostrar,  # Para debugging y preservar filtro
    }
    
    return render(request, 'preinformes/lista_revision.html', context)


@login_required
@role_required('medico_staff', 'jefe_residentes', 'instructor_residentes', 'jefe_servicio')
def asignar_revisor(request, pk):
    """Asignar un revisor a un preinforme (o asignarse a uno mismo)"""
    preinforme = get_object_or_404(Preinforme, pk=pk)
    
    # Obtener de dónde viene para redirigir correctamente
    mostrar = request.GET.get('mostrar', 'asignados')
    redirect_url = f"{reverse('preinformes:lista_revision')}?mostrar={mostrar}"
    
    # Solo se pueden asignar preinformes pendientes o en revisión
    if preinforme.estado not in ['pendiente_revision', 'en_revision']:
        messages.error(request, 'Solo se pueden asignar preinformes pendientes o en revisión.')
        return redirect(redirect_url)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'asignarme':
            # Asignarse a sí mismo
            preinforme.revisor = request.user
            preinforme.save()
            messages.success(request, f'Te asignaste el preinforme #{preinforme.numero_estudio}.')
        elif action == 'desasignar':
            # Desasignar el preinforme
            preinforme.revisor = None
            # Si estaba en revisión, volver a pendiente
            if preinforme.estado == 'en_revision':
                preinforme.estado = 'pendiente_revision'
            preinforme.save()
            messages.success(request, f'Desasignaste el preinforme #{preinforme.numero_estudio}.')
        else:
            # Asignar a otro usuario específico
            revisor_id = request.POST.get('revisor_id')
            if revisor_id:
                try:
                    revisor = User.objects.get(pk=revisor_id, rol__in=['medico_staff', 'jefe_residentes', 'instructor_residentes', 'jefe_servicio'])
                    preinforme.revisor = revisor
                    preinforme.save()
                    messages.success(request, f'Asignaste el preinforme #{preinforme.numero_estudio} a {revisor.get_full_name()}.')
                except User.DoesNotExist:
                    messages.error(request, 'Revisor no válido.')
    
    return redirect(redirect_url)


@login_required
@role_required('jefe_residentes', 'instructor_residentes')
@require_http_methods(["POST"])
def tomar_estudio(request, pk):
    """Tomar un estudio del pool compartido y asignarlo al usuario actual"""
    mostrar = request.GET.get('mostrar', 'compartidos')
    redirect_url = f"{reverse('preinformes:lista_revision')}?mostrar={mostrar}"
    
    try:
        # Usar transacción atómica con lock pesimista para evitar race conditions
        with transaction.atomic():
            # select_for_update bloquea la fila hasta que termine la transacción
            preinforme = Preinforme.objects.select_for_update().get(pk=pk)
            
            # Validar que el estudio puede ser tomado
            if not preinforme.puede_ser_tomado_por(request.user):
                messages.error(
                    request, 
                    'Este estudio no está disponible para tomar. '
                    'Puede que ya haya sido asignado a otro revisor.'
                )
                return redirect(redirect_url)
            
            # Asignar al usuario actual
            preinforme.revisor = request.user
            preinforme.asignacion_compartida = False  # Ya no está en el pool
            
            # Si está pendiente, cambiar a en_revision
            if preinforme.estado == 'pendiente_revision':
                preinforme.estado = 'en_revision'
                preinforme.fecha_inicio_revision = timezone.now()
            
            preinforme.save()
            
            messages.success(
                request, 
                f'Has tomado el estudio #{preinforme.numero_estudio} para revisión.'
            )
            
            # Redirigir directamente a la vista de revisión
            return redirect('preinformes:revisar_preinforme', pk=preinforme.pk)
            
    except Preinforme.DoesNotExist:
        messages.error(request, 'El estudio no existe.')
        return redirect(redirect_url)


@login_required
@role_required('medico_staff', 'jefe_residentes', 'instructor_residentes', 'jefe_servicio')
def revisar_preinforme(request, pk):
    """Revisar y corregir preinforme"""
    preinforme = get_object_or_404(
        Preinforme, 
        pk=pk,
        estado__in=['pendiente_revision', 'en_revision']
    )
    
    # Lógica de asignación automática
    if preinforme.estado == 'pendiente_revision':
        # Si está pendiente, iniciar revisión y asignar al usuario actual
        preinforme.iniciar_revision(request.user)
    elif preinforme.estado == 'en_revision':
        # Si está en revisión, verificar quién es el revisor
        if preinforme.revisor is None:
            # Sin revisor asignado → asignarse automáticamente
            preinforme.revisor = request.user
            preinforme.save(update_fields=['revisor'])
        elif preinforme.revisor != request.user:
            # Otro médico lo está revisando
            messages.error(
                request, 
                f'Este preinforme está siendo revisado por {preinforme.revisor.get_full_name()}.'
            )
            return redirect('preinformes:lista_revision')
    
    # Obtener o crear revisión
    revision, created = RevisionPreinforme.objects.get_or_create(
        preinforme=preinforme,
        defaults={'revisor': request.user}
    )
    
    # 1) Snapshot: congelar lo que envió el residente (una vez)
    if not revision.informe_residente_snapshot:
        revision.informe_residente_snapshot = preinforme.get_informe_html_or_legacy() or ""
        revision.save(update_fields=['informe_residente_snapshot'])
    
    # 2) Precarga del editor del staff (solo si todavía no editó)
    if not revision.informe_final_html:
        revision.informe_final_html = revision.informe_residente_snapshot
        revision.save(update_fields=['informe_final_html'])
    
    if request.method == 'POST':
        # Guardar y finalizar revisión
        form = RevisionPreinformeForm(request.POST, instance=revision, preinforme=preinforme)
        if form.is_valid():
            revision = form.save(commit=False)
            # El informe final ya está en informe_final_html, no necesitamos generar nada
            revision.save()

            archivos = request.FILES.getlist('imagenes_revisor')
            cantidad_adjuntos, error_adjuntos = _guardar_adjuntos_preinforme(
                preinforme=preinforme,
                archivos=archivos,
                subido_por=request.user,
                origen='revisor',
            )
            if error_adjuntos:
                messages.warning(request, f'Revisión guardada, pero hubo un problema al subir imágenes: {error_adjuntos}')
            elif cantidad_adjuntos:
                messages.success(request, f'Se adjuntaron {cantidad_adjuntos} imagen(es) de feedback.')
            
            if 'guardar_y_continuar' in request.POST:
                messages.success(request, 'Revisión guardada exitosamente.')
                return redirect('preinformes:revisar_preinforme', pk=pk)
            elif 'finalizar_revision' in request.POST:
                preinforme.finalizar_revision()
                # Actualizar historial del residente
                historial, _ = HistorialEstudios.objects.get_or_create(residente=preinforme.residente)
                historial.actualizar_estadisticas()
                messages.success(request, 'Revisión finalizada exitosamente.')
                return redirect('preinformes:lista_revision')
            else:
                messages.success(request, 'Revisión guardada exitosamente.')
                return redirect('preinformes:lista_revision')
    else:
        # GET: El form se crea con la instancia que ya tiene informe_final_html cargado
        form = RevisionPreinformeForm(instance=revision, preinforme=preinforme)
    
    context = {
        'form': form,
        'preinforme': preinforme,
        'revision': revision,
        'adjuntos_residente': preinforme.adjuntos.filter(origen='residente', activo=True),
        'adjuntos_revisor': preinforme.adjuntos.filter(origen='revisor', activo=True),
        'title': f'Revisar Preinforme {preinforme.numero_estudio}'
    }
    
    return render(request, 'preinformes/revisar_preinforme.html', context)


# === AUTOSAVE ===

@login_required
@require_http_methods(["POST"])
def autosave_revision(request, pk):
    """Guarda automáticamente el informe_final_html sin recargar la página"""
    try:
        # pk es el ID del preinforme, no de la revisión
        preinforme = get_object_or_404(
            Preinforme,
            pk=pk,
            estado__in=['pendiente_revision', 'en_revision']
        )
        
        # Obtener la revisión asociada
        revision = get_object_or_404(
            RevisionPreinforme,
            preinforme=preinforme,
            revisor=request.user
        )
        
        data = json.loads(request.body)
        informe_html = data.get('informe_final_html', '')
        
        if not informe_html:
            return JsonResponse({'success': False, 'error': 'Contenido vacío'}, status=400)
        
        # Guardar sin validaciones complejas
        revision.informe_final_html = informe_html
        revision.save(update_fields=['informe_final_html', 'fecha_modificacion'])
        
        return JsonResponse({
            'success': True,
            'message': 'Guardado automático exitoso',
            'timestamp': revision.fecha_modificacion.isoformat()
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


# === VISTAS AJAX ===

@login_required
def cargar_plantillas(request):
    """Cargar plantillas según tipo de estudio, región y sistema destino"""
    tipo_estudio_id = request.GET.get('tipo_estudio_id')
    region_id = request.GET.get('region_id')
    sistema_destino = request.GET.get('sistema_destino', 'eges')
    
    # Filtrar plantillas activas
    plantillas = PlantillaPreinforme.objects.filter(activa=True)
    
    # Filtrar por tipo y región si se proporcionan
    if tipo_estudio_id:
        plantillas = plantillas.filter(tipo_estudio_id=tipo_estudio_id)
    
    if region_id:
        plantillas = plantillas.filter(region_id=region_id)
    
    # Filtrar por sistema: mostrar plantillas del sistema específico o universales
    plantillas = plantillas.filter(
        Q(sistema_destino=sistema_destino) | Q(sistema_destino='universal')
    )
    
    # Filtrar según permisos:
    # - Plantillas públicas: todos las ven
    # - Plantillas borrador: solo el creador las ve
    if request.user.is_authenticated:
        plantillas = plantillas.filter(
            Q(estado='publica') | Q(creada_por=request.user)
        )
    else:
        plantillas = plantillas.filter(estado='publica')
    
    plantillas_data = [
        {
            'id': p.id, 
            'nombre': p.nombre,
            'contenido': p.contenido,
            'es_propia': p.creada_por == request.user if request.user.is_authenticated else False,
            'estado': p.estado,
            'sistema_destino': p.get_sistema_destino_display()
        } 
        for p in plantillas
    ]
    
    return JsonResponse({'plantillas': plantillas_data})


@login_required
def plantilla_json(request, pk):
    """Endpoint JSON para obtener una plantilla específica"""
    try:
        plantilla = PlantillaPreinforme.objects.get(pk=pk, activa=True)
        
        # Verificar permisos: pública o creada por el usuario
        if plantilla.estado != 'publica' and plantilla.creada_por != request.user:
            return JsonResponse({'error': 'No tienes permiso para acceder a esta plantilla'}, status=403)
        
        data = {
            'contenido': plantilla.contenido or '',
            'nombre': plantilla.nombre
        }
        
        return JsonResponse(data)
        
    except PlantillaPreinforme.DoesNotExist:
        return JsonResponse({'error': 'Plantilla no encontrada'}, status=404)


@login_required
@role_required('medico_residente', 'jefe_residentes', 'instructor_residentes')
def crear_plantilla_residente(request):
    """Vista para que residentes creen nuevas plantillas (página completa)"""
    # Obtener tipo_estudio y region desde GET o sesión
    tipo_estudio_id = request.GET.get('tipo_estudio') or request.session.get('plantilla_tipo_estudio')
    region_id = request.GET.get('region') or request.session.get('plantilla_region')
    
    # Validar que no sean strings "None" o valores inválidos
    if tipo_estudio_id in [None, '', 'None', 'null'] or region_id in [None, '', 'None', 'null']:
        messages.error(request, 'Debes seleccionar primero el tipo de estudio y región en el formulario de preinforme.')
        return redirect('preinformes:crear_preinforme')
    
    try:
        tipo_estudio = TipoEstudio.objects.get(id=tipo_estudio_id)
        region = Region.objects.get(id=region_id)
    except (TipoEstudio.DoesNotExist, Region.DoesNotExist, ValueError):
        messages.error(request, 'Tipo de estudio o región no válidos.')
        return redirect('preinformes:crear_preinforme')
    
    # Guardar en sesión para persistencia
    request.session['plantilla_tipo_estudio'] = tipo_estudio_id
    request.session['plantilla_region'] = region_id
    
    if request.method == 'POST':
        form = NuevaPlantillaResidenteForm(
            request.POST,
            tipo_estudio=tipo_estudio,
            region=region
        )
        
        if form.is_valid():
            nombre = form.cleaned_data['nombre']
            compartir = form.cleaned_data.get('compartir', False)
            sistema_destino = form.cleaned_data['sistema_destino']
            
            # Verificar duplicados según el tipo de plantilla
            if compartir:
                # Para plantillas públicas: NO permitir duplicados
                plantilla_existente = PlantillaPreinforme.objects.filter(
                    nombre__iexact=nombre,
                    tipo_estudio=tipo_estudio,
                    region=region,
                    estado='publica',
                    sistema_destino=sistema_destino
                ).first()
                
                if plantilla_existente:
                    messages.error(
                        request,
                        f'❌ Ya existe una plantilla pública con el nombre "{nombre}" '
                        f'para {tipo_estudio.nombre} - {region.nombre} ({sistema_destino}). '
                        f'No se pueden crear plantillas públicas duplicadas. '
                        f'Cambia el nombre o usa la plantilla existente creada por '
                        f'{plantilla_existente.creada_por.get_full_name() or plantilla_existente.creada_por.username}.'
                    )
                    context = {
                        'form': form,
                        'tipo_estudio': tipo_estudio,
                        'region': region,
                        'plantilla_existente': plantilla_existente,
                        'mostrar_advertencia': True
                    }
                    return render(request, 'preinformes/crear_plantilla.html', context)
            else:
                # Para plantillas privadas: solo advertir si el mismo usuario tiene una similar
                plantilla_similar = PlantillaPreinforme.objects.filter(
                    nombre__iexact=nombre,
                    tipo_estudio=tipo_estudio,
                    region=region,
                    creada_por=request.user,
                    estado='borrador',
                    sistema_destino=sistema_destino
                ).first()
                
                if plantilla_similar:
                    messages.info(
                        request,
                        f'ℹ️ Ya tienes una plantilla privada con el nombre "{nombre}" '
                        f'para {tipo_estudio.nombre} - {region.nombre}. '
                        f'Se creará esta nueva plantilla de todas formas.'
                    )
            
            # Crear la plantilla
            plantilla = form.save(commit=False)
            plantilla.tipo_estudio = tipo_estudio
            plantilla.region = region
            plantilla.creada_por = request.user
            plantilla.activa = True
            plantilla.estado = 'publica' if compartir else 'borrador'
            
            # Convertir saltos de línea a HTML si es necesario
            if plantilla.contenido:
                if not ('<p>' in plantilla.contenido or '<br>' in plantilla.contenido):
                    lines = plantilla.contenido.split('\n')
                    html_lines = []
                    for line in lines:
                        line = line.strip()
                        if line:
                            html_lines.append(f'<p>{line}</p>')
                    plantilla.contenido = ''.join(html_lines)
            
            # === LIMPIEZA DE HTML ANTES DE GUARDAR ===
            if plantilla.contenido:
                from preinformes.models import sanitize_center_alignment, normalize_html_content_soft
                from bs4 import BeautifulSoup
                
                # 1. Eliminar alineación centrada
                plantilla.contenido = sanitize_center_alignment(plantilla.contenido)
                
                # 2. Eliminar backgrounds (para evitar resaltados verdes/amarillos de Word)
                soup = BeautifulSoup(plantilla.contenido, 'html.parser')
                for tag in soup.find_all(True):
                    if tag.has_attr('style'):
                        style_parts = [s.strip() for s in tag['style'].split(';') if s.strip()]
                        cleaned_parts = [p for p in style_parts if not p.lower().startswith('background')]
                        
                        if cleaned_parts:
                            tag['style'] = '; '.join(cleaned_parts)
                        else:
                            del tag['style']
                
                plantilla.contenido = str(soup)
                
                # 3. Normalizar HTML de forma RESPETUOSA (preserva estructura original)
                plantilla.contenido = normalize_html_content_soft(plantilla.contenido)
            
            try:
                plantilla.save()
                
                messages.success(
                    request,
                    f'Plantilla "{plantilla.nombre}" creada exitosamente. ' +
                    ('Visible para todos.' if compartir else 'Solo visible para ti.')
                )
                
                # Redirigir al formulario de preinforme con la plantilla seleccionada
                return redirect(f"{reverse('preinformes:crear_preinforme')}?plantilla_id={plantilla.id}")
            
            except IntegrityError:
                # Ya existe una plantilla con el mismo nombre, tipo_estudio y región
                messages.error(
                    request,
                    f'Ya existe una plantilla con el nombre "{form.cleaned_data["nombre"]}" '
                    f'para {tipo_estudio.nombre} - {region.nombre}. '
                    f'Por favor, elige un nombre diferente.'
                )
                # Volver a renderizar el formulario con los datos ingresados
                return render(request, 'preinformes/crear_plantilla.html', {
                    'form': form,
                    'tipo_estudio': tipo_estudio,
                    'region': region,
                })
    else:
        form = NuevaPlantillaResidenteForm(
            tipo_estudio=tipo_estudio,
            region=region
        )
    
    context = {
        'form': form,
        'tipo_estudio': tipo_estudio,
        'region': region,
    }
    
    return render(request, 'preinformes/crear_plantilla.html', context)

@login_required
def autosave_preinforme(request, pk):
    """Endpoint para autoguardado de preinforme via AJAX"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    
    try:
        preinforme = get_object_or_404(
            Preinforme, 
            pk=pk, 
            residente=request.user,
            estado='borrador'
        )
        
        # Renovar marca de edición
        preinforme.marcar_en_edicion(request.user)
        
        # Obtener contenido del POST
        informe_html = request.POST.get('informe_html', '')
        
        # Guardar solo si hay cambios
        if preinforme.informe_html != informe_html:
            preinforme.informe_html = informe_html
            preinforme.save(update_fields=['informe_html'])
            return JsonResponse({
                'success': True, 
                'message': 'Preinforme guardado automáticamente',
                'timestamp': preinforme.fecha_modificacion.strftime('%H:%M:%S')
            })
        else:
            return JsonResponse({
                'success': True, 
                'message': 'Sin cambios para guardar',
                'timestamp': preinforme.fecha_modificacion.strftime('%H:%M:%S')
            })
            
    except Preinforme.DoesNotExist:
        return JsonResponse({'error': 'Preinforme no encontrado o no editable'}, status=404)
    except Exception as e:
        return JsonResponse({'error': f'Error al guardar: {str(e)}'}, status=500)


@login_required
def generar_informe_final(request, pk):
    """Obtener informe final actual de la revisión"""
    try:
        preinforme = get_object_or_404(Preinforme, pk=pk)
        
        # Verificar permisos
        if not (
            request.user == preinforme.revisor or
            request.user.rol in ['medico_staff', 'jefe_residentes', 'instructor_residentes', 'jefe_servicio']
        ):
            return JsonResponse({'error': 'Sin permisos para acceder a esta revisión'}, status=403)
        
        # Obtener la revisión
        revision = get_object_or_404(RevisionPreinforme, preinforme=preinforme)
        
        # Retornar el informe final actual (ya editado por el staff)
        informe_final = revision.informe_final_html or ''
        
        return JsonResponse({
            'success': True,
            'informe_final': informe_final
        })
        
    except Exception as e:
        return JsonResponse({'error': f'Error obteniendo informe: {str(e)}'}, status=500)


@login_required
def copiar_informe_final(request, pk):
    """Copiar informe final al portapapeles"""
    import re
    from bs4 import BeautifulSoup
    
    preinforme = get_object_or_404(Preinforme, pk=pk)
    
    # Verificar permisos
    if not (
        request.user == preinforme.residente or 
        request.user == preinforme.revisor or
        request.user.rol in ['medico_staff', 'jefe_residentes', 'instructor_residentes', 'jefe_servicio'] or
        # Banco de informes: cualquier residente puede copiar un informe finalizado de un compañero
        (request.user.rol == 'medico_residente' and preinforme.estado == 'finalizado')
    ):
        return JsonResponse({'error': 'Sin permisos para ver este informe'}, status=403)
    
    # Obtener HTML e informe final
    if hasattr(preinforme, 'revision') and preinforme.revision.informe_final_html:
        # HTML con formato desde la revisión finalizada
        informe_html_original = preinforme.revision.informe_final_html
    else:
        # Si no hay revisión, usar el preinforme original con método unificado
        informe_html_original = preinforme.get_informe_html_or_legacy()
    
    # Limpiar HTML solo de backgrounds (resaltado verde) - mantener todo lo demás fiel al guardado
    soup = BeautifulSoup(informe_html_original, 'html.parser')
    
    # Convertir <span style="color:..."> a <font color="..."> para compatibilidad con Word/EGES
    for span in soup.find_all('span'):
        if span.has_attr('style'):
            style = span['style']
            style_parts = [s.strip() for s in style.split(';') if s.strip()]
            
            color_value = None
            for part in style_parts:
                part_lower = part.lower()
                if part_lower.startswith('color:'):
                    color_value = part.split(':', 1)[1].strip()
                    break
            
            # Si tiene color, convertir a <font>
            if color_value:
                font_tag = soup.new_tag('font', color=color_value)
                font_tag.string = span.get_text()
                span.replace_with(font_tag)
    
    # Limpiar backgrounds de todos los tags
    for tag in soup.find_all(True):
        if tag.has_attr('style'):
            style = tag['style']
            style_parts = [s.strip() for s in style.split(';') if s.strip()]
            cleaned_parts = [p for p in style_parts if not p.lower().startswith('background')]
            
            if cleaned_parts:
                tag['style'] = '; '.join(cleaned_parts)
            else:
                del tag['style']
    
    informe_html = str(soup)
    
    # Convertir HTML a texto plano preservando saltos de línea
    from django.utils.html import strip_tags
    
    # Primero reemplazar etiquetas HTML con saltos de línea antes de eliminarlas
    texto_con_saltos = informe_html_original
    
    # Los </p> generan un salto simple (no doble para evitar mucho espacio)
    texto_con_saltos = texto_con_saltos.replace('</p>', '\n').replace('</P>', '\n')
    
    # Los <br> generan un salto simple
    texto_con_saltos = re.sub(r'<br\s*/?>', '\n', texto_con_saltos, flags=re.IGNORECASE)
    
    # Los </div> y otros bloques generan un salto
    texto_con_saltos = texto_con_saltos.replace('</div>', '\n').replace('</DIV>', '\n')
    
    # Los encabezados generan un salto simple
    texto_con_saltos = re.sub(r'</h[1-6]>', '\n', texto_con_saltos, flags=re.IGNORECASE)
    
    # Lista items generan salto
    texto_con_saltos = texto_con_saltos.replace('</li>', '\n').replace('</LI>', '\n')
    
    # Ahora eliminar todas las etiquetas HTML restantes
    informe_texto = strip_tags(texto_con_saltos)
    
    # Convertir entidades HTML (&nbsp;, &amp;, etc.) a texto real
    import html
    informe_texto = html.unescape(informe_texto)
    
    # Limpiar exceso de saltos (máximo 1 línea vacía entre párrafos)
    while '\n\n\n' in informe_texto:
        informe_texto = informe_texto.replace('\n\n\n', '\n\n')
    
    # Limpiar espacios y tabs al final
    informe_texto = informe_texto.strip()
    
    return JsonResponse({
        'informe_html': informe_html,
        'informe_texto': informe_texto,
        'sistema_destino': preinforme.sistema_destino,
        # Mantener compatibilidad con código antiguo
        'informe_final': informe_texto
    })


# === VISTAS DE ESTADÍSTICAS ===

@login_required
@role_required('jefe_residentes', 'instructor_residentes', 'jefe_servicio')
def estadisticas(request):
    """Estadísticas generales del sistema"""
    # Estadísticas por residente
    residentes_stats = User.objects.filter(
        rol='medico_residente'
    ).annotate(
        total_preinformes=Count('preinformes_realizados'),
        preinformes_finalizados=Count(
            'preinformes_realizados',
            filter=Q(preinformes_realizados__estado='finalizado')
        ),
        promedio_puntuacion=Avg('preinformes_realizados__revision__puntuacion'),
        promedio_scoring_ia=Avg(
            'conversaciones_asistente_preinforme__puntuacion_global',
            filter=Q(conversaciones_asistente_preinforme__evaluada=True)
        ),
    ).order_by('-total_preinformes')
    
    # Estadísticas por tipo de estudio
    estudios_stats = TipoEstudio.objects.annotate(
        total_preinformes=Count('preinforme')
    ).order_by('-total_preinformes')
    
    # Estadísticas temporales
    preinformes_mes_actual = Preinforme.objects.filter(
        fecha_creacion__month=timezone.now().month,
        fecha_creacion__year=timezone.now().year
    ).count()
    
    context = {
        'residentes_stats': residentes_stats,
        'estudios_stats': estudios_stats,
        'preinformes_mes_actual': preinformes_mes_actual,
        'title': 'Estadísticas del Sistema'
    }
    
    return render(request, 'preinformes/estadisticas.html', context)


@login_required
def panel_docencia(request):
    """
    Panel de actividad docente para administrativos del grupo 'Administrativo - Docencia'.
    Solo lectura — no expone contenido clínico de los informes.
    """
    if not (request.user.is_superuser or
            request.user.groups.filter(name='Administrativo - Docencia').exists()):
        messages.error(request, 'No tenés permisos para acceder a esta sección.')
        return redirect('home')

    residentes = User.objects.filter(
        rol='medico_residente',
        perfil_completo=True,
    ).annotate(
        total_preinformes=Count('preinformes_realizados', distinct=True),
        preinformes_finalizados=Count(
            'preinformes_realizados',
            filter=Q(preinformes_realizados__estado='finalizado'),
            distinct=True,
        ),
        preinformes_pendientes=Count(
            'preinformes_realizados',
            filter=Q(preinformes_realizados__estado__in=['borrador', 'pendiente_revision']),
            distinct=True,
        ),
        promedio_puntuacion=Avg('preinformes_realizados__revision__puntuacion'),
        promedio_ia=Avg(
            'conversaciones_asistente_preinforme__puntuacion_global',
            filter=Q(conversaciones_asistente_preinforme__evaluada=True),
        ),
        clases_subidas=Count('clases_creadas', distinct=True),
    ).order_by('anio_residencia', 'last_name', 'first_name')

    # Última actividad por residente (calculada en Python para compatibilidad con SQLite)
    ultima_actividad = {}
    for p in Preinforme.objects.filter(
        residente__in=residentes
    ).order_by('residente_id', '-fecha_modificacion'):
        if p.residente_id not in ultima_actividad:
            ultima_actividad[p.residente_id] = p.fecha_modificacion

    residentes_data = []
    for r in residentes:
        r.ultima_actividad = ultima_actividad.get(r.pk)
        if r.promedio_puntuacion:
            r.promedio_puntuacion = round(float(r.promedio_puntuacion), 1)
        if r.promedio_ia:
            r.promedio_ia = round(float(r.promedio_ia), 1)
        residentes_data.append(r)

    context = {
        'residentes': residentes_data,
        'total_residentes': len(residentes_data),
    }
    return render(request, 'preinformes/panel_docencia.html', context)


@login_required
def ver_comparacion_revision(request, pk):
    """Vista para que el residente vea la comparación entre su versión y la del staff"""
    preinforme = get_object_or_404(Preinforme, pk=pk)
    
    # Verificar permisos: solo el residente autor o staff puede ver
    if not (
        request.user == preinforme.residente or
        request.user.rol in ['medico_staff', 'jefe_residentes', 'instructor_residentes', 'jefe_servicio']
    ):
        messages.error(request, 'No tienes permisos para ver esta revisión.')
        return redirect('preinformes:mis_preinformes')
    
    # Verificar que existe la revisión
    if not hasattr(preinforme, 'revision'):
        messages.error(request, 'Este preinforme no ha sido revisado aún.')
        return redirect('preinformes:ver_preinforme', pk=pk)
    
    revision = preinforme.revision
    
    # Si no hay snapshot, crearlo ahora (retrocompatibilidad)
    if not revision.informe_residente_snapshot:
        revision.crear_snapshot_residente()
    
    # Determinar si quien ve es el residente autor o el staff revisor
    es_residente = (request.user == preinforme.residente)
    es_staff = request.user.rol in ['medico_staff', 'jefe_residentes', 'instructor_residentes', 'jefe_servicio']
    
    context = {
        'preinforme': preinforme,
        'revision': revision,
        'title': f'Comparación de Revisión - {preinforme.numero_estudio}',
        'es_residente': es_residente,
        'es_staff': es_staff,
    }
    
    return render(request, 'preinformes/comparacion_revision.html', context)


# === VISTAS PARA ETIQUETAS ===

@login_required
@require_http_methods(["POST"])
def agregar_etiquetas(request, pk):
    """Agregar etiquetas a un preinforme (AJAX)"""
    preinforme = get_object_or_404(Preinforme, pk=pk, residente=request.user)
    
    try:
        data = json.loads(request.body)
        etiquetas_nombres = data.get('etiquetas', [])
        
        if not isinstance(etiquetas_nombres, list):
            return JsonResponse({'success': False, 'error': 'Formato inválido'}, status=400)
        
        # Limpiar etiquetas existentes
        preinforme.etiquetas.clear()
        
        # Agregar las nuevas
        for nombre in etiquetas_nombres:
            nombre = nombre.strip()
            if nombre:
                # Obtener o crear etiqueta
                etiqueta, created = EtiquetaPreinforme.objects.get_or_create(
                    nombre__iexact=nombre,
                    defaults={
                        'nombre': nombre,
                        'creada_por': request.user
                    }
                )
                preinforme.etiquetas.add(etiqueta)
        
        # Devolver las etiquetas actualizadas
        etiquetas_actuales = list(preinforme.etiquetas.values('id', 'nombre', 'color'))
        
        return JsonResponse({
            'success': True,
            'etiquetas': etiquetas_actuales
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'JSON inválido'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
def buscar_etiquetas(request):
    """Buscar etiquetas para autocomplete (AJAX)"""
    query = request.GET.get('q', '').strip()
    
    if not query:
        # Devolver las más usadas
        etiquetas = EtiquetaPreinforme.objects.annotate(
            num_usos=Count('preinformes')
        ).order_by('-num_usos')[:10]
    else:
        # Buscar por nombre
        etiquetas = EtiquetaPreinforme.objects.filter(
            nombre__icontains=query
        ).order_by('nombre')[:10]
    
    resultados = [
        {'id': e.id, 'nombre': e.nombre, 'color': e.color}
        for e in etiquetas
    ]
    
    return JsonResponse({'etiquetas': resultados})


@login_required
def verificar_duplicado_preinforme(request):
    """Verificar si existe un preinforme duplicado (AJAX)"""
    numero_estudio = request.GET.get('numero_estudio', '').strip()
    dni_paciente = request.GET.get('dni_paciente', '').strip()
    tipo_estudio_id = request.GET.get('tipo_estudio')
    preinforme_actual_id = request.GET.get('preinforme_id')  # Para excluir en edición
    
    duplicados = []
    
    # Buscar por número de estudio (más preciso)
    if numero_estudio:
        query = Preinforme.objects.filter(numero_estudio__iexact=numero_estudio)
        
        # Excluir el preinforme actual si estamos editando
        if preinforme_actual_id:
            query = query.exclude(pk=preinforme_actual_id)
        
        for p in query.select_related('residente', 'tipo_estudio', 'region')[:5]:
            duplicados.append({
                'id': p.pk,
                'numero_estudio': p.numero_estudio,
                'paciente': f"{p.apellido_paciente}, {p.nombre_paciente}",
                'dni': p.dni_paciente,
                'tipo_estudio': p.tipo_estudio.nombre,
                'region': p.region.nombre,
                'estado': p.get_estado_display(),
                'estado_code': p.estado,
                'residente': f"{p.residente.first_name} {p.residente.last_name}",
                'fecha': p.fecha_creacion.strftime('%d/%m/%Y %H:%M'),
                'criterio': 'numero_estudio'
            })
    
    # Buscar por DNI + tipo de estudio similar (menos preciso pero útil)
    if dni_paciente and tipo_estudio_id and not duplicados:
        try:
            query = Preinforme.objects.filter(
                dni_paciente__iexact=dni_paciente,
                tipo_estudio_id=tipo_estudio_id
            )
            
            if preinforme_actual_id:
                query = query.exclude(pk=preinforme_actual_id)
            
            for p in query.select_related('residente', 'tipo_estudio', 'region')[:3]:
                duplicados.append({
                    'id': p.pk,
                    'numero_estudio': p.numero_estudio,
                    'paciente': f"{p.apellido_paciente}, {p.nombre_paciente}",
                    'dni': p.dni_paciente,
                    'tipo_estudio': p.tipo_estudio.nombre,
                    'region': p.region.nombre,
                    'estado': p.get_estado_display(),
                    'estado_code': p.estado,
                    'residente': f"{p.residente.first_name} {p.residente.last_name}",
                    'fecha': p.fecha_creacion.strftime('%d/%m/%Y %H:%M'),
                    'criterio': 'dni_tipo'
                })
        except (ValueError, TypeError):
            pass
    
    return JsonResponse({
        'duplicados': duplicados,
        'total': len(duplicados)
    })


# ======================================================================
# ASISTENTE IA RADIÓLOGO MENTOR
# ======================================================================

@login_required
@role_required('medico_residente', 'jefe_residentes', 'instructor_residentes')
@require_http_methods(["POST"])
def asistente_preinforme_chat(request):
    """
    Endpoint AJAX para el asistente IA de elaboración de preinformes.
    Recibe el mensaje del residente y el contexto del estudio actual.
    """
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'success': False, 'error': 'JSON inválido'}, status=400)

    mensaje = data.get('mensaje', '').strip()
    conversacion_id = data.get('conversacion_id')
    contexto_raw = data.get('contexto', {})

    if not mensaje:
        return JsonResponse({'success': False, 'error': 'El mensaje no puede estar vacío'}, status=400)

    if len(mensaje) > 500:
        return JsonResponse({'success': False, 'error': 'Mensaje demasiado largo (máx. 500 caracteres)'}, status=400)

    # Rate limiting: máximo 30 mensajes por hora por usuario
    cache_key = f'asistente_preinforme_rate_{request.user.id}'
    mensajes_enviados = cache.get(cache_key, 0)
    if mensajes_enviados >= 30:
        return JsonResponse({
            'success': False,
            'error': 'Alcanzaste el límite de 30 mensajes por hora. Intentá más tarde.'
        }, status=429)

    # Armar contexto seguro (nunca enviar nombre ni DNI)
    contexto_estudio = {
        'tipo_estudio': contexto_raw.get('tipo_estudio', ''),
        'region': contexto_raw.get('region', ''),
        'edad': contexto_raw.get('edad', ''),
        'sexo': contexto_raw.get('sexo', ''),
        'contenido_editor': contexto_raw.get('contenido_editor', ''),
    }

    from .asistente_service import AsistenteRadiologicoBot
    bot = AsistenteRadiologicoBot()
    resultado = bot.chat(
        usuario=request.user,
        mensaje=mensaje,
        conversacion_id=conversacion_id,
        contexto_estudio=contexto_estudio
    )

    # Incrementar rate limiting solo si el request fue válido
    cache.set(cache_key, mensajes_enviados + 1, 3600)

    if resultado['success']:
        return JsonResponse({
            'success': True,
            'respuesta': resultado['respuesta'],
            'conversacion_id': resultado['conversacion_id'],
            'mensaje_id': resultado.get('mensaje_id'),
        })
    else:
        return JsonResponse({'success': False, 'error': resultado['error']}, status=500)


@login_required
@require_http_methods(["POST"])
def asistente_preinforme_feedback(request):
    """
    Endpoint AJAX para registrar feedback (👍/👎) sobre respuestas del asistente.
    """
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'success': False, 'error': 'JSON inválido'}, status=400)

    mensaje_id = data.get('mensaje_id')
    feedback = data.get('feedback')

    if not mensaje_id or feedback not in ('positivo', 'negativo'):
        return JsonResponse({'success': False, 'error': 'Parámetros inválidos'}, status=400)

    from .models import MensajeAsistentePreinforme
    try:
        mensaje = MensajeAsistentePreinforme.objects.select_related(
            'conversacion'
        ).get(id=mensaje_id)
    except MensajeAsistentePreinforme.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Mensaje no encontrado'}, status=404)

    if mensaje.conversacion.usuario != request.user:
        return JsonResponse({'success': False, 'error': 'Sin permiso'}, status=403)

    if mensaje.rol != 'assistant':
        return JsonResponse({'success': False, 'error': 'Solo se puede valorar respuestas del asistente'}, status=400)

    mensaje.feedback = feedback
    mensaje.save(update_fields=['feedback'])

    return JsonResponse({'success': True})


@login_required
@role_required('medico_residente', 'jefe_residentes', 'instructor_residentes', 'jefe_servicio')
@require_http_methods(["POST"])
def asistente_preinforme_evaluar(request):
    """
    Endpoint AJAX para evaluar la calidad del razonamiento del residente.
    Exclusivo para roles docentes (jefe_residentes, instructor_residentes, jefe_servicio).
    Los médicos residentes no pueden disparar evaluaciones.
    """
    ROLES_DOCENTES = ('jefe_residentes', 'instructor_residentes', 'jefe_servicio')
    if not (request.user.is_superuser or request.user.rol in ROLES_DOCENTES):
        return JsonResponse({'success': False, 'error': 'Sin permiso'}, status=403)

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'success': False, 'error': 'JSON inválido'}, status=400)

    conversacion_id = data.get('conversacion_id')
    if not conversacion_id:
        return JsonResponse({'success': False, 'error': 'Falta conversacion_id'}, status=400)

    from .asistente_service import AsistenteRadiologicoBot
    bot = AsistenteRadiologicoBot()
    # La conversación pertenece al residente, no al docente que dispara la evaluación.
    resultado = bot.evaluar_conversacion(conversacion_id)

    if not resultado['success']:
        status_code = 400 if resultado.get('insufficient') else 500
        return JsonResponse(resultado, status=status_code)

    return JsonResponse(resultado)


@login_required
@role_required('medico_residente', 'jefe_residentes', 'instructor_residentes')
@require_http_methods(["POST"])
def asistente_analizar_borrador(request):
    """
    Endpoint AJAX para análisis proactivo del borrador del preinforme.
    La IA detecta problemas (terminología, ortografía, redundancias) y
    retorna un mensaje socrático si encuentra algo relevante.
    Rate limit: 1 llamada / 60s por usuario.
    """
    rate_key = f'analizar_borrador_{request.user.pk}'
    if cache.get(rate_key):
        return JsonResponse({'success': True, 'tiene_observacion': False, 'rate_limited': True})

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'success': False, 'error': 'JSON inválido'}, status=400)

    contenido_html = data.get('contenido_html', '')
    tipo_estudio = data.get('tipo_estudio', '')
    region = data.get('region', '')

    if not contenido_html or len(contenido_html.strip()) < 50:
        return JsonResponse({'success': True, 'tiene_observacion': False})

    cache.set(rate_key, True, timeout=60)

    from .asistente_service import AsistenteRadiologicoBot
    bot = AsistenteRadiologicoBot()
    resultado = bot.analizar_borrador(
        contenido_html=contenido_html,
        tipo_estudio=tipo_estudio,
        region=region,
    )
    return JsonResponse(resultado)


@login_required
def perfil_residente_docente(request, pk):
    """
    Perfil de un residente con historial de evaluaciones del Asistente IA.
    Accesible para roles docentes y el grupo 'Administrativo - Docencia'.
    """
    roles_docentes = ['jefe_residentes', 'instructor_residentes', 'jefe_servicio']
    es_admin_docencia = request.user.groups.filter(name='Administrativo - Docencia').exists()
    if not (request.user.is_superuser or
            request.user.rol in roles_docentes or
            es_admin_docencia):
        messages.error(request, 'No tenés permisos para acceder a esta sección.')
        return redirect('home')
    residente = get_object_or_404(User, pk=pk, rol='medico_residente')

    from .models import ConversacionAsistentePreinforme
    from django.db.models import Avg as _Avg

    conversaciones_evaluadas = ConversacionAsistentePreinforme.objects.filter(
        usuario=residente,
        evaluada=True,
    ).select_related('preinforme__tipo_estudio', 'preinforme__region').order_by('-fecha_actualizacion')

    promedio_scoring = conversaciones_evaluadas.aggregate(
        promedio=_Avg('puntuacion_global')
    )['promedio']
    if promedio_scoring is not None:
        promedio_scoring = round(promedio_scoring, 1)

    # Promedios por dimensión (calculados en Python desde el JSONField)
    dims_acum = {'razonamiento_clinico': [], 'terminologia': [], 'autonomia': [], 'receptividad': []}
    for conv in conversaciones_evaluadas:
        ev = conv.evaluacion_ia or {}
        for dim in dims_acum:
            val = ev.get(dim)
            if isinstance(val, (int, float)):
                dims_acum[dim].append(val)

    promedios_dims = {
        dim: round(sum(vals) / len(vals), 1) if vals else None
        for dim, vals in dims_acum.items()
    }

    historial = HistorialEstudios.objects.filter(residente=residente).first()

    context = {
        'residente': residente,
        'conversaciones_evaluadas': conversaciones_evaluadas,
        'promedio_scoring': promedio_scoring,
        'promedios_dims': promedios_dims,
        'historial': historial,
    }
    return render(request, 'preinformes/perfil_residente_docente.html', context)


# ─────────────────────────────────────────────────────────────────────────────
# ENCUESTA CADI 2026
# ─────────────────────────────────────────────────────────────────────────────

@login_required
@role_required('medico_residente', 'jefe_residentes', 'instructor_residentes')
def encuesta_uso(request):
    """Formulario de encuesta de experiencia para residentes. Una sola vez por residente."""
    # Si ya respondió, redirigir a su dashboard
    if EncuestaResidente.objects.filter(residente=request.user).exists():
        messages.info(request, 'Ya completaste la encuesta. ¡Gracias por tu participación!')
        return redirect('preinformes:dashboard_residente')

    PREGUNTAS_LIKERT = [
        ('p1_usabilidad',       'El sistema es fácil de usar'),
        ('p2_acceso',           'Acceder desde mi dispositivo es cómodo'),
        ('p3_feedback_util',    'Los comentarios del staff fueron útiles para mi aprendizaje'),
        ('p4_feedback_oportuno','El feedback fue oportuno (llegó en tiempo razonable)'),
        ('p5_mejora_redaccion', 'Siento que mejoré mi redacción de informes usando el sistema'),
        ('p6_banco_informes',   'El banco de informes me ayudó como referencia'),
        ('p7_comparacion',      'Comparando con lo que describiste arriba, este sistema mejoró mi proceso de trabajo'),
        ('p8_ia_asistente',     'El asistente IA (Radiólogo Mentor) fue útil'),
        ('p9_supervision',      'La supervisión del staff se volvió más estructurada'),
        ('p10_recomendacion',   'Recomendaría este sistema a otros servicios de residencia'),
    ]

    if request.method == 'POST':
        errores = []
        datos = {}

        # Validar Likert (1-5)
        for campo, _ in PREGUNTAS_LIKERT:
            if campo == 'p7_comparacion':
                continue  # se valida por separado después de la abierta
            val = request.POST.get(campo)
            if not val or not val.isdigit() or not (1 <= int(val) <= 5):
                errores.append(f"Respondé la pregunta requerida ({campo}).")
            else:
                datos[campo] = int(val)

        # p7 comparación
        val7 = request.POST.get('p7_comparacion')
        if not val7 or not val7.isdigit() or not (1 <= int(val7) <= 5):
            errores.append("Respondé la pregunta de comparación.")
        else:
            datos['p7_comparacion'] = int(val7)

        # Campos abiertos (no obligatorios)
        datos['p_contexto_previo'] = request.POST.get('p_contexto_previo', '').strip()
        datos['p_util']   = request.POST.get('p_util', '').strip()
        datos['p_mejora'] = request.POST.get('p_mejora', '').strip()
        datos['anonimizar'] = request.POST.get('anonimizar') == 'on'

        if errores:
            messages.error(request, 'Por favor completá todas las preguntas obligatorias.')
            return render(request, 'preinformes/encuesta_uso.html', {
                'preguntas_likert': PREGUNTAS_LIKERT,
                'post_data': request.POST,
            })

        EncuestaResidente.objects.create(residente=request.user, **datos)
        messages.success(request, '¡Gracias por completar la encuesta! Tu opinión es muy valiosa.')
        return redirect('preinformes:dashboard_residente')

    return render(request, 'preinformes/encuesta_uso.html', {
        'preguntas_likert': PREGUNTAS_LIKERT,
        'post_data': {},
    })


@login_required
def resultados_encuesta(request):
    """Panel de resultados de la encuesta — visible para staff y superusuarios."""
    from django.db.models import Avg
    from dictado_informes.ai_services import ai_service

    if not (request.user.is_superuser or request.user.rol in [
        'medico_staff', 'jefe_residentes', 'instructor_residentes', 'jefe_servicio'
    ]):
        messages.error(request, 'No tenés permisos para ver esta sección.')
        return redirect('preinformes:dashboard_residente')

    encuestas = EncuestaResidente.objects.select_related('residente').all()
    n = encuestas.count()

    if n == 0:
        return render(request, 'preinformes/resultados_encuesta.html', {
            'n': 0, 'promedios': {}, 'encuestas': [], 'analisis_ia': None
        })

    # Calcular promedios
    agg = encuestas.aggregate(
        p1=Avg('p1_usabilidad'), p2=Avg('p2_acceso'),
        p3=Avg('p3_feedback_util'), p4=Avg('p4_feedback_oportuno'),
        p5=Avg('p5_mejora_redaccion'), p6=Avg('p6_banco_informes'),
        p7=Avg('p7_comparacion'), p8=Avg('p8_ia_asistente'),
        p9=Avg('p9_supervision'), p10=Avg('p10_recomendacion'),
    )
    promedios = {k: round(v, 2) if v else 0 for k, v in agg.items()}
    promedio_global = round(sum(promedios.values()) / len(promedios), 2)

    # Respuestas abiertas (se anonimiza el nombre si el residente lo pidió)
    def get_abiertas(campo):
        return [
            getattr(e, campo)
            for e in encuestas
            if getattr(e, campo, '').strip()
        ]

    respuestas_abiertas = {
        'contexto_previo': get_abiertas('p_contexto_previo'),
        'util':   get_abiertas('p_util'),
        'mejora': get_abiertas('p_mejora'),
    }

    analisis_ia = None
    regenerar = request.GET.get('regenerar') == '1'

    if regenerar or request.method == 'POST':
        datos_para_ia = {
            'n_respuestas': n,
            'promedios': promedios,
            'promedio_global': promedio_global,
            'respuestas_abiertas': respuestas_abiertas,
        }
        analisis_ia = ai_service.analizar_resultados_encuesta(datos_para_ia)
        # Normalizar etiquetas de hallazgos para el template
        _LABELS_HALLAZGOS = {
            'usabilidad': 'Usabilidad',
            'feedback': 'Feedback del staff',
            'aprendizaje': 'Aprendizaje',
            'comparacion': 'Comparación',
            'ia_y_supervision': 'IA y Supervisión',
            'recomendacion': 'Recomendación',
        }
        if analisis_ia and 'error' not in analisis_ia and 'hallazgos_por_dimension' in analisis_ia:
            analisis_ia['hallazgos_por_dimension'] = {
                _LABELS_HALLAZGOS.get(k, k.replace('_', ' ').title()): v
                for k, v in analisis_ia['hallazgos_por_dimension'].items()
            }
        # Guardar en la última encuesta (referencia global)
        if analisis_ia and 'error' not in analisis_ia:
            encuestas.last().encuesta_set if False else None  # no-op
            # Guardamos en la propia instancia del modelo para persistencia
            EncuestaResidente.objects.filter(pk=encuestas.last().pk).update(analisis_ia=analisis_ia)

    # Tabla de respuestas individuales (respetando anonimato)
    tabla = []
    for e in encuestas:
        tabla.append({
            'nombre': 'Anónimo' if e.anonimizar else e.residente.get_full_name(),
            'anio': getattr(e.residente, 'anio_residencia', '—'),
            'promedio': round(e.promedio_likert, 2),
            'fecha': e.fecha_respuesta,
        })

    LABELS = {
        'p1': 'Usabilidad general',
        'p2': 'Comodidad de acceso',
        'p3': 'Utilidad del feedback del staff',
        'p4': 'Oportunidad del feedback',
        'p5': 'Mejora en redacción de informes',
        'p6': 'Banco de informes como referencia',
        'p7': 'Mejora respecto al método anterior',
        'p8': 'Utilidad del asistente IA',
        'p9': 'Supervisión más estructurada',
        'p10': 'Recomendaría a otros servicios',
    }
    promedios_lista = [(LABELS.get(k, k), k, v) for k, v in promedios.items()]

    context = {
        'n': n,
        'promedios': promedios,
        'promedios_lista': promedios_lista,
        'promedio_global': promedio_global,
        'tabla': tabla,
        'analisis_ia': analisis_ia,
        'respuestas_abiertas': respuestas_abiertas,
    }
    return render(request, 'preinformes/resultados_encuesta.html', context)