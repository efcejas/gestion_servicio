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
    
    Args:
        request: HttpRequest object
        
    Returns:
        dict: Variables de contexto disponibles en templates
    """
    return {
        'SANATORIO_NOMBRE': SANATORIO_CONFIG['NOMBRE_SANATORIO'],
        'SANATORIO_NOMBRE_CORTO': SANATORIO_CONFIG.get('NOMBRE_CORTO', SANATORIO_CONFIG['NOMBRE_SANATORIO']),
    }
