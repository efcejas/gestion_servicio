"""Vistas ejecutivas sobre la misma población del tablero de producción."""
from collections import Counter


def construir_detalle_director(filas):
    meses = sorted({fila['fecha'].strftime('%Y-%m') for fila in filas})

    def evolucion(registros, campo, nombres):
        conteo = Counter((fila['fecha'].strftime('%Y-%m'), fila[campo]) for fila in registros)
        return {'labels': meses, 'datasets': [
            {'label': nombre, 'data': [conteo[(mes, nombre)] for mes in meses]}
            for nombre in nombres
        ]}

    practicas = Counter(fila['practica'] for fila in filas).most_common(15)
    coberturas = Counter(fila['obra_social'] for fila in filas)
    evolucion_os = evolucion(filas, 'obra_social', sorted(coberturas))
    evolucion_os['opciones'] = [{'codigo': nombre, 'nombre': nombre} for nombre in sorted(coberturas)]
    eco = [fila for fila in filas if fila['modalidad'] == 'ECO'
           and fila['sub_modalidad'] in {'DOPPLER', 'ECOCARDIO'}]
    responsables = Counter((fila['medico'], fila['sub_modalidad']) for fila in eco)
    medicos = [nombre for nombre, _ in Counter(fila['medico'] for fila in eco).most_common(10)]
    guardias = [fila for fila in filas if fila['guardia'] and fila['modalidad'] in {'TC', 'ECO'}]
    base_guardias = sum(fila['modalidad'] in {'TC', 'ECO'} for fila in filas)
    guardia = evolucion(guardias, 'modalidad', ['TC', 'ECO'])
    guardia.update(total_guardia=len(guardias), porcentaje_sobre_total=(
        round(100 * len(guardias) / base_guardias, 1) if base_guardias else 0))
    procedimientos = Counter()
    for fila in filas:
        codigo = str(fila['codigo']).split('/')[0]
        if fila['modalidad'] == 'TC' and codigo in {'900446', '900441', '900413', '341317'}:
            grupo = 'Bloqueos TC'
        elif fila['procedimiento_guiado'] or 'PUNC' in fila['practica'].upper():
            grupo = {'TC': 'Procedimientos guiados · TC', 'ECO': 'Procedimientos guiados · ECO'}.get(fila['modalidad'])
        else:
            grupo = None
        if grupo:
            procedimientos[(fila['fecha'].strftime('%Y-%m'), grupo)] += 1
    return {
        'practicas': {'labels': [nombre for nombre, _ in practicas],
                      'datasets': [{'label': 'Prácticas', 'data': [n for _, n in practicas]}]},
        'obras_sociales_evolucion': evolucion_os,
        'guardias': guardia,
        'procedimientos': {'labels': meses, 'datasets': [
            {'label': nombre, 'data': [procedimientos[(mes, nombre)] for mes in meses]}
            for nombre in ('Procedimientos guiados · TC', 'Procedimientos guiados · ECO', 'Bloqueos TC')
        ]},
        'doppler': {
            'evolucion': evolucion(eco, 'sub_modalidad', ['DOPPLER', 'ECOCARDIO']),
            'responsables': {'labels': medicos, 'datasets': [
                {'label': sub, 'data': [responsables[(nombre, sub)] for nombre in medicos]}
                for sub in ('DOPPLER', 'ECOCARDIO')
            ]},
        },
    }
