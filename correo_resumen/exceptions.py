class CorreoResumenError(Exception):
    pass


class ConfiguracionCorreoError(CorreoResumenError):
    pass


class ConexionCorreoError(CorreoResumenError):
    pass


class ResumenIAError(CorreoResumenError):
    pass
