"""
Context processors para el módulo de dictado de informes
"""
from .models import TerminoMedico


def terminos_activos(request):
    """Agrega el conteo de términos activos al contexto global"""
    return {
        'terminos_activos': TerminoMedico.objects.filter(activo=True).count()
    }
