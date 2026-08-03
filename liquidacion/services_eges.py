from datetime import time
import re
import unicodedata
from collections import OrderedDict, defaultdict

from django.db.models import Q
from django.utils.dateparse import parse_date

from eges_import.models import EgesRow

from .models import RevisionCruceEgesRegistro
from .services import ROLES_RESIDENCIA, es_fecha_feriado_liquidacion


HORA_INTRA_DESDE = time(8, 0)
HORA_INTRA_HASTA = time(17, 0)
TIPOS_LIQUIDACION_ECO = {'ECO', 'DOP', 'ECOCAR'}
SINONIMOS_PRACTICAS_ECO = {
    'abdomen': {'abdominal', 'eco_abdominal'},
    'abdominal': {'abdomen', 'eco_abdominal'},
    'eco_abdominal': {'abdomen', 'abdominal'},
}


def _normalizar_texto(valor):
    texto = str(valor or '').strip().lower()
    texto = ''.join(
        c for c in unicodedata.normalize('NFKD', texto)
        if not unicodedata.combining(c)
    )
    return re.sub(r'[^a-z0-9]+', ' ', texto).strip()


def _tokens(valor):
    tokens = {
        token for token in _normalizar_texto(valor).split()
        if len(token) >= 3 and token not in {'eco', 'ecografia', 'ecografica', 'con', 'sin'}
    }
    expandidos = set(tokens)
    for token in tokens:
        expandidos.update(SINONIMOS_PRACTICAS_ECO.get(token, set()))
    return expandidos


def _nombre_usuario_eges(user):
    partes = [
        getattr(user, 'last_name', '') or '',
        getattr(user, 'first_name', '') or '',
    ]
    nombre = ' '.join(p for p in partes if p).strip()
    return _normalizar_texto(nombre or getattr(user, 'username', ''))


def _tokens_nombre_medico(valor):
    stopwords = {'medico', 'no', 'especificado', 'sin', 'dr', 'dra', 'doctor', 'doctora'}
    return {
        token for token in _normalizar_texto(valor).split()
        if len(token) >= 3 and token not in stopwords
    }


def _nombre_medico_coincide(tokens_esperados, nombre_eges):
    tokens_eges = _tokens_nombre_medico(nombre_eges)
    if not tokens_esperados or not tokens_eges:
        return False
    if tokens_esperados.issubset(tokens_eges):
        return True
    return len(tokens_esperados & tokens_eges) >= 2


def _medico_coincide(fila, medico):
    esperado = _nombre_usuario_eges(medico)
    tokens_esperados = _tokens_nombre_medico(esperado)
    if not tokens_esperados:
        return False, None

    if _nombre_medico_coincide(tokens_esperados, fila.medico_informante):
        return True, 'informante'
    if _nombre_medico_coincide(tokens_esperados, fila.medico_actuante):
        return True, 'actuante'
    return False, None


def _practicas_liquidacion(registro):
    relaciones = registro.registroestudio_set.select_related('estudio').all()
    practicas = []
    for rel in relaciones:
        if rel.estudio.tipo not in TIPOS_LIQUIDACION_ECO:
            continue
        nombre = rel.estudio.nombre
        tokens = _tokens(nombre)
        if rel.estudio.tipo:
            tokens.add(_normalizar_texto(rel.estudio.tipo))
        practicas.append({
            'relacion': rel,
            'nombre': nombre,
            'cantidad': rel.cantidad,
            'display': f'{nombre} x{rel.cantidad}',
            'tokens': tokens,
        })
    return practicas


def _practica_compatible(tokens_liquidacion, fila_eges):
    tokens_eges = _tokens(fila_eges.practica or fila_eges.servicio)
    if not tokens_liquidacion or not tokens_eges:
        return False, []
    interseccion = sorted(tokens_liquidacion & tokens_eges)
    return bool(interseccion), interseccion


def _evaluar_cobertura_practicas(practicas_liquidacion, filas_eges, evaluados_por_pk=None):
    matches = []
    eges_usadas = set()
    liquidacion_sin_match = []
    evaluados_por_pk = evaluados_por_pk or {}

    for practica in practicas_liquidacion:
        candidatos = []
        for fila in filas_eges:
            if fila.pk in eges_usadas:
                continue
            compatible, tokens_match = _practica_compatible(practica['tokens'], fila)
            if compatible:
                candidatos.append((fila, tokens_match))
        if candidatos:
            fila, tokens_match = candidatos[0]
            eges_usadas.add(fila.pk)
            cantidad_ok = int(practica['cantidad']) == int(fila.cantidad or 0)
            evaluacion_eges = evaluados_por_pk.get(fila.pk, {})
            matches.append({
                'liquidacion': practica,
                'fila_eges': fila,
                'medico_ok': evaluacion_eges.get('medico_ok', False),
                'rol_medico_eges': evaluacion_eges.get('rol_medico_eges'),
                'tokens_match': tokens_match,
                'cantidad_ok': cantidad_ok,
            })
        else:
            liquidacion_sin_match.append(practica)

    eges_sin_liquidacion = [
        fila for fila in filas_eges
        if fila.pk not in eges_usadas
    ]

    return matches, liquidacion_sin_match, eges_sin_liquidacion


