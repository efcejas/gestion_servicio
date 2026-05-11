# -*- coding: utf-8 -*-
"""
Services para el módulo consultorios.

Contiene lógica de negocio desacoplada de las vistas.
Patrón: sin `request`, retorna dict {'exito': bool, ...} o lanza excepción.

Estado actual:
  - sugerir_cobertura(): motor de propuesta de coberturas para ausencias
  - TODO Fase 2: mover ConflictDetector desde utils.py a este módulo
"""

from django.contrib.auth import get_user_model
from datetime import timedelta

from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from consultorios.models import (
    AsignacionEquipoConsultorio,
    AusenciaCobertura,
    BloqueHorario,
    EstadoAusenciaCobertura,
    EstadoBloque,
)

User = get_user_model()


# ---------------------------------------------------------------------------
# Excepciones del módulo
# ---------------------------------------------------------------------------

class ConsultoriosError(Exception):
    """Base para errores de dominio del módulo consultorios."""


class BloqueNoCubreError(ConsultoriosError):
    """El bloque no admite cobertura por residentes."""


class SinResidentesDisponiblesError(ConsultoriosError):
    """No hay residentes disponibles para cubrir el bloque."""


# ---------------------------------------------------------------------------
# Motor de cobertura
# ---------------------------------------------------------------------------

def sugerir_cobertura(bloque: BloqueHorario, fecha=None) -> dict:
    """
    Propone candidatos para cubrir un bloque ante ausencia del profesional asignado.

    Lógica de equidad:
      1. Solo residentes con rol `medico_residente` activos.
      2. Si el bloque tiene `competencia_requerida`, filtra por `cargo` o `especialidad`.
         (Fase 2: usar modelo Competencia cuando exista.)
      3. Ordena por cantidad de coberturas previas en el mismo día de semana → menor primero.
         (Fase 2: reemplazar por historial real de AusenciaCobertura cuando exista.)
      4. Retorna hasta 3 candidatos con justificación.

    Args:
        bloque: BloqueHorario con permite_cobertura_residente=True.
        fecha: date de la ausencia (opcional, usada para detectar conflictos).

    Returns:
        {
            'exito': True,
            'candidatos': [
                {
                    'usuario': <User>,
                    'nombre': str,
                    'anio_residencia': int,
                    'coberturas_previas_dia': int,
                    'justificacion': str,
                }
            ],
            'bloque': bloque,
            'fecha': fecha,
            'advertencias': [str],
        }

    Raises:
        BloqueNoCubreError: Si el bloque no admite cobertura.
        SinResidentesDisponiblesError: Si no hay residentes disponibles.
    """
    if not bloque.permite_cobertura_residente:
        raise BloqueNoCubreError(
            f"El bloque '{bloque}' no tiene habilitada la cobertura por residentes."
        )

    if bloque.estado != EstadoBloque.ACTIVO:
        raise BloqueNoCubreError(
            f"El bloque '{bloque}' no está activo (estado: {bloque.get_estado_display()})."
        )

    advertencias = []
    fecha_evaluacion = fecha or timezone.now().date()

    # 1. Pool base: residentes activos
    residentes_qs = User.objects.filter(
        is_active=True,
        rol='medico_residente',
    )

    # 2. Filtro por competencia (heurístico — Fase 2 ampliar con modelo Competencia)
    competencia = bloque.competencia_requerida
    if competencia:
        residentes_con_competencia = residentes_qs.filter(
            Q(cargo__icontains=competencia) |
            Q(especialidad__icontains=competencia) if hasattr(User, 'especialidad') else Q()
        )
        if residentes_con_competencia.exists():
            residentes_qs = residentes_con_competencia
        else:
            advertencias.append(
                f"No hay residentes con competencia '{competencia}'. "
                "Se muestra pool completo — validar manualmente."
            )

    # 3. Detección de conflicto de horario en la fecha indicada
    #    Si fecha está disponible, excluye residentes con bloque activo ese día/hora.
    dia_semana = bloque.dia_semana
    residentes_con_conflicto = set()
    bloques_ese_dia = BloqueHorario.objects.filter(
        dia_semana=dia_semana,
        estado=EstadoBloque.ACTIVO,
        hora_inicio__lt=bloque.hora_fin,
        hora_fin__gt=bloque.hora_inicio,
    ).exclude(pk=bloque.pk)

    for b in bloques_ese_dia.select_related('profesional_interno'):
        if b.profesional_interno_id:
            residentes_con_conflicto.add(b.profesional_interno_id)

    disponibles = residentes_qs.exclude(pk__in=residentes_con_conflicto)
    if not disponibles.exists():
        # Relajar: mostrar igual con advertencia
        advertencias.append(
            "Todos los residentes disponibles tienen conflicto de horario ese día. "
            "Mostrando pool completo para evaluación manual."
        )
        disponibles = residentes_qs

    if not disponibles.exists():
        raise SinResidentesDisponiblesError(
            "No hay residentes activos en el sistema para proponer cobertura."
        )

    # 4. Ordenar por equidad: menor cantidad de coberturas confirmadas primero.
    coberturas_previas = {
        row['residente_asignado_id']: row['total']
        for row in AusenciaCobertura.objects.filter(
            estado=EstadoAusenciaCobertura.CONFIRMADA,
            residente_asignado__isnull=False,
            bloque__dia_semana=dia_semana,
        ).values('residente_asignado_id').annotate(total=Count('id'))
    }

    def _nivel_residencia(usuario):
        valor = getattr(usuario, 'anio_residencia', 0)
        if valor is None:
            return 0
        if isinstance(valor, int):
            return valor
        try:
            return int(valor)
        except (TypeError, ValueError):
            digitos = ''.join(ch for ch in str(valor) if ch.isdigit())
            return int(digitos) if digitos else 0

    disponibles = sorted(
        list(disponibles),
        key=lambda r: (
            coberturas_previas.get(r.pk, 0),
            -_nivel_residencia(r),
            r.last_name or '',
            r.first_name or '',
        ),
    )

    candidatos = []
    for residente in disponibles[:3]:
        anio = _nivel_residencia(residente)
        nombre = residente.get_full_name() or residente.username
        historial = coberturas_previas.get(residente.pk, 0)
        candidatos.append({
            'usuario': residente,
            'nombre': nombre,
            'anio_residencia': anio,
            'coberturas_previas_dia': historial,
            'justificacion': (
                f"R{anio}" if anio else "Residente"
            ) + f" · sin conflicto de horario ese {bloque.get_dia_semana_display()}",
        })

    return {
        'exito': True,
        'candidatos': candidatos,
        'bloque': bloque,
        'fecha': fecha_evaluacion,
        'advertencias': advertencias,
    }


