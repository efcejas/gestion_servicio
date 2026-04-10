"""
exceptions.py — Excepciones de negocio del módulo liquidacion.

Usar estas clases para que el código que llama pueda hacer except
específico y diferenciado en lugar de capturar Exception genérico.

Jerarquía:
    LiquidacionError
    ├── SesionContableError   — la sesión no está en estado que permita la operación
    ├── RegistroInvalidoError — los datos del registro no cumplen las reglas de negocio
    └── ExportacionError      — fallo al generar el documento de exportación
"""


class LiquidacionError(Exception):
    """Clase base para errores del módulo liquidacion."""
    pass


class SesionContableError(LiquidacionError):
    """La sesión contable no está en estado que permita la operación."""
    pass


class RegistroInvalidoError(LiquidacionError):
    """Los datos del registro no cumplen las reglas de negocio."""
    pass


class ExportacionError(LiquidacionError):
    """Fallo al generar el documento de exportación (PDF/Excel)."""
    pass
