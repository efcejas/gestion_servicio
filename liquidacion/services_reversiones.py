from datetime import timedelta
from decimal import Decimal
import re
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import (
    CorreccionPacsRegistro,
    HistorialRecalculoSolicitudRevisionHorario,
    HistorialRecalculoTarifaRegistro,
    RegistroEstudio,
    RegistroEstudiosPorMedico,
    RevisionAuditoriaEcoRegistro,
    RevisionCruceEgesRegistro,
    SesionContable,
    SolicitudRevisionHorarioRegistro,
)


PREFIJO_CORRECCION_DOPPLER = 'Correccion automatica de Doppler de residente segun cruce EGES.'


def _revision_eco_de_correccion(revision, origen):
    importes = re.match(
        r'^Correccion Doppler desde EGES aplicada\. Monto: \$([0-9]+(?:\.[0-9]+)?) -> \$([0-9]+(?:\.[0-9]+)?)\.',
        revision.observacion,
    )
    return bool(
        importes and Decimal(importes.group(1)) == origen.monto_anterior
        and Decimal(importes.group(2)) == origen.monto_nuevo
        and revision.estado == 'VALIDADO' and revision.revisado_por_id == origen.corregido_por_id
        and revision.fecha_revision <= origen.fecha_correccion + timedelta(seconds=5)
    )