def _es_bloque_blando(bloque: BloqueHorario) -> bool:
    return bloque.tipo_titular in {
        'R1',
        'R2',
        'R3',
        'R4',
    }


def evaluar_migracion_agenda(
    consultorio,
    fecha_destino,
    hora_inicio_destino,
    hora_fin_destino,
    excluir_bloque_id=None,
) -> dict:
    """
    Evalúa si una agenda puede migrarse a un destino propuesto.

    Devuelve un semáforo operativo:
      - LIBRE: no hay bloques superpuestos
      - BLANDO: hay bloques de residencia que podrían sacrificarse
      - BLOQUEADO: hay al menos un bloque duro que no conviene tocar
    """
    bloques_conflictivos = list(
        BloqueHorario.objects.vigentes(fecha_destino)
        .filter(
            consultorio=consultorio,
            dia_semana=fecha_destino.weekday(),
            hora_inicio__lt=hora_fin_destino,
            hora_fin__gt=hora_inicio_destino,
        )
        .exclude(pk=excluir_bloque_id)
        .select_related('profesional_interno', 'profesional_externo', 'profesional_asignado_temporal')
        .order_by('hora_inicio')
    )

    bloques_blandos = [bloque for bloque in bloques_conflictivos if _es_bloque_blando(bloque)]
    bloques_duros = [bloque for bloque in bloques_conflictivos if bloque not in bloques_blandos]

    if not bloques_conflictivos:
        estado = 'LIBRE'
        mensaje = 'El destino está libre para esa fecha y horario.'
    elif bloques_duros:
        estado = 'BLOQUEADO'
        mensaje = 'El destino tiene bloques duros superpuestos y no conviene migrar ahí.'
    else:
        estado = 'BLANDO'
        mensaje = 'El destino sólo tiene bloques blandos de residentes y podría sacrificarse.'

    return {
        'exito': True,
        'estado': estado,
        'mensaje': mensaje,
        'consultorio': consultorio,
        'fecha_destino': fecha_destino,
        'dia_semana_destino': fecha_destino.weekday(),
        'hora_inicio_destino': hora_inicio_destino,
        'hora_fin_destino': hora_fin_destino,
        'bloques_conflictivos': bloques_conflictivos,
        'bloques_blandos': bloques_blandos,
        'bloques_duros': bloques_duros,
        'puede_migrar': estado in {'LIBRE', 'BLANDO'},
    }


