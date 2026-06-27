from .models import PreparacionLiquidacionRRHH, SolicitudRevisionHorarioRegistro
from .services_auditoria import auditar_residentes_eco_por_sesion, evaluar_gate_consistencia_sesion


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


def construir_checklist_cierre_sesion(sesion, user=None):
    siguiente_para_gate = {
        'ABIERTA': 'REVISION',
        'REVISION': 'CERRADA',
        'CERRADA': 'FACTURADA',
        'FACTURADA': 'PAGADA',
    }.get(sesion.estado, 'PAGADA')

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

    registro_ids = list(sesion.practicas.values_list('id', flat=True))
    solicitudes = SolicitudRevisionHorarioRegistro.objects.filter(registro_id__in=registro_ids)

    pendientes_count = solicitudes.filter(
        estado=SolicitudRevisionHorarioRegistro.ESTADO_PENDIENTE,
    ).count()
    aprobadas_sin_aplicar_count = solicitudes.filter(
        estado=SolicitudRevisionHorarioRegistro.ESTADO_APROBADA,
        fecha_aplicacion__isnull=True,
    ).count()

    auditoria = auditar_residentes_eco_por_sesion(sesion)
    auditoria_alertas = auditoria.get('alertas_rojas', 0) + auditoria.get('alertas_amarillas', 0)
    if auditoria_alertas:
        estado_auditoria = 'advertencia'
        detalle_auditoria = (
            f"{auditoria.get('alertas_rojas', 0)} roja(s), "
            f"{auditoria.get('alertas_amarillas', 0)} amarilla(s)"
        )
    else:
        estado_auditoria = 'ok'
        detalle_auditoria = 'Sin alertas'

    ultima_preparacion = (
        PreparacionLiquidacionRRHH.objects
        .filter(sesion_contable=sesion)
        .order_by('-version')
        .first()
    )
    if sesion.estado in {'ABIERTA', 'REVISION'}:
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

    rrhh_preparado = bool(
        ultima_preparacion
        and ultima_preparacion.estado == PreparacionLiquidacionRRHH.ESTADO_PREPARADO
    )
    sin_bloqueantes_operativos = (
        not gate['bloqueantes']
        and pendientes_count == 0
        and aprobadas_sin_aplicar_count == 0
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
        _item('auditoria_residentes_eco', 'Auditoria ECO', estado_auditoria, detalle_auditoria, auditoria_alertas),
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
