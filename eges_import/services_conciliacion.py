from collections import Counter, defaultdict
from datetime import date
import hashlib
import json
import re
import unicodedata

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils.dateparse import parse_date
from django.utils.crypto import salted_hmac

from .models import ConciliacionRevision, EgesRow, ImportBatch, NettermFila, NettermLote
from .services_netterm import clasificar_fila_netterm


VERSION_CRUCE_NETTERM_EGES = 'DNI_CODIGO_FECHA_PEDIDO_V8'
MAX_LOTES_NETTERM_CRUCE = 10
MAX_FILAS_CRUCE = 50000
ESTADOS_CRUCE = ('COINCIDENTE', 'SOLO_EGES', 'SOLO_NETTERM', 'AMBIGUO', 'CONFLICTO')
MODALIDADES_CONTEO = {'TC', 'RM', 'RX', 'MAM', 'DX', 'SERIE', 'ECO', 'SIN_CLASIFICAR'}


def _texto_normalizado(valor):
    texto = ''.join(caracter for caracter in unicodedata.normalize('NFKD', str(valor or ''))
                    if not unicodedata.combining(caracter))
    return ' '.join(re.sub(r'[^A-Z0-9]+', ' ', texto.upper()).split())


def _dni(valor):
    texto = re.sub(r'[.\s]', '', str(valor or ''))
    if not texto or not texto.isascii() or not texto.isdigit():
        return None
    # Mismo contrato numerico que _paciente_clave: formato/padding no crean otra persona.
    return texto.lstrip('0') or None


def _codigo(valor):
    texto = str(valor or '').strip()
    coincidencia = re.fullmatch(r'([0-9]+)(?:/0)?', texto)
    return coincidencia.group(1) if coincidencia else texto or None


def _profesional(valor):
    tokens = _texto_normalizado(valor).split()
    if not tokens or ' '.join(tokens) in {'MEDICO NO ESPECIFICADO', 'NO ESPECIFICADO', 'SIN ESPECIFICAR'}:
        return None
    return tuple(sorted(tokens))


def _modalidad_consolidada(modalidad):
    if modalidad in {'ECO_GENERAL', 'DOP', 'ECOCAR'}:
        return 'ECO'
    return modalidad


def _datos_eges(fila):
    return {
        'id': fila.pk, 'lote_id': fila.batch_id, 'practica': fila.practica,
        'codigo': fila.codigo_practica, 'fecha_turno': fila.fecha_turno,
        'hora_turno': fila.hora_turno, 'estado': fila.estado_turno,
        'estado_informe': fila.estado_informe,
        'modalidad': fila.modalidad,
        'paciente_clave': _paciente_clave(fila.dni_paciente),
    }


def _datos_netterm(grupo):
    fila = grupo[0]
    return {
        'id': fila.pk, 'lote_id': fila.lote_id,
        'observaciones_ids': [observacion.pk for observacion in grupo],
        'practica': fila.normalizados_json.get('practica', ''),
        'codigo': fila.normalizados_json.get('codigo_nomenclador', ''),
        'fecha_pedido': fila.fecha_pedido, 'fecha_realizacion': fila.fecha_realizacion,
        'fecha_informe': fila.fecha_informe, 'estado': fila.estado_informe,
        'anulado': fila.anulado,
        'estado_realizacion': fila.normalizados_json.get('estado_realizacion', 'DESCONOCIDO'),
        'vigencia_incierta': len({observacion.contenido_sha256 for observacion in grupo}) > 1,
        'paciente_clave': _paciente_clave(
            fila.normalizados_json.get('documento'), fila.normalizados_json.get('tipo_documento'),
        ),
        'modalidad': clasificar_fila_netterm(
            fila.normalizados_json.get('practica'), fila.normalizados_json.get('codigo_nomenclador'),
            fila.normalizados_json.get('servicio', ''),
        )['modalidad'],
    }


