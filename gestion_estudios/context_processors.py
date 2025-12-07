"""
Context processors personalizados.
Agregan variables globales disponibles en todos los templates.
"""

from .config_sanatorio import CONFIG as SANATORIO_CONFIG


def sanatorio_config(request):
    """
    Agrega la configuración del sanatorio a todos los templates.
    
    Uso en templates:
        {{ SANATORIO_NOMBRE }}
        {{ SANATORIO_NOMBRE_CORTO }}
        {{ SANATORIO_MODO }}
        {{ SANATORIO_MODULOS.equipos }}
        {{ SANATORIO_MODULOS.liquidacion }}
    
    Args:
        request: HttpRequest object
        
    Returns:
        dict: Variables de contexto disponibles en templates
    """
    return {
        'SANATORIO_NOMBRE': SANATORIO_CONFIG['NOMBRE_SANATORIO'],
        'SANATORIO_NOMBRE_CORTO': SANATORIO_CONFIG.get('NOMBRE_CORTO', SANATORIO_CONFIG['NOMBRE_SANATORIO']),
        'SANATORIO_MODO': SANATORIO_CONFIG.get('MODO', 'Modo estándar'),
        'SANATORIO_MODULOS': SANATORIO_CONFIG.get('MODULOS_ACTIVOS', {}),
        'SANATORIO_COLOR_PRIMARIO': SANATORIO_CONFIG.get('COLOR_PRIMARIO', '#4F46E5'),
        'SANATORIO_COLOR_SECUNDARIO': SANATORIO_CONFIG.get('COLOR_SECUNDARIO', '#06B6D4'),
    }
