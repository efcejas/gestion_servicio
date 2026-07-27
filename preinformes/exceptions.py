"""
exceptions.py — Excepciones de negocio del módulo preinformes.

Usar estas clases en lugar de ValueError/RuntimeError genéricos para que
el código que llama pueda hacer except específico y diferenciado.

Jerarquía:
    PreinformeError
    ├── EstadoInvalidoError       — operación no válida para el estado actual
    ├── RevisorNoDisponibleError  — el revisor indicado no tiene el rol correcto
    └── EnvioRevisionError        — el preinforme no cumple las condiciones de envío
"""


class PreinformeError(Exception):
    """Clase base para errores del módulo preinformes."""
    pass


class EstadoInvalidoError(PreinformeError):
    """La operación no es válida para el estado actual del preinforme."""
    pass


class RevisorNoDisponibleError(PreinformeError):
    """El usuario indicado no puede actuar como revisor."""
    pass


class EnvioRevisionError(PreinformeError):
    """El preinforme no puede ser enviado a revisión en su estado actual."""
    pass


class GeneracionPlantillaError(PreinformeError):
    """No fue posible generar una propuesta de plantilla segura y válida."""
    pass


class RespuestaPlantillaInvalidaError(GeneracionPlantillaError):
    """La respuesta del modelo no cumple el contrato institucional."""
    pass
