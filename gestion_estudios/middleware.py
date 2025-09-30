import logging
import traceback

logger = logging.getLogger(__name__)

class LogExceptionsMiddleware:
    """Middleware sencillo para registrar traceback completo de cualquier excepción no capturada.

    Útil en producción (DEBUG=False) cuando Heroku solo muestra status 500 sin stack.
    Quitar una vez identificado y solucionado el problema.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            return self.get_response(request)
        except Exception as exc:  # noqa: BLE001
            tb = traceback.format_exc()
            logger.error("[EXCEPTION] %s %s -> %s\n%s", request.method, request.path, exc, tb)
            # Re-elevar para que Django siga su flujo normal (500 + handler)
            raise
