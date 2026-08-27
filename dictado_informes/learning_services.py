"""Registro y consolidacion segura del aprendizaje del modulo de dictado."""

from collections import Counter

from django.conf import settings
from django.db import transaction

from .models import EventoAprendizajeDictado, PreferenciaAprendidaDictado


MIN_CONFIRMACIONES_PLANTILLA = max(
    1,
    int(getattr(settings, 'DICTADO_MEMORIA_CONFIRMACIONES_MINIMAS', 3)),
)
MIN_CONFIANZA_PLANTILLA = min(
    1.0,
    max(0.0, float(getattr(settings, 'DICTADO_MEMORIA_CONFIANZA_MINIMA', 0.75))),
)


def _normalizar_contexto(valor):
    return str(valor or '').strip().upper()


def clave_seleccion_plantilla(region='', modalidad='', lateralidad=''):
    """Construye una clave sin texto clinico para agrupar decisiones equivalentes."""
    partes = (
        _normalizar_contexto(region) or 'SIN_REGION',
        _normalizar_contexto(modalidad) or 'SIN_MODALIDAD',
        _normalizar_contexto(lateralidad) or 'SIN_LATERALIDAD',
    )
    return '|'.join(partes)


def obtener_preferencia_activa_seleccion(*, usuario, region='', modalidad='', lateralidad=''):
    """Devuelve una memoria fuerte exacta; nunca aproxima entre regiones o lados."""
    if not region:
        return None
    clave = clave_seleccion_plantilla(region, modalidad, lateralidad)
    return PreferenciaAprendidaDictado.objects.filter(
        usuario=usuario,
        categoria=PreferenciaAprendidaDictado.Categoria.SELECCION_PLANTILLA,
        clave=clave,
        estado=PreferenciaAprendidaDictado.Estado.ACTIVA,
        vigente=True,
    ).first()


@transaction.atomic
def registrar_evento_aprendizaje(*, usuario, tipo_evento, **campos):
    """Registra evidencia no clinica y consolida lo que ya es repetible."""
    evento = EventoAprendizajeDictado.objects.create(
        usuario=usuario,
        tipo_evento=tipo_evento,
        **campos,
    )
    if tipo_evento == EventoAprendizajeDictado.TipoEvento.PLANTILLA_CONFIRMADA:
        consolidar_preferencia_seleccion(evento)
    return evento


@transaction.atomic
def consolidar_preferencia_seleccion(evento):
    """Versiona la plantilla preferida cuando tres decisiones sostienen el patron."""
    if not evento.region or not evento.plantilla_confirmada_codigo:
        return None

    clave = clave_seleccion_plantilla(
        evento.region,
        evento.modalidad,
        evento.lateralidad,
    )
    eventos = EventoAprendizajeDictado.objects.filter(
        usuario=evento.usuario,
        tipo_evento=EventoAprendizajeDictado.TipoEvento.PLANTILLA_CONFIRMADA,
        region=evento.region,
        modalidad=evento.modalidad,
        lateralidad=evento.lateralidad,
        revertido=False,
    ).exclude(plantilla_confirmada_codigo='')
    conteos = Counter(eventos.values_list('plantilla_confirmada_codigo', flat=True))
    if not conteos:
        return None

    codigo_ganador, confirmaciones = conteos.most_common(1)[0]
    total = sum(conteos.values())
    confianza = round(confirmaciones / total, 4)
    estado = (
        PreferenciaAprendidaDictado.Estado.ACTIVA
        if confirmaciones >= MIN_CONFIRMACIONES_PLANTILLA and confianza >= MIN_CONFIANZA_PLANTILLA
        else PreferenciaAprendidaDictado.Estado.CANDIDATA
    )
    actual = PreferenciaAprendidaDictado.objects.select_for_update().filter(
        usuario=evento.usuario,
        categoria=PreferenciaAprendidaDictado.Categoria.SELECCION_PLANTILLA,
        clave=clave,
        vigente=True,
    ).first()
    valor = {'codigo_plantilla': codigo_ganador}

    if actual and actual.valor.get('codigo_plantilla') == codigo_ganador:
        # Una pausa explicita del usuario prevalece sobre nueva evidencia automatica.
        if actual.estado != PreferenciaAprendidaDictado.Estado.INACTIVA:
            actual.estado = estado
        actual.cantidad_evidencia = total
        actual.confirmaciones = confirmaciones
        actual.rechazos = total - confirmaciones
        actual.confianza = confianza
        actual.save(update_fields=[
            'estado', 'cantidad_evidencia', 'confirmaciones', 'rechazos',
            'confianza', 'fecha_modificacion',
        ])
        return actual

    version = 1
    if actual:
        version = actual.version + 1
        actual.vigente = False
        actual.estado = PreferenciaAprendidaDictado.Estado.REEMPLAZADA
        actual.save(update_fields=['vigente', 'estado', 'fecha_modificacion'])

    return PreferenciaAprendidaDictado.objects.create(
        usuario=evento.usuario,
        categoria=PreferenciaAprendidaDictado.Categoria.SELECCION_PLANTILLA,
        clave=clave,
        valor=valor,
        version=version,
        estado=estado,
        vigente=True,
        cantidad_evidencia=total,
        confirmaciones=confirmaciones,
        rechazos=total - confirmaciones,
        confianza=confianza,
        reemplaza_a=actual,
    )
