"""Unidad clínica de Doppler MMII y revisión de pedidos potencialmente bilaterales."""
from collections import defaultdict
import hashlib
import re
from types import SimpleNamespace

from django.core.exceptions import ValidationError

from liquidacion.services_auditoria import _clasificar_doppler_mmii
from .services_conciliacion import _texto_normalizado, _dni


def clasificar_doppler_estadistico(practica, codigo):
    nombre = _texto_normalizado(practica)
    nombre = re.sub(r'\bMM\s+INF\b', 'MM INFERIORES', nombre)
    nombre = re.sub(r'\bMIEMBRO\s+INFERIOR\b', 'MIEMBROS INFERIORES', nombre)
    return _clasificar_doppler_mmii(SimpleNamespace(
        nombre=nombre, codigo=codigo, tipo='', grupo_tarifario=None,
    ))


def detectar_grupos_bilaterales(filas, originales):
    grupos = defaultdict(list)
    for fila in filas:
        origen = originales.get(fila['id'], {})
        tipo_documento = _texto_normalizado(origen.get('tipo_documento')).replace(' ', '')
        documento = _texto_normalizado(origen.get('documento')).replace(' ', '')
        if tipo_documento == 'DNI':
            documento = _dni(documento)
        regla = clasificar_doppler_estadistico(fila['practica'], fila['codigo'])
        if not documento or not tipo_documento or not regla or regla['cantidad_esperada'] != 1:
            continue
        clave = (tipo_documento, documento, str(fila['fecha_realizacion']), regla['tipo'])
        grupos[clave].append(fila)
    resultado = []
    for clave, miembros in grupos.items():
        if len(miembros) < 2:
            continue
        primero = miembros[0]
        origen = originales[primero['id']]
        ids = sorted(fila['id'] for fila in miembros)
        firma = hashlib.sha256(repr(ids).encode()).hexdigest()[:24]
        resultado.append({
            'id': f'mmii:{firma}', 'tipo': clave[-1], 'fecha': primero['fecha_realizacion'],
            'paciente': origen.get('paciente', ''), 'documento': origen.get('documento', ''),
            'filas_ids': ids,
            'filas': [{'id': fila['id'], 'practica': fila['practica'],
                       'pedido': originales[fila['id']].get('pedido', ''),
                       'hora': originales[fila['id']].get('hora_realizacion', '')}
                      for fila in miembros],
        })
    return resultado


def aplicar_decisiones_bilaterales(practicas, grupos, decisiones):
    aceptadas = list(practicas)
    auditoria = []
    for grupo in grupos:
        decision = decisiones[grupo['id']]
        if not isinstance(decision, dict) or decision.get('accion') not in {'UNICO', 'INDEPENDIENTES'}:
            raise ValidationError('Indicá si cada grupo Doppler corresponde a un estudio bilateral o a estudios independientes.')
        if decision['accion'] == 'INDEPENDIENTES':
            continue
        ids = set(grupo['filas_ids'])
        miembros = [item for item in aceptadas
                    if item.get('netterm', {}).get('id') in ids
                    or ('fecha_pedido' in item['fila'] and item['fila']['id'] in ids)
                    or ('fecha_turno' in item['fila'] and item['fila']['id'] in grupo.get('eges_ids', []))]
        if len(miembros) > 1:
            # EGES conserva su prioridad de respaldo al elegir la fila representativa.
            representante = next((item for item in miembros if item['fuente'] == 'EGES'), miembros[0])
            aceptadas = [item for item in aceptadas if all(item is not miembro for miembro in miembros)]
            aceptadas.append(representante)
            auditoria.append({'grupo': grupo['id'], 'observaciones_netterm': grupo['filas_ids'],
                              'practicas_antes': len(miembros), 'practicas_despues': 1})
    return aceptadas, auditoria
