from .models import PreparacionLiquidacionRRHH, SolicitudRevisionHorarioRegistro
from .services_auditoria import evaluar_gate_consistencia_sesion
from .services_eges import resumir_control_eges_sesion
from .services_rrhh import evaluar_requisito_rrhh_para_facturar


ESTADOS_CHECKLIST = {'ok', 'pendiente', 'advertencia', 'bloqueante'}


def _item(key, label, estado, detalle='', count=0, url=None):
    if estado not in ESTADOS_CHECKLIST:
        raise ValueError(f'Estado de checklist invalido: {estado}')
    return {
        'key': key,
        'label': label,
        'estado': estado,
        'detalle': detalle,
        'count': count,
        'url': url,
    }


def _estado_global(items):
    estados = [item['estado'] for item in items]
    if 'bloqueante' in estados:
        return 'bloqueante'
    if 'advertencia' in estados:
        return 'advertencia'
    if 'pendiente' in estados:
        return 'pendiente'
    return 'ok'


def _proximo_paso(items):
    for prioridad in ['bloqueante', 'advertencia', 'pendiente']:
        for item in items:
            if item['estado'] == prioridad:
                return {
                    'key': item['key'],
                    'label': item['label'],
                    'estado': item['estado'],
                    'detalle': item['detalle'],
                    'url': item['url'],
                }
    return None


def construir_checklist_cierre_sesion(
    sesion,
    user=None,
    *,
    gate=None,
    control_eges=None,
    requisito_rrhh=None,
):
    siguiente_para_gate = {
        'ABIERTA': 'REVISION',
        'REVISION': 'CERRADA',
        'CERRADA': 'FACTURADA',
        'FACTURADA': 'PAGADA',
    }.get(sesion.estado, 'PAGADA')

    if gate is None:
        gate = evaluar_gate_consistencia_sesion(sesion, siguiente_para_gate)
    if gate['bloqueantes']:
        estado_gate = 'bloqueante'
        detalle_gate = f"{len(gate['bloqueantes'])} bloqueante(s)"
    elif gate['advertencias']:
        estado_gate = 'advertencia'
        detalle_gate = f"{len(gate['advertencias'])} advertencia(s)"
    else:
        estado_gate = 'ok'
        detalle_gate = 'Sin hallazgos'

    registro_ids = list(sesion.practicas.filter(anulado=False).values_list('id', flat=True))
    solicitudes = SolicitudRevisionHorarioRegistro.objects.filter(registro_id__in=registro_ids)

    pendientes_count = solicitudes.filter(
        estado=SolicitudRevisionHorarioRegistro.ESTADO_PENDIENTE,
    ).count()
    aprobadas_sin_aplicar_count = solicitudes.filter(
        estado=SolicitudRevisionHorarioRegistro.ESTADO_APROBADA,
        fecha_aplicacion__isnull=True,
    ).count()

    if control_eges is None:
        control_eges = resumir_control_eges_sesion(sesion)
    if control_eges['estado'] == 'NO_REALIZADO':
        estado_control_eges = 'pendiente'
        detalle_control_eges = 'Control no realizado'
        pendientes_control_eges = 0
    elif control_eges['desactualizado']:
        estado_control_eges = 'advertencia'
        detalle_control_eges = 'Hay registros posteriores al control'
        pendientes_control_eges = control_eges['pendientes']
    elif control_eges['pendientes']:
        estado_control_eges = 'advertencia'
        pendientes_control_eges = control_eges['pendientes']
        detalle_control_eges = f'{pendientes_control_eges} caso(s) pendiente(s)'
    else:
        estado_control_eges = 'ok'
        detalle_control_eges = 'Control completo'
        pendientes_control_eges = 0

    if requisito_rrhh is None:
        requisito_rrhh = evaluar_requisito_rrhh_para_facturar(sesion)
    ultima_preparacion = requisito_rrhh['ultima_preparacion']
    if not requisito_rrhh['requiere_rrhh']:
        estado_rrhh = 'ok'
        detalle_rrhh = 'No requerido'
    elif sesion.estado in {'ABIERTA', 'REVISION'}:
        estado_rrhh = 'pendiente'
        detalle_rrhh = 'Disponible desde CERRADA'
    elif not ultima_preparacion:
        estado_rrhh = 'pendiente'
        detalle_rrhh = 'Sin preparacion'
    elif ultima_preparacion.estado == PreparacionLiquidacionRRHH.ESTADO_BORRADOR:
        estado_rrhh = 'advertencia'
        detalle_rrhh = f'Borrador v{ultima_preparacion.version}'
    else:
        estado_rrhh = 'ok'
        detalle_rrhh = f'Preparado v{ultima_preparacion.version}'

    rrhh_preparado = requisito_rrhh['ok']
    control_eges_completo = (
        control_eges['estado'] == 'COMPLETADO'
        and not control_eges['desactualizado']
        and control_eges['pendientes'] == 0
    )
    sin_bloqueantes_operativos = (
        not gate['bloqueantes']
        and pendientes_count == 0
        and aprobadas_sin_aplicar_count == 0
        and control_eges_completo
    )
    if sesion.estado in {'FACTURADA', 'PAGADA'}:
        estado_facturar = 'ok'
        detalle_facturar = 'Facturacion confirmada'
    elif sesion.estado == 'CERRADA' and sin_bloqueantes_operativos and rrhh_preparado:
        estado_facturar = 'ok'
        detalle_facturar = 'Lista para facturar'
    else:
        estado_facturar = 'pendiente'
        detalle_facturar = 'Faltan pasos previos'

    items = [
        _item('registros_validos', 'Registros validos', estado_gate, detalle_gate, len(gate['bloqueantes'])),
        _item(
            'solicitudes_pendientes',
            'Solicitudes pendientes',
            'bloqueante' if pendientes_count else 'ok',
            f'{pendientes_count} pendiente(s)' if pendientes_count else 'Sin pendientes',
            pendientes_count,
        ),
        _item(
            'aprobadas_sin_aplicar',
            'Aprobadas sin aplicar',
            'bloqueante' if aprobadas_sin_aplicar_count else 'ok',
            f'{aprobadas_sin_aplicar_count} sin aplicar' if aprobadas_sin_aplicar_count else 'Sin pendientes',
            aprobadas_sin_aplicar_count,
        ),
        _item(
            'control_eges',
            'Control EGES',
            estado_control_eges,
            detalle_control_eges,
            pendientes_control_eges,
        ),
        _item('preparacion_rrhh', 'Preparacion RRHH', estado_rrhh, detalle_rrhh),
        _item('lista_para_facturar', 'Lista para facturar', estado_facturar, detalle_facturar),
        _item(
            'sesion_pagada',
            'Sesion pagada',
            'ok' if sesion.estado == 'PAGADA' else 'pendiente',
            'Pagada' if sesion.estado == 'PAGADA' else 'Pago pendiente',
        ),
    ]

    return {
        'sesion_id': sesion.pk,
        'estado_sesion': sesion.estado,
        'estado_global': _estado_global(items),
        'items': items,
        'proximo_paso': _proximo_paso(items),
    }
