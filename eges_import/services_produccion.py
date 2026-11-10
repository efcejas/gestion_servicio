"""Produccion respaldada por origen, separada de informes y de cantidades economicas."""
from collections import Counter

from .services_conciliacion import construir_preview_conciliacion, _texto_normalizado


ESTADOS_REALIZADOS_EGES = {'INFORMADO', 'FIN PRACTICA', 'ENTREGADO SIN INFORME'}
ETIQUETAS_PENDIENTES = {
    'eges_sin_fecha': 'EGES: falta fecha de turno',
    'eges_modalidad': 'EGES: modalidad sin clasificar',
    'eges_realizacion_sin_confirmar': 'EGES: realización sin confirmar',
    'netterm_vigencia': 'Netterm: versiones divergentes sin vigencia confirmada',
    'netterm_anulacion_contradictoria': 'Netterm: anulación contradictoria con EGES',
    'netterm_modalidad': 'Netterm: modalidad sin clasificar',
    'netterm_sin_fecha': 'Netterm: falta fecha de pedido',
    'netterm_realizacion_sin_confirmar': 'Netterm: realización sin confirmar',
    'netterm_correspondencia': 'Netterm: correspondencia ambigua o incompatible',
}


def realizada_eges(fila):
    return _texto_normalizado(fila['estado']) in ESTADOS_REALIZADOS_EGES


def realizada_netterm(fila):
    # La presencia en una exportacion no basta: contiene pendientes y anulaciones.
    if fila['anulado'] or fila['estado_realizacion'] == 'PENDIENTE':
        return False
    return bool(fila['fecha_realizacion']) or fila['estado'] in {'DEFINITIVO', 'NO_DEFINITIVO', 'ESCRITO'}


def construir_preview_produccion(**seleccion):
    preview = construir_preview_conciliacion(**seleccion)
    practicas = {}
    pendientes, excluidos = Counter(), Counter()
    estados_eges, estados_netterm = Counter(), Counter()
    for caso in preview['resultados']:
        for fila in caso['eges']:
            clave = ('EGES', fila['id'])
            if clave in practicas:
                continue
            # Una fila EGES puede estar referenciada por varios casos ambiguos.
            practicas[clave] = {'fila': fila, 'incluida': False}
    for item in practicas.values():
        fila = item['fila']
        estado = _texto_normalizado(fila['estado'])
        estados_eges[estado or 'SIN ESTADO'] += 1
        if estado in {'ANULADO', 'CANCELADO'}:
            excluidos['eges_anulado'] += 1
        elif not fila['fecha_turno']:
            pendientes['eges_sin_fecha'] += 1
        elif fila['modalidad'] in {'OTROS', 'SIN_CLASIFICAR', ''}:
            pendientes['eges_modalidad'] += 1
        elif realizada_eges(fila):
            item.update(incluida=True, fuente='EGES', informada=estado == 'INFORMADO')
        else:
            pendientes['eges_realizacion_sin_confirmar'] += 1
    for caso in preview['resultados']:
        fila = caso['netterm']
        if not fila:
            continue
        estados_netterm[fila['estado']] += 1
        if fila['vigencia_incierta']:
            pendientes['netterm_vigencia'] += 1
        elif fila['anulado']:
            excluidos['netterm_anulado'] += 1
        elif caso['contradiccion_anulacion']:
            pendientes['netterm_anulacion_contradictoria'] += 1
        elif fila['modalidad'] == 'SIN_CLASIFICAR':
            pendientes['netterm_modalidad'] += 1
        elif not fila['fecha_pedido']:
            pendientes['netterm_sin_fecha'] += 1
        elif not realizada_netterm(fila):
            pendientes['netterm_realizacion_sin_confirmar'] += 1
        elif caso['identidad_coincidente']:
            item = practicas[('EGES', caso['eges'][0]['id'])]
            if not item['incluida']:
                # Netterm puede confirmar actividad aun cuando EGES no la confirma.
                item.update(incluida=True, fuente='NETTERM', informada=False)
                pendientes['eges_realizacion_sin_confirmar'] -= 1
            item['informada'] = item['informada'] or fila['estado'] == 'DEFINITIVO'
        elif caso['estado'] == 'SOLO_NETTERM':
            modalidad = 'ECO' if fila['modalidad'] in {'ECO_GENERAL', 'DOP', 'ECOCAR'} else fila['modalidad']
            practicas[('NETTERM', fila['id'])] = {
                'fila': {**fila, 'modalidad': modalidad}, 'incluida': True,
                'fuente': 'NETTERM', 'informada': fila['estado'] == 'DEFINITIVO',
            }
        else:
            pendientes['netterm_correspondencia'] += 1
    incluidos = [p for p in practicas.values() if p['incluida']]
    produccion, informadas = Counter(), Counter()
    pacientes = set()
    sin_identidad = 0
    for p in incluidos:
        produccion[(p['fila']['modalidad'], p['fuente'])] += 1
        informadas[p['fila']['modalidad']] += p['informada']
        if p['fila']['paciente_clave']:
            pacientes.add(p['fila']['paciente_clave'])
        else:
            sin_identidad += 1
    total = len(incluidos)
    finalizadas = sum(informadas.values())
    modalidades = sorted({m for m, _ in produccion})
    return {
        'version_reglas': 'PRODUCCION_RESPALDADA_V1', 'provisional': True,
        'total_produccion': total,
        'base_eges': sum(n for (m, f), n in produccion.items() if f == 'EGES'),
        'aporte_netterm': sum(n for (m, f), n in produccion.items() if f == 'NETTERM'),
        'informadas_confirmadas': finalizadas,
        'sin_informe_confirmado': total - finalizadas,
        'tasa_finalizacion': round(100 * finalizadas / total, 1) if total else None,
        'pacientes_unicos_identificables': len(pacientes),
        'practicas_sin_identidad': sin_identidad,
        'por_modalidad': [
            {'modalidad': m, 'eges': produccion[(m, 'EGES')], 'netterm': produccion[(m, 'NETTERM')],
             'total': produccion[(m, 'EGES')] + produccion[(m, 'NETTERM')], 'informadas': informadas[m]}
            for m in modalidades
        ],
        'pendientes': {k: v for k, v in pendientes.items() if v > 0},
        'pendientes_detalle': [{'motivo': ETIQUETAS_PENDIENTES[k], 'cantidad': v}
                              for k, v in pendientes.items() if v > 0],
        'excluidos': dict(excluidos),
        'excluidos_detalle': [{'motivo': 'EGES: anuladas' if k == 'eges_anulado' else 'Netterm: anuladas', 'cantidad': v}
                             for k, v in excluidos.items()],
        'estados_eges': dict(estados_eges), 'estados_netterm': dict(estados_netterm),
        'insumos_netterm_excluidos': preview['resumen']['insumos_netterm_excluidos'],
        'fecha_desde': preview['fecha_desde'], 'fecha_hasta': preview['fecha_hasta'],
        'firma_snapshot': preview['firma_snapshot'],
        'batch_eges_ids': preview['batch_eges_ids'], 'lote_netterm_ids': preview['lote_netterm_ids'],
    }