def sugerir_destinos_migracion(
    fecha_destino,
    hora_inicio_destino,
    hora_fin_destino,
    excluir_bloque_id=None,
) -> list:
    """Rankea destinos de migración por prioridad operativa (LIBRE > BLANDO > BLOQUEADO)."""
    from consultorios.models import Consultorio

    prioridades = {
        'LIBRE': 0,
        'BLANDO': 1,
        'BLOQUEADO': 2,
    }

    resultados = []
    for consultorio in Consultorio.objects.activos().order_by('nombre'):
        evaluacion = evaluar_migracion_agenda(
            consultorio=consultorio,
            fecha_destino=fecha_destino,
            hora_inicio_destino=hora_inicio_destino,
            hora_fin_destino=hora_fin_destino,
            excluir_bloque_id=excluir_bloque_id,
        )
        resultados.append(evaluacion)

    resultados.sort(
        key=lambda item: (
            prioridades.get(item['estado'], 99),
            len(item['bloques_duros']),
            len(item['bloques_blandos']),
            item['consultorio'].nombre,
        )
    )
    return resultados


def sugerir_reubicacion_bloques_blandos(
    bloques_blandos,
    fecha_destino,
    excluir_consultorio_id=None,
) -> list:
    """Sugiere reubicación para cada bloque blando afectado por una migración."""
    resultados = []
    for bloque in bloques_blandos:
        sugerencias = sugerir_destinos_migracion(
            fecha_destino=fecha_destino,
            hora_inicio_destino=bloque.hora_inicio,
            hora_fin_destino=bloque.hora_fin,
            excluir_bloque_id=bloque.pk,
        )
        if excluir_consultorio_id is not None:
            sugerencias = [s for s in sugerencias if s['consultorio'].pk != excluir_consultorio_id]

        resultados.append({
            'bloque': bloque,
            'sugerencias': sugerencias[:3],
        })

    return resultados


