from django.conf import settings


ROLES_DOCENTES = ('jefe_residentes', 'instructor_residentes', 'jefe_servicio')


def portafolio_habilitado_para(user):
    """Aplica el rollout antes de evaluar los permisos funcionales."""
    if not user.is_authenticated:
        return False
    if getattr(settings, 'PORTAFOLIO_SOLO_SUPERUSER', True):
        return user.is_superuser
    return True


def puede_ver_todos_los_residentes(user):
    if not portafolio_habilitado_para(user):
        return False
    return (
        user.is_superuser
        or user.rol in ROLES_DOCENTES
        or user.groups.filter(name='Administrativo - Docencia').exists()
    )
