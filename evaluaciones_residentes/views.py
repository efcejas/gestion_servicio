from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.decorators import role_required

from .exceptions import EvaluacionError
from .forms import AnulacionIntentoForm, CorreccionRespuestaForm, ExamenForm, OpcionFormSet, PreguntaForm, RecuperacionIntentoForm
from .models import Examen, IntentoExamen, Pregunta, PreguntaImagen
from .selectors import (
    asignacion_para_residente,
    asignaciones_para_residente,
    examen_para_edicion,
    examenes_para_docente,
    intento_para_residente,
    intentos_para_docente,
)
from .services import (
    cerrar_examenes_vencidos,
    corregir_respuesta_desarrollo,
    entregar_intento,
    anular_intento,
    finalizar_examen,
    finalizar_correccion_manual,
    guardar_respuesta,
    eliminar_borrador,
    iniciar_examen_manual,
    iniciar_o_reanudar_intento,
    publicar_examen,
    publicar_resultado,
    recuperar_intento,
)


ROLES_DOCENTES = ('instructor_residentes', 'jefe_residentes', 'jefe_servicio')


def _actualizar_cierres_vencidos():
    cerrar_examenes_vencidos()


def _respuestas_para_entrega(intento, preguntas):
    """Normaliza las respuestas guardadas para pasarlas al servicio de entrega."""
    respuestas_guardadas = {
        respuesta.pregunta_id: respuesta
        for respuesta in intento.respuestas.prefetch_related('opciones_elegidas').all()
    }
    respuestas = {}
    for pregunta in preguntas:
        respuesta = respuestas_guardadas.get(pregunta.pk)
        if not respuesta:
            continue
        if pregunta.tipo == Pregunta.DESARROLLO:
            respuestas[pregunta.pk] = respuesta.texto_desarrollo
            continue
        ids = list(respuesta.opciones_elegidas.values_list('opcion_id', flat=True))
        if pregunta.tipo == Pregunta.OPCION_MULTIPLE:
            respuestas[pregunta.pk] = ids
        elif ids:
            respuestas[pregunta.pk] = ids[0]
    return respuestas


def _examen_editable(request, examen_id):
    examen = examen_para_edicion(request.user, examen_id)
    if examen is None:
        raise Http404('El examen no existe o no está disponible para edición.')
    return examen


def _intento_gestionable(request, intento_id):
    intento = get_object_or_404(
        IntentoExamen.objects.select_related('examen', 'residente').prefetch_related(
            'respuestas__pregunta__imagenes',
            'respuestas__pregunta__opciones',
            'respuestas__opciones_elegidas__opcion',
        ),
        pk=intento_id,
    )
    if not examenes_para_docente(request.user).filter(pk=intento.examen_id).exists():
        raise Http404('El intento no existe o no está disponible para revisión.')
    return intento


@login_required
@role_required(*ROLES_DOCENTES)
def lista_examenes(request):
    _actualizar_cierres_vencidos()
    examenes = examenes_para_docente(request.user)
    return render(request, 'evaluaciones_residentes/lista_examenes.html', {
        'examenes': examenes,
        'resumen': {
            'total': examenes.count(),
            'borradores': examenes.filter(estado=Examen.BORRADOR).count(),
            'publicadas': examenes.filter(estado=Examen.PUBLICADO).count(),
            'cerradas': examenes.filter(estado=Examen.CERRADO).count(),
        },
    })


