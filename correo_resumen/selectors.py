from django.utils import timezone
from django.db.models import Q

from .models import CorreoResumen, CorreoSincronizacion


def get_atencion_hoy(limite_dias=1):
    """
    Retorna correos que requieren atención hoy.
    Incluye:
    - Correos que requieren respuesta
    - Correos con fecha_compromiso vencida
    - No resueltos (estado != 'resuelto')
    
    Args:
        limite_dias: días desde hoy para buscar compromisos (default 1 = hoy)
    
    Returns:
        QuerySet ordenado por: prioridad → fecha_compromiso → fecha_email desc
    """
    hoy = timezone.localdate()
    fecha_limite = hoy + timezone.timedelta(days=limite_dias)
    
    qs = CorreoResumen.objects.filter(
        estado_atencion__in=['pendiente', 'en_curso']  # No resueltos
    ).filter(
        Q(requiere_respuesta=True) | Q(
            fecha_compromiso__isnull=False,
            fecha_compromiso__date__lte=fecha_limite
        )
    ).order_by('-prioridad_sugerida', 'fecha_compromiso', '-fecha_email')
    
    return qs


def get_dashboard_context():
    hoy = timezone.localdate()
    base_qs = CorreoResumen.objects.all()
    urgentes = base_qs.filter(prioridad_sugerida='URGENTE').order_by('-fecha_email')[:3]
    importantes_no_leidos = (
        base_qs.filter(leido=False, score_importancia__gte=60)
        .exclude(prioridad_sugerida='URGENTE')
        .order_by('-score_importancia', '-fecha_email')[:5]
    )
    recientes_relevantes = base_qs.filter(score_importancia__gte=45).order_by('-score_importancia', '-fecha_email')[:5]
    ultima_sync = CorreoSincronizacion.objects.first()
    
    # Nuevo: Atención Hoy
    atencion_hoy = get_atencion_hoy()[:5]

    resumen_del_dia = []
    for correo in recientes_relevantes:
        if correo.resumen_ejecutivo:
            resumen_del_dia.append(correo.resumen_ejecutivo)
        elif correo.snippet:
            resumen_del_dia.append(correo.snippet[:140])

    return {
        'correo_resumen_habilitado': True,
        'correos_atencion_hoy': atencion_hoy,
        'correos_urgentes': urgentes,
        'correos_importantes_no_leidos': importantes_no_leidos,
        'correo_resumen_del_dia': resumen_del_dia[:5],
        'correo_importantes_hoy_count': base_qs.filter(
            fecha_email__date=hoy,
            score_importancia__gte=60,
            leido=False,
        ).count(),
        'correo_urgentes_count': base_qs.filter(prioridad_sugerida='URGENTE').count(),
        'correo_atencion_hoy_count': atencion_hoy.count(),
        'correo_ultima_sync': ultima_sync,
    }
