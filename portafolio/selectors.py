from datetime import date, timedelta

from django.db.models import Count, Sum
from django.utils import timezone

from accounts.models import CustomUser
from clases_residentes.models import ClaseResidente
from control_guardias.models import AsignacionGuardia, Feriado
from liquidacion.models import Estudios, RegistroEstudio, RegistroEstudiosPorMedico
from preinformes.models import Preinforme


ESTADOS_GUARDIA_COMPUTABLES = ('PUBLICADA', 'CUMPLIDA')


def primer_dia_habil_agosto(anio):
    """Retorna el primer dia de agosto que no sea fin de semana ni feriado."""
    candidato = date(anio, 8, 1)
    while (
        candidato.weekday() >= 5
        or Feriado.objects.filter(fecha=candidato).exists()
    ):
        candidato += timedelta(days=1)
    return candidato


def periodo_ciclo_lectivo(fecha_referencia=None):
    """Construye el ciclo que contiene la fecha local indicada."""
    referencia = fecha_referencia or timezone.localdate()
    anio_inicio = referencia.year
    inicio_este_anio = primer_dia_habil_agosto(anio_inicio)
    if referencia < inicio_este_anio:
        anio_inicio -= 1

    inicio = primer_dia_habil_agosto(anio_inicio)
    fin_exclusivo = primer_dia_habil_agosto(anio_inicio + 1)
    return {
        'anio_inicio': anio_inicio,
        'inicio': inicio,
        'fin_exclusivo': fin_exclusivo,
        'fin_inclusivo': fin_exclusivo - timedelta(days=1),
        'etiqueta': f'{anio_inicio}/{str(anio_inicio + 1)[-2:]}',
    }


def resumen_guardias(residente, periodo, hoy=None):
    hoy = hoy or timezone.localdate()
    guardias = AsignacionGuardia.objects.filter(
        residente=residente,
        estado__in=ESTADOS_GUARDIA_COMPUTABLES,
        fecha__gte=periodo['inicio'],
        fecha__lt=min(periodo['fin_exclusivo'], hoy),
    )
    por_tipo = list(
        guardias.values('tipo_guardia__nombre')
        .annotate(cantidad=Count('id'))
        .order_by('-cantidad', 'tipo_guardia__nombre')
    )
    return {'total': guardias.count(), 'por_tipo': por_tipo}


def resumen_preinformes(residente, periodo):
    preinformes = Preinforme.objects.filter(
        residente=residente,
        es_registro_demo=False,
        fecha_creacion__date__gte=periodo['inicio'],
        fecha_creacion__date__lt=periodo['fin_exclusivo'],
    )
    por_modalidad_region = list(
        preinformes.values('tipo_estudio__nombre', 'region__nombre')
        .annotate(cantidad=Count('id'))
        .order_by('-cantidad', 'tipo_estudio__nombre', 'region__nombre')
    )
    return {
        'total': preinformes.count(),
        'finalizados': preinformes.filter(estado='finalizado').count(),
        'por_modalidad_region': por_modalidad_region,
    }


def resumen_estudios(residente, periodo):
    """Proyecta solamente datos academico-asistenciales permitidos."""
    registros = RegistroEstudiosPorMedico.objects.filter(
        medico=residente,
        anulado=False,
        fecha_del_informe__gte=periodo['inicio'],
        fecha_del_informe__lt=periodo['fin_exclusivo'],
    )
    registros_ids = registros.values('pk')
    practicas = RegistroEstudio.objects.filter(registro_id__in=registros_ids)

    por_modalidad = list(
        practicas.values('estudio__tipo')
        .annotate(cantidad=Sum('cantidad'))
        .order_by('estudio__tipo')
    )
    etiquetas_modalidad = dict(Estudios.TIPO_ESTUDIO_CHOICES)
    for fila in por_modalidad:
        fila['modalidad_display'] = etiquetas_modalidad.get(
            fila['estudio__tipo'], fila['estudio__tipo']
        )
    practicas_asociadas = list(
        practicas.values('estudio__tipo', 'estudio__nombre')
        .annotate(cantidad=Sum('cantidad'))
        .order_by('estudio__tipo', '-cantidad', 'estudio__nombre')
    )
    for fila in practicas_asociadas:
        fila['modalidad_display'] = etiquetas_modalidad.get(
            fila['estudio__tipo'], fila['estudio__tipo']
        )
    totales = registros.aggregate(
        total_regiones=Sum('cantidad_regiones'),
    )
    total_practicas = practicas.aggregate(
        total=Sum('cantidad'),
    )['total'] or 0

    return {
        'total_registros': registros.count(),
        'total_practicas': total_practicas,
        'total_regiones': totales['total_regiones'] or 0,
        'por_modalidad': por_modalidad,
        'practicas_asociadas': practicas_asociadas,
    }


def resumen_clases(residente, periodo):
    clases = ClaseResidente.objects.filter(
        autor=residente,
        activa=True,
        fecha_clase__gte=periodo['inicio'],
        fecha_clase__lt=periodo['fin_exclusivo'],
    )
    por_categoria = list(
        clases.values('categoria')
        .annotate(cantidad=Count('id'))
        .order_by('-cantidad', 'categoria')
    )
    etiquetas = dict(ClaseResidente.CATEGORIA_CHOICES)
    for fila in por_categoria:
        fila['categoria_display'] = etiquetas.get(fila['categoria'], fila['categoria'])
    return {'total': clases.count(), 'por_categoria': por_categoria}


def residentes_para_seguimiento():
    return CustomUser.objects.filter(
        rol='medico_residente',
        perfil_completo=True,
        is_active=True,
    ).order_by(
        'estado_residencia', 'anio_residencia', 'last_name', 'first_name'
    )
