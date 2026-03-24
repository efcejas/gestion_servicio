from functools import wraps
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.contrib import messages


def vivienda_required(view_func):
    """
    Decorador que restringe el acceso a usuarios en el grupo 'vivienda_access'.
    No requiere perfil médico completo: es independiente del sistema de roles.
    """
    @wraps(view_func)
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        if request.user.groups.filter(name='vivienda_access').exists() or request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        messages.error(request, 'No tenés acceso a esta sección.')
        return redirect('home')
    return _wrapped_view
