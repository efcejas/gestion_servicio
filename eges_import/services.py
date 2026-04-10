"""
services.py — Lógica de datos del módulo eges_import.

Separa las queries y transformaciones de datos del ciclo request/response.
Estas funciones no reciben ni retornan objetos HTTP: son reutilizables
desde vistas, management commands y tests sin levantar un servidor.
"""
from datetime import date as date_type, datetime, timedelta

from django.db.models import Count

from .models import DirectorToken, EgesRow


# ─────────────────────────────────────────────────────────────────────────────
# QuerySets base (sin filtros de fecha/modalidad)
# ─────────────────────────────────────────────────────────────────────────────

def get_base_estudios_finalizados():
    """QuerySet base: estudios finalizados (no insumos, estado Informado, con fecha)."""
    return EgesRow.objects.filter(
        es_insumo=False,
        estado_turno__iexact='Informado',
        fecha_turno__isnull=False,
    )


def get_base_rx_sin_informe():
    """QuerySet base: RX entregados sin informe (cerrados pero sin reporte médico)."""
    return EgesRow.objects.filter(
        es_insumo=False,
        modalidad='RX',
        estado_turno__iexact='Entregado Sin Informe',
        fecha_turno__isnull=False,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Filtros dinámicos
# ─────────────────────────────────────────────────────────────────────────────

def aplicar_filtros_fecha_modalidad(qs, request_params):
    """
    Aplica filtros de fecha y modalidad a un QuerySet.

    Parámetros:
        qs            : QuerySet de EgesRow (cualquier estado)
        request_params: QueryDict o dict-like con las claves:
                        fecha_desde (YYYY-MM-DD), fecha_hasta (YYYY-MM-DD),
                        modalidades o modalidades[] (lista de códigos)

    Retorna el QuerySet filtrado (puede ser vacío, nunca None).
    """
    fecha_desde = request_params.get('fecha_desde', '')
    fecha_hasta = request_params.get('fecha_hasta', '')
    # Acepta tanto ?modalidades[]=TC&modalidades[]=RM como ?modalidades=TC,RM
    mods = request_params.getlist('modalidades[]') or request_params.getlist('modalidades')

    if fecha_desde:
        try:
            qs = qs.filter(fecha_turno__gte=datetime.strptime(fecha_desde, '%Y-%m-%d').date())
        except ValueError:
            pass
    if fecha_hasta:
        try:
            qs = qs.filter(fecha_turno__lte=datetime.strptime(fecha_hasta, '%Y-%m-%d').date())
        except ValueError:
            pass
    if mods:
        qs = qs.filter(modalidad__in=mods)
    return qs


# ─────────────────────────────────────────────────────────────────────────────
# Cálculos de KPIs
# ─────────────────────────────────────────────────────────────────────────────

def calcular_kpis(estudios_finalizados_qs, estudios_candidatos_qs, sin_informe_qs=None):
    """
    Devuelve un dict con los KPIs principales.

    Parámetros:
        estudios_finalizados_qs : filtrado por estado Informado
        estudios_candidatos_qs  : todos los no-insumos (con fecha)
        sin_informe_qs          : RX entregados sin informe (estado cerrado pero sin reporte)

    Retorna:
        dict con claves: total_finalizados, total_candidatos, total_pendientes,
        promedio_dia, tasa_conversion, rx_sin_informe.
    """
    total_finalizados = estudios_finalizados_qs.count()
    total_candidatos = estudios_candidatos_qs.count()
    rx_sin_informe = sin_informe_qs.count() if sin_informe_qs is not None else 0
    # Los "Entregado Sin Informe" son estudios cerrados, no pendientes reales
    total_pendientes = max(total_candidatos - total_finalizados - rx_sin_informe, 0)

    # Rango de fechas efectivo
    fechas = estudios_finalizados_qs.values_list('fecha_turno', flat=True)
    if fechas:
        fecha_min = min(fechas)
        fecha_max = max(fechas)
        dias_periodo = max((fecha_max - fecha_min).days + 1, 1)
        # Dias hábiles aproximados (excluimos domingos)
        dias_habiles = sum(
            1 for i in range(dias_periodo)
            if (fecha_min + timedelta(days=i)).weekday() != 6
        )
        promedio_dia = round(total_finalizados / max(dias_habiles, 1), 1)
    else:
        promedio_dia = 0

    tasa_conversion = round((total_finalizados / total_candidatos * 100), 1) if total_candidatos else 0

    return {
        'total_finalizados': total_finalizados,
        'total_candidatos': total_candidatos,
        'total_pendientes': total_pendientes,
        'promedio_dia': promedio_dia,
        'tasa_conversion': tasa_conversion,
        'rx_sin_informe': rx_sin_informe,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Agrupación temporal
# ─────────────────────────────────────────────────────────────────────────────

def agrupar_periodo(d, agrupacion):
    """
    Dado un objeto date y agrupacion (dia|semana|mes), devuelve el inicio del periodo.
    Usado para el endpoint de análisis temporal con granularidad variable.
    """
    if agrupacion == 'dia':
        return d
    elif agrupacion == 'semana':
        return d - timedelta(days=d.weekday())  # lunes de esa semana
    else:
        return date_type(d.year, d.month, 1)


# ─────────────────────────────────────────────────────────────────────────────
# Control de acceso por token (Portal del Director)
# ─────────────────────────────────────────────────────────────────────────────

def verificar_token(token_str):
    """
    Verifica que el token sea válido y esté activo.

    Retorna el objeto DirectorToken si es válido, o None si no lo es.
    No lanza excepciones: los tokens inválidos o inexistentes retornan None.
    """
    try:
        import uuid as _uuid
        token_uuid = _uuid.UUID(str(token_str))
        token = DirectorToken.objects.get(token=token_uuid, activo=True)
        token.registrar_acceso()
        return token
    except (DirectorToken.DoesNotExist, ValueError):
        return None
