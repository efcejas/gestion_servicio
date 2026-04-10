"""
exceptions.py — Excepciones de negocio del módulo eges_import.

Jerarquía:
    EgesImportError
    ├── TokenInvalidoError   — el token de acceso al portal del director no es válido
    ├── ImportacionError     — fallo al procesar el archivo de importación EGES
    └── FiltroInvalidoError  — los parámetros de filtro recibidos no son válidos
"""


class EgesImportError(Exception):
    """Clase base para errores del módulo eges_import."""
    pass


class TokenInvalidoError(EgesImportError):
    """El token de acceso al portal del director no es válido o está inactivo."""
    pass


class ImportacionError(EgesImportError):
    """Fallo al procesar o validar el archivo de importación EGES."""
    pass


class FiltroInvalidoError(EgesImportError):
    """Los parámetros de filtro recibidos no son válidos."""
    pass