def _paciente_clave(documento, tipo='DNI'):
    if _texto_normalizado(tipo).replace('.', '').replace(' ', '') != 'DNI':
        return None
    dni = _dni(documento)
    if not dni:
        return None
    return salted_hmac('eges_import.paciente_conteo.v1', dni).hexdigest()


def _firma_snapshot(
    batch_id, lote_ids, eges, grupos, fecha_desde=None, fecha_hasta=None,
    modalidades_eges=None, modalidades_netterm=None,
):
    datos = {
        'version': VERSION_CRUCE_NETTERM_EGES,
        'batch_eges': batch_id,
        'lotes_netterm': sorted(lote_ids),
        'eges': [
            [fila.pk, fila.dni_paciente, fila.codigo_practica, fila.fecha_turno,
             fila.hora_turno, fila.medico_informante, fila.estado_turno, fila.practica]
            for fila in eges
        ],
        'netterm': sorted(
            [fila.pk, fila.lote_id, fila.contenido_sha256, fila.clave_candidata_sha256]
            for grupo in grupos.values() for fila in grupo
        ),
    }
    if fecha_desde or fecha_hasta:
        datos['periodo'] = [fecha_desde, fecha_hasta]
    if modalidades_netterm is not None:
        datos['modalidades_netterm'] = sorted(modalidades_netterm)
    if modalidades_eges is not None:
        datos['modalidades_eges'] = sorted(modalidades_eges)
    serializado = json.dumps(datos, ensure_ascii=False, sort_keys=True, separators=(',', ':'), default=str)
    return hashlib.sha256(serializado.encode('utf-8')).hexdigest()


