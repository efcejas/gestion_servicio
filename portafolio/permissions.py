from django.conf import settings


ROLES_PORTAFOLIO = (
    'medico_residente',
    'jefe_residentes',
    'instructor_residentes',
)
ROLES_SEGUIMIENTO = ('jefe_residentes', 'instructor_residentes')


def portafolio_habilitado_para(user):
    """Limita el módulo a los perfiles incluidos en la etapa vigente."""
    if not user.is_authenticated:
        return False
    if getattr(settings, 'PORTAFOLIO_SOLO_SUPERUSER', True):
        return user.is_superuser
    return user.is_superuser or user.rol in ROLES_PORTAFOLIO


def puede_ver_todos_los_residentes(user):
    if not portafolio_habilitado_para(user):
        return False
    return (
        user.is_superuser
        or user.rol in ROLES_SEGUIMIENTO
    )
