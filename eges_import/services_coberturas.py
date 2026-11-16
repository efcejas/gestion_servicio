"""Correspondencias estadísticas de coberturas conservando su origen."""
from collections import Counter, defaultdict
import re

from .services import _valor_valido
from .services_conciliacion import _texto_normalizado


def clave_cobertura(nombre):
    if not _valor_valido(nombre):
        return ''
    texto = re.sub(r'\(\s*C\s*\)\s*$', '', str(nombre), flags=re.IGNORECASE)
    texto = _texto_normalizado(texto)
    texto = re.sub(r'\s+(?:S A U|S A|SAU|SA|S R L|SRL)$', '', texto)
    return texto.replace(' ', '')


def construir_equivalencias_coberturas(practicas, eges, netterm, nombres_os):
    nombres_por_codigo = defaultdict(set)
    nombres_eges = {}
    for pk, fila in eges.items():
        codigo = str(fila.codigo_obra_social or '').strip()
        nombre = str(fila.obra_social or nombres_os.get(codigo) or codigo).strip()
        nombres_eges[pk] = nombre
        if codigo:
            nombres_por_codigo[codigo].add(nombre)
    por_codigo = {codigo: max(nombres, key=lambda nombre: (len(nombre), nombre))
                  for codigo, nombres in nombres_por_codigo.items()}
    por_fila_eges = {pk: por_codigo.get(str(fila.codigo_obra_social or '').strip(), nombres_eges[pk])
                     for pk, fila in eges.items()}
    nombres_por_clave = defaultdict(set)
    for pk, nombre in nombres_eges.items():
        if eges[pk].codigo_obra_social and clave_cobertura(nombre):
            nombres_por_clave[clave_cobertura(nombre)].add(por_fila_eges[pk])
    # Incorporar las variantes históricas sin código sólo si el nombre es inequívoco.
    for pk, fila in eges.items():
        candidatas = nombres_por_clave.get(clave_cobertura(nombres_eges[pk]), set())
        if not fila.codigo_obra_social and len(candidatas) == 1:
            por_fila_eges[pk] = next(iter(candidatas))
    for pk, nombre in nombres_eges.items():
        if clave_cobertura(nombre):
            nombres_por_clave[clave_cobertura(nombre)].add(por_fila_eges[pk])
    observaciones = defaultdict(lambda: defaultdict(set))
    for item in practicas:
        fila = item['fila']
        if not item.get('netterm') or 'fecha_turno' not in fila or not fila['paciente_clave']:
            continue
        datos = netterm.get(item['netterm']['id'], {})
        clave = clave_cobertura(datos.get('obra_social') or datos.get('cobertura'))
        nombre = por_fila_eges.get(fila['id'])
        if clave and clave_cobertura(nombre):
            observaciones[clave][nombre].add(fila['paciente_clave'])
    nombres_netterm = defaultdict(Counter)
    for datos in netterm.values():
        nombre = str(datos.get('obra_social') or datos.get('cobertura') or '').strip()
        if clave_cobertura(nombre):
            nombres_netterm[clave_cobertura(nombre)][nombre] += 1
    por_clave_netterm, pendientes = {}, {}
    for clave, nombres in nombres_netterm.items():
        nombre_original = nombres.most_common(1)[0][0]
        exactas = nombres_por_clave.get(clave, set())
        candidatas = exactas | set(observaciones[clave])
        if len(candidatas) == 1:
            candidata = next(iter(candidatas))
            if candidata in exactas or len(observaciones[clave][candidata]) >= 2:
                por_clave_netterm[clave] = candidata
                continue
        por_clave_netterm[clave] = nombre_original
        if candidatas:
            por_clave_netterm[clave] += ' (por revisar)'
            pendientes[clave] = {'netterm': nombre_original, 'candidatas': sorted(candidatas)}
    return {'eges': por_fila_eges, 'netterm': por_clave_netterm, 'pendientes': pendientes}
