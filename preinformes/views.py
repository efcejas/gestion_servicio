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
from django.views.decorators.http import require_http_methods
import json

from accounts.decorators import role_required
from .models import (
    Preinforme, TipoEstudio, Region, PlantillaPreinforme, 
    RevisionPreinforme, HistorialEstudios, EtiquetaPreinforme
)
from .forms import (
    PreinformeForm, FiltroPreinformesForm, 
    RevisionPreinformeForm, PlantillaPreinformeForm,
    NuevaPlantillaResidenteForm
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
    
    # Preinformes en edición activa (por cualquier residente)
    tiempo_limite = timezone.now() - timezone.timedelta(minutes=15)
    preinformes_en_edicion = Preinforme.objects.filter(
        en_edicion_por__isnull=False,
        ultima_actividad_edicion__gt=tiempo_limite,
        estado__in=['borrador', 'pendiente_revision', 'en_revision']  # Incluir más estados
    ).exclude(
        en_edicion_por=request.user  # Excluir los propios del usuario
    ).select_related('en_edicion_por', 'tipo_estudio', 'revisor').order_by('-ultima_actividad_edicion')
    
    context = {
        'historial': historial,
        'preinformes_pendientes': preinformes_pendientes,
        'preinformes_en_revision': preinformes_en_revision,
        'ultimos_preinformes': ultimos_preinformes,
        'preinformes_en_edicion': preinformes_en_edicion,
    }
    
    return render(request, 'preinformes/dashboard_residente.html', context)


@login_required
@role_required('medico_residente', 'jefe_residentes')
def crear_preinforme(request):
    """Crear un nuevo preinforme"""
    if request.method == 'POST':
        # Guardar datos del formulario en sesión antes de procesar
        if 'crear_plantilla' in request.POST:
            # Usuario quiere crear una plantilla nueva
            request.session['preinforme_form_data'] = request.POST.dict()
            tipo_estudio = request.POST.get('tipo_estudio')
            region = request.POST.get('region')
            return redirect(f"{reverse('preinformes:crear_plantilla_residente')}?tipo_estudio={tipo_estudio}&region={region}")
        
        form = PreinformeForm(request.POST)
        if form.is_valid():
            preinforme = form.save(commit=False)
            preinforme.residente = request.user
            preinforme.save()
            
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
        
        form = PreinformeForm(initial=initial_data if initial_data else None)
    
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
    
    # Marcar como en edición al abrir el formulario
    if request.method == 'GET':
        preinforme.marcar_en_edicion(request.user)
    
    if request.method == 'POST':
        form = PreinformeForm(request.POST, instance=preinforme)
        if form.is_valid():
            form.save()
            messages.success(request, 'Preinforme actualizado exitosamente.')
            
            if 'guardar_y_continuar' in request.POST:
                # Renovar marca de edición
                preinforme.marcar_en_edicion(request.user)
                return redirect('preinformes:editar_preinforme', pk=preinforme.pk)
            elif 'guardar_y_enviar' in request.POST:
                preinforme.enviar_a_revision()
                preinforme.liberar_edicion()
                messages.success(request, 'Preinforme enviado para revisión.')
                return redirect('preinformes:dashboard_residente')
            else:
                preinforme.liberar_edicion()
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
@role_required('medico_residente', 'jefe_residentes')
def crear_plantilla_residente(request):
    """Vista para que residentes creen nuevas plantillas (página completa)"""
    # Obtener tipo_estudio y region desde GET o sesión
    tipo_estudio_id = request.GET.get('tipo_estudio') or request.session.get('plantilla_tipo_estudio')
    region_id = request.GET.get('region') or request.session.get('plantilla_region')
    
    if not tipo_estudio_id or not region_id:
        messages.error(request, 'Debes seleccionar primero el tipo de estudio y región en el formulario de preinforme.')
        return redirect('preinformes:crear_preinforme')
    
    try:
        tipo_estudio = TipoEstudio.objects.get(id=tipo_estudio_id)
        region = Region.objects.get(id=region_id)
    except (TipoEstudio.DoesNotExist, Region.DoesNotExist):
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
            
            # Buscar plantillas similares (mismo nombre, tipo, región)
            plantillas_similares = PlantillaPreinforme.objects.filter(
                nombre__iexact=nombre,
                tipo_estudio=tipo_estudio,
                region=region
            )
            
            # Si va a ser pública, verificar restricción única
            if compartir:
                duplicada_publica = plantillas_similares.filter(
                    estado='publica',
                    sistema_destino=sistema_destino
                ).first()
                
                if duplicada_publica:
                    messages.error(
                        request,
                        f'Ya existe una plantilla pública con el nombre "{nombre}" '
                        f'para {tipo_estudio.nombre} - {region.nombre} - {sistema_destino}. '
                        f'Puedes usarla directamente o crear una versión privada con otro nombre.'
                    )
                    # Mostrar contexto de la plantilla existente
                    context = {
                        'form': form,
                        'tipo_estudio': tipo_estudio,
                        'region': region,
                        'plantilla_existente': duplicada_publica
                    }
                    return render(request, 'preinformes/crear_plantilla.html', context)
            
            # Si hay similares privadas, informar pero permitir
            if plantillas_similares.filter(estado='borrador').exists():
                messages.info(
                    request,
                    f'Nota: Ya existen plantillas privadas con nombre similar. '
                    f'Si necesitas acceso a una plantilla de otro residente, solicítale que la comparta.'
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
            
            plantilla.save()
            
            messages.success(
                request,
                f'Plantilla "{plantilla.nombre}" creada exitosamente. ' +
                ('Visible para todos.' if compartir else 'Solo visible para ti.')
            )
            
            # Redirigir al formulario de preinforme con la plantilla seleccionada
            return redirect(f"{reverse('preinformes:crear_preinforme')}?plantilla_id={plantilla.id}")
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
        # HTML con formato desde la revisión finalizada
        informe_html = preinforme.revision.informe_final_html
        # Texto plano como fallback
        from django.utils.html import strip_tags
        informe_texto = strip_tags(informe_html)
    else:
        # Si no hay revisión, usar el preinforme original con método unificado
        informe_html = preinforme.get_informe_html_or_legacy()
        from django.utils.html import strip_tags
        informe_texto = strip_tags(informe_html)
    
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