@login_required
@role_required(*ROLES_DOCENTES)
def lista_intentos(request, examen_id):
    _actualizar_cierres_vencidos()
    examen = get_object_or_404(examenes_para_docente(request.user), pk=examen_id)
    todos_los_intentos = intentos_para_docente(request.user, examen_id)
    total_entregados = todos_los_intentos.exclude(estado=IntentoExamen.INICIADO).count()
    corregidos = todos_los_intentos.filter(estado=IntentoExamen.CORREGIDO).count()
    porcentaje_corregidos = round(corregidos * 100 / total_entregados) if total_entregados else 0
    busqueda = request.GET.get('q', '').strip()
    estado = request.GET.get('estado', '').strip()
    anio = request.GET.get('anio', '').strip()
    intentos = todos_los_intentos
    if busqueda:
        intentos = intentos.filter(
            Q(residente__username__icontains=busqueda)
            | Q(residente__first_name__icontains=busqueda)
            | Q(residente__last_name__icontains=busqueda)
        )
    if estado in {valor for valor, _ in IntentoExamen.ESTADO_CHOICES}:
        intentos = intentos.filter(estado=estado)
    if anio in {valor for valor, _ in Examen.ANIOS_RESIDENCIA}:
        intentos = intentos.filter(residente__anio_residencia=anio)
    return render(request, 'evaluaciones_residentes/intentos_lista.html', {
        'examen': examen,
        'intentos': intentos,
        'total_entregados': total_entregados,
        'corregidos': corregidos,
        'porcentaje_corregidos': porcentaje_corregidos,
        'filtros': {
            'q': busqueda,
            'estado': estado,
            'anio': anio,
        },
        'estados': IntentoExamen.ESTADO_CHOICES,
        'anios': Examen.ANIOS_RESIDENCIA,
    })


@login_required
@role_required(*ROLES_DOCENTES)
def iniciar_examen(request, examen_id):
    if request.method != 'POST':
        return HttpResponseForbidden('Iniciar el examen requiere POST.')
    _actualizar_cierres_vencidos()
    examen = get_object_or_404(examenes_para_docente(request.user), pk=examen_id)
    try:
        iniciar_examen_manual(examen, request.user)
        messages.success(request, 'Examen iniciado. Los residentes ya pueden rendirlo.')
    except EvaluacionError as exc:
        messages.error(request, str(exc))
    return redirect('evaluaciones_residentes:lista')


@login_required
@role_required(*ROLES_DOCENTES)
def finalizar(request, examen_id):
    if request.method != 'POST':
        return HttpResponseForbidden('Finalizar el examen requiere POST.')
    examen = get_object_or_404(examenes_para_docente(request.user), pk=examen_id)
    try:
        finalizar_examen(examen, request.user)
        messages.success(request, 'Examen finalizado. Ya no acepta nuevos intentos ni cambios.')
    except EvaluacionError as exc:
        messages.error(request, str(exc))
    return redirect('evaluaciones_residentes:lista')


@login_required
@role_required(*ROLES_DOCENTES)
def revisar_intento(request, intento_id):
    intento = _intento_gestionable(request, intento_id)
    respuestas_desarrollo = [
        respuesta for respuesta in intento.respuestas.all()
        if respuesta.pregunta.tipo == Pregunta.DESARROLLO
    ]
    formularios = {
        respuesta.pk: CorreccionRespuestaForm(
            request.POST or None,
            prefix=f'respuesta_{respuesta.pk}',
            initial={
                'puntaje': respuesta.puntaje_obtenido,
                'comentario': respuesta.comentario_docente,
            },
        )
        for respuesta in respuestas_desarrollo
    }
    anulacion_form = AnulacionIntentoForm(
        request.POST or None,
        prefix='anulacion',
    )
    recuperacion_form = RecuperacionIntentoForm(
        request.POST or None,
        prefix='recuperacion',
    )
    accion = request.POST.get('accion') if request.method == 'POST' else None
    if request.method == 'POST' and accion == 'corregir':
        if intento.estado != IntentoExamen.PENDIENTE_CORRECCION:
            messages.error(request, 'El intento no está pendiente de corrección manual.')
        else:
            formularios_validos = True
            for formulario in formularios.values():
                if not formulario.is_valid():
                    formularios_validos = False
            if formularios_validos:
                try:
                    with transaction.atomic():
                        for respuesta in respuestas_desarrollo:
                            datos = formularios[respuesta.pk].cleaned_data
                            corregir_respuesta_desarrollo(
                                respuesta,
                                datos['puntaje'],
                                datos['comentario'],
                                request.user,
                            )
                        finalizar_correccion_manual(intento, request.user)
                    messages.success(request, 'Corrección guardada y resultado calculado.')
                    return redirect('evaluaciones_residentes:revisar_intento', intento_id=intento.pk)
                except EvaluacionError as exc:
                    messages.error(request, str(exc))
    elif request.method == 'POST' and accion == 'publicar':
        try:
            publicar_resultado(intento, request.user)
            messages.success(request, 'Resultado publicado para el residente.')
            return redirect('evaluaciones_residentes:revisar_intento', intento_id=intento.pk)
        except EvaluacionError as exc:
            messages.error(request, str(exc))
    elif request.method == 'POST' and accion == 'anular':
        if anulacion_form.is_valid():
            try:
                anular_intento(
                    intento,
                    request.user,
                    anulacion_form.cleaned_data['motivo'],
                )
                messages.success(request, 'Intento anulado y registrado en la auditoría.')
                return redirect('evaluaciones_residentes:revisar_intento', intento_id=intento.pk)
            except EvaluacionError as exc:
                messages.error(request, str(exc))
    elif request.method == 'POST' and accion == 'recuperar':
        if recuperacion_form.is_valid():
            try:
                recuperar_intento(
                    intento,
                    request.user,
                    recuperacion_form.cleaned_data['motivo'],
                )
                messages.success(request, 'Intento recuperado. El residente puede retomarlo.')
                return redirect('evaluaciones_residentes:revisar_intento', intento_id=intento.pk)
            except EvaluacionError as exc:
                messages.error(request, str(exc))
    return render(request, 'evaluaciones_residentes/intento_revision.html', {
        'intento': intento,
        'examen': intento.examen,
        'respuestas': intento.respuestas.all(),
        'respuestas_desarrollo': respuestas_desarrollo,
        'formularios': formularios,
        'correcciones': [
            (respuesta, formularios[respuesta.pk])
            for respuesta in respuestas_desarrollo
        ],
        'anulacion_form': anulacion_form,
        'recuperacion_form': recuperacion_form,
    })


