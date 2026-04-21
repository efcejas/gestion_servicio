from django.utils import timezone
from django.db.models import F, Q

from .models import CorreoResumen, CorreoSincronizacion, CorreoHilo


FILTROS_HILO_VALIDOS = {'todos', 'pendiente', 'en_curso', 'urgentes'}


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


def _get_hilos_atencion_base(limite_dias=1):
    hoy = timezone.localdate()
    fecha_limite = hoy + timezone.timedelta(days=limite_dias)

    return CorreoHilo.objects.filter(
        estado_hilo__in=['pendiente', 'en_curso']
    ).filter(
        Q(requiere_respuesta=True)
        | Q(fecha_compromiso__isnull=False, fecha_compromiso__date__lte=fecha_limite)
        | Q(fecha_seguimiento__isnull=False, fecha_seguimiento__date__lte=fecha_limite)
    )


def _aplicar_filtro_hilos(qs, filtro):
    if filtro == 'pendiente':
        return qs.filter(estado_hilo='pendiente')
    if filtro == 'en_curso':
        return qs.filter(estado_hilo='en_curso')
    if filtro == 'urgentes':
        return qs.filter(prioridad_hilo='URGENTE')
    return qs


def get_atencion_hoy_por_hilo(limite_dias=1, filtro='todos'):
    """
    Retorna hilos que requieren atención hoy (phase 2).
    Agrupa correos relacionados en conversaciones.
    
    Args:
        limite_dias: días desde hoy para buscar compromisos
    
    Returns:
        QuerySet de CorreoHilo ordenado por: prioridad → fecha_compromiso → fecha_ultimo_email desc
    """
    if filtro not in FILTROS_HILO_VALIDOS:
        filtro = 'todos'

    qs = _aplicar_filtro_hilos(_get_hilos_atencion_base(limite_dias=limite_dias), filtro)
    return qs.order_by(
        F('fecha_seguimiento').asc(nulls_last=True),
        F('fecha_compromiso').asc(nulls_last=True),
        '-prioridad_hilo',
        '-fecha_ultimo_email',
    )


def get_agenda_seguimiento_hilos(limite=4):
    ahora = timezone.now()
    base_qs = CorreoHilo.objects.filter(
        estado_hilo__in=['pendiente', 'en_curso'],
        fecha_seguimiento__isnull=False,
    )

    return {
        'vencidos': base_qs.filter(fecha_seguimiento__lt=ahora).order_by('fecha_seguimiento')[:limite],
        'proximos': base_qs.filter(fecha_seguimiento__gte=ahora).order_by('fecha_seguimiento')[:limite],
        'vencidos_count': base_qs.filter(fecha_seguimiento__lt=ahora).count(),
        'proximos_count': base_qs.filter(fecha_seguimiento__gte=ahora).count(),
    }


def get_dashboard_context(hilo_filtro='todos'):
    hoy = timezone.localdate()
    base_qs = CorreoResumen.objects.all()
    base_hilos_qs = CorreoHilo.objects.all()
    hilos_atencion_base = _get_hilos_atencion_base()
    urgentes = base_qs.filter(prioridad_sugerida='URGENTE').order_by('-fecha_email')[:3]
    importantes_no_leidos = (
        base_qs.filter(leido=False, score_importancia__gte=60)
        .exclude(prioridad_sugerida='URGENTE')
        .order_by('-score_importancia', '-fecha_email')[:5]
    )
    recientes_relevantes = base_qs.filter(score_importancia__gte=45).order_by('-score_importancia', '-fecha_email')[:5]
    ultima_sync = CorreoSincronizacion.objects.first()
    agenda_seguimiento = get_agenda_seguimiento_hilos()
    
    # Nuevo: Atención Hoy
    atencion_hoy = get_atencion_hoy()[:5]
    atencion_hoy_por_hilo = get_atencion_hoy_por_hilo(filtro=hilo_filtro)[:5]

    resumen_del_dia = []
    for correo in recientes_relevantes:
        if correo.resumen_ejecutivo:
            resumen_del_dia.append(correo.resumen_ejecutivo)
        elif correo.snippet:
            resumen_del_dia.append(correo.snippet[:140])

    return {
        'correo_resumen_habilitado': True,
        'correos_atencion_hoy': atencion_hoy,
        'correos_atencion_hoy_por_hilo': atencion_hoy_por_hilo,
        'correo_hilos_filtro_actual': hilo_filtro if hilo_filtro in FILTROS_HILO_VALIDOS else 'todos',
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
        'correo_hilos_atencion_hoy_count': atencion_hoy_por_hilo.count(),
        'correo_hilos_todos_count': hilos_atencion_base.count(),
        'correo_hilos_pendiente_count': hilos_atencion_base.filter(estado_hilo='pendiente').count(),
        'correo_hilos_en_curso_count': hilos_atencion_base.filter(estado_hilo='en_curso').count(),
        'correo_hilos_urgentes_count': hilos_atencion_base.filter(prioridad_hilo='URGENTE').count(),
        'correo_hilos_total_count': base_hilos_qs.count(),
        'correo_hilos_seguimiento_vencidos': agenda_seguimiento['vencidos'],
        'correo_hilos_seguimiento_proximos': agenda_seguimiento['proximos'],
        'correo_hilos_seguimiento_vencidos_count': agenda_seguimiento['vencidos_count'],
        'correo_hilos_seguimiento_proximos_count': agenda_seguimiento['proximos_count'],
        'correo_ultima_sync': ultima_sync,
    }
