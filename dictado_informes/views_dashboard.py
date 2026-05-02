"""
🚀 FASE 4: Dashboard de Métricas del Sistema de Dictado

Vista para visualizar estadísticas de performance, uso y errores.
"""
from django.shortcuts import render
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Avg, Max, Min, Count, Q
from datetime import timedelta
from .models import MetricaDictado, TipoEstudio, FeedbackCalidadDictado, PlantillaEstructurada
import logging
import json

logger = logging.getLogger(__name__)


def es_superusuario(user):
    """Helper para verificar si es superusuario"""
    return user.is_superuser


@login_required
@user_passes_test(es_superusuario)
def dashboard_metricas(request):
    """
    📊 Dashboard principal de métricas del sistema de dictado
    
    Muestra:
    - Estadísticas de performance (tiempos promedio, máximos, mínimos)
    - Uso de caché
    - Errores
    - Distribución por tipo de estudio
    - Top usuarios
    """
    # Obtener rango de fechas (últimos 7 días por defecto)
    dias = int(request.GET.get('dias', 7))
    fecha_desde = timezone.now() - timedelta(days=dias)
    fecha_hasta = timezone.now()
    
    # Obtener estadísticas del periodo
    stats = MetricaDictado.obtener_estadisticas_periodo(fecha_desde, fecha_hasta)

    # Calidad de salida (feedback explícito del usuario)
    feedback_qs = FeedbackCalidadDictado.objects.filter(
        fecha__gte=fecha_desde,
        fecha__lte=fecha_hasta,
    )
    feedback_resumen = feedback_qs.aggregate(
        total_feedback=Count('id'),
        correctos=Count('id', filter=Q(estado_feedback=FeedbackCalidadDictado.EstadoFeedback.CORRECTO)),
        requirieron_correccion=Count(
            'id',
            filter=Q(estado_feedback=FeedbackCalidadDictado.EstadoFeedback.REQUIRIO_CORRECCION)
        ),
        porcentaje_edicion_promedio=Avg('porcentaje_edicion'),
    )
    total_feedback = feedback_resumen.get('total_feedback') or 0
    correctos = feedback_resumen.get('correctos') or 0
    feedback_resumen['tasa_correcto_primer_intento'] = (
        round((correctos / total_feedback) * 100, 2) if total_feedback > 0 else 0.0
    )

    plantillas_con_mas_correccion = list(
        feedback_qs.filter(tipo_plantilla__gt='')
        .values('tipo_plantilla')
        .annotate(
            total=Count('id'),
            correcciones=Count(
                'id',
                filter=Q(estado_feedback=FeedbackCalidadDictado.EstadoFeedback.REQUIRIO_CORRECCION)
            ),
            porcentaje_edicion_promedio=Avg('porcentaje_edicion'),
        )
        .order_by('-correcciones', '-total')[:10]
    )

    # Recomendaciones automáticas por plantilla (alerta temprana de calidad)
    UMBRAL_ALERTA_CORRECCION = 40.0
    UMBRAL_ALERTA_EDICION = 25.0
    recomendaciones_plantilla = []

    for fila in plantillas_con_mas_correccion:
        total = fila.get('total') or 0
        correcciones = fila.get('correcciones') or 0
        tasa_correccion = round((correcciones / total) * 100, 2) if total > 0 else 0.0
        porcentaje_edicion = round(float(fila.get('porcentaje_edicion_promedio') or 0.0), 2)

        fila['tasa_correccion'] = tasa_correccion
        fila['nivel_alerta'] = (
            'alta'
            if (tasa_correccion >= 60 or porcentaje_edicion >= 35)
            else 'media'
            if (tasa_correccion >= UMBRAL_ALERTA_CORRECCION or porcentaje_edicion >= UMBRAL_ALERTA_EDICION)
            else 'baja'
        )

        if fila['nivel_alerta'] == 'alta':
            accion = (
                'Revisar guia_estilo en admin y agregar reglas explícitas por estructura '
                '(qué reemplazar, qué conservar y términos preferidos).'
            )
        elif fila['nivel_alerta'] == 'media':
            accion = (
                'Ajustar guía de estilo con 2-3 ejemplos de redacción para hallazgos frecuentes '
                'y validarlos con casos reales.'
            )
        else:
            accion = 'Plantilla estable. Mantener y monitorear.'

        fila['accion_sugerida'] = accion

        if fila['nivel_alerta'] in ('alta', 'media'):
            codigo = fila.get('tipo_plantilla', '')
            plantilla_obj = PlantillaEstructurada.objects.filter(codigo=codigo).values('pk').first()
            recomendaciones_plantilla.append({
                'tipo_plantilla': codigo,
                'tasa_correccion': tasa_correccion,
                'porcentaje_edicion_promedio': porcentaje_edicion,
                'nivel_alerta': fila['nivel_alerta'],
                'accion_sugerida': accion,
                'pk': plantilla_obj['pk'] if plantilla_obj else None,
            })

    recomendaciones_plantilla = sorted(
        recomendaciones_plantilla,
        key=lambda r: (r['nivel_alerta'] != 'alta', -r['tasa_correccion'], -r['porcentaje_edicion_promedio'])
    )[:5]
    
    # Obtener top usuarios
    top_usuarios = MetricaDictado.obtener_top_usuarios(fecha_desde, fecha_hasta, limite=10)
    
    # Detectar anomalías (requests lentos)
    anomalias = MetricaDictado.detectar_anomalias(umbral_ms=5000)[:20]
    
    # Distribución de tiempos (para gráfico)
    rangos_tiempo = {
        '0-500ms': MetricaDictado.objects.filter(
            fecha__gte=fecha_desde, tiempo_total_ms__lte=500
        ).count(),
        '500ms-1s': MetricaDictado.objects.filter(
            fecha__gte=fecha_desde, tiempo_total_ms__gt=500, tiempo_total_ms__lte=1000
        ).count(),
        '1s-2s': MetricaDictado.objects.filter(
            fecha__gte=fecha_desde, tiempo_total_ms__gt=1000, tiempo_total_ms__lte=2000
        ).count(),
        '2s-5s': MetricaDictado.objects.filter(
            fecha__gte=fecha_desde, tiempo_total_ms__gt=2000, tiempo_total_ms__lte=5000
        ).count(),
        '>5s': MetricaDictado.objects.filter(
            fecha__gte=fecha_desde, tiempo_total_ms__gt=5000
        ).count(),
    }
    
    # Evolución temporal (últimos 24 puntos de datos)
    if dias <= 1:
        # Por hora
        intervalo = timedelta(hours=1)
        formato_fecha = '%H:%M'
    elif dias <= 7:
        # Por día
        intervalo = timedelta(days=1)
        formato_fecha = '%d/%m'
    else:
        # Por semana
        intervalo = timedelta(days=7)
        formato_fecha = '%d/%m'
    
    evolucion_temporal = []
    fecha_actual = fecha_desde
    while fecha_actual < fecha_hasta:
        fecha_siguiente = fecha_actual + intervalo
        metricas_intervalo = MetricaDictado.objects.filter(
            fecha__gte=fecha_actual,
            fecha__lt=fecha_siguiente
        )
        
        evolucion_temporal.append({
            'fecha': fecha_actual.strftime(formato_fecha),
            'count': metricas_intervalo.count(),
            'tiempo_promedio': metricas_intervalo.aggregate(Avg('tiempo_total_ms'))['tiempo_total_ms__avg'] or 0,
            'errores': metricas_intervalo.filter(tuvo_errores=True).count()
        })
        
        fecha_actual = fecha_siguiente
    
    # Preparar datos para gráficos
    # Mapeo de códigos a etiquetas
    TIPO_ESTUDIO_LABELS = {
        'RES': 'Resonancia',
        'TOM': 'Tomografía',
        'RAD': 'Radiografía',
        'ECO': 'Ecografía',
        'MAM': 'Mamografía',
        'DEN': 'Densitometría',
        'OTR': 'Otro'
    }
    
    tipo_estudio_labels = []
    tipo_estudio_valores = []
    for codigo, count in stats.get('por_tipo_estudio', {}).items():
        tipo_estudio_labels.append(TIPO_ESTUDIO_LABELS.get(codigo, codigo))
        tipo_estudio_valores.append(count)
    
    modo_mejora_labels = []
    modo_mejora_valores = []
    for modo, count in stats.get('por_modo', {}).items():
        modo_mejora_labels.append(modo)
        modo_mejora_valores.append(count)
    
    contexto = {
        'stats': stats,
        'feedback_resumen': feedback_resumen,
        'plantillas_con_mas_correccion': plantillas_con_mas_correccion,
        'recomendaciones_plantilla': recomendaciones_plantilla,
        'umbral_alerta_correccion': UMBRAL_ALERTA_CORRECCION,
        'umbral_alerta_edicion': UMBRAL_ALERTA_EDICION,
        'top_usuarios': top_usuarios,
        'anomalias': anomalias,
        'rangos_tiempo': rangos_tiempo,
        'evolucion_temporal': evolucion_temporal,
        'dias': dias,
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
        'tipos_estudio': TipoEstudio.choices,
        # Datos para gráficos (JSON serializado)
        'tipo_estudio_labels': json.dumps(tipo_estudio_labels),
        'tipo_estudio_valores': json.dumps(tipo_estudio_valores),
        'modo_mejora_labels': json.dumps(modo_mejora_labels),
        'modo_mejora_valores': json.dumps(modo_mejora_valores),
    }
    
    return render(request, 'dictado_informes/dashboard_metricas.html', contexto)