@login_required
@role_required('medico_residente')
def lista_residente(request):
    _actualizar_cierres_vencidos()
    asignaciones = asignaciones_para_residente(request.user)
    return render(request, 'evaluaciones_residentes/residente_lista.html', {
        'asignaciones': asignaciones,
    })


@login_required
@role_required('medico_residente')
def detalle_residente(request, examen_id):
    _actualizar_cierres_vencidos()
    asignacion = asignacion_para_residente(request.user, examen_id)
    if asignacion is None:
        raise Http404('La evaluación no está asignada a este residente.')
    intento = (asignacion.examen.intento_del_residente or [None])[0]
    return render(request, 'evaluaciones_residentes/residente_detalle.html', {
        'asignacion': asignacion,
        'examen': asignacion.examen,
        'intento': intento,
    })


@login_required
@role_required('medico_residente')
def resultado_residente(request, examen_id):
    asignacion = asignacion_para_residente(request.user, examen_id)
    if asignacion is None:
        raise Http404('La evaluación no está asignada a este residente.')
    intento = intento_para_residente(request.user, examen_id)
    if intento is None or intento.estado == IntentoExamen.ANULADO or not intento.resultado_publicado_en:
        messages.info(request, 'El resultado todavía no está disponible para consulta.')
        return redirect('evaluaciones_residentes:detalle_residente', examen_id=examen_id)
    filas = []
    for respuesta in intento.respuestas.all():
        seleccionadas = set(respuesta.opciones_elegidas.values_list('opcion_id', flat=True))
        filas.append({
            'respuesta': respuesta,
            'opciones': list(respuesta.pregunta.opciones.all()),
            'seleccionadas': seleccionadas,
        })
    return render(request, 'evaluaciones_residentes/resultado_residente.html', {
        'asignacion': asignacion,
        'examen': asignacion.examen,
        'intento': intento,
        'filas': filas,
    })


@login_required
@role_required('medico_residente')
def iniciar_residente(request, examen_id):
    _actualizar_cierres_vencidos()
    if request.method != 'POST':
        return HttpResponseForbidden('Iniciar la evaluación requiere POST.')
    asignacion = asignacion_para_residente(request.user, examen_id)
    if asignacion is None:
        raise Http404('La evaluación no está asignada a este residente.')
    try:
        intento = iniciar_o_reanudar_intento(asignacion.examen, request.user)
    except EvaluacionError as exc:
        messages.error(request, str(exc))
        return redirect('evaluaciones_residentes:detalle_residente', examen_id=examen_id)
    return redirect('evaluaciones_residentes:intento_residente', intento_id=intento.pk)


