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
    if not registro_ids:
        return bloqueantes, advertencias

    solicitudes = SolicitudRevisionHorarioRegistro.objects.filter(
        registro_id__in=registro_ids
    ).select_related('registro')

    pendientes = solicitudes.filter(
        estado=SolicitudRevisionHorarioRegistro.ESTADO_PENDIENTE
    ).count()
    if pendientes:
        bloqueantes.append(
            f'{pendientes} solicitud(es) de revision horaria pendientes en la sesion.'
        )

    aprobadas_sin_aplicar = solicitudes.filter(
        estado=SolicitudRevisionHorarioRegistro.ESTADO_APROBADA,
        fecha_aplicacion__isnull=True,
    ).count()
    if aprobadas_sin_aplicar:
        bloqueantes.append(
            f'{aprobadas_sin_aplicar} solicitud(es) aprobadas sin aplicar en la sesion.'
        )

    rechazadas = solicitudes.filter(
        estado=SolicitudRevisionHorarioRegistro.ESTADO_RECHAZADA
    ).count()
    if rechazadas:
        advertencias.append(
            f'{rechazadas} solicitud(es) de revision horaria rechazadas en la sesion.'
        )

    recalculos = HistorialRecalculoSolicitudRevisionHorario.objects.filter(
        registro_id__in=registro_ids
    ).count()
    if recalculos:
        advertencias.append(
            f'{recalculos} recalculo(s) puntual(es) B3 registrados en la sesion.'
        )

    return bloqueantes, advertencias


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

    if sesion.estado not in ESTADOS_SESION_PREPARACION_RRHH:
        bloqueantes.append(
            'La preparacion RRHH solo esta disponible desde sesiones CERRADA, FACTURADA o PAGADA.'
        )

    if not registros:
        bloqueantes.append('Sesion vacia para roles de residencia.')

    for registro in registros:
        if registro.registroestudio_set.all() and Decimal(registro.monto_calculado or 0) <= Decimal('0'):
            bloqueantes.append(
                f'Registro #{registro.pk} con estudios asociados y monto_calculado <= 0.'
            )

    gate = evaluar_gate_consistencia_sesion(sesion, 'FACTURADA')
    bloqueantes.extend(gate['bloqueantes'])
    advertencias.extend(gate['advertencias'])

    if sesion.estado == 'CERRADA':
        advertencias.append('La sesion esta CERRADA pero todavia no FACTURADA.')

    registro_ids = [registro.pk for registro in registros]
    rev_bloqueantes, rev_advertencias = _validaciones_revision_horaria(sesion, registro_ids)
    bloqueantes.extend(rev_bloqueantes)
    advertencias.extend(rev_advertencias)

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
        },
    }
