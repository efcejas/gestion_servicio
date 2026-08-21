from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import get_object_or_404, render

from accounts.models import CustomUser

from .permissions import portafolio_habilitado_para, puede_ver_todos_los_residentes
from .selectors import periodos_disponibles_residente, residentes_para_seguimiento
from .services import construir_resumen_portafolio, construir_trayectoria_portafolio


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
