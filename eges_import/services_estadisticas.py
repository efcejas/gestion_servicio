"""Una poblacion conciliada para indicadores, graficos y PDF del tablero."""
from collections import Counter
from datetime import timedelta

from django.core.exceptions import ValidationError

from .models import EgesRow, ImportBatch, NettermFila, NombreObraSocial
from .services import _valor_valido, agrupar_periodo
from .services_produccion import construir_preview_produccion


COLORES = {'TC': '#3b82f6', 'RM': '#9333ea', 'RX': '#22c55e', 'DX': '#f97316',
           'MAM': '#ec4899', 'ECO': '#eab308', 'SERIE': '#14b8a6', 'OTROS': '#6b7280'}
SIN_DATO = 'Sin dato'


def _grafico(labels, valores, color='#3b82f6'):
    return {'labels': labels, 'datasets': [{'label': 'Prácticas respaldadas', 'data': valores,
                                           'backgroundColor': color, 'borderColor': color}]}


def _ranking(conteo):
    conocidos = sorted(((clave, total) for clave, total in conteo.items() if clave != SIN_DATO),
                       key=lambda item: (-item[1], item[0]))
    resultado = conocidos[:10]
    if len(conocidos) > 10:
        resultado.append(('Otros', sum(total for _, total in conocidos[10:])))
    if conteo[SIN_DATO]:
        resultado.append((SIN_DATO, conteo[SIN_DATO]))
    return resultado


def _poblacion(seleccion, modalidades):
    resultado = construir_preview_produccion(**seleccion, permitir_fuente_unica=True, incluir_practicas=True)
    practicas = resultado.pop('practicas')
    if modalidades is not None:
        practicas = [item for item in practicas if item['fila']['modalidad'] in modalidades]
    eges_ids = {item['fila']['id'] for item in practicas if 'fecha_turno' in item['fila']}
    netterm_ids = {item.get('netterm', item['fila'])['id'] for item in practicas
                   if item.get('netterm') or 'fecha_pedido' in item['fila']}
    eges = {fila.pk: fila for fila in EgesRow.objects.filter(pk__in=eges_ids).only(
        'pk', 'medico_informante', 'sub_modalidad', 'obra_social', 'codigo_obra_social',
    )}
    netterm = dict(NettermFila.objects.filter(pk__in=netterm_ids).values_list('pk', 'normalizados_json'))
    nombres_os = dict(NombreObraSocial.objects.values_list('codigo', 'nombre'))
    filas = []
    for item in practicas:
        fila = item['fila']
        original = eges.get(fila['id']) if 'fecha_turno' in fila else None
        nt_fila = item.get('netterm', fila)
        nt = netterm.get(nt_fila['id'], {}) if item.get('netterm') or 'fecha_pedido' in fila else {}
        medico = original.medico_informante if original else ''
        medico = medico if _valor_valido(medico) else nt.get('informante', '')
        medico = ' '.join(sorted(str(medico).upper().split())) if _valor_valido(medico) else SIN_DATO
        os_codigo = (original.obra_social or original.codigo_obra_social) if original else None
        os_codigo = os_codigo or nt.get('obra_social')
        subtipo = original.sub_modalidad if original else None
        subtipo = subtipo or {'DOP': 'DOPPLER', 'ECOCAR': 'ECOCARDIO'}.get(nt_fila.get('modalidad'))
        filas.append({
            'fecha': fila.get('fecha_turno') or fila.get('fecha_pedido'),
            'hora': fila.get('hora_turno'),
            'modalidad': fila['modalidad'], 'sub_modalidad': subtipo,
            'paciente': fila['paciente_clave'], 'informada': item['informada'],
            'fuente': item['fuente'], 'medico': medico,
            'obra_social': nombres_os.get(os_codigo, os_codigo) or SIN_DATO,
            'practica': fila['practica'],
        })
    return resultado, filas


