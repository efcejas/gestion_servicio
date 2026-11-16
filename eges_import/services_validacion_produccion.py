"""Revisión de excepciones y confirmación del conjunto estadístico."""
from copy import deepcopy
from datetime import date
import hashlib
import json

from django.core.exceptions import ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.utils.dateparse import parse_date, parse_time

from .models import ImportBatch, NettermLote, NettermFila, ProduccionValidada
from .services_conciliacion import _codigo, construir_preview_conciliacion
from .services_produccion import construir_preview_produccion, realizada_netterm, resumir_practicas_produccion
from .services_bilateralidad import detectar_grupos_bilaterales, aplicar_decisiones_bilaterales
from .services_identificacion import completar_identificacion_practicas
from .services_procedimientos import (
    detectar_grupos_procedimientos, aplicar_decisiones_procedimientos,
    completar_decisiones_procedimientos,
    CODIGOS_COMPLEMENTARIOS,
)


MODALIDADES = ('ECO', 'TC', 'RM', 'RX', 'MAM', 'DX', 'SERIE')


def _excepcion_produccion(caso, fecha):
    fila = caso['netterm']
    motivos = list(caso['motivos'])
    if _codigo(fila['codigo']) in CODIGOS_COMPLEMENTARIOS:
        motivos.append('Biopsia o citología complementaria. Revisá su relación con un procedimiento guiado.')
    return {
        'id': str(fila['id']), 'practica': fila['practica'], 'fecha': fecha,
        'candidatas': caso['eges'], 'motivos': motivos,
        'modalidad': 'ECO' if fila['modalidad'] in {'DOP', 'ECOCAR', 'ECO_GENERAL'} else fila['modalidad'],
        'vigencia_incierta': fila['vigencia_incierta'],
    }


def preparar_validacion_produccion(*, batch_eges_ids, lote_netterm_ids, fecha_desde, fecha_hasta):
    try:
        desde = fecha_desde if isinstance(fecha_desde, date) else parse_date(str(fecha_desde))
        hasta = fecha_hasta if isinstance(fecha_hasta, date) else parse_date(str(fecha_hasta))
    except (ValueError, TypeError):
        raise ValidationError('Seleccioná un período válido.') from None
    if not desde or not hasta or desde > hasta:
        raise ValidationError('Seleccioná desde y hasta para confirmar la producción.')
    preview = construir_preview_conciliacion(
        batch_eges_ids=batch_eges_ids, lote_netterm_ids=lote_netterm_ids,
    )
    firma = hashlib.sha256(json.dumps([
        preview['firma_snapshot'], str(desde), str(hasta), 'PRODUCCION_REVISION_CLINICA_V7',
    ]).encode()).hexdigest()
    excepciones = []
    automaticas = 0
    elegibles = []
    for caso in preview['resultados']:
        fila = caso['netterm']
        if not fila or not realizada_netterm(fila) or fila['estado'] != 'DEFINITIVO':
            continue
        fecha = fila['fecha_realizacion']
        if not fecha or not desde <= fecha <= hasta:
            continue
        elegibles.append(fila)
        clara = (caso['identidad_coincidente'] and not caso['contradiccion_anulacion']) or caso['estado'] == 'SOLO_NETTERM'
        if (clara and not fila['vigencia_incierta'] and fila['modalidad'] != 'SIN_CLASIFICAR'
                and _codigo(fila['codigo']) not in CODIGOS_COMPLEMENTARIOS):
            automaticas += 1
            continue
        excepciones.append(_excepcion_produccion(caso, fecha))
    casos = {caso['netterm']['id']: caso for caso in preview['resultados'] if caso['netterm']}
    pacientes = dict(NettermFila.objects.filter(
        pk__in=casos,
    ).values_list('pk', 'normalizados_json'))
    procedimientos = detectar_grupos_procedimientos(
        [caso['netterm'] for caso in casos.values()], pacientes, casos,
        elegibles_ids={item['id'] for item in elegibles},
    )
    excepciones_ids = {item['id'] for item in excepciones}
    for grupo in procedimientos:
        for componente, candidatas in grupo['candidatas_componentes'].items():
            if len(candidatas) > 1 and componente not in excepciones_ids:
                excepciones.append(_excepcion_produccion(casos[int(componente)], grupo['fecha']))
                excepciones_ids.add(componente)
    for item in excepciones:
        origen = pacientes.get(int(item['id']), {})
        item['paciente'] = origen.get('paciente', '')
        item['documento'] = origen.get('documento', '')
        item['candidatas'] = [{**fila, 'accion': f"VINCULAR:{fila['id']}"} for fila in item['candidatas']]
    return {
        'preview': preview, 'firma': firma, 'excepciones': excepciones,
        'automaticas': automaticas, 'fecha_desde': desde, 'fecha_hasta': hasta,
        'grupos_bilaterales': detectar_grupos_bilaterales(elegibles, pacientes),
        'grupos_procedimientos': procedimientos,
    }