@login_required
@user_passes_test(es_superusuario)
def api_metricas_resumen(request):
    """
    📊 API JSON para obtener resumen de métricas
    
    Útil para actualizar dashboard sin recargar página
    """
    try:
        dias = int(request.GET.get('dias', 1))
        fecha_desde = timezone.now() - timedelta(days=dias)
        fecha_hasta = timezone.now()
        
        stats = MetricaDictado.obtener_estadisticas_periodo(fecha_desde, fecha_hasta)
        
        # Convertir QuerySet a lista para JSON
        stats['por_tipo_estudio_list'] = [
            {'tipo': k, 'count': v} 
            for k, v in stats.get('por_tipo_estudio', {}).items()
        ]
        stats['por_modo_list'] = [
            {'modo': k, 'count': v} 
            for k, v in stats.get('por_modo', {}).items()
        ]
        
        return JsonResponse({
            'success': True,
            'stats': stats,
            'periodo': {
                'desde': fecha_desde.isoformat(),
                'hasta': fecha_hasta.isoformat(),
                'dias': dias
            }
        })
    
    except Exception as e:
        logger.error(f"Error obteniendo métricas: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@user_passes_test(es_superusuario)
def api_anomalias(request):
    """
    🚨 API para obtener anomalías detectadas
    """
    try:
        umbral_ms = int(request.GET.get('umbral', 5000))
        limite = int(request.GET.get('limite', 20))
        
        anomalias = MetricaDictado.detectar_anomalias(umbral_ms)[:limite]
        
        datos_anomalias = []
        for metrica in anomalias:
            datos_anomalias.append({
                'id': metrica.id,
                'usuario': metrica.usuario.username if metrica.usuario else 'Desconocido',
                'tiempo_total_ms': metrica.tiempo_total_ms,
                'tiempo_transcripcion_ms': metrica.tiempo_transcripcion_ms,
                'tiempo_mejora_ms': metrica.tiempo_mejora_ms,
                'fecha': metrica.fecha.isoformat(),
                'tuvo_errores': metrica.tuvo_errores,
                'error_detalle': metrica.error_detalle[:100] if metrica.error_detalle else '',
                'tipo_estudio': metrica.get_tipo_estudio_display() if metrica.tipo_estudio else 'N/A'
            })
        
        return JsonResponse({
            'success': True,
            'anomalias': datos_anomalias,
            'umbral_ms': umbral_ms,
            'total': len(datos_anomalias)
        })
    
    except Exception as e:
        logger.error(f"Error obteniendo anomalías: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
