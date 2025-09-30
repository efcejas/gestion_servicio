import logging
import traceback
import sys

# Usar un logger específico y también fallback al de django.request
logger = logging.getLogger("gestion_estudios.middleware")
django_request_logger = logging.getLogger("django.request")

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
            message = f"[EXCEPTION] {request.method} {request.path} -> {exc}\n{tb}"
            # Intentar varios canales para garantizar que aparezca en Heroku logs
            try:
                logger.error(message)
            except Exception:  # pragma: no cover
                pass
            try:
                django_request_logger.error(message)
            except Exception:  # pragma: no cover
                pass
            # Fallback directo a stdout (Heroku captura stdout/stderr)
            print(message, file=sys.stderr, flush=True)
            # Re-elevar para que Django genere el 500 estándar
            raise
