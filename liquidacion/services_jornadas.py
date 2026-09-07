from datetime import date, time, timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import JornadaContractual, ROLES_LIQUIDAR_COMO_EXTRA_RESIDENCIA


INICIO_JORNADAS = date(2026, 8, 1)
DIAS_SEMANA = ('Lunes', 'Martes', 'Miercoles', 'Jueves', 'Viernes', 'Sabado', 'Domingo')
ESTADO_DENTRO_JORNADA = 'DENTRO'
ESTADO_FUERA_JORNADA = 'FUERA'
ESTADO_JORNADA_MANUAL = 'MANUAL'
ESTADO_JORNADA_SIN_CONFIGURACION = 'SIN_CONFIGURACION'
ESTADO_JORNADA_NO_APLICA = 'NO_APLICA'
_JORNADA_NO_PROVISTA = object()


def puede_gestionar_jornadas(user):
    return user.is_authenticated and (
        user.is_superuser or user.rol == 'jefe_servicio' or (
            user.rol == 'administrativo' and user.has_perm('liquidacion.gestionar_jornadas_contractuales')
        )
    )


def puede_ver_todas_jornadas(user):
    return user.is_authenticated and (user.is_superuser or user.rol in {'administrativo', 'jefe_servicio'})


def validar_semana(semana):
    # Los siete dias deben estar declarados: [] significa sin jornada confirmada.
    if not isinstance(semana, dict) or set(semana) != {str(dia) for dia in range(7)}:
        raise ValidationError('Debes declarar la jornada de los siete dias.')
    for dia, tramos in semana.items():
        if not isinstance(tramos, list) or len(tramos) > 2:
            raise ValidationError('Cada dia admite una lista de hasta dos tramos.')
        fin_anterior = None
        for tramo in tramos:
            try:
                if not isinstance(tramo, list) or len(tramo) != 2 or not all(isinstance(hora, str) and len(hora) == 5 for hora in tramo):
                    raise ValueError
                inicio, fin = (time.fromisoformat(hora) for hora in tramo)
                if inicio >= fin or (fin_anterior and inicio < fin_anterior):
                    raise ValueError
                fin_anterior = fin
            except (TypeError, ValueError):
                raise ValidationError(f'{DIAS_SEMANA[int(dia)]}: horarios invalidos o superpuestos.')


@transaction.atomic
def crear_jornada_contractual(*, profesional, vigencia_desde, semana, observacion, user):
    if not puede_gestionar_jornadas(user):
        raise PermissionDenied
    # Serializa incluso la primera version, cuando aun no hay jornada que bloquear.
    profesional = get_user_model().objects.select_for_update().get(pk=profesional.pk)
    if profesional.rol not in ROLES_LIQUIDAR_COMO_EXTRA_RESIDENCIA:
        raise ValidationError('El profesional debe ser jefe o instructor de residentes.')
    if vigencia_desde < INICIO_JORNADAS:
        raise ValidationError('La configuracion comienza a partir del 01/08/2026.')
    if not observacion.strip():
        raise ValidationError('Indica la referencia o motivo de la jornada.')
    ultima = JornadaContractual.objects.filter(profesional=profesional).order_by('-vigencia_desde').first()
    if ultima and vigencia_desde <= ultima.vigencia_desde:
        raise ValidationError('La nueva version debe comenzar despues de la ultima jornada registrada.')
    jornada = JornadaContractual(profesional=profesional, vigencia_desde=vigencia_desde,
                                 semana=semana, observacion=observacion.strip(), creado_por=user)
    jornada.full_clean()
    if ultima:
        ultima.vigencia_hasta = vigencia_desde - timedelta(days=1)
        ultima.cerrado_por = user
        ultima.fecha_cierre = timezone.now()
        ultima.save(update_fields=['vigencia_hasta', 'cerrado_por', 'fecha_cierre'])
    jornada.save()
    return jornada


def jornada_para_fecha(profesional, fecha):
    return JornadaContractual.objects.filter(profesional=profesional, vigencia_desde__lte=fecha).filter(
        Q(vigencia_hasta__isnull=True) | Q(vigencia_hasta__gte=fecha)
    ).order_by('-vigencia_desde').first()


def _hora_serializable(valor):
    return valor.strftime('%H:%M') if valor else None


def _resultado_evaluacion_jornada(*, estado, profesional, fecha, hora_inicio, hora_fin,
                                  motivo, jornada=None, tramos=None):
    return {
        'estado': estado,
        'aplica': estado != ESTADO_JORNADA_NO_APLICA,
        'profesional_id': getattr(profesional, 'pk', None),
        'fecha': fecha.isoformat() if fecha else None,
        'dia_semana': DIAS_SEMANA[fecha.weekday()] if fecha else None,
        'hora_inicio': _hora_serializable(hora_inicio),
        'hora_fin': _hora_serializable(hora_fin),
        'jornada_id': jornada.pk if jornada else None,
        'vigencia_desde': jornada.vigencia_desde.isoformat() if jornada else None,
        'vigencia_hasta': jornada.vigencia_hasta.isoformat() if jornada and jornada.vigencia_hasta else None,
        'tramos': tramos or [],
        'tramos_display': [f'{desde}-{hasta}' for desde, hasta in (tramos or [])],
        'motivo': motivo,
    }


