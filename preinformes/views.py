from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import models
from django.http import JsonResponse, HttpResponse
from django.urls import reverse
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Q, Count, Avg
from django.contrib.auth import get_user_model

from accounts.decorators import role_required
from .models import (
    Preinforme, TipoEstudio, Region, PlantillaPreinforme, 
    RevisionPreinforme, HistorialEstudios
)
from .forms import (
    PreinformeForm, FiltroPreinformesForm, 
    RevisionPreinformeForm, PlantillaPreinformeForm
)

User = get_user_model()


# === VISTAS PARA RESIDENTES ===

@login_required
@role_required('medico_residente', 'jefe_residentes')
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
    
    context = {
        'historial': historial,
        'preinformes_pendientes': preinformes_pendientes,
        'preinformes_en_revision': preinformes_en_revision,
        'ultimos_preinformes': ultimos_preinformes,
    }
    
    return render(request, 'preinformes/dashboard_residente.html', context)


@login_required
@role_required('medico_residente', 'jefe_residentes')
def crear_preinforme(request):
    """Crear un nuevo preinforme"""
    if request.method == 'POST':
        form = PreinformeForm(request.POST)
        if form.is_valid():
            preinforme = form.save(commit=False)
            preinforme.residente = request.user
            preinforme.save()
            
            # Actualizar historial
            historial, created = HistorialEstudios.objects.get_or_create(residente=request.user)
            historial.actualizar_estadisticas()
            
            messages.success(request, 'Preinforme creado exitosamente.')
            
            if 'guardar_y_continuar' in request.POST:
                return redirect('preinformes:editar_preinforme', pk=preinforme.pk)
            elif 'guardar_y_enviar' in request.POST:
                preinforme.enviar_a_revision()
                messages.success(request, 'Preinforme enviado para revisión.')
                return redirect('preinformes:dashboard_residente')
            else:
                return redirect('preinformes:dashboard_residente')
    else:
        form = PreinformeForm()
    
    context = {
        'form': form,
        'title': 'Nuevo Preinforme'
    }
    
    return render(request, 'preinformes/form_preinforme.html', context)


@login_required
@role_required('medico_residente', 'jefe_residentes')
def editar_preinforme(request, pk):
    """Editar preinforme existente (solo en borrador)"""
    preinforme = get_object_or_404(
        Preinforme, 
        pk=pk, 
        residente=request.user,
        estado='borrador'
    )
    
    if request.method == 'POST':
        form = PreinformeForm(request.POST, instance=preinforme)
        if form.is_valid():
            form.save()
            messages.success(request, 'Preinforme actualizado exitosamente.')
            
            if 'guardar_y_continuar' in request.POST:
                return redirect('preinformes:editar_preinforme', pk=preinforme.pk)
            elif 'guardar_y_enviar' in request.POST:
                preinforme.enviar_a_revision()
                messages.success(request, 'Preinforme enviado para revisión.')
                return redirect('preinformes:dashboard_residente')
            else:
                return redirect('preinformes:dashboard_residente')
    else:
        form = PreinformeForm(instance=preinforme)
    
    context = {
        'form': form,
        'preinforme': preinforme,
        'title': 'Editar Preinforme'
    }
    
    return render(request, 'preinformes/form_preinforme.html', context)


@login_required
@role_required('medico_residente', 'jefe_residentes')
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
    
    preinformes = preinformes.order_by('-fecha_creacion')
    
    # Paginación
    paginator = Paginator(preinformes, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'form': form,
        'title': 'Mis Preinformes'
    }
    
    return render(request, 'preinformes/mis_preinformes.html', context)


@login_required
@role_required('medico_residente', 'jefe_residentes')
def ver_preinforme(request, pk):
    """Ver detalle de preinforme con revisión si existe"""
    preinforme = get_object_or_404(Preinforme, pk=pk, residente=request.user)
    
    context = {
        'preinforme': preinforme,
        'title': f'Preinforme {preinforme.numero_estudio}'
    }
    
    return render(request, 'preinformes/ver_preinforme.html', context)


# === VISTAS PARA STAFF ===

