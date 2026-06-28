import hashlib
import json
from collections import defaultdict
from decimal import Decimal

from django.db.models import Max

from .models import (
    HistorialRecalculoSolicitudRevisionHorario,
    PreparacionLiquidacionRRHH,
    RegistroEstudiosPorMedico,
    SolicitudRevisionHorarioRegistro,
)
from .services import ROLES_RESIDENCIA
from .services_auditoria import evaluar_gate_consistencia_sesion


ESTADOS_SESION_PREPARACION_RRHH = {'CERRADA', 'FACTURADA', 'PAGADA'}


def _fecha_issue(value):
    return value.isoformat() if hasattr(value, 'isoformat') else value


def sesion_tiene_practicas_residencia(sesion):
    return RegistroEstudiosPorMedico.objects.filter(
        sesion_contable=sesion,
        medico__rol__in=ROLES_RESIDENCIA,
    ).exists()


def ultima_preparacion_rrhh(sesion):
    return (
        PreparacionLiquidacionRRHH.objects
        .filter(sesion_contable=sesion)
        .order_by('-version')
        .first()
    )


def evaluar_requisito_rrhh_para_facturar(sesion):
    requiere = sesion_tiene_practicas_residencia(sesion)
    ultima = ultima_preparacion_rrhh(sesion)

    if not requiere:
        return {
            'ok': True,
            'requiere_rrhh': False,
            'ultima_preparacion': ultima,
            'mensaje': 'No hay practicas de residencia en la sesion; RRHH no requerido.',
        }

    if not ultima:
        return {
            'ok': False,
            'requiere_rrhh': True,
            'ultima_preparacion': None,
            'mensaje': 'La sesion tiene practicas de residencia y requiere una preparacion RRHH en estado PREPARADO.',
        }

    if ultima.estado != PreparacionLiquidacionRRHH.ESTADO_PREPARADO:
        return {
            'ok': False,
            'requiere_rrhh': True,
            'ultima_preparacion': ultima,
            'mensaje': f'La ultima preparacion RRHH esta en estado {ultima.estado}; debe estar PREPARADO para facturar.',
        }

    return {
        'ok': True,
        'requiere_rrhh': True,
        'ultima_preparacion': ultima,
        'mensaje': f'Preparacion RRHH v{ultima.version} preparada.',
    }


def decimal_to_str(value):
    return str(Decimal(value or 0).quantize(Decimal('0.01')))


