"""Base EGES completa y aportes Netterm aprobados por período y modalidad."""
from collections import Counter, defaultdict
import hashlib
import json

from django.core.exceptions import ValidationError

from .models import EgesRow, ImportBatch, NettermFila, NettermLote, ProduccionValidada
from .services_conciliacion import _datos_eges, _dni, _modalidad_consolidada, _texto_normalizado
from .services_identificacion import _hc_netterm
from .services_produccion import ETIQUETAS_PENDIENTES, realizada_eges, resumir_practicas_produccion
from .services_procedimientos import MODALIDADES_GUIADAS
from .services_unidades import aplicar_unidades_rx
from .services_validacion_produccion import leer_produccion_validada
from .querysets import filas_eges_produccion


def _validacion_del_estudio(validaciones, fecha, modalidad):
    for info in validaciones:
        validacion = info['validacion']
        if (validacion.fecha_desde <= fecha <= validacion.fecha_hasta
                and modalidad in info['modalidades']):
            return info
    return None


def _clave_estudio_netterm(fila):
    datos = fila.normalizados_json
    hc = _hc_netterm(datos.get('historia_clinica'))
    documento = _dni(datos.get('documento')) or _texto_normalizado(datos.get('documento'))
    if hc:
        paciente = ('HC', _dni(hc) or hc)
    elif documento:
        paciente = ('DOC', documento)
    else:
        paciente = ('OBSERVACION', fila.pk)
    return fila.clave_candidata_sha256, paciente


def _base_eges_dashboard(batches, validaciones, cubiertos):
    if not batches:
        raise ValidationError('Cargá un lote EGES para ver la producción.')
    practicas, afectados = [], set()
    pendientes, excluidos, estados = Counter(), Counter(), Counter()
    firma = hashlib.sha256()
    filas = filas_eges_produccion().filter(batch_id__in=batches).only(
        'pk', 'batch_id', 'dni_paciente', 'codigo_practica', 'fecha_turno',
        'hora_turno', 'estado_turno', 'practica', 'estado_informe', 'modalidad', 'cantidad',
    ).order_by('pk')
    for origen in filas.iterator(chunk_size=500):
        fila = _datos_eges(origen)
        firma.update(json.dumps(fila, sort_keys=True, default=str).encode())
        estado = _texto_normalizado(fila['estado'])
        estados[estado or 'SIN ESTADO'] += 1
        if estado in {'ANULADO', 'CANCELADO'}:
            excluidos['eges_anulado'] += 1
            continue
        motivo = None
        if not fila['fecha_turno']:
            motivo = 'eges_sin_fecha'
        elif fila['modalidad'] in {'OTROS', 'SIN_CLASIFICAR', ''}:
            motivo = 'eges_modalidad'
        elif not realizada_eges(fila):
            motivo = 'eges_realizacion_sin_confirmar'
        elif estado != 'INFORMADO':
            motivo = 'eges_informe_sin_confirmar'
        if motivo:
            pendientes[motivo] += 1
            continue
        if fila['id'] in cubiertos:
            continue
        info = _validacion_del_estudio(validaciones, fila['fecha_turno'], fila['modalidad'])
        if info and fila['lote_id'] in info['validacion'].lotes_eges_ids:
            continue
        if info:
            afectados.add((info['validacion'].pk, fila['modalidad']))
        item = {'fila': fila, 'incluida': True, 'fuente': 'EGES', 'informada': True,
                'fecha_produccion': fila['fecha_turno']}
        modalidad_guiada = MODALIDADES_GUIADAS.get(str(fila['codigo']).removesuffix('/0'))
        if modalidad_guiada and modalidad_guiada == fila['modalidad']:
            item.update(procedimiento_guiado=True, procedimiento_guiado_modalidad=modalidad_guiada)
        practicas.append(item)
    resultado = {
        'practicas': aplicar_unidades_rx(practicas), 'pendientes': dict(pendientes),
        'excluidos': dict(excluidos), 'estados_eges': dict(estados), 'estados_netterm': {},
        'provisional': True, 'version_reglas': 'BASE_EGES_DASHBOARD_V2',
        'insumos_netterm_excluidos': 0, 'fecha_desde': None, 'fecha_hasta': None,
        'vinculaciones_humanas_consumidas': 0, 'vinculaciones_rechazadas_consumidas': 0,
    }
    resultado['pendientes_detalle'] = [{'motivo': ETIQUETAS_PENDIENTES[motivo], 'cantidad': cantidad}
                                      for motivo, cantidad in resultado['pendientes'].items()]
    anuladas = sum(resultado['excluidos'].values())
    resultado['excluidos_detalle'] = [{'motivo': 'EGES: anuladas', 'cantidad': anuladas}] if anuladas else []
    resultado['batch_eges_ids'] = sorted(batches)
    resultado['firma_snapshot'] = firma.hexdigest()
    return resultado, afectados


