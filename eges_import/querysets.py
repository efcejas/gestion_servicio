"""Selección estadística sin modificar ni eliminar las filas originales."""
from django.db.models import Count, OuterRef, Q, Subquery, Value
from django.db.models.functions import Coalesce


def filas_eges_produccion(qs=None):
    from .models import EgesRow

    if qs is None:
        qs = EgesRow.objects.all()
    principales = EgesRow.objects.filter(
        Q(codigo_practica='900079') | Q(codigo_practica__startswith='900079/'),
        batch_id=OuterRef('batch_id'),
        historia_clinica=OuterRef('historia_clinica'),
        fecha_turno=OuterRef('fecha_turno'),
        hora_turno=OuterRef('hora_turno'),
        centro_atencion=OuterRef('centro_atencion'),
        es_insumo=False,
    ).exclude(estado_turno__iexact='Anulado').exclude(estado_turno__iexact='Cancelado')
    cantidad = principales.order_by().values('batch_id').annotate(n=Count('pk')).values('n')
    componentes = (
        Q(codigo_practica__in=['150101', '150111'])
        | Q(codigo_practica__startswith='150101/')
        | Q(codigo_practica__startswith='150111/')
    )
    identificados = (
        Q(historia_clinica__isnull=False) & ~Q(historia_clinica='')
        & Q(fecha_turno__isnull=False) & Q(hora_turno__isnull=False)
        & Q(centro_atencion__isnull=False) & ~Q(centro_atencion='')
    )
    return qs.filter(es_insumo=False).alias(
        _principales_ecoguiados=Coalesce(Subquery(cantidad), Value(0)),
    ).exclude(componentes & identificados & Q(_principales_ecoguiados=1))
