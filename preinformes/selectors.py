"""
selectors.py - Queries reutilizables del modulo preinformes.

Cada funcion encapsula un patron de filtrado frecuente. Retornan QuerySets
(no listas), por lo que el caller puede seguir encadenando .filter(), .count(),
.order_by(), etc., sin reescribir la logica base.
"""
from django.contrib.auth import get_user_model
from django.db.models import Q

from .models import Preinforme, PlantillaPreinforme

User = get_user_model()

# Estados que indican que un preinforme esta activo en el flujo de revision.
ESTADOS_ACTIVOS = ['pendiente_revision', 'en_revision']
ROLES_POOL_COMPARTIDO = ['jefe_residentes', 'instructor_residentes']
ROLES_REVISORES = ['medico_staff', 'jefe_residentes', 'instructor_residentes', 'jefe_servicio']
MODOS_LISTA_REVISION = [
    'asignados',
    'sin_asignar',
    'asignados_otros',
    'compartidos',
    'todos',
    'finalizados',
]


def _aplicar_scope_demo(qs, usuario=None):
    if getattr(usuario, 'is_demo_user', False):
        return qs.filter(
            Q(es_registro_demo=False) |
            Q(es_registro_demo=True, residente=usuario)
        )
    return qs.filter(es_registro_demo=False)


def get_asignados_de(revisor):
    """
    Preinformes activos asignados a un revisor.

    Uso tipico:
        get_asignados_de(request.user).count()
        get_asignados_de(request.user).order_by('-fecha_envio_revision')[:5]
    """
    return _aplicar_scope_demo(Preinforme.objects.filter(
        revisor=revisor,
        estado__in=ESTADOS_ACTIVOS,
    ), revisor)


def get_pendientes_sin_revisor(usuario=None):
    """
    Preinformes en pendiente_revision que aun no tienen revisor asignado.

    Se conserva para contadores historicos del dashboard. Para la bandeja
    operativa de revision usar get_sin_asignar_para_revision().
    """
    return _aplicar_scope_demo(Preinforme.objects.filter(
        estado='pendiente_revision',
        revisor__isnull=True,
    ), usuario)


def get_sin_asignar_para_revision(usuario=None):
    """
    Bandeja operativa de estudios sin revisor.

    Excluye el pool compartido, que se maneja con reglas propias para jefes e
    instructores. Incluye en_revision sin revisor por compatibilidad con datos
    previos o estados intermedios.
    """
    return _aplicar_scope_demo(Preinforme.objects.filter(
        estado__in=ESTADOS_ACTIVOS,
        revisor__isnull=True,
        asignacion_compartida=False,
    ), usuario)


def get_pool_compartido_para(usuario):
    """
    Estudios del pool compartido visibles para jefes/instructores.
    Otros roles reciben QuerySet vacio para que la vista no replique permisos.
    """
    if getattr(usuario, 'rol', None) not in ROLES_POOL_COMPARTIDO:
        return Preinforme.objects.none()

    return _aplicar_scope_demo(Preinforme.objects.filter(
        asignacion_compartida=True,
        revisor__isnull=True,
        estado__in=ESTADOS_ACTIVOS,
    ), usuario)


def get_finalizados_de(revisor):
    """Preinformes finalizados por un revisor."""
    return _aplicar_scope_demo(Preinforme.objects.filter(
        revisor=revisor,
        estado='finalizado',
    ), revisor)


def get_asignados_a_otros(usuario):
    """
    Estudios activos asignados a otro revisor.

    Permite ubicar errores de asignacion y tomar el estudio cuando corresponde.
    No incluye finalizados para evitar reabrir historiales ajenos.
    """
    return _aplicar_scope_demo(Preinforme.objects.filter(
        estado__in=ESTADOS_ACTIVOS,
        revisor__isnull=False,
    ).exclude(revisor=usuario), usuario)


def get_revision_todos_para(usuario):
    """
    Bandeja "todos" del staff: mis activos + disponibles para tomar.

    Jefes e instructores ven tambien el pool compartido. Staff y jefe_servicio
    ven solo sin asignar no compartidos.
    """
    base_filter = Q(estado__in=ESTADOS_ACTIVOS, revisor=usuario)

    if getattr(usuario, 'rol', None) in ROLES_POOL_COMPARTIDO:
        base_filter |= Q(estado__in=ESTADOS_ACTIVOS, revisor__isnull=True)
    else:
        base_filter |= Q(
            estado__in=ESTADOS_ACTIVOS,
            revisor__isnull=True,
            asignacion_compartida=False,
        )

    return _aplicar_scope_demo(Preinforme.objects.filter(base_filter), usuario)


def get_revision_queryset(usuario, mostrar):
    """
    Retorna el QuerySet base para cada pestana de revision staff.

    `mostrar` puede ser asignados, sin_asignar, compartidos, todos o
    finalizados. Valores desconocidos caen en "todos" para conservar el
    comportamiento previo.
    """
    if mostrar == 'asignados':
        return get_asignados_de(usuario)
    if mostrar == 'sin_asignar':
        return get_sin_asignar_para_revision(usuario)
    if mostrar == 'asignados_otros':
        return get_asignados_a_otros(usuario)
    if mostrar == 'compartidos':
        return get_pool_compartido_para(usuario)
    if mostrar == 'finalizados':
        return get_finalizados_de(usuario).select_related(
            'revision',
            'residente',
            'tipo_estudio',
            'region',
        )
    return get_revision_todos_para(usuario)


def get_plantillas_activas(tipo_estudio=None, region=None):
    """
    Plantillas de preinformes visibles para los residentes.

    Parametros opcionales para filtrar por tipo_estudio y/o region:
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

    Retorna un QuerySet de User, util para poblar desplegables de asignacion
    manual o para validar un revisor_id recibido del frontend.
    """
    return User.objects.filter(rol__in=ROLES_REVISORES)
