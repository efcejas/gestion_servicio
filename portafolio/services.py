from .selectors import (
    periodo_ciclo_lectivo,
    periodos_disponibles_residente,
    resumen_clases,
    resumen_estudios,
    resumen_guardias,
    resumen_preinformes,
    totales_actividad_ciclo,
)


def construir_resumen_portafolio(residente, fecha_referencia=None, periodo=None):
    periodo = periodo or periodo_ciclo_lectivo(fecha_referencia)
    return {
        'periodo': periodo,
        'guardias': resumen_guardias(residente, periodo, hoy=fecha_referencia),
        'preinformes': resumen_preinformes(residente, periodo),
        'estudios': resumen_estudios(residente, periodo),
        'clases': resumen_clases(residente, periodo),
    }


def construir_trayectoria_portafolio(residente, fecha_referencia=None):
    periodos = periodos_disponibles_residente(residente, fecha_referencia)
    acumulado = {
        'preinformes': 0,
        'preinformes_finalizados': 0,
        'estudios': 0,
        'registros_estudios': 0,
        'regiones': 0,
        'guardias': 0,
        'clases': 0,
    }
    ciclos = []
    for periodo in periodos:
        totales = totales_actividad_ciclo(
            residente,
            periodo,
            hoy=fecha_referencia,
        )
        for clave, valor in totales.items():
            acumulado[clave] += valor
        ciclos.append({'periodo': periodo, 'totales': totales})

    return {'ciclos': ciclos, 'acumulado': acumulado}
