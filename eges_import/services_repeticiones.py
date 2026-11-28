"""Revisión explícita de repeticiones ECO; nunca deduplicar por proximidad horaria."""
from collections import defaultdict
import hashlib
from django.core.exceptions import ValidationError
from django.utils.dateparse import parse_time
from .services_conciliacion import _codigo, _texto_normalizado
from .services_bilateralidad import clasificar_doppler_estadistico
from .services_procedimientos import CODIGOS_COMPLEMENTARIOS


def detectar_repeticiones_eco(preview, elegibles, originales, desde, hasta, *, incluir_mmii=False):
    grupos = defaultdict(lambda: {'eges': {}, 'netterm': {}})
    for caso in preview['resultados']:
        for fila in caso['eges']:
            if (fila['modalidad'] != 'ECO' or not fila['paciente_clave']
                    or not fila['fecha_turno'] or not desde <= fila['fecha_turno'] <= hasta
                    or _texto_normalizado(fila['estado']) not in {'INFORMADO', 'FIN PRACTICA', 'ENTREGADO SIN INFORME'}):
                continue
            clave = (fila['paciente_clave'], fila['fecha_turno'], _codigo(fila['codigo']))
            grupos[clave]['eges'][fila['id']] = fila
    for fila in elegibles:
        if fila['modalidad'] not in {'ECO', 'ECO_GENERAL', 'DOP', 'ECOCAR'} or not fila['paciente_clave']:
            continue
        clave = (fila['paciente_clave'], fila['fecha_realizacion'], _codigo(fila['codigo']))
        grupos[clave]['netterm'][fila['id']] = fila
    resultado = []
    for clave, miembros in grupos.items():
        eges, nt = list(miembros['eges'].values()), list(miembros['netterm'].values())
        if max(len(eges), len(nt)) < 2 or clave[2] in CODIGOS_COMPLEMENTARIOS or clave[2] == '900079':
            continue
        ejemplo = (eges or nt)[0]
        if not incluir_mmii and clasificar_doppler_estadistico(ejemplo['practica'], ejemplo['codigo']):
            continue  # La pantalla bilateral ya revisa estos grupos.
        ids_eges, ids_nt = sorted(miembros['eges']), sorted(miembros['netterm'])
        firma = hashlib.sha256(repr((ids_eges, ids_nt)).encode()).hexdigest()[:24]
        origen = originales.get(ids_nt[0], {}) if ids_nt else {}
        # No se deduce independencia por la diferencia de horas. Las horas sólo
        # permiten distribuir vínculos DESPUÉS de la decisión humana.
        independientes, usadas = {}, set()
        for fila in nt:
            hora = originales.get(fila['id'], {}).get('hora_pedido')
            if isinstance(hora, str):
                hora = parse_time(hora)
            candidatas = [item for item in eges if hora is not None and item['hora_turno'] == hora]
            if len(candidatas) == 1 and candidatas[0]['id'] not in usadas:
                usadas.add(candidatas[0]['id'])
                independientes[str(fila['id'])] = {'accion': f"VINCULAR:{candidatas[0]['id']}", 'modalidad': 'ECO'}
            elif not eges:
                independientes[str(fila['id'])] = {'accion': 'ADICIONAL', 'modalidad': 'ECO'}
        unico = {}
        for indice, fila in enumerate(nt):
            unico[str(fila['id'])] = (
                {'accion': f"VINCULAR:{ids_eges[0]}", 'modalidad': 'ECO'} if indice == 0 and ids_eges
                else {'accion': 'ADICIONAL', 'modalidad': 'ECO'} if indice == 0
                else {'accion': 'EXCLUIR'}
            )
        resultado.append({
            'id': 'eco:' + firma, 'tipo': 'REPETICION_ECO', 'fecha': clave[1],
            'paciente': origen.get('paciente', ''), 'documento': origen.get('documento', ''),
            'practica': ejemplo['practica'], 'filas_ids': ids_nt, 'eges_ids': ids_eges,
            'filas': [{'fuente': 'EGES', 'id': fila['id'], 'hora': fila['hora_turno'],
                       'practica': fila['practica'], 'cantidad': fila['cantidad']} for fila in eges]
                     + [{'fuente': 'Netterm', 'id': fila['id'], 'hora': originales.get(fila['id'], {}).get('hora_realizacion'),
                         'pedido': originales.get(fila['id'], {}).get('pedido', ''),
                         'practica': fila['practica']} for fila in nt],
            'sugerencias': {'UNICO': unico, 'INDEPENDIENTES': independientes},
        })
    return resultado


def completar_decisiones_repeticiones(grupos, excepciones, decisiones):
    if not isinstance(decisiones, dict):
        raise ValidationError('Las decisiones no son válidas.')
    resultado = dict(decisiones)
    for grupo in grupos:
        decision = resultado.get(grupo['id'], {})
        if not isinstance(decision, dict):
            raise ValidationError('La decisión del grupo no es válida.')
        accion = decision.get('accion', '')
        if accion in {'UNICO', 'INDEPENDIENTES'}:
            for clave, sugerencia in grupo['sugerencias'][accion].items():
                if clave in excepciones and (accion == 'UNICO' or not resultado.get(clave, {}).get('accion')):
                    resultado[clave] = sugerencia
    return resultado


def aplicar_repeticiones(practicas, grupos, decisiones):
    aceptadas, auditoria = list(practicas), []
    for grupo in grupos:
        accion = decisiones.get(grupo['id'], {}).get('accion')
        if accion not in {'UNICO', 'INDEPENDIENTES'}:
            raise ValidationError('Revisá si la repetición es carga duplicada o realizaciones independientes.')
        ids_eges, ids_nt = set(grupo['eges_ids']), set(grupo['filas_ids'])
        miembros = [item for item in aceptadas if (
            ('fecha_turno' in item['fila'] and item['fila']['id'] in ids_eges)
            or ('fecha_pedido' in item['fila'] and item['fila']['id'] in ids_nt)
            or item.get('netterm', {}).get('id') in ids_nt)]
        antes = len(miembros)
        if accion == 'UNICO' and miembros:
            representante = next((item for item in miembros if item['fuente'] == 'EGES'), miembros[0])
            aceptadas = [item for item in aceptadas if all(item is not otro for otro in miembros)]
            aceptadas.append(representante)
        auditoria.append({'grupo': grupo['id'], 'decision': accion,
            'filas_eges': grupo['eges_ids'], 'filas_netterm': grupo['filas_ids'],
            'practicas_antes': antes, 'practicas_despues': 1 if accion == 'UNICO' and miembros else antes})
    return aceptadas, auditoria
