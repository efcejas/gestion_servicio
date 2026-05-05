"""
Signals de la app consultorios.

Genera automáticamente TareaAgendaEGES cuando ocurren eventos relevantes:
  - BloqueHorario creado (ACTIVO)       → HABILITAR
  - BloqueHorario desactivado/pausado   → DESHABILITAR
  - BloqueHorario modificado (profesional o franja) → REASIGNAR / HABILITAR
  - AusenciaCobertura sin cobertura confirmada → DESHABILITAR (para la fecha puntual)
  - AusenciaCobertura con cobertura confirmada → REASIGNAR
  - Cobertura cancelada (CANCELADA tras CONFIRMADA) → DESHABILITAR
"""

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import (
    AccionEGES,
    AusenciaCobertura,
    BloqueHorario,
    EstadoAusenciaCobertura,
    EstadoBloque,
    OrigenTareaEGES,
    TareaAgendaEGES,
)


def _crear_tarea(accion, origen, bloque, fecha_afectada=None, fecha_desde=None,
                 fecha_hasta=None, notas='', profesional_interno=None, profesional_externo=None):
    """Helper interno: crea una TareaAgendaEGES sin duplicados por (accion, origen, consultorio, fecha)."""
    TareaAgendaEGES.objects.create(
        accion=accion,
        origen=origen,
        consultorio=bloque.consultorio,
        profesional_interno=profesional_interno if profesional_interno is not None else bloque.profesional_interno,
        profesional_externo=profesional_externo if profesional_externo is not None else bloque.profesional_externo,
        fecha_afectada=fecha_afectada,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        hora_inicio=bloque.hora_inicio,
        hora_fin=bloque.hora_fin,
        notas=notas,
    )


# ---------------------------------------------------------------------------
# BloqueHorario
# ---------------------------------------------------------------------------

# Estado previo del bloque (capturado en pre_save para comparar en post_save)
_bloque_estado_previo = {}


@receiver(pre_save, sender=BloqueHorario)
def capturar_estado_previo_bloque(sender, instance, **kwargs):
    """Guarda el estado anterior del bloque antes de guardar para comparación."""
    if instance.pk:
        try:
            previo = BloqueHorario.objects.get(pk=instance.pk)
            _bloque_estado_previo[instance.pk] = {
                'estado': previo.estado,
                'profesional_interno_id': previo.profesional_interno_id,
                'profesional_externo_id': previo.profesional_externo_id,
                'hora_inicio': previo.hora_inicio,
                'hora_fin': previo.hora_fin,
            }
        except BloqueHorario.DoesNotExist:
            pass


@receiver(post_save, sender=BloqueHorario)
def bloque_horario_post_save(sender, instance, created, **kwargs):
    """Genera TareaAgendaEGES según el tipo de cambio en el bloque."""

    if created:
        # Bloque nuevo activo → habilitar agenda en EGES
        if instance.estado == EstadoBloque.ACTIVO:
            _crear_tarea(
                accion=AccionEGES.HABILITAR,
                origen=OrigenTareaEGES.BLOQUE_NUEVO,
                bloque=instance,
                notas=(
                    f'Nuevo bloque creado: {instance.get_dia_semana_display()} '
                    f'{instance.hora_inicio.strftime("%H:%M")}-{instance.hora_fin.strftime("%H:%M")}. '
                    f'Habilitar agenda para {instance.nombre_profesional()}.'
                ),
            )
        return

    previo = _bloque_estado_previo.pop(instance.pk, None)
    if previo is None:
        return

    estado_anterior = previo['estado']
    estado_nuevo = instance.estado

    # Bloque desactivado o pausado desde ACTIVO
    if estado_anterior == EstadoBloque.ACTIVO and estado_nuevo in (EstadoBloque.PAUSADO, EstadoBloque.FINALIZADO):
        _crear_tarea(
            accion=AccionEGES.DESHABILITAR,
            origen=OrigenTareaEGES.BLOQUE_DESACTIVADO,
            bloque=instance,
            notas=(
                f'Bloque {instance.get_estado_display().lower()}: {instance.get_dia_semana_display()} '
                f'{instance.hora_inicio.strftime("%H:%M")}-{instance.hora_fin.strftime("%H:%M")}. '
                f'Deshabilitar agenda de {instance.nombre_profesional()} en EGES.'
            ),
        )
        return

    # Bloque reactivado desde PAUSADO/FINALIZADO
    if estado_anterior != EstadoBloque.ACTIVO and estado_nuevo == EstadoBloque.ACTIVO:
        _crear_tarea(
            accion=AccionEGES.HABILITAR,
            origen=OrigenTareaEGES.BLOQUE_MODIFICADO,
            bloque=instance,
            notas=(
                f'Bloque reactivado: {instance.get_dia_semana_display()} '
                f'{instance.hora_inicio.strftime("%H:%M")}-{instance.hora_fin.strftime("%H:%M")}. '
                f'Habilitar agenda de {instance.nombre_profesional()} en EGES.'
            ),
        )
        return

    # Bloque activo con cambio de profesional
    if estado_nuevo == EstadoBloque.ACTIVO:
        profesional_cambio = (
            previo['profesional_interno_id'] != instance.profesional_interno_id
            or previo['profesional_externo_id'] != instance.profesional_externo_id
        )
        horario_cambio = (
            previo['hora_inicio'] != instance.hora_inicio
            or previo['hora_fin'] != instance.hora_fin
        )

        if profesional_cambio or horario_cambio:
            _crear_tarea(
                accion=AccionEGES.REASIGNAR,
                origen=OrigenTareaEGES.BLOQUE_MODIFICADO,
                bloque=instance,
                notas=(
                    f'Bloque modificado: {instance.get_dia_semana_display()} '
                    f'{instance.hora_inicio.strftime("%H:%M")}-{instance.hora_fin.strftime("%H:%M")}. '
                    f'Actualizar agenda en EGES para {instance.nombre_profesional()}.'
                ),
            )


