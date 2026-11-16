"""Una poblacion conciliada para indicadores, graficos y PDF del tablero."""
from collections import Counter, defaultdict
from datetime import timedelta
from itertools import chain

from django.core.exceptions import ValidationError
from django.utils.dateparse import parse_time

from .models import EgesRow, NettermFila, NombreObraSocial, ProduccionValidada
from .services import _valor_valido, agrupar_periodo
from .services_produccion import construir_preview_produccion
from .services_unidades import unidades_practica
from .services_identificacion import _identidades_netterm
from .services_conciliacion import _profesional
from .services_coberturas import clave_cobertura, construir_equivalencias_coberturas
from .rendimiento import MedicionEstadisticas


COLORES = {'TC': '#3b82f6', 'RM': '#9333ea', 'RX': '#22c55e', 'DX': '#f97316',
           'MAM': '#ec4899', 'ECO': '#eab308', 'SERIE': '#14b8a6', 'OTROS': '#6b7280'}
SIN_DATO = 'Sin dato'
ALIAS_MEDICOS_ESTADISTICAS = {
    'ARIANNE CARRIEL DENIS GONZALEZ': 'ARIANNE CARRIEL DENISSE GONZALEZ',
    'ANA BELEN IZURIETA': 'ANA BELEN IZURIETA PENAHERRERA',
    'CARLOS D SARABIA': 'CARLOS DAVID LEYVA SARABIA',
    'LIZBETH M SANCHEZ': 'KATHERINE LIZBETH MURILLO SANCHEZ',
    'KATHERINE LIZB MURILLO SANCHEZ': 'KATHERINE LIZBETH MURILLO SANCHEZ',
    'ALEJANDRA H MA MALDONADO': 'ALEJANDRA HERNANDEZ MALDONADO MARIA',
    'ALE HERNANDEZ MALDONADO MARIA': 'ALEJANDRA HERNANDEZ MALDONADO MARIA',
    'ALEJAND HERNANDEZ MAIRA MOJICA': 'ALEJANDRA HERNANDEZ MAIRA MOJICA',
    'BALCAZAR NICOLE PINEDA STEPHAN': 'BALCAZAR NICOLE PINEDA STEPHANIE',
    'DAVI HERRERA SALINAS YEFFERSON': 'DAVID HERRERA SALINAS YEFFERSON',
}


def _nombre_medico_estadistica(valor):
    tokens = _profesional(valor) if _valor_valido(valor) else None
    if not tokens:
        return SIN_DATO
    nombre = ' '.join(tokens)
    return ALIAS_MEDICOS_ESTADISTICAS.get(nombre, nombre)


def _aliases_medicos_por_estudios(practicas, eges, netterm):
    """Agrupa nombres incompletos con correspondencias reiteradas y nombre completo único."""
    coincidencias = defaultdict(set)
    for item in practicas:
        fila = item['fila']
        if not item.get('netterm') or 'fecha_turno' not in fila or not fila['paciente_clave']:
            continue
        original = eges.get(fila['id'])
        datos = netterm.get(item['netterm']['id'], {})
        primero = _nombre_medico_estadistica(original.medico_informante if original else '')
        segundo = _nombre_medico_estadistica(datos.get('informante'))
        if primero == segundo or SIN_DATO in {primero, segundo}:
            continue
        tokens_primero, tokens_segundo = set(primero.split()), set(segundo.split())
        if min(len(tokens_primero), len(tokens_segundo)) < 2:
            continue
        if not (tokens_primero <= tokens_segundo or tokens_segundo <= tokens_primero):
            continue
        coincidencias[tuple(sorted((primero, segundo)))].add(fila['paciente_clave'])
    vecinos = defaultdict(set)
    for (primero, segundo), pacientes in coincidencias.items():
        if len(pacientes) >= 2:
            vecinos[primero].add(segundo)
            vecinos[segundo].add(primero)
    aliases = {}
    visitados = set()
    for nombre in vecinos:
        if nombre in visitados:
            continue
        grupo, pendientes = set(), [nombre]
        while pendientes:
            actual = pendientes.pop()
            if actual in grupo:
                continue
            grupo.add(actual)
            pendientes.extend(vecinos[actual] - grupo)
        visitados.update(grupo)
        tokens_grupo = set().union(*(set(variante.split()) for variante in grupo))
        completos = [variante for variante in grupo if set(variante.split()) == tokens_grupo]
        if len(completos) == 1:
            aliases.update({variante: completos[0] for variante in grupo})
    return aliases


