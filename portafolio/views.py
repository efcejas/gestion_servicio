from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, render

from accounts.models import CustomUser

from .permissions import portafolio_habilitado_para, puede_ver_todos_los_residentes
from .selectors import residentes_para_seguimiento
from .services import construir_resumen_portafolio


def _render_portafolio(request, residente):
    return render(
        request,
        'portafolio/resumen.html',
        {
            'residente': residente,
            'resumen': construir_resumen_portafolio(residente),
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
