import re
from datetime import date, timedelta

from django.db.models import Count, Min, Q, Sum
from django.utils import timezone

from accounts.models import CustomUser
from clases_residentes.models import ClaseResidente
from control_guardias.models import AsignacionGuardia, Feriado
from liquidacion.models import Estudios, RegistroEstudio, RegistroEstudiosPorMedico
from preinformes.models import Preinforme


ESTADOS_GUARDIA_COMPUTABLES = ('PUBLICADA', 'CUMPLIDA')
MESES_CICLO_LECTIVO = (
    'Ago',
    'Sep',
    'Oct',
    'Nov',
    'Dic',
    'Ene',
    'Feb',
    'Mar',
    'Abr',
    'May',
    'Jun',
    'Jul',
)


def primer_dia_habil_agosto(anio):
    """Retorna el primer dia de agosto que no sea fin de semana ni feriado."""
    candidato = date(anio, 8, 1)
    while (
        candidato.weekday() >= 5
        or Feriado.objects.filter(fecha=candidato).exists()
    ):
        candidato += timedelta(days=1)
    return candidato


def periodo_ciclo_lectivo_por_anio(anio_inicio):
    """Construye un ciclo a partir de su año calendario de inicio."""
    inicio = primer_dia_habil_agosto(anio_inicio)
    fin_exclusivo = primer_dia_habil_agosto(anio_inicio + 1)
    return {
        'anio_inicio': anio_inicio,
        'inicio': inicio,
        'fin_exclusivo': fin_exclusivo,
        'fin_inclusivo': fin_exclusivo - timedelta(days=1),
        'etiqueta': f'{anio_inicio}/{str(anio_inicio + 1)[-2:]}',
    }


def periodo_ciclo_lectivo(fecha_referencia=None):
    """Construye el ciclo que contiene la fecha local indicada."""
    referencia = fecha_referencia or timezone.localdate()
    anio_inicio = referencia.year
    inicio_este_anio = primer_dia_habil_agosto(anio_inicio)
    if referencia < inicio_este_anio:
        anio_inicio -= 1

    return periodo_ciclo_lectivo_por_anio(anio_inicio)


def _primera_fecha_de_actividad(residente):
    """Busca una fecha inicial cuando el perfil no informa ingreso."""
    fechas = [
        AsignacionGuardia.objects.filter(residente=residente).aggregate(
            fecha=Min('fecha')
        )['fecha'],
        Preinforme.objects.filter(
            residente=residente,
            es_registro_demo=False,
        ).aggregate(fecha=Min('fecha_creacion'))['fecha'],
        RegistroEstudiosPorMedico.objects.filter(
            medico=residente,
            anulado=False,
        ).aggregate(fecha=Min('fecha_del_informe'))['fecha'],
        ClaseResidente.objects.filter(
            autor=residente,
            activa=True,
        ).aggregate(fecha=Min('fecha_clase'))['fecha'],
    ]
    normalizadas = []
    for fecha in fechas:
        if fecha is None:
            continue
        if hasattr(fecha, 'date'):
            if timezone.is_aware(fecha):
                fecha = timezone.localtime(fecha)
            fecha = fecha.date()
        normalizadas.append(fecha)
    return min(normalizadas) if normalizadas else None


def periodos_disponibles_residente(residente, fecha_referencia=None):
    """Retorna, del más reciente al más antiguo, los ciclos consultables."""
    referencia = fecha_referencia or timezone.localdate()
    periodo_actual = periodo_ciclo_lectivo(referencia)
    fecha_inicio = residente.fecha_ingreso_residencia
    if fecha_inicio is None:
        fecha_inicio = _primera_fecha_de_actividad(residente) or referencia

    fecha_fin = referencia
    if residente.estado_residencia == 'EGRESADO' and residente.fecha_egreso_residencia:
        fecha_fin = min(residente.fecha_egreso_residencia, referencia)

    anio_inicio = periodo_ciclo_lectivo(fecha_inicio)['anio_inicio']
    anio_fin = periodo_ciclo_lectivo(fecha_fin)['anio_inicio']
    if anio_inicio > anio_fin:
        anio_inicio = anio_fin

    periodos = []
    for anio in range(anio_fin, anio_inicio - 1, -1):
        periodo = periodo_ciclo_lectivo_por_anio(anio)
        periodo['es_actual'] = anio == periodo_actual['anio_inicio']
        periodo['estado'] = 'EN_CURSO' if periodo['es_actual'] else 'CUMPLIDO'
        periodos.append(periodo)
    return periodos


def fin_datos_exclusivo(periodo, hoy=None):
    """Limita fuentes fechadas hasta hoy sin recortar ciclos ya cumplidos."""
    hoy = hoy or timezone.localdate()
    return min(periodo['fin_exclusivo'], hoy + timedelta(days=1))