def construir_resultado_validado(preparacion, decisiones):
    if not isinstance(decisiones, dict):
        raise ValidationError('La selección de decisiones no es válida.')
    excepciones = {item['id']: item for item in preparacion['excepciones']}
    grupos = preparacion.get('grupos_bilaterales', [])
    procedimientos = preparacion.get('grupos_procedimientos', [])
    decisiones = completar_decisiones_procedimientos(procedimientos, set(excepciones), decisiones)
    if set(decisiones) != set(excepciones) | {grupo['id'] for grupo in grupos + procedimientos}:
        raise ValidationError('Resolvé todas las excepciones antes de confirmar la producción.')
    preview = deepcopy(preparacion['preview'])
    # Conservar la base EGES aunque la decisión sustituya la lista de candidatas.
    base_eges = {fila['id']: fila for caso in preview['resultados'] for fila in caso['eges']}
    utilizadas = {
        caso['eges'][0]['id'] for caso in preview['resultados']
        if caso['identidad_coincidente'] and caso['netterm']
        and str(caso['netterm']['id']) not in excepciones
    }
    for caso in preview['resultados']:
        fila = caso['netterm']
        if not fila or str(fila['id']) not in excepciones:
            continue
        decision = decisiones[str(fila['id'])]
        if not isinstance(decision, dict):
            raise ValidationError('Una decisión no es válida.')
        accion = str(decision.get('accion', ''))
        if accion == 'EXCLUIR':
            caso['netterm'] = None
            continue
        if fila['vigencia_incierta']:
            raise ValidationError('Las versiones divergentes requieren seleccionar fuentes consistentes o excluir el caso.')
        modalidad = decision.get('modalidad')
        if modalidad not in MODALIDADES:
            raise ValidationError('Indicá la modalidad de cada práctica aceptada.')
        fila['modalidad'] = modalidad
        if accion.startswith('VINCULAR:'):
            try:
                eges_id = int(accion.split(':', 1)[1])
            except ValueError:
                raise ValidationError('La candidata EGES no es válida.') from None
            candidatas = [eges for eges in caso['eges'] if eges['id'] == eges_id]
            if len(candidatas) != 1 or eges_id in utilizadas:
                raise ValidationError('Una práctica EGES sólo puede vincularse una vez y debe ser candidata.')
            if caso['contradiccion_anulacion'] or candidatas[0]['modalidad'] != modalidad:
                raise ValidationError('La vinculación tiene una contradicción de anulación o modalidad.')
            utilizadas.add(eges_id)
            caso.update(eges=candidatas, identidad_coincidente=True, estado='COINCIDENTE')
        elif accion == 'ADICIONAL':
            fila['adicional_independiente'] = True
            caso.update(eges=[], identidad_coincidente=False, estado='SOLO_NETTERM', contradiccion_anulacion=False)
        else:
            raise ValidationError('Seleccioná vincular, práctica adicional o excluir.')
    for fila in base_eges.values():
        preview['resultados'].append({'eges': [fila], 'netterm': None})
    resultado = construir_preview_produccion(
        batch_eges_ids=preview['batch_eges_ids'], lote_netterm_ids=preview['lote_netterm_ids'],
        fecha_desde=preparacion['fecha_desde'], fecha_hasta=preparacion['fecha_hasta'],
        incluir_practicas=True, preview_conciliado=preview,
    )
    practicas, auditoria = aplicar_decisiones_bilaterales(resultado['practicas'], grupos, decisiones)
    practicas, auditoria_procedimientos = aplicar_decisiones_procedimientos(practicas, procedimientos, decisiones)
    completar_identificacion_practicas(practicas)
    resultado.update(resumir_practicas_produccion(practicas))
    resultado['practicas'] = practicas
    resultado['agrupaciones_bilaterales'] = auditoria
    resultado['agrupaciones_procedimientos'] = auditoria_procedimientos
    resultado['version_reglas'] = 'PRODUCCION_REVISION_CLINICA_V7'
    return resultado


@transaction.atomic
def confirmar_produccion(*, usuario, firma_esperada, decisiones, **seleccion):
    if not usuario.is_superuser:
        raise ValidationError('La confirmación requiere permiso de administración.')
    list(ImportBatch.objects.select_for_update().filter(pk__in=seleccion['batch_eges_ids']))
    list(NettermLote.objects.select_for_update().filter(pk__in=seleccion['lote_netterm_ids']))
    preparacion = preparar_validacion_produccion(**seleccion)
    if preparacion['firma'] != firma_esperada:
        raise ValidationError('Las fuentes o los criterios cambiaron. Revisá el análisis actualizado antes de confirmar.')
    decisiones = completar_decisiones_procedimientos(
        preparacion['grupos_procedimientos'], {item['id'] for item in preparacion['excepciones']}, decisiones,
    )
    resultado = construir_resultado_validado(preparacion, decisiones)
    firma = hashlib.sha256(json.dumps([
        firma_esperada, decisiones,
    ], sort_keys=True).encode()).hexdigest()
    validacion, _ = ProduccionValidada.objects.get_or_create(
        firma=firma,
        defaults={
            'firma_fuentes': preparacion['preview']['firma_snapshot'],
            'lotes_eges_ids': preparacion['preview']['batch_eges_ids'],
            'lotes_netterm_ids': preparacion['preview']['lote_netterm_ids'],
            'fecha_desde': preparacion['fecha_desde'], 'fecha_hasta': preparacion['fecha_hasta'],
            'decisiones_json': decisiones, 'confirmado_por': usuario,
            'resultado_json': json.loads(json.dumps(resultado, cls=DjangoJSONEncoder)),
        },
    )
    return validacion


def leer_produccion_validada(validacion_id):
    validacion = (validacion_id if isinstance(validacion_id, ProduccionValidada)
                  else ProduccionValidada.objects.filter(pk=validacion_id).first())
    if not validacion:
        raise ValidationError('La producción confirmada no existe.')
    resultado = (validacion.resultado_json if isinstance(validacion_id, ProduccionValidada)
                 else deepcopy(validacion.resultado_json))
    for item in resultado['practicas']:
        item['fecha_produccion'] = parse_date(item['fecha_produccion'])
        hora = item['fila'].get('hora_turno')
        if hora:
            item['fila']['hora_turno'] = parse_time(hora)
    return resultado