def _grafico(labels, valores, color='#3b82f6'):
    return {'labels': labels, 'datasets': [{'label': 'Prácticas respaldadas', 'data': valores,
                                           'backgroundColor': color, 'borderColor': color}]}


def _ranking(conteo):
    conocidos = sorted(((clave, total) for clave, total in conteo.items() if clave != SIN_DATO),
                       key=lambda item: (-item[1], item[0]))
    return conocidos[:10]


def _resto_ranking(conteo):
    conocidos = sorted(((nombre, total) for nombre, total in conteo.items() if nombre != SIN_DATO),
                       key=lambda item: (-item[1], item[0]))
    return [{'nombre': nombre, 'total': total} for nombre, total in conocidos[10:]]


def _poblacion(seleccion, modalidades, produccion_dashboard=None, filas_anteriores=None, medicion=None):
    seleccion = seleccion.copy()
    validacion_id = seleccion.pop('validacion_id', None)
    dashboard_global = seleccion.pop('dashboard_global', False)
    incluir_netterm = seleccion.pop('incluir_netterm', False)
    if dashboard_global:
        from .services_dashboard import construir_produccion_dashboard
        resultado = dict(produccion_dashboard) if produccion_dashboard is not None else construir_produccion_dashboard(incluir_netterm=incluir_netterm)
    elif validacion_id:
        from .services_validacion_produccion import leer_produccion_validada
        resultado = leer_produccion_validada(validacion_id)
        validacion = ProduccionValidada.objects.get(pk=validacion_id)
        if (not set(validacion.lotes_eges_ids).issubset(seleccion['batch_eges_ids'])
                or set(validacion.lotes_netterm_ids) != set(seleccion['lote_netterm_ids'])):
            raise ValidationError('La selección requiere una nueva validación de fuentes.')
        adicionales = set(seleccion['batch_eges_ids']) - set(validacion.lotes_eges_ids)
        if adicionales:
            historico = construir_preview_produccion(
                batch_eges_ids=sorted(adicionales), lote_netterm_ids=[],
                permitir_fuente_unica=True, incluir_practicas=True,
            )
            if any(validacion.fecha_desde <= item['fecha_produccion'] <= validacion.fecha_hasta
                   for item in historico['practicas']):
                raise ValidationError('Los lotes EGES agregados contienen prácticas del período aprobado. Integralos y validalos para actualizar ese período.')
            resultado['practicas'].extend(historico['practicas'])
            for clave in ('pendientes', 'excluidos'):
                resultado[clave] = dict(Counter(resultado[clave]) + Counter(historico[clave]))
                detalle = f'{clave}_detalle'
                cantidades = Counter()
                for item in resultado[detalle] + historico[detalle]:
                    cantidades[item['motivo']] += item['cantidad']
                resultado[detalle] = [{'motivo': motivo, 'cantidad': cantidad}
                                      for motivo, cantidad in cantidades.items()]
        resultado['historico_eges'] = bool(adicionales)
    else:
        resultado = construir_preview_produccion(**seleccion, permitir_fuente_unica=True, incluir_practicas=True)
    practicas = resultado.pop('practicas')
    if medicion:
        medicion.marcar('produccion')
    eges_ids = {item['fila']['id'] for item in practicas if 'fecha_turno' in item['fila']}
    netterm_ids = {item.get('netterm', item['fila'])['id'] for item in practicas
                   if item.get('netterm') or 'fecha_pedido' in item['fila']}
    eges = {fila.pk: fila for fila in EgesRow.objects.filter(pk__in=eges_ids).only(
        'pk', 'medico_informante', 'sub_modalidad', 'obra_social', 'codigo_obra_social',
        'dni_paciente', 'apellido_nombre',
    )}
    netterm = {}
    for origen in NettermFila.objects.filter(pk__in=netterm_ids).only('normalizados_json', 'originales_json'):
        datos = dict(origen.normalizados_json)
        # Los lotes anteriores conservan cobertura en su fila original de 37 columnas.
        if not datos.get('cobertura') and isinstance(origen.originales_json, list) and len(origen.originales_json) == 37:
            cobertura = origen.originales_json[13]
            if isinstance(cobertura, dict):
                cobertura = cobertura.get('valor')
            datos['cobertura'] = str(cobertura or '').strip()
        netterm[origen.pk] = datos
    if medicion:
        medicion.marcar('lectura_contexto')
    identidades_netterm = _identidades_netterm(eges, netterm)
    if medicion:
        medicion.marcar('identidades')
    aliases_medicos = _aliases_medicos_por_estudios(practicas, eges, netterm)
    if medicion:
        medicion.marcar('medicos')
    nombres_os = dict(NombreObraSocial.objects.values_list('codigo', 'nombre'))
    coberturas = construir_equivalencias_coberturas(practicas, eges, netterm, nombres_os)
    if medicion:
        medicion.marcar('coberturas')
    practicas_anteriores = []
    desde, hasta = seleccion.get('fecha_desde'), seleccion.get('fecha_hasta')
    if filas_anteriores is not None and desde and hasta:
        desde_previo = desde - timedelta(days=(hasta - desde).days + 1)
        practicas_anteriores = [item for item in practicas
                               if desde_previo <= item['fecha_produccion'] < desde
                               and (modalidades is None or item['fila']['modalidad'] in modalidades)]
    if validacion_id or dashboard_global:
        desde, hasta = seleccion.get('fecha_desde'), seleccion.get('fecha_hasta')
        practicas = [item for item in practicas
                     if (not desde or item['fecha_produccion'] >= desde)
                     and (not hasta or item['fecha_produccion'] <= hasta)]
    if modalidades is not None:
        practicas = [item for item in practicas if item['fila']['modalidad'] in modalidades]
    disponibles = resultado.pop('aportes_disponibles', [])
    desde, hasta = seleccion.get('fecha_desde'), seleccion.get('fecha_hasta')
    resultado['aporte_netterm_disponible'] = sum(
        (not desde or item['fecha_produccion'] >= desde)
        and (not hasta or item['fecha_produccion'] <= hasta)
        and (modalidades is None or item['fila']['modalidad'] in modalidades)
        for item in disponibles
    )
    resultado['aporte_netterm_aplicado'] = sum(unidades_practica(item) for item in practicas
                                             if item['fuente'] == 'NETTERM')
    filas = []
    for item in chain(practicas, practicas_anteriores):
        fila = item['fila']
        original = eges.get(fila['id']) if 'fecha_turno' in fila else None
        nt_fila = item.get('netterm', fila)
        nt = netterm.get(nt_fila['id'], {}) if item.get('netterm') or 'fecha_pedido' in fila else {}
        medico = original.medico_informante if original else ''
        medico = medico if _valor_valido(medico) else nt.get('informante', '')
        medico_original = ' '.join(_profesional(medico) or ()) or SIN_DATO
        medico = _nombre_medico_estadistica(medico)
        medico = aliases_medicos.get(medico, medico)
        cobertura_original = (original.obra_social or original.codigo_obra_social) if original else None
        cobertura_original = cobertura_original or nt.get('obra_social') or nt.get('cobertura')
        clave_nt = clave_cobertura(nt.get('obra_social') or nt.get('cobertura'))
        cobertura = (coberturas['eges'].get(original.pk) if original else None)
        cobertura = cobertura or coberturas['netterm'].get(clave_nt) or cobertura_original or SIN_DATO
        subtipo = original.sub_modalidad if original else None
        subtipo = subtipo or {'DOP': 'DOPPLER', 'ECOCAR': 'ECOCARDIO'}.get(
            item.get('sub_modalidad_netterm') or nt_fila.get('modalidad'),
        )
        if not subtipo and fila['modalidad'] == 'ECO':
            subtipo = EgesRow(practica=fila['practica']).clasificar_sub_modalidad()
        if item.get('procedimiento_guiado') and fila['modalidad'] == 'ECO':
            subtipo = 'PROCEDIMIENTOS_GUIADOS'
        hora_realizacion = nt.get('hora_realizacion')
        if isinstance(hora_realizacion, str):
            hora_realizacion = parse_time(hora_realizacion)
        fila_estadistica = {
            'fecha': item['fecha_produccion'],
            'hora': hora_realizacion or fila.get('hora_turno'),
            'modalidad': fila['modalidad'], 'sub_modalidad': subtipo,
            'paciente': fila['paciente_clave'] or (identidades_netterm.get(nt_fila['id']) if nt else None),
            'informada': item['informada'],
            'fuente': item['fuente'], 'medico': medico, 'medico_original': medico_original,
            'obra_social': cobertura, 'cobertura_original': cobertura_original or SIN_DATO,
            'revision_cobertura': coberturas['pendientes'].get(clave_nt) if not original else None,
            'practica': fila['practica'],
        }
        # Las unidades comparten los mismos datos de lectura para los gráficos.
        destino = (filas_anteriores if filas_anteriores is not None and desde
                   and item['fecha_produccion'] < desde else filas)
        destino.extend([fila_estadistica] * unidades_practica(item))
    if medicion:
        medicion.marcar('filas_graficos')
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
        'practicas_por_paciente': round((total - sin_identidad) / len(pacientes), 2) if pacientes else None,
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
                                   fecha_hasta=None, modalidades=None, agrupacion='mes', validacion_id=None,
                                   dashboard_global=False, incluir_netterm=False):
    if not batch_eges_ids and not lote_netterm_ids:
        raise ValidationError('Seleccioná al menos un lote de origen y aplicá los filtros.')
    if agrupacion not in {'dia', 'semana', 'mes'}:
        raise ValidationError('La agrupación no es válida.')
    if modalidades is not None and not set(modalidades).issubset(COLORES):
        raise ValidationError('La selección de modalidades no es válida.')
    seleccion = dict(batch_eges_ids=batch_eges_ids, lote_netterm_ids=lote_netterm_ids,
                     fecha_desde=fecha_desde, fecha_hasta=fecha_hasta)
    if validacion_id:
        seleccion['validacion_id'] = validacion_id
    if dashboard_global:
        seleccion.update(dashboard_global=True, incluir_netterm=incluir_netterm)
    medicion = MedicionEstadisticas()
    produccion_dashboard = None
    if dashboard_global:
        from .services_dashboard import construir_produccion_dashboard
        produccion_dashboard = construir_produccion_dashboard(incluir_netterm=incluir_netterm)
    anteriores = []
    produccion, filas = _poblacion(seleccion, modalidades, produccion_dashboard,
                                 anteriores if dashboard_global else None, medicion=medicion)
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
    sub_nombres['PROCEDIMIENTOS_GUIADOS'] = 'Procedimientos intervencionistas ecoguiados'
    sub = Counter(sub_nombres.get(fila['sub_modalidad'], fila['sub_modalidad']) or SIN_DATO
                  for fila in filas if fila['modalidad'] == 'ECO')
    conteo_medicos = Counter(fila['medico'] for fila in filas)
    variantes_medicos = defaultdict(set)
    for fila in filas:
        variantes_medicos[fila['medico']].add(fila['medico_original'])
    conteo_cobertura = Counter(fila['obra_social'] for fila in filas)
    variantes_coberturas = defaultdict(set)
    revisiones_coberturas = {}
    for fila in filas:
        variantes_coberturas[fila['obra_social']].add(fila['cobertura_original'])
        if fila['revision_cobertura']:
            revision = fila['revision_cobertura']
            revisiones_coberturas[revision['netterm']] = revision
    medicos = _ranking(conteo_medicos)
    os = _ranking(conteo_cobertura)
    resto_medicos = _resto_ranking(conteo_medicos)
    resto_coberturas = _resto_ranking(conteo_cobertura)
    desglose = Counter((fila['medico'], fila['modalidad']) for fila in filas)
    med_datasets = [{'label': nombres.get(mod, mod), 'backgroundColor': COLORES[mod],
                     'data': [sum(total for (medico, tipo), total in desglose.items()
                                  if tipo == mod and medico == nombre)
                              for nombre, _ in medicos]} for mod in mods]
    previo = None
    periodo_anterior = None
    if fecha_desde and fecha_hasta:
        hasta_previo = fecha_desde - timedelta(days=1)
        desde_previo = fecha_desde - timedelta(days=(fecha_hasta - fecha_desde).days + 1)
        periodo_anterior = {'desde': desde_previo.isoformat(), 'hasta': hasta_previo.isoformat()}
        if not dashboard_global:
            _, anteriores = _poblacion({**seleccion, 'fecha_desde': desde_previo, 'fecha_hasta': hasta_previo}, modalidades,
                                      medicion=medicion)
        if anteriores:
            previo = _indicadores(anteriores, desde_previo, hasta_previo)
    comparativa = {'hay_datos_anterior': previo is not None,
                  'motivo_sin_comparativa': ('Seleccioná fechas desde y hasta para comparar con el período anterior.'
                                            if not fecha_desde or not fecha_hasta else
                                            'Las fuentes seleccionadas no contienen producción del período anterior.'),
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
    if dashboard_global:
        fuente = 'EGES + aporte Netterm validado' if incluir_netterm else 'EGES'
    medicion.marcar('indicadores')
    return {
        'kpis': kpis,
        'temporal': {'labels': [periodo.strftime(formato) for periodo in periodos], 'datasets': datasets},
        'dia_semana': _grafico(['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo'],
                               [semana[dia] for dia in range(7)]),
        'franja': _grafico([f'{hora:02d}-{hora + 2:02d}' for hora in range(0, 24, 2)] + [SIN_DATO],
                           [franjas[franja] for franja in range(13)]),
        'modalidad': {**_grafico([nombres.get(mod, mod) for mod in mods], [conteo[mod] for mod in mods],
                     [COLORES[mod] for mod in mods]), 'modalidades': mods},
        'sub_eco': _grafico([nombre for nombre, _ in sub.most_common()],
                            [total for _, total in sub.most_common()], '#eab308'),
        'medicos': {'labels': [nombre for nombre, _ in medicos], 'datasets': med_datasets,
                    'resto': resto_medicos,
                    'total_resto': sum(item['total'] for item in resto_medicos),
                    'sin_dato': conteo_medicos[SIN_DATO],
                    'equivalencias': [{'nombre': nombre, 'variantes': sorted(variantes)}
                                     for nombre, variantes in sorted(variantes_medicos.items())
                                     if variantes != {nombre}]},
        'obras_sociales': {**_grafico([nombre for nombre, _ in os], [total for _, total in os]),
                           'resto': resto_coberturas,
                           'total_resto': sum(item['total'] for item in resto_coberturas),
                           'sin_dato': conteo_cobertura[SIN_DATO],
                           'equivalencias': [{'nombre': nombre, 'variantes': sorted(variantes)}
                                            for nombre, variantes in sorted(variantes_coberturas.items())
                                            if variantes != {nombre}],
                           'revisiones': list(revisiones_coberturas.values())},
        'comparativa': {'comparativa': comparativa, 'periodo_anterior': periodo_anterior,
                        'periodo_actual': {'desde': fecha_desde.isoformat(), 'hasta': fecha_hasta.isoformat()}
                                          if fecha_desde and fecha_hasta else None},
        'kpis_anterior': previo,
        'metadatos': {'version': 'ESTADISTICAS_FUENTES_V7', 'fuente': fuente,
                      'confirmada': bool(validacion_id), 'validacion_id': validacion_id,
                      'base_eges_completa': dashboard_global,
                      'aporte_netterm_activo': incluir_netterm,
                      'aporte_netterm_disponible': produccion.get('aporte_netterm_disponible', 0),
                      'aporte_netterm_aplicado': produccion.get('aporte_netterm_aplicado', 0),
                      'advertencias_dashboard': produccion.get('advertencias_dashboard', []),
                      'historico_eges': produccion.get('historico_eges', False),
                      'criterio_produccion': 'Realizado e informado definitivamente, por fecha de realización Netterm o turno EGES',
                      'alcance_pendientes': 'Conjunto completo de lotes seleccionados',
                      'firma': produccion['firma_snapshot'], 'lotes_eges': batch_eges_ids,
                      'fecha_desde': (fecha_desde or min((fila['fecha'] for fila in filas), default=None)),
                      'fecha_hasta': (fecha_hasta or max((fila['fecha'] for fila in filas), default=None)),
                      'lotes_netterm': (produccion.get('lote_netterm_ids', []) if incluir_netterm else []) if dashboard_global else lote_netterm_ids,
                      'pendientes': produccion['pendientes_detalle'],
                      'excluidos': produccion['excluidos_detalle'], 'sin_identidad': kpis['sin_identidad'],
                      'incompleto': bool(produccion['pendientes']) or bool(kpis['sin_identidad']),
                      'cobertura_confirmada': False,
                      'advertencia_cobertura': False},
    }