def _clave_grupo_turno_eges(fila):
    return (
        fila.historia_clinica or fila.dni_paciente or '',
        fila.fecha_turno,
        fila.hora_turno,
        fila.hora_hasta,
        _normalizar_texto(fila.centro_atencion),
        _normalizar_texto(fila.tipo_atencion),
    )


def _agrupar_por_turno_eges(filas):
    grupos = OrderedDict()
    for fila in filas:
        clave = _clave_grupo_turno_eges(fila)
        if clave not in grupos:
            grupos[clave] = []
        grupos[clave].append(fila)
    return list(grupos.values())


def horario_esperado_por_eges(fila_eges):
    """
    Reglas de auditoría alineadas a liquidación:
    - sábados, domingos y feriados no aplican INTRA;
    - en día hábil no feriado, entre 08:00 y antes de 17:00 espera INTRA;
    - fuera de ese rango espera EXTRA;
    - si cruza 17:00 o falta hora, requiere revisión manual.
    """
    if not fila_eges or not fila_eges.fecha_turno or not fila_eges.hora_turno:
        return 'MANUAL', 'Sin hora EGES confiable.'

    if fila_eges.fecha_turno.weekday() >= 5:
        return 'EXTRA', 'Sábado/domingo no aplica INTRA.'

    if es_fecha_feriado_liquidacion(fila_eges.fecha_turno):
        return 'EXTRA', 'Feriado no aplica INTRA.'

    inicio = fila_eges.hora_turno
    fin = fila_eges.hora_hasta
    if fin and inicio < HORA_INTRA_HASTA <= fin:
        return 'MANUAL', 'El turno EGES cruza el límite de las 17:00.'

    if HORA_INTRA_DESDE <= inicio < HORA_INTRA_HASTA:
        return 'INTRA', 'Horario EGES entre 08:00 y 17:00.'
    return 'EXTRA', 'Horario EGES fuera de 08:00 a 17:00.'


def _buscar_candidatos_eges(registro, batch, indice_candidatos=None):
    if indice_candidatos is not None:
        clave = (registro.fecha_del_informe, str(registro.dni_paciente or '').strip())
        return indice_candidatos.get(clave, [])

    qs = EgesRow.objects.filter(
        batch=batch,
        fecha_turno=registro.fecha_del_informe,
        modalidad='ECO',
        es_insumo=False,
    )
    if registro.dni_paciente:
        qs = qs.filter(
            Q(dni_paciente=registro.dni_paciente)
            | Q(historia_clinica=registro.dni_paciente)
        )
    return list(qs.order_by('hora_turno', 'practica'))


