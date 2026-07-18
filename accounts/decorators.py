"""
Decoradores personalizados para control de acceso basado en perfiles y roles.
"""
from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.urls import reverse
from django.contrib.auth.decorators import login_required


def profile_required(view_func):
    """
    Decorador que requiere que el usuario tenga su perfil completo.
    - Si no está autenticado: redirige a login
    - Si está autenticado pero perfil incompleto: redirige a completar perfil
    - Si el perfil está completo: permite el acceso
    """
    @wraps(view_func)
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        # Superusuarios siempre tienen acceso
        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        
        # Verificar si el perfil está completo
        if not request.user.perfil_completo:
            messages.warning(
                request, 
                'Necesitas completar tu perfil para acceder a esta sección.'
            )
            return redirect('accounts:completar_perfil')
        
        return view_func(request, *args, **kwargs)
    
    return _wrapped_view


def role_required(*allowed_roles):
    """
    Decorador que requiere que el usuario tenga uno de los roles especificados.
    
    Uso:
        @role_required('medico_staff', 'medico_residente')
        def mi_vista(request):
            ...
    
    Roles disponibles:
        - medico_staff
        - medico_residente
        - jefe_servicio
        - tecnico
        - administrativo
        - enfermeria
        - otro
    """
    def decorator(view_func):
        @wraps(view_func)
        @profile_required
        def _wrapped_view(request, *args, **kwargs):
            # Superusuarios siempre tienen acceso
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            
            # Verificar si el usuario tiene alguno de los roles permitidos
            if request.user.rol not in allowed_roles:
                messages.error(
                    request,
                    f'Acceso denegado. Esta sección está disponible solo para: {", ".join(allowed_roles)}'
                )
                return redirect('home')

            if (
                request.user.rol == 'medico_residente'
                and not request.user.es_residente_activo()
            ):
                messages.error(
                    request,
                    'Tu ciclo de residencia finalizó; esta función es exclusiva para residentes activos.'
                )
                return redirect('home')
            
            return view_func(request, *args, **kwargs)
        
        return _wrapped_view
    
    return decorator


def medical_staff_required(view_func):
    """
    Decorador que requiere que el usuario sea personal médico.
    Incluye: médicos staff, residentes, jefes de residentes, instructores y jefes de servicio.
    """
    @wraps(view_func)
    @profile_required
    def _wrapped_view(request, *args, **kwargs):
        if request.user.is_superuser or request.user.es_medico():
            return view_func(request, *args, **kwargs)
        
        messages.error(
            request,
            'Esta sección está disponible solo para personal médico.'
        )
        return redirect('home')
    
    return _wrapped_view


def protocolos_access_required(view_func):
    """
    Decorador específico para acceso a protocolos radiológicos.
    Permite: médicos staff, residentes, jefes de residentes, instructores, jefes de servicio y técnicos.
    """
    @wraps(view_func)
    @profile_required
    def _wrapped_view(request, *args, **kwargs):
        if request.user.is_superuser or request.user.puede_acceder_protocolos():
            return view_func(request, *args, **kwargs)
        
        messages.error(
            request,
            'El acceso a protocolos está disponible solo para personal médico y técnico.'
        )
        return redirect('home')
    
    return _wrapped_view


def dashboard_pedidos_required(view_func):
    """
    Decorador para acceso al dashboard completo de pedidos de estudios.
    Permite: superusuarios, administrativos, jefe de servicio, jefe de residentes, instructor de residentes.
    """
    @wraps(view_func)
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        # Roles permitidos para ver dashboard completo
        roles_permitidos = ['administrativo', 'jefe_servicio', 'jefe_residentes', 'instructor_residentes']
        
        if request.user.is_superuser or request.user.rol in roles_permitidos:
            return view_func(request, *args, **kwargs)
        
        messages.error(
            request,
            'Acceso denegado. El dashboard de pedidos está disponible para personal administrativo y coordinadores.'
        )
        return redirect('home')
    
    return _wrapped_view


def puede_procesar_emails(user):
    """
    Verifica si un usuario puede procesar emails manualmente.
    Solo superusuarios y administrativos.
    """
    return user.is_superuser or user.rol == 'administrativo'
