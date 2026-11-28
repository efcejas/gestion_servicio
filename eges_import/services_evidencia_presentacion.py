"""Datos de respaldo para la interfaz; no infiere eventos ni altera el cruce."""
from .models import EgesRow
from .services_netterm import _fecha, _hora


def _evento(valor, convertir):
    if valor is None or valor == '':
        return None
    try:
        return convertir(valor)
    except (ValueError, TypeError):
        return None


def detalle_netterm(origen):
    return {
        'fuente': 'Netterm',
        **{campo: _evento(origen.get(campo), convertir) for campo, convertir in (
            ('fecha_pedido', _fecha), ('hora_pedido', _hora),
            ('fecha_realizacion', _fecha), ('hora_realizacion', _hora),
            ('fecha_informe', _fecha), ('hora_informe', _hora),
        )},
        'profesional': origen.get('informante', ''),
        'sector': origen.get('sector', ''), 'servicio': origen.get('servicio', ''),
        'estado': origen.get('estado_original') or origen.get('estado_informe', ''),
    }


def detalle_eges(origen):
    return {
        'fuente': 'EGES', 'fecha_turno': origen.get('fecha_turno'),
        'hora_turno': origen.get('hora_turno'),
        'profesional': origen.get('medico_informante', ''),
        'sector': origen.get('tipo_atencion', ''), 'servicio': origen.get('servicio', ''),
        'estado': origen.get('estado_turno', ''),
    }


def enriquecer_evidencias(grupos, originales, excepciones=()):
    # Sólo consultar las filas que efectivamente se presentan para revisión.
    ids = {fila['id'] for grupo in grupos for fila in grupo['filas'] if fila.get('fuente') == 'EGES'}
    ids.update(fila['id'] for caso in excepciones for fila in caso['candidatas'])
    eges = {fila['id']: fila for fila in EgesRow.objects.filter(pk__in=ids).values(
        'id', 'fecha_turno', 'hora_turno', 'medico_informante', 'tipo_atencion', 'servicio', 'estado_turno',
    )}
    for grupo in grupos:
        for fila in grupo['filas']:
            fila['detalle'] = (detalle_eges(eges.get(fila['id'], {})) if fila.get('fuente') == 'EGES'
                               else detalle_netterm(originales.get(fila['id'], {})))
    for caso in excepciones:
        caso['detalle'] = detalle_netterm(originales.get(int(caso['id']), {}))
        for fila in caso['candidatas']:
            fila['detalle'] = detalle_eges(eges.get(fila['id'], {}))