def calcular_hash_snapshot(snapshot):
    payload = json.dumps(snapshot, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()


def proxima_version_preparacion_rrhh(sesion):
    actual = (
        PreparacionLiquidacionRRHH.objects
        .filter(sesion_contable=sesion)
        .aggregate(max_version=Max('version'))['max_version']
        or 0
    )
    return actual + 1


def asunto_default_rrhh(sesion):
    return f"Liquidacion residencia - {sesion.mes:02d}/{sesion.año}"


def cuerpo_default_rrhh(snapshot):
    sesion = snapshot['sesion']
    total = snapshot['totales']['total_general']
    return (
        "Hola,\n\n"
        f"Se prepara la liquidacion de residencia correspondiente a "
        f"{sesion['mes']:02d}/{sesion['año']}.\n\n"
        f"Total general: ${total}\n"
        f"Profesionales incluidos: {snapshot['totales']['profesionales']}\n\n"
        "Este es un preview administrativo sin envio automatico.\n\n"
        "Saludos."
    )


def _validaciones_revision_horaria(sesion, registro_ids):
    bloqueantes = []
    advertencias = []
    items = []
    if not registro_ids:
        return bloqueantes, advertencias, items

    solicitudes = SolicitudRevisionHorarioRegistro.objects.filter(
        registro_id__in=registro_ids
    ).select_related('registro')

    pendientes = solicitudes.filter(
        estado=SolicitudRevisionHorarioRegistro.ESTADO_PENDIENTE
    ).count()
    if pendientes:
        mensaje = f'{pendientes} solicitud(es) de revision horaria pendientes en la sesion.'
        bloqueantes.append(mensaje)
        items.append({
            'tipo': 'revision_horaria_pendiente',
            'estado': 'bloqueante',
            'mensaje': mensaje,
            'sesion_id': sesion.pk,
            'estado_solicitud': SolicitudRevisionHorarioRegistro.ESTADO_PENDIENTE,
            'count': pendientes,
        })

    aprobadas_sin_aplicar = solicitudes.filter(
        estado=SolicitudRevisionHorarioRegistro.ESTADO_APROBADA,
        fecha_aplicacion__isnull=True,
    ).count()
    if aprobadas_sin_aplicar:
        mensaje = f'{aprobadas_sin_aplicar} solicitud(es) aprobadas sin aplicar en la sesion.'
        bloqueantes.append(mensaje)
        items.append({
            'tipo': 'revision_horaria_aprobada_sin_aplicar',
            'estado': 'bloqueante',
            'mensaje': mensaje,
            'sesion_id': sesion.pk,
            'estado_solicitud': SolicitudRevisionHorarioRegistro.ESTADO_APROBADA,
            'count': aprobadas_sin_aplicar,
        })

    rechazadas = solicitudes.filter(
        estado=SolicitudRevisionHorarioRegistro.ESTADO_RECHAZADA
    ).count()
    if rechazadas:
        mensaje = f'{rechazadas} solicitud(es) de revision horaria rechazadas en la sesion.'
        advertencias.append(mensaje)
        items.append({
            'tipo': 'revision_horaria_rechazada',
            'estado': 'advertencia',
            'mensaje': mensaje,
            'sesion_id': sesion.pk,
            'estado_solicitud': SolicitudRevisionHorarioRegistro.ESTADO_RECHAZADA,
            'count': rechazadas,
        })

    recalculos = HistorialRecalculoSolicitudRevisionHorario.objects.filter(
        registro_id__in=registro_ids
    ).count()
    if recalculos:
        mensaje = f'{recalculos} recalculo(s) puntual(es) B3 registrados en la sesion.'
        advertencias.append(mensaje)
        items.append({
            'tipo': 'recalculo_b3',
            'estado': 'advertencia',
            'mensaje': mensaje,
            'sesion_id': sesion.pk,
            'count': recalculos,
        })

    return bloqueantes, advertencias, items


def construir_snapshot_liquidacion_rrhh(sesion):
    registros = list(
        RegistroEstudiosPorMedico.objects.filter(
            sesion_contable=sesion,
            medico__rol__in=ROLES_RESIDENCIA,
        )
        .select_related('medico')
        .prefetch_related('registroestudio_set')
        .order_by('medico__last_name', 'medico__first_name', 'medico__id')
    )

    bloqueantes = []
    advertencias = []
    validaciones_items = []

    if sesion.estado not in ESTADOS_SESION_PREPARACION_RRHH:
        mensaje = 'La preparacion RRHH solo esta disponible desde sesiones CERRADA, FACTURADA o PAGADA.'
        bloqueantes.append(mensaje)
        validaciones_items.append({
            'tipo': 'sesion_estado_no_habilitado_rrhh',
            'estado': 'bloqueante',
            'mensaje': mensaje,
            'sesion_id': sesion.pk,
        })

    requiere_rrhh = bool(registros)
    if not registros:
        mensaje = 'No hay practicas de residencia en la sesion; RRHH no requerido.'
        advertencias.append(mensaje)
        validaciones_items.append({
            'tipo': 'rrhh_no_requerido',
            'estado': 'advertencia',
            'mensaje': mensaje,
            'sesion_id': sesion.pk,
        })

    for registro in registros:
        if registro.registroestudio_set.all() and Decimal(registro.monto_calculado or 0) <= Decimal('0'):
            mensaje = f'Registro #{registro.pk} con estudios asociados y monto_calculado <= 0.'
            bloqueantes.append(mensaje)
            validaciones_items.append({
                'tipo': 'monto_cero_con_estudios',
                'estado': 'bloqueante',
                'mensaje': mensaje,
                'registro_id': registro.pk,
                'fecha': _fecha_issue(registro.fecha_del_informe),
            })

    gate = evaluar_gate_consistencia_sesion(sesion, 'FACTURADA')
    bloqueantes.extend(gate['bloqueantes'])
    advertencias.extend(gate['advertencias'])
    validaciones_items.extend(gate.get('items', []))

    if sesion.estado == 'CERRADA':
        mensaje = 'La sesion esta CERRADA pero todavia no FACTURADA.'
        advertencias.append(mensaje)
        validaciones_items.append({
            'tipo': 'sesion_cerrada_no_facturada',
            'estado': 'advertencia',
            'mensaje': mensaje,
            'sesion_id': sesion.pk,
        })

    registro_ids = [registro.pk for registro in registros]
    rev_bloqueantes, rev_advertencias, rev_items = _validaciones_revision_horaria(sesion, registro_ids)
    bloqueantes.extend(rev_bloqueantes)
    advertencias.extend(rev_advertencias)
    validaciones_items.extend(rev_items)

    por_medico = {}
    for registro in registros:
        medico = registro.medico
        data = por_medico.setdefault(
            medico.pk,
            {
                'usuario_id': medico.pk,
                'apellido': medico.last_name or '',
                'nombre': medico.first_name or medico.username,
                'rol': medico.rol,
                'cantidad_practicas': 0,
                'monto_practicas': Decimal('0.00'),
                'total': Decimal('0.00'),
            },
        )
        data['cantidad_practicas'] += 1
        data['monto_practicas'] += Decimal(registro.monto_calculado or 0)
        data['total'] += Decimal(registro.monto_calculado or 0)

    profesionales = []
    for data in por_medico.values():
        profesionales.append({
            **data,
            'monto_practicas': decimal_to_str(data['monto_practicas']),
            'total': decimal_to_str(data['total']),
        })
    profesionales.sort(key=lambda item: (item['apellido'], item['nombre'], item['usuario_id']))

    total_practicas = sum(item['cantidad_practicas'] for item in profesionales)
    monto_practicas = sum(Decimal(item['monto_practicas']) for item in profesionales)

    return {
        'sesion': {
            'id': sesion.pk,
            'mes': sesion.mes,
            'año': sesion.año,
            'estado': sesion.estado,
            'requiere_rrhh': requiere_rrhh,
        },
        'profesionales': profesionales,
        'totales': {
            'profesionales': len(profesionales),
            'cantidad_practicas': total_practicas,
            'monto_practicas': decimal_to_str(monto_practicas),
            'cantidad_guardias': 0,
            'monto_guardias': decimal_to_str(0),
            'total_general': decimal_to_str(monto_practicas),
        },
        'validaciones': {
            'bloqueantes': bloqueantes,
            'advertencias': advertencias,
            'items': validaciones_items,
        },
    }
