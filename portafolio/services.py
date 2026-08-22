import hashlib
from pathlib import Path

from django.db import transaction
from django.utils import timezone

from .models import ActividadCurricular, DocumentoActividadCurricular
from .permissions import puede_ver_todos_los_residentes
from .selectors import (
    evolucion_actividad,
    periodo_ciclo_lectivo,
    periodos_disponibles_residente,
    resumen_actividades_curriculares,
    resumen_clases,
    resumen_estudios,
    resumen_guardias,
    resumen_preinformes,
    totales_actividad_ciclo,
)


class ActividadCurricularError(Exception):
    """Error controlado del flujo de actividades curriculares."""


def guardar_documentos_actividad(actividad, archivos, subido_por):
    """Persiste evidencias privadas y registra metadatos para auditoría."""
    documentos = []
    for archivo in archivos:
        digest = hashlib.sha256()
        for bloque in archivo.chunks():
            digest.update(bloque)
        archivo.seek(0)
        documentos.append(
            DocumentoActividadCurricular.objects.create(
                actividad=actividad,
                archivo=archivo,
                nombre_original=Path(archivo.name).name[:255],
                tipo_mime=getattr(archivo, 'content_type', '') or '',
                tamanio_bytes=archivo.size,
                sha256=digest.hexdigest(),
                subido_por=subido_por,
            )
        )
    return documentos


@transaction.atomic
def enviar_actividad(actividad, residente):
    actividad = ActividadCurricular.objects.select_for_update().get(pk=actividad.pk)
    if actividad.residente_id != residente.pk:
        raise ActividadCurricularError('Solo podés enviar una actividad propia.')
    if not residente.es_residente_activo():
        raise ActividadCurricularError('Solo un residente activo puede enviar actividades.')
    if not actividad.puede_editar_residente:
        raise ActividadCurricularError('La actividad ya no está disponible para edición.')

    actividad.estado = 'ENVIADA'
    actividad.enviada_en = timezone.now()
    actividad.revisada_en = None
    actividad.revisada_por = None
    actividad.observacion_docente = ''
    actividad.save(
        update_fields=[
            'estado',
            'enviada_en',
            'revisada_en',
            'revisada_por',
            'observacion_docente',
            'actualizada_en',
        ]
    )
    return actividad


@transaction.atomic
def revisar_actividad(actividad, revisor, accion, observacion=''):
    actividad = ActividadCurricular.objects.select_for_update().get(pk=actividad.pk)
    if not puede_ver_todos_los_residentes(revisor):
        raise ActividadCurricularError('No tenés permisos para revisar actividades.')
    if actividad.estado != 'ENVIADA':
        raise ActividadCurricularError('La actividad ya no está pendiente de revisión.')

    observacion = observacion.strip()
    if accion == 'VALIDAR':
        actividad.estado = 'VALIDADA'
    elif accion == 'OBSERVAR':
        if not observacion:
            raise ActividadCurricularError('La observación es obligatoria.')
        actividad.estado = 'OBSERVADA'
    else:
        raise ActividadCurricularError('Acción de revisión inválida.')

    actividad.revisada_por = revisor
    actividad.observacion_docente = observacion
    actividad.revisada_en = timezone.now()
    actividad.save(
        update_fields=[
            'estado',
            'revisada_por',
            'observacion_docente',
            'revisada_en',
            'actualizada_en',
        ]
    )
    return actividad


@transaction.atomic
def eliminar_documento_actividad(documento, residente):
    documento = (
        DocumentoActividadCurricular.objects.select_for_update()
        .select_related('actividad')
        .get(pk=documento.pk)
    )
    if documento.actividad.residente_id != residente.pk:
        raise ActividadCurricularError('Solo podés eliminar documentos propios.')
    if not documento.actividad.puede_editar_residente:
        raise ActividadCurricularError('La actividad ya no está disponible para edición.')
    documento.archivo.delete(save=False)
    documento.delete()


def construir_resumen_portafolio(residente, fecha_referencia=None, periodo=None):
    periodo = periodo or periodo_ciclo_lectivo(fecha_referencia)
    return {
        'periodo': periodo,
        'guardias': resumen_guardias(residente, periodo, hoy=fecha_referencia),
        'preinformes': resumen_preinformes(residente, periodo),
        'estudios': resumen_estudios(residente, periodo),
        'clases': resumen_clases(residente, periodo),
        'actividades': resumen_actividades_curriculares(residente, periodo),
        'evolucion': evolucion_actividad(
            residente,
            periodo,
            hoy=fecha_referencia,
        ),
    }


def construir_trayectoria_portafolio(residente, fecha_referencia=None):
    periodos = periodos_disponibles_residente(residente, fecha_referencia)
    acumulado = {
        'preinformes': 0,
        'preinformes_finalizados': 0,
        'estudios': 0,
        'registros_estudios': 0,
        'regiones': 0,
        'guardias': 0,
        'clases': 0,
        'actividades': 0,
    }
    ciclos = []
    for periodo in periodos:
        totales = totales_actividad_ciclo(
            residente,
            periodo,
            hoy=fecha_referencia,
        )
        for clave, valor in totales.items():
            acumulado[clave] += valor
        ciclos.append({'periodo': periodo, 'totales': totales})

    return {'ciclos': ciclos, 'acumulado': acumulado}
