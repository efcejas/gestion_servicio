from urllib.parse import quote

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.models import CustomUser

from .forms import ActividadCurricularForm, RevisionActividadForm
from .models import ActividadCurricular, DocumentoActividadCurricular
from .permissions import portafolio_habilitado_para, puede_ver_todos_los_residentes
from .selectors import periodos_disponibles_residente, residentes_para_seguimiento
from .services import (
    ActividadCurricularError,
    construir_resumen_portafolio,
    construir_trayectoria_portafolio,
    eliminar_documento_actividad,
    enviar_actividad,
    guardar_documentos_actividad,
    revisar_actividad,
)


def _puede_ver_actividad(user, actividad):
    return (
        portafolio_habilitado_para(user)
        and (
            user.pk == actividad.residente_id
            or puede_ver_todos_los_residentes(user)
        )
    )


def _exigir_residente_activo(user):
    if not portafolio_habilitado_para(user) or not user.es_residente_activo():
        raise PermissionDenied


def _seleccionar_periodo(request, residente):
    periodos = periodos_disponibles_residente(residente)
    anio_solicitado = request.GET.get('ciclo')
    if not anio_solicitado:
        return periodos, periodos[0]
    try:
        anio_solicitado = int(anio_solicitado)
    except (TypeError, ValueError) as exc:
        raise Http404('Ciclo lectivo inexistente.') from exc

    periodo = next(
        (
            disponible
            for disponible in periodos
            if disponible['anio_inicio'] == anio_solicitado
        ),
        None,
    )
    if periodo is None:
        raise Http404('Ciclo lectivo inexistente.')
    return periodos, periodo


def _render_portafolio(request, residente):
    periodos, periodo_seleccionado = _seleccionar_periodo(request, residente)
    return render(
        request,
        'portafolio/resumen.html',
        {
            'residente': residente,
            'resumen': construir_resumen_portafolio(
                residente,
                periodo=periodo_seleccionado,
            ),
            'ciclos_disponibles': periodos,
            'es_portafolio_propio': request.user.pk == residente.pk,
        },
    )


@login_required
def mi_portafolio(request):
    if (
        not portafolio_habilitado_para(request.user)
        or request.user.rol != 'medico_residente'
    ):
        raise PermissionDenied
    return _render_portafolio(request, request.user)


@login_required
def seguimiento_residentes(request):
    if not puede_ver_todos_los_residentes(request.user):
        raise PermissionDenied
    return render(
        request,
        'portafolio/seguimiento.html',
        {'residentes': residentes_para_seguimiento()},
    )


@login_required
def detalle_residente(request, pk):
    residente = get_object_or_404(CustomUser, pk=pk, rol='medico_residente')
    if not portafolio_habilitado_para(request.user):
        raise PermissionDenied
    if (
        request.user.pk != residente.pk
        and not puede_ver_todos_los_residentes(request.user)
    ):
        raise PermissionDenied
    return _render_portafolio(request, residente)


@login_required
def trayectoria_residente(request, pk):
    residente = get_object_or_404(CustomUser, pk=pk, rol='medico_residente')
    if not puede_ver_todos_los_residentes(request.user):
        raise PermissionDenied
    return render(
        request,
        'portafolio/trayectoria.html',
        {
            'residente': residente,
            'trayectoria': construir_trayectoria_portafolio(residente),
        },
    )


@login_required
def actividades_propias(request):
    if (
        not portafolio_habilitado_para(request.user)
        or request.user.rol != 'medico_residente'
    ):
        raise PermissionDenied
    actividades = (
        ActividadCurricular.objects.filter(residente=request.user)
        .prefetch_related('documentos')
    )
    return render(
        request,
        'portafolio/actividades_lista.html',
        {
            'actividades': actividades,
            'puede_registrar': request.user.es_residente_activo(),
        },
    )


@login_required
def actividad_crear(request):
    _exigir_residente_activo(request.user)
    form = ActividadCurricularForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        actividad = form.save(commit=False)
        actividad.residente = request.user
        actividad.save()
        guardar_documentos_actividad(
            actividad,
            form.cleaned_data.get('documentos', []),
            request.user,
        )
        if request.POST.get('accion') == 'enviar':
            enviar_actividad(actividad, request.user)
            messages.success(request, 'Actividad enviada para revisión.')
        else:
            messages.success(request, 'Borrador guardado correctamente.')
        return redirect('portafolio:actividad_detalle', pk=actividad.pk)
    return render(
        request,
        'portafolio/actividad_form.html',
        {'form': form, 'actividad': None},
    )