@login_required
@role_required('medico_staff', 'jefe_residentes', 'instructor_residentes', 'jefe_servicio')
def dashboard_staff(request):
    """Dashboard para médicos de staff"""
    # Preinformes pendientes de revisión
    pendientes_revision = Preinforme.objects.filter(
        estado='pendiente_revision'
    ).count()
    
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
    
    # Últimos preinformes pendientes
    ultimos_pendientes = Preinforme.objects.filter(
        estado='pendiente_revision'
    ).order_by('-fecha_envio_revision')[:5]
    
    context = {
        'pendientes_revision': pendientes_revision,
        'en_revision': en_revision,
        'total_preinformes_mes': total_preinformes_mes,
        'ultimos_pendientes': ultimos_pendientes,
    }
    
    return render(request, 'preinformes/dashboard_staff.html', context)


@login_required
@role_required('medico_staff', 'jefe_residentes', 'instructor_residentes', 'jefe_servicio')
def lista_revision(request):
    """Lista de preinformes para revisar"""
    form = FiltroPreinformesForm(request.GET)
    
    # Solo preinformes pendientes o en revisión por este usuario
    preinformes = Preinforme.objects.filter(
        Q(estado='pendiente_revision') | 
        Q(estado='en_revision', revisor=request.user)
    )
    
    # Aplicar filtros (eliminar residente del form para staff)
    if form.is_valid():
        if form.cleaned_data['estado']:
            preinformes = preinformes.filter(estado=form.cleaned_data['estado'])
        if form.cleaned_data['tipo_estudio']:
            preinformes = preinformes.filter(tipo_estudio=form.cleaned_data['tipo_estudio'])
        if form.cleaned_data['region']:
            preinformes = preinformes.filter(region=form.cleaned_data['region'])
        if form.cleaned_data['residente']:
            preinformes = preinformes.filter(residente=form.cleaned_data['residente'])
        if form.cleaned_data['fecha_desde']:
            preinformes = preinformes.filter(fecha_envio_revision__date__gte=form.cleaned_data['fecha_desde'])
        if form.cleaned_data['fecha_hasta']:
            preinformes = preinformes.filter(fecha_envio_revision__date__lte=form.cleaned_data['fecha_hasta'])
        if form.cleaned_data['numero_estudio']:
            preinformes = preinformes.filter(numero_estudio__icontains=form.cleaned_data['numero_estudio'])
    
    preinformes = preinformes.order_by('-fecha_envio_revision')
    
    # Paginación
    paginator = Paginator(preinformes, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'form': form,
        'title': 'Preinformes para Revisar'
    }
    
    return render(request, 'preinformes/lista_revision.html', context)


@login_required
@role_required('medico_staff', 'jefe_residentes', 'instructor_residentes', 'jefe_servicio')
def revisar_preinforme(request, pk):
    """Revisar y corregir preinforme"""
    preinforme = get_object_or_404(
        Preinforme, 
        pk=pk,
        estado__in=['pendiente_revision', 'en_revision']
    )
    
    # Si está pendiente, iniciar revisión
    if preinforme.estado == 'pendiente_revision':
        preinforme.iniciar_revision(request.user)
    
    # Verificar que este usuario es el revisor
    if preinforme.estado == 'en_revision' and preinforme.revisor != request.user:
        messages.error(request, 'Este preinforme está siendo revisado por otro médico.')
        return redirect('preinformes:lista_revision')
    
    # Obtener o crear revisión
    revision, created = RevisionPreinforme.objects.get_or_create(
        preinforme=preinforme,
        defaults={'revisor': request.user}
    )
    
    # CRÍTICO: Asegurar que snapshot existe SIEMPRE
    if not revision.informe_residente_snapshot:
        revision.crear_snapshot_residente()
    
    # CRÍTICO: Pre-cargar informe_final_html si está vacío
    # Esto debe hacerse ANTES de crear el form para que aparezca en el editor
    if not revision.informe_final_html:
        revision.informe_final_html = revision.informe_residente_snapshot or revision.generar_informe_original_residente()
        revision.save()
    
    if request.method == 'POST':
        form = RevisionPreinformeForm(request.POST, instance=revision, preinforme=preinforme)
        if form.is_valid():
            revision = form.save(commit=False)
            # El informe final ya está en informe_final_html, no necesitamos generar nada
            revision.save()
            
            if 'guardar_y_continuar' in request.POST:
                messages.success(request, 'Revisión guardada exitosamente.')
                return redirect('preinformes:revisar_preinforme', pk=pk)
            elif 'finalizar_revision' in request.POST:
                preinforme.finalizar_revision()
                # Actualizar historial del residente
                historial, _ = HistorialEstudios.objects.get_or_create(residente=preinforme.residente)
                historial.actualizar_estadisticas()
                messages.success(request, 'Revisión finalizada exitosamente.')
                return redirect('preinformes:dashboard_staff')
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
        'title': f'Revisar Preinforme {preinforme.numero_estudio}'
    }
    
    return render(request, 'preinformes/revisar_preinforme.html', context)


