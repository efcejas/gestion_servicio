"""Guardado por excepción, separado de la aprobación definitiva."""
from django.core.exceptions import ValidationError
from django.db import transaction
from .models import RevisionProduccionParcial
from .services_repeticiones import completar_decisiones_repeticiones


def decisiones_guardadas(preparacion):
    resultado = {}
    for revision in RevisionProduccionParcial.objects.filter(
        firma_fuentes=preparacion['firma'],
    ).order_by('pk'):
        if revision.decision:
            resultado[revision.clave] = revision.decision
        else:
            resultado.pop(revision.clave, None)
    return resultado


def validar_decisiones_parciales(preparacion, decisiones):
    if not isinstance(decisiones, dict):
        raise ValidationError('Las decisiones no son válidas.')
    excepciones = {item['id']: item for item in preparacion['excepciones']}
    grupos = {item['id']: item for item in (
        preparacion.get('grupos_bilaterales', []) + preparacion.get('grupos_procedimientos', [])
        + preparacion.get('grupos_repeticiones', [])
    )}
    limpias = {}
    utilizadas = set()
    decisiones = completar_decisiones_repeticiones(preparacion.get('grupos_repeticiones', [])
        + [g for g in preparacion.get('grupos_bilaterales', []) if 'sugerencias' in g], set(excepciones), decisiones)
    for clave, decision in decisiones.items():
        if clave not in excepciones and clave not in grupos or not isinstance(decision, dict):
            raise ValidationError('La revisión no corresponde al análisis actual.')
        accion = decision.get('accion', '')
        if not accion:
            limpias[clave] = {}
            continue
        if clave in grupos:
            if accion not in {'UNICO', 'INDEPENDIENTES'}:
                raise ValidationError('Seleccioná una decisión válida para el grupo.')
            limpias[clave] = {'accion': accion}
            continue
        item = excepciones[clave]
        if accion == 'EXCLUIR':
            limpias[clave] = {'accion': accion}
            continue
        modalidad = decision.get('modalidad')
        if modalidad not in ('ECO', 'TC', 'RM', 'RX', 'MAM', 'DX', 'SERIE') or item['vigencia_incierta']:
            raise ValidationError('Revisá la modalidad y las versiones de la práctica.')
        if accion.startswith('VINCULAR:'):
            candidatas = [fila for fila in item['candidatas'] if fila['accion'] == accion]
            if len(candidatas) != 1 or candidatas[0]['modalidad'] != modalidad:
                raise ValidationError('La práctica EGES seleccionada no es válida.')
            if accion in utilizadas:
                raise ValidationError('Una práctica EGES no puede vincularse dos veces.')
            utilizadas.add(accion)
        elif accion != 'ADICIONAL':
            raise ValidationError('La decisión de la práctica no es válida.')
        limpias[clave] = {'accion': accion, 'modalidad': modalidad}
    return limpias


@transaction.atomic
def guardar_revision_parcial(*, preparacion, firma_esperada, decisiones, usuario, motivo):
    if not usuario.is_active or not usuario.is_superuser:
        raise ValidationError('El guardado requiere permiso de administración.')
    if firma_esperada != preparacion['firma']:
        raise ValidationError('Las fuentes cambiaron. Volvé a analizar antes de guardar.')
    motivo = str(motivo or '').strip()
    if not motivo or len(motivo) > 2000:
        raise ValidationError('Indicá un motivo de revisión de hasta 2000 caracteres.')
    limpias = validar_decisiones_parciales(preparacion, decisiones)
    anteriores = decisiones_guardadas(preparacion)
    cambios = 0
    for clave, decision in limpias.items():
        if anteriores.get(clave, {}) == decision:
            continue
        RevisionProduccionParcial.objects.create(
            firma_fuentes=preparacion['firma'], clave=clave, decision=decision,
            motivo=motivo, revisado_por=usuario,
        )
        cambios += 1
    return cambios