@transaction.atomic
def revertir_correcciones_doppler_eges(*, correccion_ids, sesion_id,
                                     autor_correccion_id, usuario, motivo,
                                     aplicar=False, revisiones_eges_a_reabrir_ids=(),
                                     batch_eges_autorizado_id=None):
    """Restaura snapshots explicitos, sin recalcular ni borrar historial."""
    if not usuario.is_authenticated or not (usuario.is_superuser or usuario.rol == 'jefe_servicio'):
        raise ValidationError('Solo superusuario o jefatura puede revertir ajustes economicos.')
    if not motivo.strip() or len(motivo.strip()) > 1000:
        raise ValidationError('Indica un motivo de hasta 1000 caracteres.')
    ids = set(correccion_ids)
    if not ids or len(ids) != len(correccion_ids) or len(ids) > 200:
        raise ValidationError('Selecciona entre 1 y 200 correcciones distintas.')
    autorizadas = set(revisiones_eges_a_reabrir_ids)
    if autorizadas and not batch_eges_autorizado_id:
        raise ValidationError('Indica el batch de las revisiones posteriores autorizadas.')
    encontradas_autorizadas = set()
    sesiones = SesionContable.objects
    if aplicar:
        sesiones = sesiones.select_for_update()
    sesion = sesiones.get(pk=sesion_id)
    if sesion.estado not in {'ABIERTA', 'REVISION'}:
        raise ValidationError('La sesion debe estar ABIERTA o REVISION para revertir.')
    correcciones = CorreccionPacsRegistro.objects.filter(pk__in=ids).order_by('registro_id', 'pk')
    origenes = list(correcciones)
    if len(origenes) != len(ids) or len({origen.registro_id for origen in origenes}) != len(ids):
        raise ValidationError('Faltan correcciones o hay mas de una por registro; revisar la seleccion.')
    registros_qs = RegistroEstudiosPorMedico.objects.filter(
        pk__in=[origen.registro_id for origen in origenes],
    ).order_by('pk')
    if aplicar:
        registros_qs = registros_qs.select_for_update()
    registros = {registro.pk: registro for registro in registros_qs}
    if aplicar:
        origenes = list(correcciones.select_for_update())
        list(RegistroEstudio.objects.select_for_update().filter(
            registro_id__in=registros,
        ).order_by('registro_id', 'pk'))
    preparados = []
    conflictos = []
    for origen in origenes:
        registro = registros[origen.registro_id]
        errores = []
        marca = f'Reversion Doppler EGES #{origen.pk};'
        if (
            origen.sesion_contable_id != sesion.pk or registro.sesion_contable_id != sesion.pk
            or origen.corregido_por_id != autor_correccion_id
            or origen.tipo_correccion != CorreccionPacsRegistro.TIPO_HORARIO_RECALCULADO
            or not origen.observacion.startswith(PREFIJO_CORRECCION_DOPPLER)
        ):
            errores.append('No corresponde a la sesion, autor o accion esperados.')
        if registro.anulado or registro.medico.rol != 'medico_residente':
            errores.append('El registro esta anulado o el profesional ya no es residente.')
        if (
            registro.horario != origen.horario_nuevo
            or registro.monto_calculado != origen.monto_nuevo
            or not origen.horario_anterior
        ):
            errores.append('El horario o monto actual no coincide con la correccion.')
        if registro.fecha_modificacion and registro.fecha_modificacion > origen.fecha_correccion:
            errores.append('Existe una modificacion posterior registrada.')
        if CorreccionPacsRegistro.objects.filter(
            registro=registro, observacion__startswith=marca,
        ).exists():
            errores.append('La correccion ya fue revertida.')
        if CorreccionPacsRegistro.objects.filter(
            registro=registro, fecha_correccion__gt=origen.fecha_correccion,
        ).exists():
            errores.append('Existe otra correccion economica posterior.')
        if (
            HistorialRecalculoTarifaRegistro.objects.filter(
                registro=registro, fecha_recalculo__gt=origen.fecha_correccion,
            ).exists()
            or HistorialRecalculoSolicitudRevisionHorario.objects.filter(
                registro=registro, fecha_recalculo__gt=origen.fecha_correccion,
            ).exists()
            or SolicitudRevisionHorarioRegistro.objects.filter(
                registro=registro, fecha_aplicacion__gt=origen.fecha_correccion,
            ).exists()
        ):
            errores.append('Hay un recalculo o aplicacion horaria posterior.')
        if not registro.registroestudio_set.exists() or registro.registroestudio_set.exclude(estudio__tipo='DOP').exists():
            errores.append('El registro ya no contiene exclusivamente Doppler.')
        eco_posteriores = list(RevisionAuditoriaEcoRegistro.objects.filter(
            registro=registro, fecha_revision__gte=origen.fecha_correccion,
        ).order_by('fecha_revision', 'pk'))
        eco_generadas = [revision for revision in eco_posteriores if _revision_eco_de_correccion(revision, origen)]
        if len(eco_generadas) != 1 or len(eco_posteriores) != 1:
            errores.append('La validacion ECO generada no es unica o hubo decisiones posteriores.')
        eges_posteriores = list(RevisionCruceEgesRegistro.objects.filter(
            registro=registro, fecha_revision__gte=origen.fecha_correccion,
        ).order_by('fecha_revision', 'pk'))
        eges_generadas = [revision for revision in eges_posteriores if (
            revision.estado == 'VALIDADO' and revision.revisado_por_id == origen.corregido_por_id
            and revision.observacion == f'Correccion economica #{origen.pk} aplicada. Revision EGES cerrada automaticamente.'
            and revision.fecha_revision <= origen.fecha_correccion + timedelta(seconds=5)
        )]
        eges_autorizadas = [revision for revision in eges_posteriores if (
            revision.pk in autorizadas and revision.estado == 'VALIDADO'
            and revision.revisado_por_id == autor_correccion_id
            and revision.batch_eges_id == batch_eges_autorizado_id
            and revision.sesion_contable_id == sesion.pk
        )]
        encontradas_autorizadas.update(revision.pk for revision in eges_autorizadas)
        permitidas = {revision.pk for revision in eges_generadas + eges_autorizadas}
        if any(revision.pk not in permitidas for revision in eges_posteriores) or len(eges_generadas) > 1:
            errores.append('Hay decisiones EGES posteriores no vinculadas inequivocamente a esta correccion.')
        if errores:
            conflictos.append({'correccion_id': origen.pk, 'registro_id': registro.pk, 'motivos': errores})
        preparados.append((origen, registro, eco_generadas, {
            revision.pk: revision for revision in eges_generadas + eges_autorizadas
        }.values()))
    if encontradas_autorizadas != autorizadas:
        conflictos.append({
            'motivos': ['Las revisiones autorizadas no coinciden con la seleccion, estado, autor o batch.'],
            'revision_ids_no_coincidentes': sorted(autorizadas - encontradas_autorizadas),
        })
    actual = sum((origen.monto_nuevo for origen in origenes), Decimal('0.00'))
    anterior = sum((origen.monto_anterior for origen in origenes), Decimal('0.00'))
    resultado = {
        'aplicado': False, 'sesion_id': sesion.pk, 'estado_sesion': sesion.estado,
        'correccion_ids': sorted(ids), 'registros': len(origenes),
        'monto_aplicado_original': str(actual), 'monto_a_restaurar': str(anterior),
        'diferencia_restituida': str(anterior - actual), 'conflictos': conflictos,
        'revisiones_posteriores_autorizadas_ids': sorted(autorizadas),
    }
    if not aplicar:
        return resultado
    if conflictos:
        raise ValidationError(f'Reversion abortada sin cambios: {conflictos}')
    lote = str(uuid4())
    nuevos_ids = []
    revisiones_eges_ids = []
    revisiones_eco_ids = []
    for origen, registro, eco_generadas, eges_generadas in preparados:
        observacion = (
            f'Reversion Doppler EGES #{origen.pk}; lote={lote}. '
            f'Restauracion de snapshot, sin recalculo: horario {origen.horario_nuevo} -> {origen.horario_anterior}; '
            f'monto ${origen.monto_nuevo} -> ${origen.monto_anterior}. {motivo.strip()}'
        )
        revision_eco = RevisionAuditoriaEcoRegistro.objects.create(
            sesion_contable=sesion, registro=registro, estado='REQUIERE_CORRECCION',
            motivos_json=eco_generadas[0].motivos_json,
            observacion=f'{observacion} Evidencia pendiente de verificacion; reemplaza revision ECO #{eco_generadas[0].pk}.',
            revisado_por=usuario,
        )
        revisiones_eco_ids.append(revision_eco.pk)
        for revision in eges_generadas:
            nueva = RevisionCruceEgesRegistro.objects.create(
                sesion_contable=sesion, registro=registro, batch_eges_id=revision.batch_eges_id,
                estado='REQUIERE_CORRECCION', motivos_json=revision.motivos_json,
                snapshot_json=revision.snapshot_json,
                observacion=f'{observacion} Reemplaza revision EGES #{revision.pk}; pendiente de evidencia.',
                revisado_por=usuario,
            )
            revisiones_eges_ids.append(nueva.pk)
        RegistroEstudiosPorMedico.objects.filter(pk=registro.pk).update(
            horario=origen.horario_anterior, monto_calculado=origen.monto_anterior,
            modificado_por=usuario, fecha_modificacion=timezone.now(), motivo_modificacion=observacion,
        )
        inversa = CorreccionPacsRegistro.objects.create(
            sesion_contable=sesion, registro=registro, revision_auditoria_eco=revision_eco,
            tipo_correccion=CorreccionPacsRegistro.TIPO_MONTO_MANUAL,
            horario_anterior=origen.horario_nuevo, horario_nuevo=origen.horario_anterior,
            monto_anterior=origen.monto_nuevo, monto_nuevo=origen.monto_anterior,
            observacion=observacion, corregido_por=usuario,
        )
        nuevos_ids.append(inversa.pk)
    resultado.update({
        'aplicado': True, 'lote_reversion': lote, 'ajustes_compensatorios_ids': nuevos_ids,
        'revisiones_eco_pendientes_ids': revisiones_eco_ids,
        'revisiones_eges_pendientes_ids': revisiones_eges_ids,
    })
    return resultado