def construir_produccion_dashboard(*, incluir_netterm=False):
    batches = set(ImportBatch.objects.values_list('pk', flat=True))
    lotes_netterm = set(NettermLote.objects.values_list('pk', flat=True))
    validaciones = []
    advertencias = []
    for validacion in ProduccionValidada.objects.defer('decisiones_json').iterator(chunk_size=1):
        if (not set(validacion.lotes_eges_ids).issubset(batches)
                or not set(validacion.lotes_netterm_ids).issubset(lotes_netterm)):
            continue
        snapshot = leer_produccion_validada(validacion)
        modalidades = {item['fila']['modalidad'] for item in snapshot['practicas']}
        rx_incompleto = any(item['fila']['modalidad'] == 'RX'
                            and 'unidades_estadisticas' not in item
                            for item in snapshot['practicas'])
        # El objeto de metadatos deja de retener el JSON completo ya leído.
        del validacion.resultado_json
        if rx_incompleto:
            modalidades.discard('RX')
            snapshot['practicas'] = [item for item in snapshot['practicas']
                                     if item['fila']['modalidad'] != 'RX']
            advertencias.append('Hay una validación anterior de RX que requiere revisar cantidades. '
                                'Revalidá ese período para incorporar su aporte Netterm.')
        validaciones.append({
            'validacion': validacion,
            'snapshot': snapshot,
            'modalidades': modalidades,
            'rx_incompleto': rx_incompleto,
        })

    batches_validados = {batch_id for info in validaciones
                         for batch_id in info['validacion'].lotes_eges_ids}
    lotes_netterm_validados = {lote_id for info in validaciones
                               for lote_id in info['validacion'].lotes_netterm_ids}
    modalidades_eges = defaultdict(set)
    for batch_id, modalidad in EgesRow.objects.filter(batch_id__in=batches_validados).order_by(
    ).values_list('batch_id', 'modalidad').distinct().iterator(chunk_size=500):
        modalidades_eges[batch_id].add(modalidad)
    modalidades_netterm = defaultdict(set)
    for lote_id, modalidad in NettermFila.objects.filter(lote_id__in=lotes_netterm_validados).order_by(
    ).values_list('lote_id', 'modalidad').distinct().iterator(chunk_size=500):
        modalidades_netterm[lote_id].add(_modalidad_consolidada(modalidad))
    for info in validaciones:
        validacion = info['validacion']
        info['modalidades'].update(
            modalidad for batch_id in validacion.lotes_eges_ids
            for modalidad in modalidades_eges[batch_id]
        )
        info['modalidades'].update(
            modalidad for lote_id in validacion.lotes_netterm_ids
            for modalidad in modalidades_netterm[lote_id]
        )
        if info['rx_incompleto']:
            info['modalidades'].discard('RX')

    cubiertos = {item['fila']['id'] for info in validaciones for item in info['snapshot']['practicas']
                 if 'fecha_turno' in item['fila']
                 and _validacion_del_estudio(validaciones, item['fecha_produccion'], item['fila']['modalidad']) is info}
    resultado, afectados = _base_eges_dashboard(batches, validaciones, cubiertos)
    base = {item['fila']['id']: item for item in resultado.pop('practicas')}
    nt_ids = {item.get('netterm', item['fila'])['id']
              for info in validaciones for item in info['snapshot']['practicas']
              if item.get('netterm') or 'fecha_pedido' in item['fila']}
    claves_nt = {fila.pk: _clave_estudio_netterm(fila) for fila in
                 NettermFila.objects.filter(pk__in=nt_ids).only('clave_candidata_sha256', 'normalizados_json')}
    aportes, vistos_nt, vistos_eges, versiones = [], set(), set(), []
    for info in validaciones:
        validacion = info['validacion']
        utilizada = False
        claves_version, eges_version = set(), set()
        for item in info['snapshot']['practicas']:
            fila = item['fila']
            if _validacion_del_estudio(validaciones, item['fecha_produccion'], fila['modalidad']) is not info:
                continue
            es_eges = 'fecha_turno' in fila
            nt = item.get('netterm', fila) if item.get('netterm') or not es_eges else None
            clave_nt = claves_nt.get(nt['id']) if nt else None
            if (clave_nt and clave_nt in vistos_nt) or (es_eges and fila['id'] in vistos_eges):
                continue
            utilizada = True
            if es_eges:
                base.pop(fila['id'], None)
                eges_version.add(fila['id'])
            if clave_nt:
                claves_version.add(clave_nt)
            if item['fuente'] == 'EGES':
                base[fila['id']] = item
            elif (validacion.pk, fila['modalidad']) not in afectados:
                aportes.append(item)
        # Una observación actualizada puede mover un estudio entre dos períodos.
        # Su versión anterior queda sustituida también si la nueva revisión lo excluyó.
        vistos_eges.update(eges_version)
        vistos_nt.update(claves_version)
        filas_version = NettermFila.objects.filter(
            lote_id__in=validacion.lotes_netterm_ids,
            fecha_realizacion__gte=validacion.fecha_desde,
            fecha_realizacion__lte=validacion.fecha_hasta,
        ).only('clave_candidata_sha256', 'normalizados_json')
        vistos_nt.update(_clave_estudio_netterm(fila)
                         for fila in filas_version.iterator(chunk_size=500))
        if utilizada:
            versiones.append(validacion.pk)
        modalidades_afectadas = sorted(modalidad for pk, modalidad in afectados if pk == validacion.pk)
        if modalidades_afectadas:
            nombres = dict(EgesRow.MODALIDAD_CHOICES)
            texto = ', '.join(nombres.get(modalidad, modalidad) for modalidad in modalidades_afectadas)
            advertencias.append(f'Hay nuevos lotes EGES de {texto} dentro de un período conciliado. '
                                'La base EGES está incluida. Revalidá ese aporte Netterm para incorporarlo.')
    practicas = list(base.values()) + (aportes if incluir_netterm else [])
    resultado.update(resumir_practicas_produccion(practicas))
    resultado.update({
        'practicas': practicas, 'aportes_disponibles': aportes,
        'dashboard_global': True, 'incluir_netterm': incluir_netterm,
        'validaciones_dashboard': versiones, 'advertencias_dashboard': advertencias,
        'lote_netterm_ids': sorted({pk for info in validaciones for pk in info['validacion'].lotes_netterm_ids}),
        'firma_snapshot': hashlib.sha256(json.dumps([
            resultado['firma_snapshot'], versiones, incluir_netterm,
        ]).encode()).hexdigest(),
    })
    if incluir_netterm:
        anuladas = NettermFila.objects.filter(lote_id__in=resultado['lote_netterm_ids'], anulado=True).count()
        if anuladas:
            resultado['excluidos_detalle'].append({
                'motivo': 'Netterm: observaciones anuladas archivadas', 'cantidad': anuladas,
            })
    return resultado
