from datetime import time
import re
import unicodedata

from django.db.models import Q

from eges_import.models import EgesRow

from .services import ROLES_RESIDENCIA, es_fecha_feriado_liquidacion


HORA_INTRA_DESDE = time(8, 0)
HORA_INTRA_HASTA = time(17, 0)
TIPOS_LIQUIDACION_ECO = {'ECO', 'DOP', 'ECOCAR'}


def _normalizar_texto(valor):
    texto = str(valor or '').strip().lower()
    texto = ''.join(
        c for c in unicodedata.normalize('NFKD', texto)
        if not unicodedata.combining(c)
    )
    return re.sub(r'[^a-z0-9]+', ' ', texto).strip()


def _tokens(valor):
    return {
        token for token in _normalizar_texto(valor).split()
        if len(token) >= 3 and token not in {'eco', 'ecografia', 'ecografica', 'con', 'sin'}
    }


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


def _evaluar_cobertura_practicas(practicas_liquidacion, filas_eges):
    matches = []
    eges_usadas = set()
    liquidacion_sin_match = []

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
            matches.append({
                'liquidacion': practica,
                'fila_eges': fila,
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


def _buscar_candidatos_eges(registro, batch):
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


def _evaluar_registro(registro, batch):
    practicas = _practicas_liquidacion(registro)
    candidatos = _buscar_candidatos_eges(registro, batch)
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
    mejor = evaluados[0] if evaluados else None

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
        filas_para_cobertura = [
            item['fila_eges'] for item in evaluados
            if item['medico_ok']
        ] or [item['fila_eges'] for item in evaluados]
        matches_practicas, liquidacion_sin_match, eges_sin_liquidacion = _evaluar_cobertura_practicas(
            practicas,
            filas_para_cobertura,
        )

        if len([e for e in evaluados if e['puntaje'] == mejor['puntaje']]) > 1:
            motivos.append('Hay múltiples coincidencias EGES posibles.')
        if not mejor['medico_ok']:
            motivos.append('El profesional no coincide claramente como informante ni actuante.')
        if liquidacion_sin_match:
            motivos.append('Hay prácticas cargadas en liquidación sin coincidencia EGES ECO.')
        if eges_sin_liquidacion:
            motivos.append('Hay prácticas EGES ECO del mismo paciente/fecha/profesional no cargadas en liquidación.')
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


def construir_preview_cruce_liquidacion_eges(sesion, batch):
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

    resultados = [_evaluar_registro(registro, batch) for registro in registros]
    resumen = {
        'total': len(resultados),
        'ok': sum(1 for r in resultados if r['estado'] == 'ok'),
        'advertencia': sum(1 for r in resultados if r['estado'] == 'advertencia'),
        'manual': sum(1 for r in resultados if r['estado'] == 'manual'),
    }
    return {
        'sesion': sesion,
        'batch': batch,
        'resumen': resumen,
        'resultados': resultados,
    }