def construir_preview_conciliacion(
    *, lote_netterm_ids, batch_eges_id=None, batch_eges_ids=None,
    fecha_desde=None, fecha_hasta=None, modalidades_eges=None, modalidades_netterm=None,
    permitir_fuente_unica=False,
):
    """Compara origenes seleccionados sin fusionar, validar o persistir decisiones."""
    try:
        ids = [int(valor) for valor in lote_netterm_ids]
        batch_ids = [int(valor) for valor in batch_eges_ids] if batch_eges_ids is not None else [int(batch_eges_id)]
    except (TypeError, ValueError):
        raise ValidationError('Selecciona identificadores de lotes validos.') from None
    seleccion_incompleta = not ids or not batch_ids
    if (len(ids) != len(set(ids)) or len(batch_ids) != len(set(batch_ids))
            or (seleccion_incompleta and not permitir_fuente_unica) or (not ids and not batch_ids)):
        raise ValidationError('Selecciona lotes EGES y Netterm distintos, al menos uno de cada fuente.')
    if batch_eges_ids is not None and batch_eges_id is not None:
        raise ValidationError('Usa una sola seleccion de lotes EGES.')
    if (ImportBatch.objects.filter(pk__in=batch_ids).count() != len(batch_ids)
            or NettermLote.objects.filter(pk__in=ids).count() != len(ids)):
        raise ValidationError('Uno de los lotes seleccionados no existe.')
    try:
        desde = fecha_desde if isinstance(fecha_desde, date) else parse_date(str(fecha_desde)) if fecha_desde else None
        hasta = fecha_hasta if isinstance(fecha_hasta, date) else parse_date(str(fecha_hasta)) if fecha_hasta else None
    except (TypeError, ValueError):
        raise ValidationError('El periodo de analisis no es valido.') from None
    if (fecha_desde and not desde) or (fecha_hasta and not hasta) or (desde and hasta and desde > hasta):
        raise ValidationError('El periodo de analisis no es valido.')
    if modalidades_netterm is None:
        modalidades = None
    else:
        modalidades = set(modalidades_netterm)
        if not modalidades or not modalidades.issubset(MODALIDADES_CONTEO):
            raise ValidationError('La seleccion contiene una modalidad Netterm no valida.')
    if modalidades_eges is None:
        modalidades_eges_filtradas = None
    else:
        modalidades_eges_filtradas = set(modalidades_eges)
        if not modalidades_eges_filtradas or not modalidades_eges_filtradas.issubset(MODALIDADES_CONTEO):
            raise ValidationError('La seleccion contiene una modalidad EGES no valida.')
    batch_ids = sorted(batch_ids)
    batch_id = batch_ids[0] if len(batch_ids) == 1 else None
    eges_qs = EgesRow.objects.filter(batch_id__in=batch_ids, es_insumo=False).only(
        'pk', 'batch_id', 'dni_paciente', 'codigo_practica', 'fecha_turno',
        'hora_turno', 'medico_informante', 'estado_turno', 'practica',
        'modalidad', 'estado_informe',
    ).order_by('pk')
    netterm_qs = NettermFila.objects.filter(lote_id__in=ids).only(
        'pk', 'lote_id', 'clave_candidata_sha256', 'contenido_sha256', 'clase_observacion', 'normalizados_json',
        'fecha_pedido', 'fecha_realizacion', 'fecha_informe', 'estado_informe', 'anulado',
    ).order_by('-lote_id', '-pk')
    if desde:
        eges_qs = eges_qs.filter(fecha_turno__gte=desde)
    if hasta:
        eges_qs = eges_qs.filter(fecha_turno__lte=hasta)
    if modalidades_eges_filtradas is not None:
        eges_qs = eges_qs.filter(modalidad__in=modalidades_eges_filtradas)
    cantidad_eges, cantidad_netterm = eges_qs.count(), netterm_qs.count()
    if cantidad_eges + cantidad_netterm > MAX_FILAS_CRUCE:
        raise ValidationError('El cruce supera 50000 filas; selecciona menos lotes.')
    eges = list(eges_qs)
    grupos = defaultdict(list)
    for fila in netterm_qs.iterator(chunk_size=500):
        grupos[fila.clave_candidata_sha256].append(fila)
    grupos_periodo = {}
    cantidad_insumos = 0
    cantidad_netterm = 0
    cantidad_netterm_modalidad = 0
    for clave_grupo, grupo in grupos.items():
        grupo.sort(key=lambda observacion: observacion.pk)
        fila = grupo[0]
        vigencia_incierta = len({observacion.contenido_sha256 for observacion in grupo}) > 1
        fechas = [observacion.fecha_pedido for observacion in grupo] if vigencia_incierta else [fila.fecha_pedido]
        if (desde or hasta) and not any(
            fecha and (not desde or fecha >= desde) and (not hasta or fecha <= hasta)
            for fecha in fechas
        ):
            continue
        cantidad_netterm += len(grupo)
        normalizados = fila.normalizados_json
        clasificacion = clasificar_fila_netterm(
            normalizados.get('practica'), normalizados.get('codigo_nomenclador'),
            normalizados.get('servicio', ''),
        )
        if clasificacion['es_insumo'] and not vigencia_incierta:
            cantidad_insumos += len(grupo)
            continue
        modalidad = _modalidad_consolidada(clasificacion['modalidad'])
        if modalidades is not None and modalidad not in modalidades:
            continue
        cantidad_netterm_modalidad += len(grupo)
        grupos_periodo[clave_grupo] = grupo
    grupos = grupos_periodo
    indice_eges = defaultdict(list)
    for fila in eges:
        clave = (_dni(fila.dni_paciente), _codigo(fila.codigo_practica), fila.fecha_turno)
        if all(clave):
            indice_eges[clave].append(fila)
    candidatos_por_grupo = {}
    motivos_por_grupo = {}
    grupos_por_eges = defaultdict(set)
    for clave_grupo, grupo in grupos.items():
        fila = grupo[0]
        normalizados = fila.normalizados_json
        motivos = []
        tipo_documento = re.sub(r'[^A-Z]', '', _texto_normalizado(normalizados.get('tipo_documento')))
        clave = (_dni(normalizados.get('documento')), _codigo(normalizados.get('codigo_nomenclador')), fila.fecha_pedido)
        if tipo_documento != 'DNI' or not all(clave):
            motivos.append('Documento DNI, codigo o fecha de pedido insuficientes para comparar.')
            candidatos = []
        else:
            candidatos = indice_eges.get(clave, [])
        candidatos_por_grupo[clave_grupo] = candidatos
        motivos_por_grupo[clave_grupo] = motivos
        for candidata in candidatos:
            grupos_por_eges[candidata.pk].add(clave_grupo)
    resultados = []
    for clave_grupo, grupo in grupos.items():
        fila = grupo[0]
        candidatas = candidatos_por_grupo[clave_grupo]
        motivos = list(motivos_por_grupo[clave_grupo])
        advertencias = ['Cantidad Netterm desconocida; no se valido cantidad ni horario economico.']
        estado = 'SOLO_NETTERM'
        identidad_coincidente = False
        comparacion_estados = 'NO_COMPARADOS'
        contradiccion_anulacion = False
        observaciones_ultimo_lote = sum(observacion.lote_id == fila.lote_id for observacion in grupo)
        ambiguedad_origen = (
            observaciones_ultimo_lote > 1
            or len({observacion.contenido_sha256 for observacion in grupo}) > 1
            or any(observacion.clase_observacion == NettermFila.CLASE_AMBIGUA for observacion in grupo)
        )
        if ambiguedad_origen or len(candidatas) > 1 or any(len(grupos_por_eges[candidata.pk]) > 1 for candidata in candidatas):
            estado = 'AMBIGUO'
            motivos.append('Multiples observaciones o correspondencias posibles; no se eligio un estudio automaticamente.')
            if len({observacion.contenido_sha256 for observacion in grupo}) > 1:
                motivos.append('Vigencia de exportacion no verificada; el orden de importacion no determina la version actual.')
        elif motivos:
            estado = 'CONFLICTO'
        elif candidatas:
            candidata = candidatas[0]
            estado = 'COINCIDENTE'
            modalidad_netterm = _modalidad_consolidada(fila.normalizados_json.get('modalidad'))
            if modalidad_netterm != candidata.modalidad:
                motivos.append('Las modalidades de ambas fuentes difieren; verificar nomenclador antes de contar.')
            else:
                identidad_coincidente = True
            informante_netterm = _profesional(fila.normalizados_json.get('informante'))
            informante_eges = _profesional(candidata.medico_informante)
            if not informante_netterm or not informante_eges:
                advertencias.append('Informantes incompletos: alerta de origen, no bloquea la correspondencia de produccion ni valida cobro.')
            elif informante_netterm != informante_eges:
                advertencias.append('Informantes distintos: alerta de origen, no bloquea la correspondencia de produccion ni valida cobro.')
            estados_eges = {'INFORMADO': 'DEFINITIVO', 'CANCELADO': 'ANULADO', 'ANULADO': 'ANULADO'}
            estado_netterm = 'ANULADO' if fila.anulado else fila.estado_informe
            estado_eges = estados_eges.get(_texto_normalizado(candidata.estado_turno))
            contradiccion_anulacion = (estado_eges == 'ANULADO') != (estado_netterm == 'ANULADO')
            if contradiccion_anulacion:
                comparacion_estados = 'ANULACION_CONTRADICTORIA'
            elif estado_eges == estado_netterm:
                comparacion_estados = 'EQUIVALENTES'
            elif estado_eges is None or estado_netterm == 'DESCONOCIDO':
                comparacion_estados = 'NO_COMPARABLES'
            else:
                comparacion_estados = 'DIFERENTES'
            if estado_eges != estado_netterm:
                motivos.append('Los estados de informe/anulacion no son equivalentes o no son comparables.')
            if motivos:
                estado = 'CONFLICTO'
        else:
            motivos.append('Sin candidata EGES por DNI, codigo y fecha de pedido dentro de los lotes EGES seleccionados.')
        # La categoria historica conserva sus reglas para no cambiar el conteo.
        # Una diferencia de estado sin anulacion no invalida la identidad ni exige
        # decidir manualmente VINCULAR/NO_VINCULAR para cada pareja.
        alerta_estado = identidad_coincidente and estado == 'CONFLICTO' and not contradiccion_anulacion
        revision_identidad = estado in {'AMBIGUO', 'CONFLICTO'} and not identidad_coincidente
        revision_estado = identidad_coincidente and contradiccion_anulacion
        resultados.append({
            'estado': estado, 'motivos': motivos,
            'netterm': _datos_netterm(grupo),
            'eges': [_datos_eges(candidata) for candidata in candidatas],
            'advertencias': advertencias,
            'identidad_coincidente': identidad_coincidente,
            'comparacion_estados': comparacion_estados,
            'alerta_estado_no_bloqueante': alerta_estado,
            'contradiccion_anulacion': contradiccion_anulacion,
            'requiere_revision_identidad': revision_identidad,
            'requiere_revision_estado': revision_estado,
            'requiere_revision_produccion': revision_identidad or revision_estado,
        })
    for fila in eges:
        relacionadas = grupos_por_eges.get(fila.pk, set())
        if relacionadas:
            continue
        clave = (_dni(fila.dni_paciente), _codigo(fila.codigo_practica), fila.fecha_turno)
        estado = 'SOLO_EGES' if all(clave) else 'CONFLICTO'
        resultados.append({
            'estado': estado,
            'motivos': ['Sin observacion Netterm candidata en los lotes seleccionados.'] if all(clave) else [
                'La fila EGES no tiene DNI, codigo o fecha suficientes para comparar.',
            ],
            'netterm': None, 'eges': [_datos_eges(fila)], 'advertencias': [],
            'identidad_coincidente': False, 'comparacion_estados': 'NO_COMPARADOS',
            'alerta_estado_no_bloqueante': False, 'contradiccion_anulacion': False,
            'requiere_revision_identidad': estado == 'CONFLICTO',
            'requiere_revision_estado': False,
            'requiere_revision_produccion': estado == 'CONFLICTO',
        })
    conteos = Counter(resultado['estado'] for resultado in resultados)
    return {
        'version_motor': VERSION_CRUCE_NETTERM_EGES,
        'firma_snapshot': _firma_snapshot(
            batch_id if batch_id else batch_ids, ids, eges, grupos, desde, hasta,
            modalidades_eges_filtradas, modalidades,
        ),
        'batch_eges_id': batch_id, 'lote_netterm_ids': sorted(ids),
        'batch_eges_ids': batch_ids,
        'fecha_desde': desde, 'fecha_hasta': hasta,
        'modalidades_netterm': sorted(modalidades) if modalidades is not None else None,
        'modalidades_eges': sorted(modalidades_eges_filtradas) if modalidades_eges_filtradas is not None else None,
        'permite_revision': (len(batch_ids) == 1 and len(ids) <= MAX_LOTES_NETTERM_CRUCE
                     and not desde and not hasta and modalidades is None
                     and modalidades_eges_filtradas is None),
        'resumen': {
            'filas_eges': cantidad_eges, 'observaciones_netterm': cantidad_netterm,
            'observaciones_netterm_modalidad': cantidad_netterm_modalidad,
            'insumos_netterm_excluidos': cantidad_insumos,
            'grupos_netterm': len(grupos),
            'observaciones_adicionales': cantidad_netterm_modalidad - len(grupos),
            'estados': [{'estado': estado, 'cantidad': conteos[estado]} for estado in ESTADOS_CRUCE],
            'filas_eges_con_candidata': len(grupos_por_eges),
            'correspondencias_identidad_unica': sum(item['identidad_coincidente'] for item in resultados),
            'alertas_estado_no_bloqueantes': sum(item['alerta_estado_no_bloqueante'] for item in resultados),
            'contradicciones_anulacion': sum(item['requiere_revision_estado'] for item in resultados),
            'excepciones_produccion': sum(item['requiere_revision_produccion'] for item in resultados),
        },
        'resultados': resultados,
    }


