# -*- coding: utf-8 -*-
"""
Context processor para el módulo consultorios.
Inyecta variables de contexto comunes en todas las vistas del módulo.
"""

from .models import AusenciaCobertura, EstadoAusenciaCobertura


def consultorios_context(request):
    """
    Inyecta en todos los templates:
      - puede_gestionar_bloques: bool
      - ausencias_pendientes_count: int (ausencias REPORTADAS o PROPUESTAS)
    """
    if not request.user.is_authenticated:
        return {}

    from .views import usuario_puede_gestionar_bloques
    puede = usuario_puede_gestionar_bloques(request.user)

    count = 0
    if puede:
        count = AusenciaCobertura.objects.filter(
            estado__in=[
                EstadoAusenciaCobertura.REPORTADA,
                EstadoAusenciaCobertura.PROPUESTA,
            ]
        ).count()

    return {
        'puede_gestionar_bloques': puede,
        'ausencias_pendientes_count': count,
    }