def _evaluar_registro(registro, batch, indice_candidatos=None):
    practicas = _practicas_liquidacion(registro)
    candidatos = _buscar_candidatos_eges(registro, batch, indice_candidatos=indice_candidatos)
    evaluados = []

    for fila in candidatos:
        medico_ok, rol_medico_eges = _medico_coincide(fila, registro.medico)
        horario_esperado, motivo_horario = horario_esperado_por_eges(fila)
        horario_ok = horario_esperado == registro.horario

        puntaje = 0
        puntaje += 4 if medico_ok else 0
        puntaje += 2 if horario_ok else 0

        evaluados.append({
            'fila_eges': fila,
            'medico_ok': medico_ok,
            'rol_medico_eges': rol_medico_eges,
            'horario_esperado': horario_esperado,
            'motivo_horario': motivo_horario,
            'horario_ok': horario_ok,
            'puntaje': puntaje,
        })

    evaluados.sort(key=lambda item: item['puntaje'], reverse=True)
    grupos_evaluados = []
    evaluados_por_pk = {item['fila_eges'].pk: item for item in evaluados}

    for filas_grupo in _agrupar_por_turno_eges(candidatos):
        filas_evaluadas = [
            evaluados_por_pk[fila.pk]
            for fila in filas_grupo
            if fila.pk in evaluados_por_pk
        ]
        if not filas_evaluadas:
            continue

        representante = filas_evaluadas[0]
        grupo_medico_ok = any(item['medico_ok'] for item in filas_evaluadas)
        rol_medico_eges = next(
            (item['rol_medico_eges'] for item in filas_evaluadas if item['rol_medico_eges']),
            None,
        )
        matches_grupo, liquidacion_sin_match_grupo, eges_sin_liquidacion_grupo = _evaluar_cobertura_practicas(
            practicas,
            filas_grupo,
            evaluados_por_pk=evaluados_por_pk,
        )
        practicas_otro_profesional = [
            match for match in matches_grupo
            if not match['medico_ok']
        ]

        puntaje = 0
        puntaje += 4 if grupo_medico_ok else 0
        puntaje += 2 if representante['horario_ok'] else 0
        puntaje += 3 * len(matches_grupo)
        puntaje -= 2 * len(liquidacion_sin_match_grupo)
        puntaje -= len(eges_sin_liquidacion_grupo)
        puntaje -= 2 * len(practicas_otro_profesional)

        grupos_evaluados.append({
            **representante,
            'filas_eges': filas_grupo,
            'filas_evaluadas': filas_evaluadas,
            'filas_count': len(filas_grupo),
            'medico_ok': grupo_medico_ok,
            'rol_medico_eges': rol_medico_eges,
            'matches_practicas': matches_grupo,
            'liquidacion_sin_match': liquidacion_sin_match_grupo,
            'eges_sin_liquidacion': eges_sin_liquidacion_grupo,
            'practicas_otro_profesional': practicas_otro_profesional,
            'puntaje': puntaje,
        })

    grupos_evaluados.sort(key=lambda item: item['puntaje'], reverse=True)
    mejor = grupos_evaluados[0] if grupos_evaluados else None

    estado = 'manual'
    motivos = []
    matches_practicas = []
    liquidacion_sin_match = []
    eges_sin_liquidacion = []

    if not practicas:
        estado = 'manual'
        motivos.append('El registro no tiene prácticas ECO/DOP/ECOCAR para este cruce.')
    elif not candidatos:
        estado = 'manual'
        motivos.append('No se encontró práctica EGES ECO para el DNI y fecha del registro.')
        liquidacion_sin_match = practicas
    else:
        matches_practicas = mejor['matches_practicas']
        liquidacion_sin_match = mejor['liquidacion_sin_match']
        eges_sin_liquidacion = mejor['eges_sin_liquidacion']

        if len([grupo for grupo in grupos_evaluados if grupo['puntaje'] == mejor['puntaje']]) > 1:
            motivos.append('Hay múltiples coincidencias EGES posibles.')
        if not mejor['medico_ok']:
            motivos.append('El profesional no coincide claramente como informante ni actuante.')
        if liquidacion_sin_match:
            motivos.append('Hay prácticas cargadas en liquidación sin coincidencia EGES ECO.')
        if eges_sin_liquidacion:
            motivos.append('Hay prácticas EGES ECO del mismo paciente/fecha/profesional no cargadas en liquidación.')
        if mejor.get('practicas_otro_profesional'):
            motivos.append('Hay prácticas EGES del mismo paciente/fecha realizadas por otro profesional.')
        if any(not match['cantidad_ok'] for match in matches_practicas):
            motivos.append('Hay prácticas con cantidad distinta entre liquidación y EGES.')
        if mejor['horario_esperado'] == 'MANUAL':
            motivos.append(mejor['motivo_horario'])
        elif not mejor['horario_ok']:
            motivos.append(f'EGES sugiere {mejor["horario_esperado"]}; liquidación figura {registro.horario}.')

        if motivos:
            estado = 'advertencia'
        else:
            estado = 'ok'
            motivos.append('Coincide DNI, fecha, médico, prácticas ECO y horario esperado.')

    return {
        'registro': registro,
        'practicas_liquidacion': [practica['display'] for practica in practicas],
        'matches_practicas': matches_practicas,
        'liquidacion_sin_match': liquidacion_sin_match,
        'eges_sin_liquidacion': eges_sin_liquidacion,
        'estado': estado,
        'motivos': motivos,
        'mejor_match': mejor,
        'candidatos_count': len(candidatos),
        'candidatos_eges': evaluados,
        'otros_candidatos': evaluados[1:4],
    }


def _parse_fecha_filtro(valor):
    return parse_date(str(valor or '').strip()) if valor else None


