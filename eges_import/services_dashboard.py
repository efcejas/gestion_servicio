"""Base EGES completa y aportes Netterm aprobados por período y modalidad."""
from collections import Counter
import hashlib
import json

from django.core.exceptions import ValidationError

from .models import EgesRow, ImportBatch, NettermFila, NettermLote, ProduccionValidada
from .services_conciliacion import _dni, _modalidad_consolidada, _texto_normalizado
from .services_identificacion import _hc_netterm
from .services_produccion import ETIQUETAS_PENDIENTES, construir_preview_produccion, resumir_practicas_produccion
from .services_validacion_produccion import leer_produccion_validada


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


def _base_eges_dashboard(batches):
    resultado = None
    firmas = []
    for batch_id in sorted(batches):
        parcial = construir_preview_produccion(
            batch_eges_ids=[batch_id], lote_netterm_ids=[],
            permitir_fuente_unica=True, incluir_practicas=True,
        )
        firmas.append(parcial['firma_snapshot'])
        if resultado is None:
            resultado = parcial
            continue
        resultado['practicas'].extend(parcial['practicas'])
        for clave in ('pendientes', 'excluidos', 'estados_eges'):
            resultado[clave] = dict(Counter(resultado[clave]) + Counter(parcial[clave]))
    if resultado is None:
        raise ValidationError('Cargá un lote EGES para ver la producción.')
    resultado['pendientes_detalle'] = [{'motivo': ETIQUETAS_PENDIENTES[motivo], 'cantidad': cantidad}
                                      for motivo, cantidad in resultado['pendientes'].items()]
    anuladas = sum(resultado['excluidos'].values())
    resultado['excluidos_detalle'] = [{'motivo': 'EGES: anuladas', 'cantidad': anuladas}] if anuladas else []
    resultado['batch_eges_ids'] = sorted(batches)
    resultado['firma_snapshot'] = hashlib.sha256(json.dumps(firmas).encode()).hexdigest()
    return resultado


def construir_produccion_dashboard(*, incluir_netterm=False):
    batches = set(ImportBatch.objects.values_list('pk', flat=True))
    resultado = _base_eges_dashboard(batches)
    lotes_netterm = set(NettermLote.objects.values_list('pk', flat=True))
    validaciones = []
    advertencias = []
    for validacion in ProduccionValidada.objects.all():
        if (not set(validacion.lotes_eges_ids).issubset(batches)
                or not set(validacion.lotes_netterm_ids).issubset(lotes_netterm)):
            continue
        snapshot = leer_produccion_validada(validacion.pk)
        modalidades = set(EgesRow.objects.filter(batch_id__in=validacion.lotes_eges_ids).order_by()
                          .values_list('modalidad', flat=True).distinct())
        modalidades.update(_modalidad_consolidada(modalidad) for modalidad in
                           NettermFila.objects.filter(lote_id__in=validacion.lotes_netterm_ids).order_by()
                           .values_list('modalidad', flat=True).distinct())
        modalidades.update(item['fila']['modalidad'] for item in snapshot['practicas'])
        if any(item['fila']['modalidad'] == 'RX' and 'unidades_estadisticas' not in item
               for item in snapshot['practicas']):
            modalidades.discard('RX')
            snapshot['practicas'] = [item for item in snapshot['practicas']
                                     if item['fila']['modalidad'] != 'RX']
            advertencias.append('Hay una validación anterior de RX que requiere revisar cantidades. '
                                'Revalidá ese período para incorporar su aporte Netterm.')
        validaciones.append({'validacion': validacion, 'snapshot': snapshot, 'modalidades': modalidades})
    cubiertos = {item['fila']['id'] for info in validaciones for item in info['snapshot']['practicas']
                 if 'fecha_turno' in item['fila']
                 and _validacion_del_estudio(validaciones, item['fecha_produccion'], item['fila']['modalidad']) is info}
    base = {}
    afectados = set()
    for item in resultado['practicas']:
        fila = item['fila']
        if fila['id'] in cubiertos:
            continue
        info = _validacion_del_estudio(validaciones, item['fecha_produccion'], fila['modalidad'])
        if info and fila['lote_id'] in info['validacion'].lotes_eges_ids:
            continue
        base[fila['id']] = item
        if info:
            afectados.add((info['validacion'].pk, fila['modalidad']))
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
        vistos_nt.update(_clave_estudio_netterm(fila) for fila in NettermFila.objects.filter(
            lote_id__in=validacion.lotes_netterm_ids,
            fecha_realizacion__gte=validacion.fecha_desde,
            fecha_realizacion__lte=validacion.fecha_hasta,
        ).only('clave_candidata_sha256', 'normalizados_json'))
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