def aplicar_migracion_agenda(
    bloque_origen: BloqueHorario,
    consultorio_destino,
    fecha_destino,
    hora_inicio_destino,
    hora_fin_destino,
    usuario=None,
) -> dict:
    """Aplica una migración real: crea destino, libera origen y pausa blandos desplazados."""
    evaluacion = evaluar_migracion_agenda(
        consultorio=consultorio_destino,
        fecha_destino=fecha_destino,
        hora_inicio_destino=hora_inicio_destino,
        hora_fin_destino=hora_fin_destino,
        excluir_bloque_id=bloque_origen.pk,
    )

    if evaluacion['estado'] == 'BLOQUEADO':
        raise ConsultoriosError('No se puede aplicar la migración: el destino tiene bloqueos duros.')

    hoy = timezone.now().date()
    es_migracion_futura = fecha_destino > hoy
    asignacion_equipo_valida = False
    if bloque_origen.equipo_id:
        asignacion_equipo_valida = AsignacionEquipoConsultorio.objects.filter(
            consultorio=consultorio_destino,
            equipo=bloque_origen.equipo,
        ).filter(
            Q(es_permanente=True) |
            Q(fecha_inicio__lte=hoy, fecha_fin__gte=hoy)
        ).exists()

    with transaction.atomic():
        blandos_pausados = []
        blandos_diferidos = []
        for bloque_blando in evaluacion['bloques_blandos']:
            fin_blando = fecha_destino - timedelta(days=1)
            if fin_blando < bloque_blando.fecha_inicio_vigencia:
                fin_blando = bloque_blando.fecha_inicio_vigencia

            if es_migracion_futura:
                bloque_blando.fecha_fin_vigencia = fin_blando
                nota = (
                    f"[MIGRACION] Vigencia recortada por migración futura de bloque #{bloque_origen.pk} "
                    f"hacia {consultorio_destino.nombre} ({fecha_destino} {hora_inicio_destino}-{hora_fin_destino})."
                )
                bloque_blando.observaciones = f"{(bloque_blando.observaciones or '').strip()}\n{nota}".strip()
                bloque_blando.save(update_fields=['fecha_fin_vigencia', 'observaciones', 'fecha_modificacion'])
                blandos_diferidos.append(bloque_blando)
                continue

            bloque_blando.estado = EstadoBloque.PAUSADO
            nota = (
                f"[MIGRACION] Pausado por migración de bloque #{bloque_origen.pk} "
                f"hacia {consultorio_destino.nombre} ({fecha_destino} {hora_inicio_destino}-{hora_fin_destino})."
            )
            bloque_blando.observaciones = f"{(bloque_blando.observaciones or '').strip()}\n{nota}".strip()
            bloque_blando.save(update_fields=['estado', 'observaciones', 'fecha_modificacion'])
            blandos_pausados.append(bloque_blando)

        fin_origen = fecha_destino - timedelta(days=1)
        if fin_origen < bloque_origen.fecha_inicio_vigencia:
            fin_origen = bloque_origen.fecha_inicio_vigencia
        bloque_origen.fecha_fin_vigencia = fin_origen
        if es_migracion_futura:
            bloque_origen.estado = EstadoBloque.ACTIVO
            nota_origen = (
                f"[MIGRACION] Vigencia recortada por migración futura al bloque destino pendiente "
                f"({consultorio_destino.nombre} {fecha_destino} {hora_inicio_destino}-{hora_fin_destino})."
            )
        else:
            bloque_origen.estado = EstadoBloque.FINALIZADO
            nota_origen = (
                f"[MIGRACION] Finalizado por migración al bloque destino pendiente "
                f"({consultorio_destino.nombre} {fecha_destino} {hora_inicio_destino}-{hora_fin_destino})."
            )
        bloque_origen.observaciones = f"{(bloque_origen.observaciones or '').strip()}\n{nota_origen}".strip()
        bloque_origen.save(update_fields=['estado', 'fecha_fin_vigencia', 'observaciones', 'fecha_modificacion'])

        nuevo_bloque = BloqueHorario(
            consultorio=consultorio_destino,
            tipo_titular=bloque_origen.tipo_titular,
            profesional_interno=bloque_origen.profesional_interno,
            profesional_externo=bloque_origen.profesional_externo,
            profesional_asignado_temporal=bloque_origen.profesional_asignado_temporal,
            equipo=bloque_origen.equipo if asignacion_equipo_valida else None,
            dia_semana=fecha_destino.weekday(),
            hora_inicio=hora_inicio_destino,
            hora_fin=hora_fin_destino,
            fecha_inicio_vigencia=fecha_destino,
            fecha_fin_vigencia=None,
            tipo_actividad=bloque_origen.tipo_actividad,
            tipo_lista=bloque_origen.tipo_lista,
            permite_cobertura_residente=bloque_origen.permite_cobertura_residente,
            prioridad_cobertura=bloque_origen.prioridad_cobertura,
            competencia_requerida=bloque_origen.competencia_requerida,
            estado=EstadoBloque.ACTIVO,
            observaciones=(
                f"{(bloque_origen.observaciones or '').strip()}\n"
                f"[MIGRACION] Creado desde bloque #{bloque_origen.pk}."
            ).strip(),
            creado_por=usuario or bloque_origen.creado_por,
        )
        nuevo_bloque.full_clean()
        nuevo_bloque.save()

        if es_migracion_futura:
            nota_origen = (
                f"[MIGRACION] Vigencia recortada por migración futura al bloque #{nuevo_bloque.pk} "
                f"({consultorio_destino.nombre} {fecha_destino} {hora_inicio_destino}-{hora_fin_destino})."
            )
        else:
            nota_origen = (
                f"[MIGRACION] Finalizado por migración al bloque #{nuevo_bloque.pk} "
                f"({consultorio_destino.nombre} {fecha_destino} {hora_inicio_destino}-{hora_fin_destino})."
            )
        bloque_origen.observaciones = f"{(bloque_origen.observaciones or '').strip()}\n{nota_origen}".strip()
        bloque_origen.save(update_fields=['observaciones', 'fecha_modificacion'])

    return {
        'exito': True,
        'nuevo_bloque': nuevo_bloque,
        'bloque_origen': bloque_origen,
        'blandos_pausados': blandos_pausados,
        'blandos_diferidos': blandos_diferidos,
        'evaluacion': evaluacion,
    }


def reactivar_bloque_blando_migrado(bloque: BloqueHorario) -> dict:
    """Reabre un bloque blando pausado por migración."""
    if not _es_bloque_blando(bloque):
        raise ConsultoriosError('Solo se pueden reabrir bloques blandos de residentes.')

    if bloque.estado != EstadoBloque.PAUSADO:
        raise ConsultoriosError('El bloque seleccionado no está pausado.')

    bloque.estado = EstadoBloque.ACTIVO
    nota = '[MIGRACION] Reabierto manualmente desde la interfaz.'
    bloque.observaciones = f"{(bloque.observaciones or '').strip()}\n{nota}".strip()
    bloque.save(update_fields=['estado', 'observaciones', 'fecha_modificacion'])

    return {
        'exito': True,
        'bloque': bloque,
    }


def bloques_con_cobertura_posible(consultorio=None) -> list:
    """
    Retorna los bloques activos que permiten cobertura por residentes,
    opcionalmente filtrados por consultorio.

    Útil para el dashboard de ausencias y futura UI de coverage engine.
    """
    qs = BloqueHorario.objects.filter(
        estado=EstadoBloque.ACTIVO,
        permite_cobertura_residente=True,
    ).select_related('consultorio', 'profesional_interno', 'profesional_externo')

    if consultorio:
        qs = qs.filter(consultorio=consultorio)

    return list(qs)