@login_required
@role_required('medico_residente')
def intento_residente(request, intento_id):
    intento = get_object_or_404(
        IntentoExamen.objects.select_related('examen').prefetch_related(
            'examen__preguntas__opciones',
            'examen__preguntas__imagenes',
        ),
        pk=intento_id,
        residente=request.user,
    )
    if intento.estado != IntentoExamen.INICIADO:
        return redirect('evaluaciones_residentes:detalle_residente', examen_id=intento.examen_id)
    if timezone.now() >= intento.examen.fecha_vencimiento:
        messages.warning(request, 'El período de la evaluación ya terminó y no acepta nuevas respuestas.')
        return redirect('evaluaciones_residentes:detalle_residente', examen_id=intento.examen_id)
    preguntas = list(intento.examen.preguntas.all())
    try:
        indice = max(0, min(int(request.GET.get('pregunta', 0)), len(preguntas) - 1))
    except (TypeError, ValueError):
        indice = 0
    pregunta = preguntas[indice] if preguntas else None
    respuesta_actual = None
    opciones_seleccionadas = set()
    if pregunta:
        respuesta_actual = intento.respuestas.filter(pregunta=pregunta).first()
        if respuesta_actual:
            opciones_seleccionadas = set(
                respuesta_actual.opciones_elegidas.values_list('opcion_id', flat=True)
            )
    if request.method == 'POST' and pregunta:
        accion = request.POST.get('accion', 'siguiente')
        valores = request.POST.getlist(f'pregunta_{pregunta.pk}')
        respuesta_recibida = valores if pregunta.tipo == Pregunta.OPCION_MULTIPLE else (valores[0] if valores else request.POST.get(f'texto_{pregunta.pk}', ''))
        try:
            guardar_respuesta(intento, pregunta, respuesta_recibida)
        except EvaluacionError as exc:
            messages.error(request, str(exc))
            return redirect(request.path + f'?pregunta={indice}')
        if accion == 'anterior':
            anterior = max(0, indice - 1)
            return redirect(request.path + f'?pregunta={anterior}')
        if accion == 'entregar' and indice == len(preguntas) - 1:
            return redirect('evaluaciones_residentes:confirmar_entrega', intento_id=intento.pk)
        siguiente = indice + 1
        if siguiente < len(preguntas):
            return redirect(request.path + f'?pregunta={siguiente}')
        messages.success(request, 'Respuesta guardada. Ya completaste las preguntas disponibles.')
        return redirect(request.path + f'?pregunta={indice}')
    return render(request, 'evaluaciones_residentes/intento_residente.html', {
        'intento': intento,
        'examen': intento.examen,
        'pregunta': pregunta,
        'indice': indice,
        'total_preguntas': len(preguntas),
        'respuesta_actual': respuesta_actual,
        'opciones_seleccionadas': opciones_seleccionadas,
        'puede_ir_anterior': indice > 0,
        'es_ultima_pregunta': bool(preguntas) and indice == len(preguntas) - 1,
    })


@login_required
@role_required('medico_residente')
def confirmar_entrega(request, intento_id):
    intento = get_object_or_404(
        IntentoExamen.objects.select_related('examen').prefetch_related('examen__preguntas'),
        pk=intento_id,
        residente=request.user,
    )
    if intento.estado != IntentoExamen.INICIADO:
        return redirect('evaluaciones_residentes:detalle_residente', examen_id=intento.examen_id)
    if timezone.now() >= intento.examen.fecha_vencimiento:
        messages.warning(request, 'El período de la evaluación ya terminó y no acepta nuevas respuestas.')
        return redirect('evaluaciones_residentes:detalle_residente', examen_id=intento.examen_id)
    preguntas = list(intento.examen.preguntas.all())
    respondidas = intento.respuestas.filter(
        pregunta_id__in=[pregunta.pk for pregunta in preguntas],
    ).count()
    contexto = {
        'intento': intento,
        'examen': intento.examen,
        'total_preguntas': len(preguntas),
        'respondidas': respondidas,
        'sin_responder': max(0, len(preguntas) - respondidas),
    }
    if request.method != 'POST':
        return render(request, 'evaluaciones_residentes/confirmar_entrega.html', contexto)
    try:
        entregar_intento(intento, _respuestas_para_entrega(intento, preguntas))
    except EvaluacionError as exc:
        messages.error(request, str(exc))
        return redirect('evaluaciones_residentes:confirmar_entrega', intento_id=intento.pk)
    messages.success(request, 'Evaluación entregada correctamente.')
    return redirect('evaluaciones_residentes:detalle_residente', examen_id=intento.examen_id)