def evaluar_horario_en_jornada(*, profesional, fecha, hora_inicio, hora_fin=None,
                               jornada=_JORNADA_NO_PROVISTA):
    """Evalua un intervalo contra la jornada vigente sin modificar liquidaciones.

    Los intervalos se consideran semiabiertos: un estudio que comienza exactamente
    al finalizar un tramo ya esta fuera de jornada. Si un estudio cruza el limite
    de un tramo, se deriva a revision manual.
    """
    rol = getattr(profesional, 'rol', None)
    if rol not in ROLES_LIQUIDAR_COMO_EXTRA_RESIDENCIA:
        return _resultado_evaluacion_jornada(
            estado=ESTADO_JORNADA_NO_APLICA,
            profesional=profesional,
            fecha=fecha,
            hora_inicio=hora_inicio,
            hora_fin=hora_fin,
            motivo='La jornada contractual solo aplica a jefes e instructores de residentes.',
        )

    if not fecha or not hora_inicio:
        return _resultado_evaluacion_jornada(
            estado=ESTADO_JORNADA_MANUAL,
            profesional=profesional,
            fecha=fecha,
            hora_inicio=hora_inicio,
            hora_fin=hora_fin,
            motivo='Falta fecha u hora de inicio confiable para evaluar la jornada.',
        )

    if hora_fin and hora_fin <= hora_inicio:
        return _resultado_evaluacion_jornada(
            estado=ESTADO_JORNADA_MANUAL,
            profesional=profesional,
            fecha=fecha,
            hora_inicio=hora_inicio,
            hora_fin=hora_fin,
            motivo='El intervalo cruza medianoche o tiene una duracion invalida.',
        )

    if jornada is _JORNADA_NO_PROVISTA:
        jornada = jornada_para_fecha(profesional, fecha)
    if not jornada:
        return _resultado_evaluacion_jornada(
            estado=ESTADO_JORNADA_SIN_CONFIGURACION,
            profesional=profesional,
            fecha=fecha,
            hora_inicio=hora_inicio,
            hora_fin=hora_fin,
            motivo='No existe una jornada contractual vigente para esa fecha.',
        )

    tramos = jornada.semana[str(fecha.weekday())]
    if not tramos:
        return _resultado_evaluacion_jornada(
            estado=ESTADO_FUERA_JORNADA,
            profesional=profesional,
            fecha=fecha,
            hora_inicio=hora_inicio,
            hora_fin=hora_fin,
            jornada=jornada,
            tramos=tramos,
            motivo='El profesional no tiene jornada contractual declarada ese dia.',
        )

    tramos_time = [
        (time.fromisoformat(desde), time.fromisoformat(hasta))
        for desde, hasta in tramos
    ]
    instante_fin = hora_fin or hora_inicio

    for desde, hasta in tramos_time:
        if hora_fin:
            if desde <= hora_inicio and hora_fin <= hasta:
                return _resultado_evaluacion_jornada(
                    estado=ESTADO_DENTRO_JORNADA,
                    profesional=profesional,
                    fecha=fecha,
                    hora_inicio=hora_inicio,
                    hora_fin=hora_fin,
                    jornada=jornada,
                    tramos=tramos,
                    motivo='El intervalo EGES esta contenido en la jornada contractual.',
                )
        elif desde <= hora_inicio < hasta:
            return _resultado_evaluacion_jornada(
                estado=ESTADO_DENTRO_JORNADA,
                profesional=profesional,
                fecha=fecha,
                hora_inicio=hora_inicio,
                hora_fin=hora_fin,
                jornada=jornada,
                tramos=tramos,
                motivo='La hora EGES esta dentro de la jornada contractual.',
            )

    if hora_fin and any(hora_inicio < hasta and instante_fin > desde for desde, hasta in tramos_time):
        return _resultado_evaluacion_jornada(
            estado=ESTADO_JORNADA_MANUAL,
            profesional=profesional,
            fecha=fecha,
            hora_inicio=hora_inicio,
            hora_fin=hora_fin,
            jornada=jornada,
            tramos=tramos,
            motivo='El intervalo EGES cruza el limite de la jornada contractual.',
        )

    return _resultado_evaluacion_jornada(
        estado=ESTADO_FUERA_JORNADA,
        profesional=profesional,
        fecha=fecha,
        hora_inicio=hora_inicio,
        hora_fin=hora_fin,
        jornada=jornada,
        tramos=tramos,
        motivo='El horario EGES esta fuera de la jornada contractual.',
    )


def dias_jornada(jornada):
    return [{'nombre': nombre, 'tramos': jornada.semana[str(dia)]} for dia, nombre in enumerate(DIAS_SEMANA)]
