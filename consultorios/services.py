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
from django.db.models import Count, Q
from django.utils import timezone

from consultorios.models import (
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
