"""
selectors.py — Queries reutilizables del módulo preinformes.

Cada función encapsula un patrón de filtrado frecuente. Retornan QuerySets
(no listas), por lo que el caller puede seguir encadenando .filter(), .count(),
.order_by(), etc., sin reescribir la lógica base.

Convenio de nombres:
    get_*()  → retorna un QuerySet (puede estar vacío, nunca None)
"""
from django.contrib.auth import get_user_model

from .models import Preinforme, PlantillaPreinforme

User = get_user_model()

# Estados que indican que un preinforme está activo en el flujo de revisión
ESTADOS_ACTIVOS = ['pendiente_revision', 'en_revision']


def get_asignados_de(revisor):
    """
    Preinformes activos (pendiente_revision o en_revision) asignados a un revisor.

    Uso típico:
        get_asignados_de(request.user).count()
        get_asignados_de(request.user).order_by('-fecha_envio_revision')[:5]
    """
    return Preinforme.objects.filter(
        revisor=revisor,
        estado__in=ESTADOS_ACTIVOS,
    )


def get_pendientes_sin_revisor():
    """
    Preinformes en estado pendiente_revision que aún no tienen revisor asignado.

    No incluye los en estado en_revision (esos ya fueron tomados por alguien).

    Uso típico:
        get_pendientes_sin_revisor().count()
        get_pendientes_sin_revisor().order_by('-fecha_envio_revision')[:10]
    """
    return Preinforme.objects.filter(
        estado='pendiente_revision',
        revisor__isnull=True,
    )


def get_plantillas_activas(tipo_estudio=None, region=None):
    """
    Plantillas de preinformes visibles para los residentes.

    Parámetros opcionales para filtrar por tipo_estudio y/o region:
        get_plantillas_activas(tipo_estudio=tipo, region=region)
    """
    qs = PlantillaPreinforme.objects.filter(activa=True)
    if tipo_estudio:
        qs = qs.filter(tipo_estudio=tipo_estudio)
    if region:
        qs = qs.filter(region=region)
    return qs


def get_revisores_disponibles():
    """
    Usuarios con rol habilitado para revisar preinformes.

    Retorna un QuerySet de User, útil para poblar desplegables de
    asignación manual o para validar un revisor_id recibido del frontend.
    """
    return User.objects.filter(
        rol__in=['medico_staff', 'jefe_residentes', 'instructor_residentes', 'jefe_servicio'],
    )