@login_required
@role_required(*ROLES_DOCENTES)
def crear_examen(request):
    if request.method == 'POST':
        form = ExamenForm(request.POST)
        if form.is_valid():
            examen = form.save(commit=False)
            examen.creador = request.user
            examen.save()
            form.save_m2m()
            messages.success(request, 'Borrador creado. Ahora agrega las preguntas.')
            return redirect('evaluaciones_residentes:preguntas', examen_id=examen.pk)
    else:
        form = ExamenForm()
    return render(request, 'evaluaciones_residentes/examen_form.html', {'form': form, 'modo': 'Crear'})


@login_required
@role_required(*ROLES_DOCENTES)
def editar_examen(request, examen_id):
    examen = _examen_editable(request, examen_id)
    if request.method == 'POST':
        form = ExamenForm(request.POST, instance=examen)
        if form.is_valid():
            form.save()
            messages.success(request, 'Borrador actualizado.')
            return redirect('evaluaciones_residentes:preguntas', examen_id=examen.pk)
    else:
        form = ExamenForm(instance=examen)
    return render(request, 'evaluaciones_residentes/examen_form.html', {'form': form, 'modo': 'Editar', 'examen': examen})


@login_required
@role_required(*ROLES_DOCENTES)
def lista_preguntas(request, examen_id):
    examen = _examen_editable(request, examen_id)
    preguntas = examen.preguntas.prefetch_related('opciones', 'imagenes').all()
    return render(request, 'evaluaciones_residentes/preguntas_lista.html', {'examen': examen, 'preguntas': preguntas})


@login_required
@role_required(*ROLES_DOCENTES)
def crear_pregunta(request, examen_id):
    examen = _examen_editable(request, examen_id)
    pregunta = Pregunta(examen=examen, orden=examen.preguntas.count() + 1)
    if request.method == 'POST':
        form = PreguntaForm(request.POST, request.FILES, instance=pregunta)
        if form.is_valid():
            pregunta = form.save(commit=False)
            pregunta.examen = examen
            imagenes = form.cleaned_data.get('imagenes') or []
            formset = (
                OpcionFormSet(request.POST, instance=pregunta)
                if pregunta.tipo != Pregunta.DESARROLLO
                else OpcionFormSet(instance=pregunta)
            )
            if pregunta.tipo == Pregunta.DESARROLLO or formset.is_valid():
                with transaction.atomic():
                    pregunta.save()
                    if pregunta.tipo == Pregunta.DESARROLLO:
                        pregunta.opciones.all().delete()
                    else:
                        formset.instance = pregunta
                        formset.save()
                    PreguntaImagen.objects.bulk_create([
                        PreguntaImagen(pregunta=pregunta, archivo=archivo, orden=indice)
                        for indice, archivo in enumerate(imagenes, start=1)
                    ])
                messages.success(request, 'Pregunta agregada.')
                return redirect('evaluaciones_residentes:preguntas', examen_id=examen.pk)
        else:
            formset = OpcionFormSet(request.POST, instance=pregunta)
    else:
        form = PreguntaForm(instance=pregunta)
        formset = OpcionFormSet(instance=pregunta)
    return render(request, 'evaluaciones_residentes/pregunta_form.html', {
        'form': form,
        'formset': formset,
        'examen': examen,
        'modo': 'Agregar',
    })


