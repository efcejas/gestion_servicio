class EvaluacionError(Exception):
    """Error base para reglas de negocio de evaluaciones."""


class PermisoEvaluacionError(EvaluacionError):
    pass


class TransicionEvaluacionError(EvaluacionError):
    pass


class EvaluacionNoDisponibleError(EvaluacionError):
    pass


class RespuestasInvalidasError(EvaluacionError):
    pass