def resumen_guardias(residente, periodo, hoy=None):
    hoy = hoy or timezone.localdate()
    guardias = AsignacionGuardia.objects.filter(
        residente=residente,
        estado__in=ESTADOS_GUARDIA_COMPUTABLES,
        fecha__gte=periodo['inicio'],
        fecha__lt=min(periodo['fin_exclusivo'], hoy),
    )
    tipos_registrados = list(
        guardias.values('tipo_guardia__nombre')
        .annotate(cantidad=Count('id'))
        .order_by('-cantidad', 'tipo_guardia__nombre')
    )
    tipos_unificados = {}
    for fila in tipos_registrados:
        nombre = fila['tipo_guardia__nombre'] or 'Sin tipo informado'
        nombre = re.sub(r'\s+\(\d+\)\s*$', '', nombre).strip()
        clave = nombre.casefold()
        if clave not in tipos_unificados:
            tipos_unificados[clave] = {
                'tipo_guardia__nombre': nombre,
                'cantidad': 0,
            }
        tipos_unificados[clave]['cantidad'] += fila['cantidad']
    por_tipo = sorted(
        tipos_unificados.values(),
        key=lambda fila: (-fila['cantidad'], fila['tipo_guardia__nombre']),
    )
    return {'total': guardias.count(), 'por_tipo': por_tipo}


def resumen_preinformes(residente, periodo):
    fin_exclusivo = fin_datos_exclusivo(periodo)
    preinformes = Preinforme.objects.filter(
        residente=residente,
        es_registro_demo=False,
        fecha_creacion__date__gte=periodo['inicio'],
        fecha_creacion__date__lt=fin_exclusivo,
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
        'principales': por_modalidad_region[:8],
    }


def resumen_estudios(residente, periodo):
    """Proyecta solamente datos academico-asistenciales permitidos."""
    fin_exclusivo = fin_datos_exclusivo(periodo)
    registros = RegistroEstudiosPorMedico.objects.filter(
        medico=residente,
        anulado=False,
        fecha_del_informe__gte=periodo['inicio'],
        fecha_del_informe__lt=fin_exclusivo,
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
        .order_by('-cantidad', 'estudio__tipo', 'estudio__nombre')
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
        'practicas_destacadas': practicas_asociadas[:8],
    }


def resumen_clases(residente, periodo):
    fin_exclusivo = fin_datos_exclusivo(periodo)
    clases = list(
        ClaseResidente.objects.filter(
            autor=residente,
            activa=True,
            fecha_clase__gte=periodo['inicio'],
            fecha_clase__lt=fin_exclusivo,
        )
        .only(
            'id',
            'titulo',
            'categoria',
            'fecha_clase',
            'archivo_thumbnail',
        )
        .order_by('-fecha_clase', '-fecha_creacion')
    )
    return {'total': len(clases), 'items': clases}


def _indice_mes_ciclo(fecha, periodo):
    """Ubica una fecha en los doce meses visuales del ciclo agosto-julio."""
    if hasattr(fecha, 'date'):
        if timezone.is_aware(fecha):
            fecha = timezone.localtime(fecha)
        fecha = fecha.date()
    if fecha < periodo['inicio'] or fecha >= periodo['fin_exclusivo']:
        return None

    anio_inicio = periodo['anio_inicio']
    if fecha.year == anio_inicio + 1 and fecha.month == 8:
        # Los primeros días de agosto pueden pertenecer al cierre del ciclo.
        return 11
    indice = (fecha.year - anio_inicio) * 12 + fecha.month - 8
    return indice if 0 <= indice < 12 else None


def _serie_acumulada(valores):
    acumulado = 0
    resultado = []
    for valor in valores:
        if valor is None:
            resultado.append(None)
            continue
        acumulado += valor
        resultado.append(acumulado)
    return resultado


