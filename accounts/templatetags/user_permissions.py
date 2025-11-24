from django import template

register = template.Library()

@register.filter
def has_group(user, group_name):
    """
    Verifica si un usuario pertenece a un grupo específico
    Uso: {{ user|has_group:"nombre_del_grupo" }}
    """
    if not user or not user.is_authenticated:
        return False
    return user.groups.filter(name=group_name).exists()

@register.filter 
def has_any_group(user, group_names):
    """
    Verifica si un usuario pertenece a cualquiera de los grupos especificados
    Uso: {{ user|has_any_group:"grupo1,grupo2,grupo3" }}
    """
    if not user or not user.is_authenticated:
        return False
    
    groups = [name.strip() for name in group_names.split(',')]
    return user.groups.filter(name__in=groups).exists()

@register.filter
def has_cargo(user, cargo_names):
    """
    Verifica si un usuario tiene cualquiera de los cargos especificados
    Uso: {{ user|has_cargo:"médico,jefe,técnico radiólogo" }}
    """
    if not user or not user.is_authenticated or not user.cargo:
        return False
    
    cargos = [name.strip() for name in cargo_names.split(',')]
    return user.cargo in cargos

@register.filter
def can_access_liquidacion(user):
    """
    Verifica si el usuario puede acceder al módulo de liquidación
    """
    if not user or not user.is_authenticated:
        return False
    
    # Grupos autorizados para liquidación
    liquidacion_groups = ['Médicos de staff', 'Médicos de staff - informes']
    has_group = user.groups.filter(name__in=liquidacion_groups).exists()
    
    # Cargos autorizados para liquidación  
    liquidacion_cargos = ['médico', 'jefe', 'jefe tecnico']
    has_cargo = user.cargo in liquidacion_cargos if user.cargo else False
    
    return has_group or has_cargo

@register.filter
def can_access_eventos(user):
    """
    Verifica si el usuario puede acceder a eventos del servicio
    """
    if not user or not user.is_authenticated:
        return False
    
    # Grupos autorizados para eventos
    eventos_groups = ['Técnicos de tomografía', 'Técnicos de resonancia']
    has_group = user.groups.filter(name__in=eventos_groups).exists()
    
    # Cargos autorizados para eventos
    eventos_cargos = ['técnico radiólogo', 'jefe tecnico', 'jefe']
    has_cargo = user.cargo in eventos_cargos if user.cargo else False
    
    return has_group or has_cargo

@register.filter
def can_access_guardias(user):
    """
    Verifica si el usuario puede acceder al control de guardias
    """
    if not user or not user.is_authenticated:
        return False
    
    # Cargos autorizados para guardias
    guardias_cargos = ['médico', 'médico residente', 'enfermero/a', 'jefe de enfermería', 'jefe']
    return user.cargo in guardias_cargos if user.cargo else False

@register.filter  
def can_access_pedidos(user):
    """
    Verifica si el usuario puede acceder a pedidos de estudios
    """
    if not user or not user.is_authenticated:
        return False
    
    # Prácticamente todos pueden acceder a pedidos excepto roles muy específicos
    excluded_cargos = []  # Por ahora ninguno excluido
    return True  # Acceso amplio por defecto