"""Identificación estadística con documentos alternativos y HC de Netterm."""
from collections import defaultdict

from django.utils.crypto import salted_hmac

from .models import EgesRow, NettermFila
from .services_conciliacion import _dni, _paciente_clave, _texto_normalizado
from .services import _valor_valido


def _hc_netterm(valor):
    hc = _texto_normalizado(valor) if _valor_valido(valor) else ''
    return hc if hc.strip('0 ') else ''


def _nombre_identificacion(valor):
    if not _valor_valido(valor):
        return ()
    return tuple(sorted(_texto_normalizado(valor).split()))


def _identidades_netterm(eges, netterm):
    """Identificación estadística por documento y nombre, o HC propia de Netterm."""
    nombres_por_dni = defaultdict(set)
    dnis_por_hc = defaultdict(set)
    for fila in eges.values():
        dni = _dni(fila.dni_paciente)
        nombre = _nombre_identificacion(fila.apellido_nombre)
        if dni:
            nombres_por_dni[dni].add(nombre)
    for datos in netterm.values():
        dni = _dni(datos.get('documento'))
        tipo = _texto_normalizado(datos.get('tipo_documento')).replace(' ', '')
        if tipo == 'DNI' and dni:
            nombre = _nombre_identificacion(datos.get('paciente'))
            nombres_por_dni[dni].add(nombre)
            hc = _hc_netterm(datos.get('historia_clinica'))
            if hc:
                dnis_por_hc[hc].add(dni)
    identidades = {}
    for pk, datos in netterm.items():
        documento = _texto_normalizado(datos.get('documento')) if _valor_valido(datos.get('documento')) else ''
        if not documento.strip('0 '):
            documento = ''
        dni = _dni(datos.get('documento'))
        tipo = _texto_normalizado(datos.get('tipo_documento')).replace(' ', '')
        nombre = _nombre_identificacion(datos.get('paciente'))
        hc = _hc_netterm(datos.get('historia_clinica'))
        candidatos_hc = dnis_por_hc.get(hc, set())
        identidad = _paciente_clave(datos.get('documento'), datos.get('tipo_documento'))
        if not identidad:
            if len(candidatos_hc) == 1:
                dni_hc = next(iter(candidatos_hc))
                if dni not in nombres_por_dni or dni == dni_hc:
                    identidad = _paciente_clave(dni_hc)
            elif candidatos_hc:
                identidad = None
            elif dni in nombres_por_dni:
                if nombre and nombre in nombres_por_dni[dni]:
                    identidad = _paciente_clave(dni)
            elif documento and tipo in {'LC', 'LE', 'CI', 'PASAP', 'PASAPORTE'}:
                identidad = salted_hmac('eges_import.paciente_documento_alternativo.v1', f'{tipo}|{dni or documento}').hexdigest()
            elif not documento and hc:
                identidad = salted_hmac('eges_import.paciente_hc_netterm.v1', hc).hexdigest()
        identidades[pk] = identidad
    return identidades



def completar_identificacion_practicas(practicas):
    pendientes = [item for item in practicas if not item['fila']['paciente_clave']
                  and (item.get('netterm') or 'fecha_pedido' in item['fila'])]
    if not pendientes:
        return
    eges_ids = {item['fila']['id'] for item in practicas if 'fecha_turno' in item['fila']}
    netterm_ids = {item.get('netterm', item['fila'])['id'] for item in practicas
                   if item.get('netterm') or 'fecha_pedido' in item['fila']}
    eges = {fila.pk: fila for fila in EgesRow.objects.filter(pk__in=eges_ids).only(
        'dni_paciente', 'apellido_nombre',
    )}
    netterm = dict(NettermFila.objects.filter(pk__in=netterm_ids).values_list('pk', 'normalizados_json'))
    identidades = _identidades_netterm(eges, netterm)
    for item in pendientes:
        nt_id = item.get('netterm', item['fila'])['id']
        item['fila']['paciente_clave'] = identidades.get(nt_id)