def evolucion_actividad(residente, periodo, hoy=None):
    """Construye series mensuales sin exponer información clínica sensible."""
    hoy = hoy or timezone.localdate()
    fin_exclusivo = fin_datos_exclusivo(periodo, hoy)
    valores = {
        'estudios': [0] * 12,
        'preinformes': [0] * 12,
        'guardias': [0] * 12,
        'clases': [0] * 12,
    }

    def sumar(clave, fecha, cantidad=1):
        indice = _indice_mes_ciclo(fecha, periodo)
        if indice is not None:
            valores[clave][indice] += cantidad or 0

    practicas = RegistroEstudio.objects.filter(
        registro__medico=residente,
        registro__anulado=False,
        registro__fecha_del_informe__gte=periodo['inicio'],
        registro__fecha_del_informe__lt=fin_exclusivo,
    ).values_list('registro__fecha_del_informe', 'cantidad')
    for fecha, cantidad in practicas:
        sumar('estudios', fecha, cantidad)

    preinformes = Preinforme.objects.filter(
        residente=residente,
        es_registro_demo=False,
        fecha_creacion__date__gte=periodo['inicio'],
        fecha_creacion__date__lt=fin_exclusivo,
    ).values_list('fecha_creacion', flat=True)
    for fecha in preinformes:
        sumar('preinformes', fecha)

    guardias = AsignacionGuardia.objects.filter(
        residente=residente,
        estado__in=ESTADOS_GUARDIA_COMPUTABLES,
        fecha__gte=periodo['inicio'],
        fecha__lt=min(periodo['fin_exclusivo'], hoy),
    ).values_list('fecha', flat=True)
    for fecha in guardias:
        sumar('guardias', fecha)

    clases = ClaseResidente.objects.filter(
        autor=residente,
        activa=True,
        fecha_clase__gte=periodo['inicio'],
        fecha_clase__lt=fin_exclusivo,
    ).values_list('fecha_clase', flat=True)
    for fecha in clases:
        sumar('clases', fecha)

    mes_actual = None
    for indice in range(12):
        mes = 8 + indice
        anio = periodo['anio_inicio']
        if mes > 12:
            mes -= 12
            anio += 1
        inicio_mes = date(anio, mes, 1)
        if indice == 0:
            inicio_mes = periodo['inicio']
        if indice == 11:
            fin_mes = periodo['fin_exclusivo']
        else:
            mes_siguiente = mes + 1
            anio_siguiente = anio
            if mes_siguiente == 13:
                mes_siguiente = 1
                anio_siguiente += 1
            fin_mes = date(anio_siguiente, mes_siguiente, 1)

        if inicio_mes <= hoy < fin_mes:
            mes_actual = indice
        if inicio_mes > hoy:
            for serie in valores.values():
                serie[indice] = None

    configuracion = (
        ('estudios', 'Estudios', 'prácticas'),
        ('preinformes', 'Preinformes', 'preinformes'),
        ('guardias', 'Guardias', 'guardias'),
        ('clases', 'Clases', 'clases'),
    )
    series = []
    for clave, etiqueta, unidad in configuracion:
        series.append(
            {
                'clave': clave,
                'etiqueta': etiqueta,
                'unidad': unidad,
                'mensual': valores[clave],
                'acumulada': _serie_acumulada(valores[clave]),
            }
        )

    return {
        'etiquetas': list(MESES_CICLO_LECTIVO),
        'series': series,
        'mes_actual': mes_actual,
    }


def totales_actividad_ciclo(residente, periodo, hoy=None):
    """Calcula solo los totales necesarios para la trayectoria por ciclo."""
    hoy = hoy or timezone.localdate()
    fin_exclusivo = fin_datos_exclusivo(periodo, hoy)
    guardias = AsignacionGuardia.objects.filter(
        residente=residente,
        estado__in=ESTADOS_GUARDIA_COMPUTABLES,
        fecha__gte=periodo['inicio'],
        fecha__lt=min(periodo['fin_exclusivo'], hoy),
    ).count()

    preinformes = Preinforme.objects.filter(
        residente=residente,
        es_registro_demo=False,
        fecha_creacion__date__gte=periodo['inicio'],
        fecha_creacion__date__lt=fin_exclusivo,
    ).aggregate(
        total=Count('id'),
        finalizados=Count('id', filter=Q(estado='finalizado')),
    )

    registros = RegistroEstudiosPorMedico.objects.filter(
        medico=residente,
        anulado=False,
        fecha_del_informe__gte=periodo['inicio'],
        fecha_del_informe__lt=fin_exclusivo,
    )
    totales_registros = registros.aggregate(
        total=Count('id'),
        regiones=Sum('cantidad_regiones'),
    )
    practicas = RegistroEstudio.objects.filter(
        registro__in=registros,
    ).aggregate(total=Sum('cantidad'))['total'] or 0

    clases = ClaseResidente.objects.filter(
        autor=residente,
        activa=True,
        fecha_clase__gte=periodo['inicio'],
        fecha_clase__lt=fin_exclusivo,
    ).count()

    return {
        'preinformes': preinformes['total'] or 0,
        'preinformes_finalizados': preinformes['finalizados'] or 0,
        'estudios': practicas,
        'registros_estudios': totales_registros['total'] or 0,
        'regiones': totales_registros['regiones'] or 0,
        'guardias': guardias,
        'clases': clases,
    }


def residentes_para_seguimiento():
    return CustomUser.objects.filter(
        rol='medico_residente',
        perfil_completo=True,
        is_active=True,
    ).order_by(
        'estado_residencia', 'anio_residencia', 'last_name', 'first_name'
    )