def construir_preview_conteo_consolidado(**seleccion):
    """Cuenta practicas informadas por fecha de turno/pedido; no publica ni persiste."""
    preview = construir_preview_conciliacion(**seleccion)
    eges_por_id = {
        fila['id']: fila for caso in preview['resultados'] for fila in caso['eges']
    }
    base_eges = Counter()
    aporte_netterm = Counter()
    pendientes = Counter()
    excluidos = Counter()
    pacientes = set()
    pacientes_eges = set()
    pacientes_netterm = set()
    no_identificables = Counter()
    compartidos = 0
    for fila in eges_por_id.values():
        if not fila['paciente_clave']:
            no_identificables['filas_eges_consultadas'] += 1
        estado = _texto_normalizado(fila['estado'])
        if estado in {'ANULADO', 'CANCELADO'}:
            excluidos['eges_anulado'] += 1
        elif estado != 'INFORMADO':
            pendientes['eges_estado_no_informado'] += 1
        elif not fila['fecha_turno']:
            pendientes['eges_sin_fecha'] += 1
        elif fila['modalidad'] in {'OTROS', 'SIN_CLASIFICAR', ''}:
            pendientes['eges_clasificacion'] += 1
        else:
            base_eges[fila['modalidad']] += 1
            if fila['paciente_clave']:
                pacientes.add(fila['paciente_clave'])
                pacientes_eges.add(fila['paciente_clave'])
            else:
                no_identificables['practicas_eges_incluidas'] += 1
    for caso in preview['resultados']:
        fila = caso['netterm']
        if not fila:
            continue
        if not fila['paciente_clave']:
            no_identificables['grupos_netterm_consultados'] += 1
        if fila['vigencia_incierta']:
            pendientes['netterm_vigencia_no_verificada'] += 1
            continue
        if fila['anulado']:
            excluidos['netterm_anulado'] += 1
            continue
        if fila['estado'] != 'DEFINITIVO':
            pendientes['netterm_estado_no_definitivo'] += 1
            continue
        if not fila['fecha_pedido']:
            pendientes['netterm_sin_fecha'] += 1
            continue
        if fila['modalidad'] == 'SIN_CLASIFICAR':
            pendientes['netterm_clasificacion'] += 1
            continue
        if caso['estado'] == 'SOLO_NETTERM':
            modalidad = 'ECO' if fila['modalidad'] in {'ECO_GENERAL', 'DOP', 'ECOCAR'} else fila['modalidad']
            aporte_netterm[modalidad] += 1
            if fila['paciente_clave']:
                pacientes.add(fila['paciente_clave'])
                pacientes_netterm.add(fila['paciente_clave'])
            else:
                no_identificables['practicas_netterm_incluidas'] += 1
        elif caso['estado'] != 'COINCIDENTE':
            pendientes['netterm_correspondencia_no_resuelta'] += 1
        else:
            compartidos += 1
    modalidades = sorted(set(base_eges) | set(aporte_netterm))
    explicaciones = {
        'eges_estado_no_informado': 'No cumple INFORMADO; puede agregar practicas si se confirma un estado elegible.',
        'eges_sin_fecha': 'No puede ubicarse en el periodo; una fecha verificada puede cambiar el total.',
        'eges_clasificacion': 'Modalidad pendiente; clasificar puede agregar practicas.',
        'netterm_estado_no_definitivo': 'No cumple DEFINITIVO; no inferir equivalencia con otros estados.',
        'netterm_sin_fecha': 'Fecha de pedido ausente; no sustituir por fecha de informe.',
        'netterm_clasificacion': 'Modalidad desconocida; solo agrega si tambien es exclusivo y elegible.',
        'netterm_correspondencia_no_resuelta': 'Puede agregar cero o mas practicas; no todos los candidatos son extras.',
        'netterm_vigencia_no_verificada': 'Exportaciones divergentes sin cronologia verificable; no elegir por importacion.',
    }
    desglose = [
        {'motivo': motivo, 'cantidad': cantidad, 'tipo': 'pendiente',
         'puede_modificar_total': True, 'explicacion': explicaciones[motivo]}
        for motivo, cantidad in sorted(pendientes.items())
    ]
    desglose.extend([
        {'motivo': motivo, 'cantidad': cantidad, 'tipo': 'exclusion',
         'puede_modificar_total': False,
         'explicacion': 'No aporta practicas con la evidencia actual; solo cambia con una rectificacion de origen.'}
        for motivo, cantidad in sorted(excluidos.items())
    ])
    desglose.append({
        'motivo': 'netterm_insumo', 'cantidad': preview['resumen']['insumos_netterm_excluidos'],
        'tipo': 'exclusion', 'puede_modificar_total': False,
        'explicacion': 'Material conservado en origen, no practica; un falso positivo requiere corregir clasificacion.',
    })
    return {
        'version_reglas': 'INFORMADAS_TURNO_PEDIDO_V2',
        'indicador': 'Practicas informadas por fecha de turno EGES / pedido Netterm',
        'unidad': 'Practica identificada, no cantidad economica ni paciente',
        'provisional': True,
        'batch_eges_ids': preview['batch_eges_ids'],
        'lote_netterm_ids': preview['lote_netterm_ids'],
        'fecha_desde': preview['fecha_desde'], 'fecha_hasta': preview['fecha_hasta'],
        'firma_snapshot': preview['firma_snapshot'],
        'base_eges': sum(base_eges.values()),
        'aporte_netterm': sum(aporte_netterm.values()),
        'total_provisional': sum(base_eges.values()) + sum(aporte_netterm.values()),
        'por_modalidad': [
            {'modalidad': modalidad, 'eges': base_eges[modalidad], 'netterm': aporte_netterm[modalidad],
             'total': base_eges[modalidad] + aporte_netterm[modalidad]}
            for modalidad in modalidades
        ],
        'pendientes': dict(pendientes), 'excluidos': dict(excluidos),
        'desglose': desglose,
        'netterm_compartidos_sin_aporte': compartidos,
        'pacientes_unicos_identificables': len(pacientes),
        'pacientes_eges_identificables': len(pacientes_eges),
        'pacientes_aporte_netterm_identificables': len(pacientes_netterm),
        'pacientes_compartidos_entre_aportes': len(pacientes_eges & pacientes_netterm),
        'no_identificables': dict(no_identificables),
        'identidad_paciente': 'DNI numerico normalizado, sin HC ni nombres; total de practicas incluidas solamente',
        'insumos_netterm_excluidos': preview['resumen']['insumos_netterm_excluidos'],
        'requiere_revision_individual_de_coincidencias': False,
    }


