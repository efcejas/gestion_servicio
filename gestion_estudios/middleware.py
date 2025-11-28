"""
Middleware personalizado para prevenir cacheo agresivo de archivos estáticos.
"""


class NoCacheMiddleware:
    """
    Agrega headers para prevenir cacheo en proxies y navegadores.
    Especialmente útil en redes hospitalarias con proxies agresivos.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        response = self.get_response(request)
        
        # Solo aplicar a archivos CSS y JS estáticos
        if request.path.endswith(('.css', '.js')) and '/static/' in request.path:
            response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
            response['Pragma'] = 'no-cache'
            response['Expires'] = '0'
        
        return response