# ---------------------------------------------------------------------------
# AusenciaCobertura
# ---------------------------------------------------------------------------

_ausencia_estado_previo = {}


@receiver(pre_save, sender=AusenciaCobertura)
def capturar_estado_previo_ausencia(sender, instance, **kwargs):
    if instance.pk:
        try:
            previo = AusenciaCobertura.objects.get(pk=instance.pk)
            _ausencia_estado_previo[instance.pk] = {
                'estado': previo.estado,
                'residente_asignado_id': previo.residente_asignado_id,
            }
        except AusenciaCobertura.DoesNotExist:
            pass


@receiver(post_save, sender=AusenciaCobertura)
def ausencia_post_save(sender, instance, created, **kwargs):
    """
    Genera tareas EGES según la transición de estado de la ausencia.

    REPORTADA (sin cobertura)  → DESHABILITAR para la fecha afectada
    CONFIRMADA (con cobertura) → REASIGNAR al residente que cubre
    CANCELADA (desde CONFIRMADA) → DESHABILITAR (vuelve a quedar sin profesional)
    """
    bloque = instance.bloque

    if created:
        # Ausencia recién reportada sin cobertura aún
        _crear_tarea(
            accion=AccionEGES.DESHABILITAR,
            origen=OrigenTareaEGES.AUSENCIA_SIN_COBERTURA,
            bloque=bloque,
            fecha_afectada=instance.fecha_ausencia,
            fecha_desde=instance.fecha_ausencia if instance.fecha_fin_ausencia else None,
            fecha_hasta=instance.fecha_fin_ausencia,
            notas=(
                f'Ausencia reportada: {instance.nombre_profesional_ausente()} — '
                f'{instance.fecha_ausencia}. '
                f'Deshabilitar agenda en EGES hasta confirmar cobertura.'
            ),
            profesional_interno=instance.profesional_ausente_interno,
            profesional_externo=instance.profesional_ausente_externo,
        )
        return

    previo = _ausencia_estado_previo.pop(instance.pk, None)
    if previo is None:
        return

    estado_anterior = previo['estado']
    estado_nuevo = instance.estado

    # Cobertura confirmada
    if (
        estado_anterior != EstadoAusenciaCobertura.CONFIRMADA
        and estado_nuevo == EstadoAusenciaCobertura.CONFIRMADA
        and instance.residente_asignado
    ):
        _crear_tarea(
            accion=AccionEGES.REASIGNAR,
            origen=OrigenTareaEGES.AUSENCIA_CON_COBERTURA,
            bloque=bloque,
            fecha_afectada=instance.fecha_ausencia,
            notas=(
                f'Cobertura confirmada: {instance.residente_asignado.get_full_name()} cubre '
                f'a {instance.nombre_profesional_ausente()} el {instance.fecha_ausencia}. '
                f'Reasignar agenda en EGES al residente cubridor.'
            ),
            profesional_interno=instance.residente_asignado,
            profesional_externo=None,
        )

    # Cobertura cancelada
    elif (
        estado_anterior == EstadoAusenciaCobertura.CONFIRMADA
        and estado_nuevo == EstadoAusenciaCobertura.CANCELADA
    ):
        _crear_tarea(
            accion=AccionEGES.DESHABILITAR,
            origen=OrigenTareaEGES.COBERTURA_CANCELADA,
            bloque=bloque,
            fecha_afectada=instance.fecha_ausencia,
            notas=(
                f'Cobertura cancelada para {instance.fecha_ausencia}. '
                f'Deshabilitar agenda en EGES (sin cobertura activa).'
            ),
            profesional_interno=instance.profesional_ausente_interno,
            profesional_externo=instance.profesional_ausente_externo,
        )