@login_required
@role_required(*ROLES_DOCENTES)
def editar_pregunta(request, examen_id, pregunta_id):
    examen = _examen_editable(request, examen_id)
    pregunta = get_object_or_404(Pregunta, pk=pregunta_id, examen=examen)
    if request.method == 'POST':
        form = PreguntaForm(request.POST, request.FILES, instance=pregunta)
        formset = (
            OpcionFormSet(request.POST, instance=pregunta)
            if request.POST.get('tipo') != Pregunta.DESARROLLO
            else OpcionFormSet(instance=pregunta)
        )
        if form.is_valid() and (
            request.POST.get('tipo') == Pregunta.DESARROLLO or formset.is_valid()
        ):
            imagenes = form.cleaned_data.get('imagenes') or []
            eliminar_ids = {
                int(valor) for valor in request.POST.getlist('eliminar_imagen')
                if valor.isdigit()
            }
            ordenes_imagenes = {
                int(nombre.rsplit('_', 1)[1]): int(valor)
                for nombre, valor in request.POST.items()
                if nombre.startswith('orden_imagen_') and valor.isdigit()
            }
            with transaction.atomic():
                form.save()
                if pregunta.tipo == Pregunta.DESARROLLO:
                    pregunta.opciones.all().delete()
                else:
                    formset.save()
                pregunta.imagenes.filter(pk__in=eliminar_ids).delete()
                imagenes_restantes = list(pregunta.imagenes.exclude(pk__in=eliminar_ids).all())
                for indice, imagen in enumerate(imagenes_restantes, start=1):
                    # Valores positivos temporales para respetar el CHECK de orden.
                    imagen.orden = 30000 - indice
                    imagen.save(update_fields=['orden'])
                imagenes_restantes.sort(key=lambda imagen: ordenes_imagenes.get(imagen.pk, imagen.orden))
                for orden, imagen in enumerate(imagenes_restantes, start=1):
                    imagen.orden = orden
                    imagen.save(update_fields=['orden'])
                ultimo_orden = pregunta.imagenes.order_by('-orden').values_list('orden', flat=True).first() or 0
                PreguntaImagen.objects.bulk_create([
                    PreguntaImagen(pregunta=pregunta, archivo=archivo, orden=ultimo_orden + indice)
                    for indice, archivo in enumerate(imagenes, start=1)
                ])
            messages.success(request, 'Pregunta actualizada.')
            return redirect('evaluaciones_residentes:preguntas', examen_id=examen.pk)
    else:
        form = PreguntaForm(instance=pregunta)
        formset = OpcionFormSet(instance=pregunta)
    pregunta.imagenes.all()
    return render(request, 'evaluaciones_residentes/pregunta_form.html', {
        'form': form,
        'formset': formset,
        'examen': examen,
        'pregunta': pregunta,
        'modo': 'Editar',
    })


@login_required
@role_required(*ROLES_DOCENTES)
def revisar_examen(request, examen_id):
    examen = _examen_editable(request, examen_id)
    preguntas = examen.preguntas.prefetch_related('opciones', 'imagenes').all()
    return render(request, 'evaluaciones_residentes/examen_revision.html', {'examen': examen, 'preguntas': preguntas})


@login_required
@role_required(*ROLES_DOCENTES)
def publicar(request, examen_id):
    if request.method != 'POST':
        return HttpResponseForbidden('La publicación requiere una confirmación POST.')
    examen = _examen_editable(request, examen_id)
    try:
        publicar_examen(examen, request.user)
    except EvaluacionError as exc:
        messages.error(request, str(exc))
        return redirect('evaluaciones_residentes:revision', examen_id=examen.pk)
    messages.success(request, 'Evaluación publicada y congelada.')
    return redirect('evaluaciones_residentes:lista')


@login_required
@role_required(*ROLES_DOCENTES)
def eliminar(request, examen_id):
    if request.method != 'POST':
        return HttpResponseForbidden('La eliminación requiere una confirmación POST.')
    examen = get_object_or_404(Examen, pk=examen_id)
    try:
        eliminar_borrador(examen, request.user)
    except EvaluacionError as exc:
        messages.error(request, str(exc))
        return redirect('evaluaciones_residentes:lista')
    messages.success(request, 'Borrador eliminado.')
    return redirect('evaluaciones_residentes:lista')