# === VISTAS AJAX ===

@login_required
def cargar_plantillas(request):
    """Cargar plantillas según tipo de estudio y región"""
    tipo_estudio_id = request.GET.get('tipo_estudio_id')
    region_id = request.GET.get('region_id')
    
    plantillas = PlantillaPreinforme.objects.filter(activa=True)
    
    if tipo_estudio_id:
        plantillas = plantillas.filter(tipo_estudio_id=tipo_estudio_id)
    
    if region_id:
        plantillas = plantillas.filter(region_id=region_id)
    
    plantillas_data = [
        {
            'id': p.id, 
            'nombre': p.nombre,
            'contenido': p.contenido
        } 
        for p in plantillas
    ]
    
    return JsonResponse({'plantillas': plantillas_data})


@login_required
def plantilla_json(request, pk):
    """Endpoint JSON para obtener una plantilla específica con campos separados"""
    try:
        plantilla = PlantillaPreinforme.objects.get(pk=pk, activa=True)
        
        data = {
            'tecnica': plantilla.tecnica_template or '',
            'hallazgos': plantilla.hallazgos_template or '',
            'conclusion': plantilla.conclusion_template or '',
            'nombre': plantilla.nombre
        }
        
        return JsonResponse(data)
        
    except PlantillaPreinforme.DoesNotExist:
        return JsonResponse({'error': 'Plantilla no encontrada'}, status=404)


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
        
        # Obtener datos del POST
        tecnica = request.POST.get('tecnica', '')
        hallazgos = request.POST.get('hallazgos', '')
        conclusion = request.POST.get('conclusion', '')
        
        # Guardar solo si hay cambios
        cambios = False
        if preinforme.tecnica != tecnica:
            preinforme.tecnica = tecnica
            cambios = True
        if preinforme.hallazgos != hallazgos:
            preinforme.hallazgos = hallazgos
            cambios = True
        if preinforme.conclusion != conclusion:
            preinforme.conclusion = conclusion
            cambios = True
        
        if cambios:
            preinforme.save(update_fields=['tecnica', 'hallazgos', 'conclusion'])
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
    preinforme = get_object_or_404(Preinforme, pk=pk)
    
    # Verificar permisos
    if not (
        request.user == preinforme.residente or 
        request.user == preinforme.revisor or
        request.user.rol in ['medico_staff', 'jefe_residentes', 'instructor_residentes', 'jefe_servicio']
    ):
        return JsonResponse({'error': 'Sin permisos para ver este informe'}, status=403)
    
    # Obtener HTML e informe final
    if hasattr(preinforme, 'revision') and preinforme.revision.informe_final_html:
        # HTML con formato
        informe_html = preinforme.revision.informe_final_html
        # Texto plano como fallback
        from django.utils.html import strip_tags
        informe_texto = strip_tags(informe_html)
    else:
        # Si no hay revisión, usar el preinforme original
        tecnica_html = preinforme.tecnica
        hallazgos_html = preinforme.hallazgos
        conclusion_html = preinforme.conclusion
        
        informe_html = f"""
<h3>TÉCNICA</h3>
{tecnica_html}

<h3>HALLAZGOS</h3>
{hallazgos_html}

<h3>CONCLUSIÓN</h3>
{conclusion_html}
        """.strip()
        
        from django.utils.html import strip_tags
        informe_texto = f"""TÉCNICA:
{strip_tags(tecnica_html)}

HALLAZGOS:
{strip_tags(hallazgos_html)}

CONCLUSIÓN:
{strip_tags(conclusion_html)}"""
    
    return JsonResponse({
        'informe_html': informe_html,
        'informe_texto': informe_texto,
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
        promedio_puntuacion=Avg('preinformes_realizados__revision__puntuacion')
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


def test_tinymce(request):
    """Vista de prueba para TinyMCE"""
    return render(request, 'preinformes/test_tinymce.html')


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
    
    context = {
        'preinforme': preinforme,
        'revision': revision,
        'title': f'Comparación de Revisión - {preinforme.numero_estudio}'
    }
    
    return render(request, 'preinformes/comparacion_revision.html', context)