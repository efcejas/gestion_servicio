from .selectors import (
    periodo_ciclo_lectivo,
    resumen_clases,
    resumen_estudios,
    resumen_guardias,
    resumen_preinformes,
)


def construir_resumen_portafolio(residente, fecha_referencia=None):
    periodo = periodo_ciclo_lectivo(fecha_referencia)
    return {
        'periodo': periodo,
        'guardias': resumen_guardias(residente, periodo, hoy=fecha_referencia),
        'preinformes': resumen_preinformes(residente, periodo),
        'estudios': resumen_estudios(residente, periodo),
        'clases': resumen_clases(residente, periodo),
    }
