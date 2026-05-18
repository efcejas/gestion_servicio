"""
Funciones de control de permisos para módulo liquidación.

Separa lógica de permisos de vistas/templates para reutilización y testing.
"""


def puede_ver_desglose_administrativo(user):
    """
    Retorna True si el usuario puede ver desglose administrativo completo.
    
    Desglose administrativo incluye:
    - Grupo tarifario
    - Tarifa vigente y vigencia
    - Precio base por estudio
    - Fórmula de cálculo
    - Alertas de consistencia de tarifa
    
    Args:
        user: Usuario a validar
    
    Returns:
        bool: True si user tiene permisos para ver desglose admin
    """
    if not user or not user.is_authenticated:
        return False
    
    return user.is_superuser or user.rol in [
        'administrativo',
        'jefe_servicio',
    ]


def puede_editar_tarifas(user):
    """
    Retorna True si el usuario puede editar tarifas/grupos tarifarios.
    
    Solo admins y superuser.
    """
    if not user or not user.is_authenticated:
        return False
    
    return user.is_superuser or user.rol == 'administrativo'