@login_required
def actividad_editar(request, pk):
    _exigir_residente_activo(request.user)
    actividad = get_object_or_404(
        ActividadCurricular,
        pk=pk,
        residente=request.user,
    )
    if not actividad.puede_editar_residente:
        raise PermissionDenied

    form = ActividadCurricularForm(
        request.POST or None,
        request.FILES or None,
        instance=actividad,
    )
    if request.method == 'POST' and form.is_valid():
        actividad = form.save()
        guardar_documentos_actividad(
            actividad,
            form.cleaned_data.get('documentos', []),
            request.user,
        )
        if request.POST.get('accion') == 'enviar':
            enviar_actividad(actividad, request.user)
            messages.success(request, 'Actividad enviada para revisión.')
        else:
            messages.success(request, 'Cambios guardados correctamente.')
        return redirect('portafolio:actividad_detalle', pk=actividad.pk)
    return render(
        request,
        'portafolio/actividad_form.html',
        {'form': form, 'actividad': actividad},
    )


@login_required
def actividad_detalle(request, pk):
    actividad = get_object_or_404(
        ActividadCurricular.objects.select_related(
            'residente',
            'revisada_por',
        ).prefetch_related('documentos'),
        pk=pk,
    )
    if not _puede_ver_actividad(request.user, actividad):
        raise PermissionDenied
    return render(
        request,
        'portafolio/actividad_detalle.html',
        {
            'actividad': actividad,
            'es_propietario': request.user.pk == actividad.residente_id,
            'puede_revisar': puede_ver_todos_los_residentes(request.user),
            'revision_form': RevisionActividadForm(),
        },
    )


@login_required
@require_POST
def actividad_enviar(request, pk):
    _exigir_residente_activo(request.user)
    actividad = get_object_or_404(
        ActividadCurricular,
        pk=pk,
        residente=request.user,
    )
    try:
        enviar_actividad(actividad, request.user)
    except ActividadCurricularError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, 'Actividad enviada para revisión.')
    return redirect('portafolio:actividad_detalle', pk=actividad.pk)


@login_required
def actividades_revision(request):
    if not puede_ver_todos_los_residentes(request.user):
        raise PermissionDenied
    pendientes = (
        ActividadCurricular.objects.filter(estado='ENVIADA')
        .select_related('residente')
        .prefetch_related('documentos')
        .order_by('enviada_en')
    )
    return render(
        request,
        'portafolio/actividades_revision.html',
        {'actividades': pendientes},
    )


@login_required
@require_POST
def actividad_revisar(request, pk):
    if not puede_ver_todos_los_residentes(request.user):
        raise PermissionDenied
    actividad = get_object_or_404(ActividadCurricular, pk=pk)
    form = RevisionActividadForm(request.POST)
    if form.is_valid():
        try:
            revisar_actividad(
                actividad,
                request.user,
                form.cleaned_data['accion'],
                form.cleaned_data['observacion'],
            )
        except ActividadCurricularError as exc:
            messages.error(request, str(exc))
        else:
            mensaje = (
                'Actividad validada correctamente.'
                if form.cleaned_data['accion'] == 'VALIDAR'
                else 'Actividad devuelta con observaciones.'
            )
            messages.success(request, mensaje)
            return redirect('portafolio:actividades_revision')
    return render(
        request,
        'portafolio/actividad_detalle.html',
        {
            'actividad': actividad,
            'es_propietario': False,
            'puede_revisar': True,
            'revision_form': form,
        },
        status=400,
    )


@login_required
def documento_actividad_descargar(request, pk):
    documento = get_object_or_404(
        DocumentoActividadCurricular.objects.select_related('actividad'),
        pk=pk,
    )
    if not _puede_ver_actividad(request.user, documento.actividad):
        raise PermissionDenied

    disposicion = f"attachment; filename*=UTF-8''{quote(documento.nombre_original)}"
    try:
        url = documento.archivo.storage.url(
            documento.archivo.name,
            parameters={'ResponseContentDisposition': disposicion},
            expire=300,
        )
    except TypeError:
        url = documento.archivo.url
    return redirect(url)


@login_required
@require_POST
def documento_actividad_eliminar(request, pk):
    _exigir_residente_activo(request.user)
    documento = get_object_or_404(
        DocumentoActividadCurricular.objects.select_related('actividad'),
        pk=pk,
    )
    actividad_pk = documento.actividad_id
    try:
        eliminar_documento_actividad(documento, request.user)
    except ActividadCurricularError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, 'Documento eliminado.')
    return redirect('portafolio:actividad_detalle', pk=actividad_pk)