def _aplicar_filtros_base_registros(registros, filtros=None, registro_ids=None):
    filtros = filtros or {}

    if registro_ids is not None:
        registros = registros.filter(pk__in=registro_ids)

    profesional = str(filtros.get('profesional') or '').strip()
    if profesional:
        registros = registros.filter(medico_id=profesional)

    fecha_desde = _parse_fecha_filtro(filtros.get('fecha_desde'))
    if fecha_desde:
        registros = registros.filter(fecha_del_informe__gte=fecha_desde)

    fecha_hasta = _parse_fecha_filtro(filtros.get('fecha_hasta'))
    if fecha_hasta:
        registros = registros.filter(fecha_del_informe__lte=fecha_hasta)

    busqueda = str(filtros.get('q') or '').strip()
    if busqueda:
        registros = registros.filter(
            Q(dni_paciente__icontains=busqueda)
            | Q(apellido_paciente__icontains=busqueda)
            | Q(nombre_paciente__icontains=busqueda)
        )

    return registros


def _indexar_candidatos_eges(batch, registros):
    claves = {
        (registro.fecha_del_informe, str(registro.dni_paciente or '').strip())
        for registro in registros
        if registro.fecha_del_informe and registro.dni_paciente
    }
    if not claves:
        return {}

    fechas = {fecha for fecha, _dni in claves}
    dnis = {dni for _fecha, dni in claves}
    filas = (
        EgesRow.objects
        .filter(
            batch=batch,
            fecha_turno__in=fechas,
            modalidad='ECO',
            es_insumo=False,
        )
        .filter(Q(dni_paciente__in=dnis) | Q(historia_clinica__in=dnis))
        .order_by('fecha_turno', 'dni_paciente', 'hora_turno', 'practica')
    )

    indice = defaultdict(list)
    for fila in filas:
        for identificador in {fila.dni_paciente, fila.historia_clinica}:
            identificador = str(identificador or '').strip()
            if identificador:
                indice[(fila.fecha_turno, identificador)].append(fila)
    return indice


def construir_preview_cruce_liquidacion_eges(sesion, batch, filtros=None, registro_ids=None):
    registros = (
        sesion.practicas
        .filter(
            medico__rol__in=ROLES_RESIDENCIA,
            registroestudio__estudio__tipo__in=TIPOS_LIQUIDACION_ECO,
        )
        .distinct()
        .select_related('medico')
        .prefetch_related('registroestudio_set__estudio')
        .order_by('medico__last_name', 'medico__first_name', 'fecha_del_informe', 'apellido_paciente')
    )
    registros = _aplicar_filtros_base_registros(registros, filtros=filtros, registro_ids=registro_ids)
    registros = list(registros)

    indice_candidatos = _indexar_candidatos_eges(batch, registros)
    resultados = [
        _evaluar_registro(registro, batch, indice_candidatos=indice_candidatos)
        for registro in registros
    ]
    registro_ids = [resultado['registro'].pk for resultado in resultados]
    revisiones = (
        RevisionCruceEgesRegistro.objects
        .filter(registro_id__in=registro_ids, batch_eges=batch)
        .order_by('registro_id', '-fecha_revision')
    )
    revisiones_por_registro = {}
    for revision in revisiones:
        revisiones_por_registro.setdefault(revision.registro_id, revision)

    for resultado in resultados:
        revision = revisiones_por_registro.get(resultado['registro'].pk)
        resultado['revision_cruce_eges'] = revision
        resultado['cruce_eges_resuelto'] = bool(
            revision
            and revision.estado in {
                RevisionCruceEgesRegistro.ESTADO_VALIDADO,
                RevisionCruceEgesRegistro.ESTADO_DESCARTADO,
            }
        )
        resultado['cruce_eges_requiere_correccion'] = bool(
            revision
            and revision.estado == RevisionCruceEgesRegistro.ESTADO_REQUIERE_CORRECCION
        )

    resumen = {
        'total': len(resultados),
        'ok': sum(1 for r in resultados if r['estado'] == 'ok'),
        'advertencia': sum(1 for r in resultados if r['estado'] == 'advertencia'),
        'manual': sum(1 for r in resultados if r['estado'] == 'manual'),
        'pendientes_revision': sum(
            1 for r in resultados
            if r['estado'] != 'ok' and not r['cruce_eges_resuelto']
        ),
        'resueltos': sum(1 for r in resultados if r['cruce_eges_resuelto']),
        'requieren_correccion': sum(1 for r in resultados if r['cruce_eges_requiere_correccion']),
    }
    return {
        'sesion': sesion,
        'batch': batch,
        'resumen': resumen,
        'resultados': resultados,
    }
