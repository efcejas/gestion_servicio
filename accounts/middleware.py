"""
Middleware para verificación de perfil completo y timeout de sesión por inactividad.
"""
from django.shortcuts import redirect
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth import logout
from django.utils import timezone
from django.conf import settings


class ProfileRequiredMiddleware:
    """
    Middleware que verifica si el usuario tiene su perfil completo.
    
    Si el usuario está autenticado pero no tiene perfil completo,
    lo redirige a la página de completar perfil.
    
    Excepciones (URLs permitidas sin perfil completo):
    - Completar perfil
    - Logout
    - Login
    - Registro
    - Archivos estáticos/media
    - Admin (para superusuarios)
    """
    
    # URLs que NO requieren perfil completo
    EXEMPT_URLS = [
        '/accounts/completar-perfil/',
        '/accounts/login/',
        '/accounts/logout/',
        '/accounts/register/',
        '/accounts/password_reset/',
        '/accounts/recuperar-usuario/',
        '/static/',
        '/media/',
        '/admin/',
        '/vivienda/',  # App personal de ahorro vivienda (acceso independiente del perfil médico)
    ]
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Si el usuario no está autenticado, dejar pasar
        if not request.user.is_authenticated:
            return self.get_response(request)
        
        # Superusuarios no necesitan completar perfil
        if request.user.is_superuser:
            return self.get_response(request)
        
        # Verificar si la URL actual está exenta
        path = request.path_info
        is_exempt = any(path.startswith(url) for url in self.EXEMPT_URLS)
        
        if is_exempt:
            return self.get_response(request)
        
        # Si el perfil no está completo, redirigir
        if not request.user.perfil_completo:
            # Evitar loop infinito
            completar_perfil_url = reverse('accounts:completar_perfil')
            if path != completar_perfil_url:
                messages.info(
                    request,
                    'Por favor, completa tu perfil para acceder al sistema.'
                )
                return redirect('accounts:completar_perfil')
        
        return self.get_response(request)


class SessionTimeoutMiddleware:
    """
    Cierra la sesión del usuario si estuvo inactivo más de SESSION_INACTIVITY_TIMEOUT
    segundos (default: 30 minutos). Solo afecta a usuarios autenticados.
    URLs de archivos estáticos y de autenticación están exentas.
    """

    EXEMPT_PREFIXES = ('/static/', '/media/', '/accounts/login/', '/accounts/logout/')

    def __init__(self, get_response):
        self.get_response = get_response
        self.timeout = getattr(settings, 'SESSION_INACTIVITY_TIMEOUT', 30 * 60)

    def __call__(self, request):
        if (
            request.user.is_authenticated
            and not any(request.path.startswith(p) for p in self.EXEMPT_PREFIXES)
        ):
            last_activity = request.session.get('_last_activity')
            now = timezone.now().timestamp()

            if last_activity is not None and (now - last_activity) > self.timeout:
                logout(request)
                messages.warning(
                    request,
                    'Tu sesión se cerró automáticamente por inactividad. '
                    'Por favor, inicia sesión nuevamente.',
                )
                return redirect(settings.LOGIN_URL)

            request.session['_last_activity'] = now

        return self.get_response(request)