def registrar_revision_conciliacion(
    *, batch_eges_id, lote_netterm_ids, fila_netterm_id, fila_eges_id,
    firma_esperada, decision, motivo, usuario,
):
    """Registra una decision explicita para un par del snapshot actual, sin fusionarlo."""
    if not getattr(usuario, 'is_superuser', False):
        raise ValidationError('Solo un superusuario puede revisar la conciliacion.')
    if decision not in dict(ConciliacionRevision.DECISION_CHOICES):
        raise ValidationError('Selecciona una decision de revision valida.')
    motivo = str(motivo or '').strip()
    if len(motivo) < 8 or len(motivo) > 2000:
        raise ValidationError('El motivo debe tener entre 8 y 2000 caracteres.')
    try:
        batch_id = int(batch_eges_id)
        netterm_id = int(fila_netterm_id)
        eges_id = int(fila_eges_id)
        lote_ids = [int(valor) for valor in lote_netterm_ids]
    except (TypeError, ValueError):
        raise ValidationError('La seleccion de origen no es valida.') from None

    try:
        with transaction.atomic():
            batch = ImportBatch.objects.select_for_update().filter(pk=batch_id).first()
            if batch is None:
                raise ValidationError('El lote EGES seleccionado ya no existe.')
            preview = construir_preview_conciliacion(batch_eges_id=batch_id, lote_netterm_ids=lote_ids)
            if preview['firma_snapshot'] != firma_esperada:
                raise ValidationError('Las fuentes cambiaron desde el preview; vuelve a cargarlo antes de revisar.')
            caso = next((
                item for item in preview['resultados']
                if item['netterm'] and item['netterm']['id'] == netterm_id
                and any(fila['id'] == eges_id for fila in item['eges'])
            ), None)
            if caso is None:
                raise ValidationError('Ese par de filas no es candidato en el preview seleccionado.')
            fila_eges = EgesRow.objects.select_for_update().filter(pk=eges_id, batch_id=batch_id).first()
            fila_netterm = NettermFila.objects.select_for_update().filter(
                pk=netterm_id, lote_id__in=lote_ids,
            ).first()
            if fila_eges is None or fila_netterm is None:
                raise ValidationError('Una de las filas de origen ya no existe.')
            preview_confirmado = construir_preview_conciliacion(
                batch_eges_id=batch_id, lote_netterm_ids=lote_ids,
            )
            if preview_confirmado['firma_snapshot'] != firma_esperada:
                raise ValidationError('Las fuentes cambiaron durante la revision; vuelve a cargar el preview.')
            caso = next((
                item for item in preview_confirmado['resultados']
                if item['netterm'] and item['netterm']['id'] == netterm_id
                and any(fila['id'] == eges_id for fila in item['eges'])
            ), None)
            if caso is None:
                raise ValidationError('Ese par de filas dejo de ser candidato durante la revision.')
            preview = preview_confirmado

            revisiones_actuales = ConciliacionRevision.objects.select_for_update().filter(
                firma_snapshot=firma_esperada, revision_siguiente__isnull=True,
            )
            revision_previa = revisiones_actuales.filter(
                fila_netterm=fila_netterm, fila_eges=fila_eges,
            ).first()
            if revision_previa and revision_previa.decision == decision:
                raise ValidationError('Esta decision ya esta vigente para el par seleccionado.')
            vinculaciones = revisiones_actuales.filter(decision=ConciliacionRevision.DECISION_VINCULAR)
            if revision_previa:
                vinculaciones = vinculaciones.exclude(pk=revision_previa.pk)
            if decision == ConciliacionRevision.DECISION_VINCULAR and (
                vinculaciones.filter(fila_eges=fila_eges).exists()
                or vinculaciones.filter(fila_netterm=fila_netterm).exists()
            ):
                raise ValidationError('Otra decision vigente ya vincula una de estas filas en este snapshot.')

            return ConciliacionRevision.objects.create(
                firma_snapshot=firma_esperada,
                batch_eges=batch,
                fila_netterm=fila_netterm,
                fila_eges=fila_eges,
                lotes_netterm_ids=preview['lote_netterm_ids'],
                observaciones_netterm_ids=caso['netterm']['observaciones_ids'],
                candidatas_eges_ids=[fila['id'] for fila in caso['eges']],
                version_motor=preview['version_motor'],
                estado_preview=caso['estado'],
                decision=decision,
                motivos_cruce_json=caso['motivos'],
                motivo=motivo,
                revisado_por=usuario,
                reemplaza_revision=revision_previa,
            )
    except IntegrityError:
        raise ValidationError('La decision cambio en paralelo; vuelve a cargar el preview.') from None