def _indicadores(filas, desde, hasta):
    pacientes = {fila['paciente'] for fila in filas if fila['paciente']}
    sin_identidad = sum(not fila['paciente'] for fila in filas)
    fechas = [fila['fecha'] for fila in filas]
    desde = desde or (min(fechas) if fechas else None)
    hasta = hasta or (max(fechas) if fechas else None)
    habiles = sum((desde + timedelta(days=dia)).weekday() < 5
                  for dia in range((hasta - desde).days + 1)) if desde and hasta else 0
    total = len(filas)
    informadas = sum(fila['informada'] for fila in filas)
    return {
        'pacientes_atendidos': len(pacientes), 'practicas_realizadas': total,
        'practicas_por_paciente': round(total / len(pacientes), 2) if pacientes and not sin_identidad else None,
        'total_finalizados': informadas, 'total_pendientes': total - informadas,
        'promedio_dia': round(total / habiles, 1) if habiles else None,
        'tasa_conversion': round(100 * informadas / total, 1) if total else None,
        'rx_sin_informe': sum(fila['modalidad'] == 'RX' and not fila['informada'] for fila in filas),
        'sin_identidad': sin_identidad,
    }


def _metrica(actual, anterior):
    if actual is None or anterior is None:
        return dict(actual=actual, anterior=anterior, absoluta=None, porcentaje=None, estado='SIN_DATO')
    diferencia = actual - anterior
    estado = 'AUMENTO' if diferencia > 0 else 'DISMINUCION' if diferencia < 0 else 'SIN_CAMBIOS'
    return dict(actual=actual, anterior=anterior, absoluta=round(diferencia, 2),
                porcentaje=round(100 * diferencia / anterior, 1) if anterior else None, estado=estado)


