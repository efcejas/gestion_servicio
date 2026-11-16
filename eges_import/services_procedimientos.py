"""Revisión conjunta de procedimientos guiados y sus registros complementarios."""
from collections import defaultdict
from copy import deepcopy
import hashlib

from django.core.exceptions import ValidationError

from .services_conciliacion import _codigo, _texto_normalizado


CODIGO_GUIADO = '900079'
MODALIDADES_GUIADAS = {
    CODIGO_GUIADO: 'ECO',
    '900080': 'TC', '900042': 'TC', '341311': 'TC', '341312': 'TC', '341306': 'TC',
    '900082': 'TC', '900034': 'TC', '341317': 'TC', '900413': 'TC', '900441': 'TC',
}
CODIGOS_COMPLEMENTARIOS = {'150101', '150111'}


def completar_decisiones_procedimientos(grupos, excepciones_ids, decisiones):
    if not isinstance(decisiones, dict):
        raise ValidationError('La selección de decisiones no es válida.')
    resultado = deepcopy(decisiones)
    for grupo in grupos:
        decision = resultado.get(grupo['id'], {})
        if not isinstance(decision, dict) or decision.get('accion') != 'UNICO':
            continue
        for componente, candidatas in grupo['candidatas_componentes'].items():
            if componente in excepciones_ids and len(candidatas) <= 1:
                resultado[componente] = {'accion': 'EXCLUIR'}
    return resultado


def detectar_grupos_procedimientos(filas, originales, casos, elegibles_ids=None):
    pedidos = defaultdict(list)
    codigos_admitidos = CODIGOS_COMPLEMENTARIOS | set(MODALIDADES_GUIADAS)
    for fila in filas:
        if _codigo(fila['codigo']) not in codigos_admitidos:
            continue
        origen = originales[fila['id']]
        documento = _texto_normalizado(origen.get('documento'))
        pedido = str(origen.get('pedido', '')).strip()
        if not documento or not pedido:
            continue
        clave = (pedido, _texto_normalizado(origen.get('tipo_documento')), documento)
        pedidos[clave].append(fila)
    grupos = []
    for miembros in pedidos.values():
        principales = [fila for fila in miembros if _codigo(fila['codigo']) in MODALIDADES_GUIADAS
                       and (elegibles_ids is None or fila['id'] in elegibles_ids)]
        complementarios = [fila for fila in miembros if _codigo(fila['codigo']) in CODIGOS_COMPLEMENTARIOS]
        if not principales or not complementarios:
            continue
        modalidades = {MODALIDADES_GUIADAS[_codigo(fila['codigo'])] for fila in principales}
        fechas = {fila['fecha_realizacion'] for fila in principales}
        if len(modalidades) != 1 or len(fechas) != 1:
            continue
        if elegibles_ids is not None and not any(
            fila['id'] in elegibles_ids or any(_texto_normalizado(eges['estado']) == 'INFORMADO'
                                             for eges in casos[fila['id']]['eges'])
            for fila in complementarios
        ):
            continue
        ids = sorted(fila['id'] for fila in miembros)
        firma = hashlib.sha256(repr(ids).encode()).hexdigest()[:24]
        primero = principales[0]
        origen = originales[primero['id']]
        grupos.append({
            'id': f'procedimiento:{firma}', 'paciente': origen.get('paciente', ''),
            'documento': origen.get('documento', ''), 'fecha': primero['fecha_realizacion'],
            'pedido': origen['pedido'], 'filas_ids': ids,
            'modalidad': next(iter(modalidades)),
            'modalidad_nombre': 'Tomografía' if 'TC' in modalidades else 'Ecografía',
            'principales_ids': [fila['id'] for fila in principales],
            'componentes_ids': [fila['id'] for fila in complementarios],
            'candidatas_componentes': {str(fila['id']): [eges['id'] for eges in casos[fila['id']]['eges']]
                                       for fila in complementarios},
            'candidatas_principales': {str(fila['id']): [eges['id'] for eges in casos[fila['id']]['eges']]
                                       for fila in principales},
            'filas': [{'id': fila['id'], 'practica': fila['practica'], 'estado': fila['estado']} for fila in miembros],
        })
    return grupos


def aplicar_decisiones_procedimientos(practicas, grupos, decisiones):
    aceptadas = list(practicas)
    auditoria = []
    for grupo in grupos:
        decision = decisiones[grupo['id']]
        if not isinstance(decision, dict) or decision.get('accion') not in {'UNICO', 'INDEPENDIENTES'}:
            raise ValidationError('Revisá si los registros del pedido representan un procedimiento guiado o prácticas independientes.')
        if decision['accion'] == 'INDEPENDIENTES':
            continue
        eges_complementarios = set()
        for netterm_id, candidatas in grupo['candidatas_componentes'].items():
            accion = decisiones.get(netterm_id, {}).get('accion', '')
            if len(candidatas) <= 1:
                eges_complementarios.update(candidatas)
            elif accion.startswith('VINCULAR:'):
                eges_complementarios.add(int(accion.split(':', 1)[1]))
            else:
                raise ValidationError('Elegí la candidata EGES de cada componente ambiguo antes de agrupar el procedimiento.')
        componentes = set(grupo['componentes_ids'])
        principales_eges = set()
        for netterm_id, candidatas in grupo['candidatas_principales'].items():
            accion = decisiones.get(netterm_id, {}).get('accion', '')
            if len(candidatas) <= 1:
                principales_eges.update(candidatas)
            elif accion.startswith('VINCULAR:'):
                principales_eges.add(int(accion.split(':', 1)[1]))
        conservadas = []
        retiradas = 0

        def es_principal(item):
            fila = item['fila']
            return (item.get('netterm', {}).get('id') in grupo['principales_ids']
                    or ('fecha_turno' in fila and fila['id'] in principales_eges)
                    or ('fecha_turno' not in fila and fila['id'] in grupo['principales_ids']))

        principales_aceptadas = [item for item in aceptadas if es_principal(item)]
        if not principales_aceptadas:
            raise ValidationError('Para agrupar el pedido debe quedar aceptada la práctica guiada principal.')
        principal = min(principales_aceptadas, key=lambda item: (item.get('fuente', 'EGES') != 'EGES', item['fila']['id']))
        for item in aceptadas:
            fila = item['fila']
            netterm_id = item.get('netterm', {}).get('id')
            es_eges = 'fecha_turno' in fila
            if (netterm_id in componentes or (es_eges and fila['id'] in eges_complementarios)
                    or (not es_eges and fila['id'] in componentes)):
                retiradas += 1
                continue
            if es_principal(item):
                if item is not principal:
                    retiradas += 1
                    continue
                item['procedimiento_guiado'] = True
                item['procedimiento_guiado_modalidad'] = grupo.get('modalidad', 'ECO')
            conservadas.append(item)
        aceptadas = conservadas
        auditoria.append({'grupo': grupo['id'], 'observaciones_netterm': grupo['filas_ids'],
                          'componentes_retirados_del_conteo': retiradas})
    return aceptadas, auditoria
