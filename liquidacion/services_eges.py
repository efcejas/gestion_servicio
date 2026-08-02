from datetime import time
import re
import unicodedata

from django.db.models import Q

from eges_import.models import EgesRow

from .services import ROLES_RESIDENCIA


HORA_INTRA_DESDE = time(8, 0)
HORA_INTRA_HASTA = time(17, 0)


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


def _medico_coincide(fila, medico):
    esperado = _nombre_usuario_eges(medico)
    if not esperado:
        return False, None

    informante = _normalizar_texto(fila.medico_informante)
    actuante = _normalizar_texto(fila.medico_actuante)
    if esperado and (esperado in informante or informante in esperado):
        return True, 'informante'
    if esperado and (esperado in actuante or actuante in esperado):
        return True, 'actuante'
    return False, None


def _practicas_liquidacion(registro):
    relaciones = registro.registroestudio_set.select_related('estudio').all()
    nombres = []
    tokens = set()
    for rel in relaciones:
        nombre = rel.estudio.nombre
        nombres.append(f'{nombre} x{rel.cantidad}')
        tokens.update(_tokens(nombre))
        if rel.estudio.tipo:
            tokens.add(_normalizar_texto(rel.estudio.tipo))
    return nombres, tokens


def _practica_compatible(tokens_liquidacion, fila_eges):
    tokens_eges = _tokens(fila_eges.practica or fila_eges.servicio)
    if not tokens_liquidacion or not tokens_eges:
        return False, []
    interseccion = sorted(tokens_liquidacion & tokens_eges)
    return bool(interseccion), interseccion


def horario_esperado_por_eges(fila_eges):
    """
    Reglas de auditoría:
    - entre 08:00 y antes de 17:00 espera INTRA;
    - fuera de ese rango espera EXTRA;
    - si cruza 17:00 o falta hora, requiere revisión manual.
    """
    if not fila_eges or not fila_eges.hora_turno:
        return 'MANUAL', 'Sin hora EGES confiable.'

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
        es_insumo=False,
    )
    if registro.dni_paciente:
        qs = qs.filter(
            Q(dni_paciente=registro.dni_paciente)
            | Q(historia_clinica=registro.dni_paciente)
        )
    return list(qs.order_by('hora_turno', 'practica'))


def _evaluar_registro(registro, batch):
    practicas, tokens_liquidacion = _practicas_liquidacion(registro)
    candidatos = _buscar_candidatos_eges(registro, batch)
    evaluados = []

    for fila in candidatos:
        medico_ok, rol_medico_eges = _medico_coincide(fila, registro.medico)
        practica_ok, tokens_match = _practica_compatible(tokens_liquidacion, fila)
        horario_esperado, motivo_horario = horario_esperado_por_eges(fila)
        horario_ok = horario_esperado == registro.horario

        puntaje = 0
        puntaje += 4 if medico_ok else 0
        puntaje += 3 if practica_ok else 0
        puntaje += 2 if horario_ok else 0

        evaluados.append({
            'fila_eges': fila,
            'medico_ok': medico_ok,
            'rol_medico_eges': rol_medico_eges,
            'practica_ok': practica_ok,
            'tokens_match': tokens_match,
            'horario_esperado': horario_esperado,
            'motivo_horario': motivo_horario,
            'horario_ok': horario_ok,
            'puntaje': puntaje,
        })

    evaluados.sort(key=lambda item: item['puntaje'], reverse=True)
    mejor = evaluados[0] if evaluados else None

    estado = 'manual'
    motivos = []
    if not candidatos:
        estado = 'manual'
        motivos.append('No se encontró práctica EGES para el DNI y fecha del registro.')
    elif len([e for e in evaluados if e['puntaje'] == mejor['puntaje']]) > 1:
        estado = 'advertencia'
        motivos.append('Hay múltiples coincidencias EGES posibles.')
    elif mejor['medico_ok'] and mejor['practica_ok'] and mejor['horario_ok']:
        estado = 'ok'
        motivos.append('Coincide DNI, fecha, médico, práctica y horario esperado.')
    else:
        estado = 'advertencia'
        if not mejor['medico_ok']:
            motivos.append('El profesional no coincide claramente como informante ni actuante.')
        if not mejor['practica_ok']:
            motivos.append('La práctica EGES no coincide claramente con la práctica cargada.')
        if mejor['horario_esperado'] == 'MANUAL':
            motivos.append(mejor['motivo_horario'])
        elif not mejor['horario_ok']:
            motivos.append(f'EGES sugiere {mejor["horario_esperado"]}; liquidación figura {registro.horario}.')

    return {
        'registro': registro,
        'practicas_liquidacion': practicas,
        'estado': estado,
        'motivos': motivos,
        'mejor_match': mejor,
        'candidatos_count': len(candidatos),
        'otros_candidatos': evaluados[1:4],
    }


def construir_preview_cruce_liquidacion_eges(sesion, batch):
    registros = (
        sesion.practicas
        .filter(medico__rol__in=ROLES_RESIDENCIA)
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