def construir_estadisticas_fuentes(*, batch_eges_ids, lote_netterm_ids, fecha_desde=None,
                                   fecha_hasta=None, modalidades=None, agrupacion='mes'):
    if not batch_eges_ids and not lote_netterm_ids:
        raise ValidationError('Seleccioná al menos un lote de origen y aplicá los filtros.')
    if agrupacion not in {'dia', 'semana', 'mes'}:
        raise ValidationError('La agrupación no es válida.')
    if modalidades is not None and not set(modalidades).issubset(COLORES):
        raise ValidationError('La selección de modalidades no es válida.')
    seleccion = dict(batch_eges_ids=batch_eges_ids, lote_netterm_ids=lote_netterm_ids,
                     fecha_desde=fecha_desde, fecha_hasta=fecha_hasta)
    produccion, filas = _poblacion(seleccion, modalidades)
    kpis = _indicadores(filas, fecha_desde, fecha_hasta)
    nombres = dict(EgesRow.MODALIDAD_CHOICES)
    conteo = Counter(fila['modalidad'] for fila in filas)
    mods = sorted(conteo)
    temporal = Counter((agrupar_periodo(fila['fecha'], agrupacion), fila['modalidad']) for fila in filas)
    periodos = sorted({periodo for periodo, _ in temporal})
    formato = '%d/%m/%Y' if agrupacion == 'dia' else 'Sem %d/%m/%Y' if agrupacion == 'semana' else '%m/%Y'
    datasets = [{'label': nombres.get(mod, mod), 'data': [temporal[(periodo, mod)] for periodo in periodos],
                 'borderColor': COLORES[mod], 'backgroundColor': COLORES[mod]} for mod in mods]
    semana = Counter(fila['fecha'].weekday() for fila in filas)
    franjas = Counter(fila['hora'].hour // 2 if fila['hora'] else 12 for fila in filas)
    sub_nombres = dict(EgesRow.SUB_MODALIDAD_ECO_CHOICES)
    sub = Counter(sub_nombres.get(fila['sub_modalidad'], fila['sub_modalidad']) or SIN_DATO
                  for fila in filas if fila['modalidad'] == 'ECO')
    medicos = _ranking(Counter(fila['medico'] for fila in filas))
    os = _ranking(Counter(fila['obra_social'] for fila in filas))
    desglose = Counter((fila['medico'], fila['modalidad']) for fila in filas)
    top = {nombre for nombre, _ in medicos if nombre != 'Otros'}
    med_datasets = [{'label': nombres.get(mod, mod), 'backgroundColor': COLORES[mod],
                     'data': [sum(total for (medico, tipo), total in desglose.items()
                                  if tipo == mod and (medico == nombre if nombre != 'Otros' else medico not in top))
                              for nombre, _ in medicos]} for mod in mods]
    previo = None
    anteriores = []
    periodo_anterior = None
    if fecha_desde and fecha_hasta:
        hasta_previo = fecha_desde - timedelta(days=1)
        desde_previo = fecha_desde - timedelta(days=(fecha_hasta - fecha_desde).days + 1)
        periodo_anterior = {'desde': desde_previo.isoformat(), 'hasta': hasta_previo.isoformat()}
        _, anteriores = _poblacion({**seleccion, 'fecha_desde': desde_previo, 'fecha_hasta': hasta_previo}, modalidades)
        if anteriores:
            previo = _indicadores(anteriores, desde_previo, hasta_previo)
    comparativa = {'hay_datos_anterior': previo is not None,
                  'practicas_mayores_aumentos': [], 'practicas_mayores_disminuciones': [], 'bloqueos_tc': None}
    if previo:
        actual_practicas = Counter(fila['practica'] for fila in filas)
        previas_practicas = Counter(fila['practica'] for fila in anteriores)
        cambios = [{'practica': practica, **_metrica(actual_practicas[practica], previas_practicas[practica])}
                   for practica in actual_practicas.keys() | previas_practicas.keys()]
        comparativa['practicas_mayores_aumentos'] = sorted(
            (item for item in cambios if item['absoluta'] > 0), key=lambda item: (-item['absoluta'], item['practica']),
        )[:5]
        comparativa['practicas_mayores_disminuciones'] = sorted(
            (item for item in cambios if item['absoluta'] < 0), key=lambda item: (item['absoluta'], item['practica']),
        )[:5]
    for clave, indicador in [('pacientes', 'pacientes_atendidos'), ('practicas', 'practicas_realizadas'),
                             ('practicas_por_paciente', 'practicas_por_paciente')]:
        comparativa[clave] = _metrica(kpis[indicador], previo[indicador] if previo else None)
    fuente = 'EGES + Netterm' if batch_eges_ids and lote_netterm_ids else 'EGES' if batch_eges_ids else 'Netterm'
    return {
        'kpis': kpis,
        'temporal': {'labels': [periodo.strftime(formato) for periodo in periodos], 'datasets': datasets},
        'dia_semana': _grafico(['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo'],
                               [semana[dia] for dia in range(7)]),
        'franja': _grafico([f'{hora:02d}-{hora + 2:02d}' for hora in range(0, 24, 2)] + [SIN_DATO],
                           [franjas[franja] for franja in range(13)]),
        'modalidad': {**_grafico([nombres.get(mod, mod) for mod in mods], [conteo[mod] for mod in mods],
                     [COLORES[mod] for mod in mods]), 'modalidades': mods},
        'sub_eco': _grafico(list(sub), list(sub.values()), '#eab308'),
        'medicos': {'labels': [nombre for nombre, _ in medicos], 'datasets': med_datasets},
        'obras_sociales': _grafico([nombre for nombre, _ in os], [total for _, total in os]),
        'comparativa': {'comparativa': comparativa, 'periodo_anterior': periodo_anterior,
                        'periodo_actual': {'desde': fecha_desde.isoformat(), 'hasta': fecha_hasta.isoformat()}
                                          if fecha_desde and fecha_hasta else None},
        'kpis_anterior': previo,
        'metadatos': {'version': 'ESTADISTICAS_FUENTES_V1', 'fuente': fuente,
                      'firma': produccion['firma_snapshot'], 'lotes_eges': batch_eges_ids,
                      'fecha_desde': (fecha_desde or min((fila['fecha'] for fila in filas), default=None)),
                      'fecha_hasta': (fecha_hasta or max((fila['fecha'] for fila in filas), default=None)),
                      'lotes_netterm': lote_netterm_ids, 'pendientes': produccion['pendientes_detalle'],
                      'excluidos': produccion['excluidos_detalle'], 'sin_identidad': kpis['sin_identidad'],
                      'incompleto': bool(produccion['pendientes']) or bool(kpis['sin_identidad']),
                      'cobertura_confirmada': False,
                      'advertencia_cobertura': ImportBatch.objects.filter(pk__in=batch_eges_ids, total_filas__gte=1000).exists()},
    }