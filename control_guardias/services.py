"""
services.py — Lógica de negocio del módulo control_guardias.

Separamos aquí todo lo que no pertenece a models ni a views:
  - Algoritmo de distribución automática equitativa
  - Publicación / cancelación de borradores
"""
import calendar
import random
from collections import defaultdict
from datetime import date, timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.urls import reverse
from django.utils import timezone

from .models import (
    AjusteCuotaGuardia,
    AsignacionGuardia,
    AusenciaResidente,
    ConfiguracionTipoGuardia,
    CuotaMensualGuardia,
    Feriado,
    RotacionExterna,
    SolicitudSlotVacante,
)

# Mapeo de código de día a weekday() de Python (0=Lunes, 6=Domingo)
DIA_SEMANA_MAP = {'L': 0, 'M': 1, 'X': 2, 'J': 3, 'V': 4, 'S': 5, 'D': 6}


class DistribucionError(Exception):
    """Error controlado del módulo de distribución de guardias."""
    pass


def generar_distribucion(mes, anio, tipos_guardia, creado_por, reemplazar_borradores=False, restricciones_anio=False):
    """
    Genera asignaciones en estado BORRADOR para el periodo mes/año indicado.

    Algoritmo equitativo:
      - Respeta la cuota mensual de cada residente según su año de residencia.
      - Ningún residente tiene guardias en dos días consecutivos.
      - Para feriados: prioriza a residentes con menos feriados históricos cumplidos.
      - Dentro de igual prioridad, elige al azar para evitar sesgo de orden.

    Parámetros:
        mes (int): 1-12
        anio (int): año de 4 dígitos
        tipos_guardia (QuerySet[ConfiguracionTipoGuardia]): tipos a distribuir
        creado_por (CustomUser): jefe/instructor que ejecuta la distribución
        reemplazar_borradores (bool): si True, elimina los BORRADOR existentes antes de generar

    Retorna:
        dict con claves:
          - asignaciones_creadas (int)
          - slots_sin_cubrir (list[dict]): [{'fecha': date, 'tipo': str}, ...]
          - metricas (dict): {nombre_residente: cantidad_guardias_generadas}
          - advertencias (list[str])

    Lanza:
        DistribucionError si hay condiciones que impiden la ejecución.
    """
    from django.contrib.auth import get_user_model
    User = get_user_model()

    # ------------------------------------------------------------------
    # 1. Validaciones previas
    # ------------------------------------------------------------------
    if not 1 <= mes <= 12:
        raise DistribucionError(f"Mes inválido: {mes}")

    tipos_lista = list(tipos_guardia.filter(activo=True))
    if not tipos_lista:
        raise DistribucionError("No hay tipos de guardia activos seleccionados.")

    residentes = list(
        User.objects.filter(
            rol='medico_residente',
            estado_residencia='ACTIVO',
            perfil_completo=True,
            is_active=True,
        ).order_by('last_name', 'first_name')
    )
    if not residentes:
        raise DistribucionError("No hay residentes activos con perfil completo para asignar.")

    primer_dia = date(anio, mes, 1)
    ultimo_dia = date(anio, mes, calendar.monthrange(anio, mes)[1])
    hoy = timezone.localdate()

    if ultimo_dia < hoy:
        raise DistribucionError(
            f"No se puede generar un borrador para {_nombre_mes(mes)} {anio} porque el mes ya finalizó."
        )

    guardias_publicadas_o_historicas = AsignacionGuardia.objects.filter(
        fecha__gte=primer_dia,
        fecha__lte=ultimo_dia,
    ).exclude(estado='BORRADOR')
    if guardias_publicadas_o_historicas.exists():
        raise DistribucionError(
            f"No se puede generar un borrador para {_nombre_mes(mes)} {anio} porque ese mes ya fue publicado."
        )

    # Verificar borradores existentes
    borradores_existentes = AsignacionGuardia.objects.filter(
        fecha__gte=primer_dia,
        fecha__lte=ultimo_dia,
        estado='BORRADOR',
    )
    if borradores_existentes.exists() and not reemplazar_borradores:
        raise DistribucionError(
            f"Ya existen asignaciones en BORRADOR para {_nombre_mes(mes)} {anio}. "
            "Cancelá el borrador actual antes de generar uno nuevo, o usá la opción "
            "'Reemplazar borrador existente'."
        )

    advertencias = []

    # ------------------------------------------------------------------
    # 2. Cuotas por año de residencia
    # ------------------------------------------------------------------
    cuotas = {c.anio_residencia: c.guardias_efectivas for c in CuotaMensualGuardia.objects.all()}

    # Avisar si algún año de residencia no tiene cuota configurada
    anios_presentes = {r.anio_residencia for r in residentes if r.anio_residencia}
    for anio_res in anios_presentes:
        if anio_res not in cuotas:
            advertencias.append(
                f"No hay cuota configurada para {anio_res}. Esos residentes recibirán 0 guardias."
            )

    cuota_disponible = {
        r.pk: cuotas.get(r.anio_residencia, 0)
        for r in residentes
    }

    # Aplicar ajustes de cuota del mes (CARRYOVER y PENALIZACION)
    ajustes = AjusteCuotaGuardia.objects.filter(mes=mes, anio=anio).select_related('residente')
    ajustes_por_residente = defaultdict(int)
    for ajuste in ajustes:
        ajustes_por_residente[ajuste.residente_id] += ajuste.cantidad
    for r in residentes:
        extra = ajustes_por_residente.get(r.pk, 0)
        if extra:
            cuota_disponible[r.pk] += extra
            tipo_ajuste = 'Traslado' if extra > 0 else 'ajuste'
            advertencias.append(
                f"{r.get_full_name()}: cuota aumentada +{extra} por {tipo_ajuste} ({_nombre_mes(mes)} {anio})."
            )

    # ------------------------------------------------------------------
    # 3. Feriados del período
    # ------------------------------------------------------------------
    feriados_set = set(
        Feriado.objects.filter(fecha__gte=primer_dia, fecha__lte=ultimo_dia)
        .values_list('fecha', flat=True)
    )

    # ------------------------------------------------------------------
    # 4. Construir slots (fecha, tipo_guardia, es_feriado)
    # ------------------------------------------------------------------
    slots = []
    current = primer_dia
    while current <= ultimo_dia:
        weekday = current.weekday()
        es_feriado = current in feriados_set

        for tipo in tipos_lista:
            dias_aplicables = {
                DIA_SEMANA_MAP[d] for d in tipo.dias_semana.split(',')
                if d in DIA_SEMANA_MAP
            }
            if es_feriado and tipo.aplica_feriados:
                slots.append((current, tipo, True))
            elif not es_feriado and weekday in dias_aplicables:
                slots.append((current, tipo, False))

        current += timedelta(days=1)

    if not slots:
        raise DistribucionError(
            "No hay slots a cubrir: ningún tipo de guardia aplica a las fechas del período."
        )

    # Reordenar slots por "ronda de cobertura" con fechas aleatorizadas dentro de cada ronda:
    # Ronda 1 → 1er slot de cada fecha (garantiza que todos los días queden cubiertos primero)
    # Ronda 2 → 2do slot de la misma fecha (doble cobertura solo si queda cuota)
    # Las fechas se mezclan dentro de cada ronda para que el día "inicial" sea aleatorio
    # en cada corrida y evitar concentrar residentes en las primeras semanas.
    date_occurrence: dict = {}
    slots_por_ronda: dict = {}
    for fecha, tipo, es_feriado in slots:
        date_occurrence[fecha] = date_occurrence.get(fecha, 0) + 1
        ronda = date_occurrence[fecha]
        slots_por_ronda.setdefault(ronda, []).append((fecha, tipo, es_feriado))

    slots = []
    for ronda in sorted(slots_por_ronda):
        # Intercalar semanas evita consumir toda la cuota mensual en un bloque
        # del mes antes de haber considerado fechas de las demás semanas.
        slots.extend(_intercalar_slots_por_semana(slots_por_ronda[ronda]))

    # ------------------------------------------------------------------
    # 5. Contadores históricos de feriados (para trato equitativo)
    # ------------------------------------------------------------------
    feriados_historicos = defaultdict(int)
    for r in residentes:
        feriados_historicos[r.pk] = AsignacionGuardia.objects.filter(
            residente=r,
            es_feriado=True,
            estado__in=['PUBLICADA', 'CUMPLIDA'],
        ).count()

    # ------------------------------------------------------------------
    # 6. Eliminar borradores previos si se solicitó
    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # 7. Algoritmo de asignación greedy equitativo
    # ------------------------------------------------------------------
    # Mezclar la lista de residentes al inicio para romper cualquier sesgo
    # de orden (alfabético, fecha de ingreso, etc.) en los grupos de empate.
    random.shuffle(residentes)

    guardias_en_borrador = defaultdict(int)   # residente_pk → guardias generadas en esta corrida
    guardias_por_semana = defaultdict(int)    # (residente_pk, año_iso, semana_iso) → cantidad
    anio_por_fecha = defaultdict(set)         # fecha → set de anio_residencia ya asignados ese día

    # Pre-cargar fechas ya asignadas en BD para el período (publicadas o borradores restantes)
    # Evita IntegrityError por violación del unique_together (residente, fecha, tipo_guardia)
    fechas_asignadas = defaultdict(set)   # residente_pk → set(fecha, tipo_guardia_id)
    fechas_ocupadas = defaultdict(set)    # residente_pk → set(fecha) — un residente no puede tener 2 guardias el mismo día
    asignaciones_existentes = AsignacionGuardia.objects.filter(
        fecha__gte=primer_dia,
        fecha__lte=ultimo_dia,
    )
    if reemplazar_borradores:
        # El borrador anterior se reemplaza por completo y no debe condicionar
        # el cálculo del nuevo. Se elimina recién al persistir, dentro del mismo
        # bloque atómico que crea las asignaciones nuevas.
        asignaciones_existentes = asignaciones_existentes.exclude(estado='BORRADOR')

    for asig in asignaciones_existentes.select_related('residente').values(
        'residente_id', 'fecha', 'tipo_guardia_id', 'residente__anio_residencia'
    ):
        fechas_asignadas[asig['residente_id']].add((asig['fecha'], asig['tipo_guardia_id']))
        fechas_ocupadas[asig['residente_id']].add(asig['fecha'])
        guardias_por_semana[
            (asig['residente_id'], *_clave_semana(asig['fecha']))
        ] += 1
        anio_por_fecha[asig['fecha']].add(asig['residente__anio_residencia'])

    # Pre-cargar fechas bloqueadas por ausencias reportadas dentro del período.
    # Se trata como restricción dura: si un residente está ausente en una fecha,
    # no puede ser candidato para ese slot.
    fechas_ausentes = defaultdict(set)  # residente_pk -> set(fecha)
    residentes_ids = [r.pk for r in residentes]
    ausencias_periodo = AusenciaResidente.objects.filter(
        residente_id__in=residentes_ids,
        fecha_fin__gte=primer_dia,
        fecha_inicio__lte=ultimo_dia,
    ).values('residente_id', 'fecha_inicio', 'fecha_fin')

    for ausencia in ausencias_periodo:
        fecha_inicio = max(ausencia['fecha_inicio'], primer_dia)
        fecha_fin = min(ausencia['fecha_fin'], ultimo_dia)
        fecha_actual = fecha_inicio
        while fecha_actual <= fecha_fin:
            fechas_ausentes[ausencia['residente_id']].add(fecha_actual)
            fecha_actual += timedelta(days=1)

    # Residentes en rotación externa activa durante el período (preferencia jueves)
    residentes_en_rotacion = set(
        RotacionExterna.objects.filter(
            activo=True,
            fecha_inicio__lte=ultimo_dia,
            fecha_fin__gte=primer_dia,
        ).values_list('residente_id', flat=True)
    )

    asignaciones_a_crear = []
    slots_sin_cubrir = []
    slots_fallback_anio = 0   # contador de slots cubiertos fuera de restricción de año

    for fecha, tipo, es_feriado_slot in slots:
        weekday = fecha.weekday()  # 0=Lunes … 6=Domingo
        clave_semana = _clave_semana(fecha)
        # Candidatos elegibles: cuota disponible, sin guardia ese día (ningún tipo), sin día consecutivo
        dia_anterior = fecha - timedelta(days=1)
        dia_siguiente = fecha + timedelta(days=1)
        candidatos = [
            r for r in residentes
            if cuota_disponible[r.pk] > 0
            and fecha not in fechas_ocupadas[r.pk]
            and dia_anterior not in fechas_ocupadas[r.pk]
            and dia_siguiente not in fechas_ocupadas[r.pk]
            and fecha not in fechas_ausentes[r.pk]
        ]

        if not candidatos:
            slots_sin_cubrir.append({'fecha': fecha, 'tipo': tipo.nombre})
            continue

        # Restricciones por año (opcional): R1→V/D/Feriados, R2→S, R3/R4→L-J
        if restricciones_anio:
            candidatos_restringidos = [
                r for r in candidatos
                if _anio_puede_cubrir_slot(r.anio_residencia, weekday, es_feriado_slot)
            ]
            if candidatos_restringidos:
                candidatos = candidatos_restringidos
            else:
                slots_fallback_anio += 1  # fallback suave: usa el pool general

        # Diversidad de año:
        # - Con restricciones_anio=True: hard constraint (no dos del mismo año el mismo día).
        #   Si todos los candidatos son del año ya asignado, el slot queda sin cubrir.
        # - Sin restricciones_anio: preferencia suave (prefiere otro año si hay, si no usa todos).
        anios_en_fecha = anio_por_fecha[fecha]
        if anios_en_fecha:
            candidatos_otros_anios = [
                r for r in candidatos
                if r.anio_residencia not in anios_en_fecha
            ]
            if candidatos_otros_anios:
                candidatos = candidatos_otros_anios
            elif restricciones_anio:
                # Hard constraint: no se asigna un segundo residente del mismo año
                slots_sin_cubrir.append({'fecha': fecha, 'tipo': tipo.nombre})
                continue
            # else: fallback suave sin restricciones → usa candidatos original

        # Ordenar candidatos según equidad
        if es_feriado_slot:
            # Para feriados: primero menos guardias este mes, luego menos feriados históricos
            prioridad = lambda r: (
                guardias_por_semana[(r.pk, *clave_semana)],
                guardias_en_borrador[r.pk],
                feriados_historicos[r.pk],
                _score_cercania(r.pk, fecha, fechas_ocupadas),
            )
        elif weekday == 3 and residentes_en_rotacion:
            # Jueves con rotantes: dar prioridad a residentes en rotación externa
            # (tienen disponibilidad reducida entre semana, el jueves les conviene más)
            prioridad = lambda r: (
                0 if r.pk in residentes_en_rotacion else 1,
                guardias_por_semana[(r.pk, *clave_semana)],
                guardias_en_borrador[r.pk],
                _score_cercania(r.pk, fecha, fechas_ocupadas),
            )
        else:
            # Para días normales: primero menos guardias, luego penalización por cercanía de 2 días
            prioridad = lambda r: (
                guardias_por_semana[(r.pk, *clave_semana)],
                guardias_en_borrador[r.pk],
                _score_cercania(r.pk, fecha, fechas_ocupadas),
            )

        # El azar solo desempata candidatos con la misma prioridad completa.
        elegido = _elegir_candidato_priorizado(candidatos, prioridad)

        asignaciones_a_crear.append(AsignacionGuardia(
            residente=elegido,
            tipo_guardia=tipo,
            fecha=fecha,
            estado='BORRADOR',
            es_feriado=es_feriado_slot,
            creada_por=creado_por,
        ))

        # Actualizar contadores
        guardias_en_borrador[elegido.pk] += 1
        guardias_por_semana[(elegido.pk, *clave_semana)] += 1
        cuota_disponible[elegido.pk] -= 1
        fechas_asignadas[elegido.pk].add((fecha, tipo.pk))  # reservado para posible uso futuro
        fechas_ocupadas[elegido.pk].add(fecha)
        anio_por_fecha[fecha].add(elegido.anio_residencia)
        if es_feriado_slot:
            feriados_historicos[elegido.pk] += 1  # actualizar para próximos feriados en la misma corrida

    # ------------------------------------------------------------------
    # 8. Persistir en una sola transacción
    # ------------------------------------------------------------------
    with transaction.atomic():
        if reemplazar_borradores:
            AsignacionGuardia.objects.filter(
                fecha__gte=primer_dia,
                fecha__lte=ultimo_dia,
                estado='BORRADOR',
            ).delete()
        AsignacionGuardia.objects.bulk_create(asignaciones_a_crear)

    if slots_fallback_anio:
        advertencias.append(
            f"{slots_fallback_anio} slot(s) cubierto(s) por residentes fuera de las restricciones "
            "de año por falta de candidatos disponibles."
        )

    # ------------------------------------------------------------------
    # 9. Construir métricas de equidad
    # ------------------------------------------------------------------
    metricas = {
        r.get_full_name() or r.username: guardias_en_borrador[r.pk]
        for r in residentes
    }

    if slots_sin_cubrir:
        advertencias.append(
            f"{len(slots_sin_cubrir)} slot(s) quedaron sin cubrir por insuficiencia de cuota."
        )

    return {
        'asignaciones_creadas': len(asignaciones_a_crear),
        'slots_sin_cubrir': slots_sin_cubrir,
        'metricas': metricas,
        'advertencias': advertencias,
    }


def publicar_borrador(mes, anio):
    """
    Cambia estado BORRADOR → PUBLICADA para todas las asignaciones del mes/año.

    Retorna:
        int: cantidad de asignaciones publicadas
    """
    primer_dia = date(anio, mes, 1)
    ultimo_dia = date(anio, mes, calendar.monthrange(anio, mes)[1])

    borradores = list(
        AsignacionGuardia.objects.filter(
            fecha__gte=primer_dia,
            fecha__lte=ultimo_dia,
            estado='BORRADOR',
        ).select_related('residente')
    )
    count = AsignacionGuardia.objects.filter(
        fecha__gte=primer_dia,
        fecha__lte=ultimo_dia,
        estado='BORRADOR',
    ).update(estado='PUBLICADA')

    if count:
        por_residente = defaultdict(list)
        for guardia in borradores:
            por_residente[guardia.residente].append(guardia.fecha)

        for residente, fechas in por_residente.items():
            fechas_ordenadas = sorted(set(fechas))
            desde = fechas_ordenadas[0].strftime('%d/%m/%Y')
            hasta = fechas_ordenadas[-1].strftime('%d/%m/%Y')
            total = len(fechas)
            crear_notificacion(
                residente,
                'PUBLICACION',
                f"Se publicaron tus guardias de {_nombre_mes(mes)} {anio}. "
                f"Total: {total}. Rango: {desde} a {hasta}.",
            )

    return count


def cancelar_borrador(mes, anio):
    """
    Elimina todas las asignaciones en estado BORRADOR del mes/año.

    Retorna:
        int: cantidad de asignaciones eliminadas
    """
    primer_dia = date(anio, mes, 1)
    ultimo_dia = date(anio, mes, calendar.monthrange(anio, mes)[1])

    count, _ = AsignacionGuardia.objects.filter(
        fecha__gte=primer_dia,
        fecha__lte=ultimo_dia,
        estado='BORRADOR',
    ).delete()

    return count or 0


def obtener_metricas_mes(mes, anio):
    """
    Calcula métricas de equidad para las asignaciones publicadas/cumplidas de un mes.

    Retorna:
        dict con claves:
          - por_residente (list[dict]): [{nombre, total, feriados, anio_residencia}, ...]
          - desviacion_std (float): desviación estándar de guardias por residente
          - total_asignaciones (int)
    """
    primer_dia = date(anio, mes, 1)
    ultimo_dia = date(anio, mes, calendar.monthrange(anio, mes)[1])

    asignaciones = (
        AsignacionGuardia.objects
        .filter(
            fecha__gte=primer_dia,
            fecha__lte=ultimo_dia,
            estado__in=['PUBLICADA', 'CUMPLIDA', 'BORRADOR'],
        )
        .select_related('residente')
    )

    conteo = defaultdict(lambda: {'total': 0, 'feriados': 0, 'residente': None})
    for a in asignaciones:
        pk = a.residente_id
        conteo[pk]['total'] += 1
        conteo[pk]['residente'] = a.residente
        if a.es_feriado:
            conteo[pk]['feriados'] += 1

    por_residente = sorted(
        [
            {
                'nombre': v['residente'].get_full_name() or v['residente'].username,
                'anio_residencia': v['residente'].anio_residencia or '—',
                'total': v['total'],
                'feriados': v['feriados'],
            }
            for v in conteo.values()
        ],
        key=lambda x: (-x['total'], x['nombre']),
    )

    totales = [r['total'] for r in por_residente]
    desviacion = _desviacion_std(totales) if totales else 0.0

    return {
        'por_residente': por_residente,
        'desviacion_std': round(desviacion, 2),
        'total_asignaciones': sum(totales),
    }


# ------------------------------------------------------------------
# Helpers privados
# ------------------------------------------------------------------

def _es_consecutivo(fecha, ultima):
    """True si fecha y ultima son días consecutivos (diferencia de 1 día)."""
    if ultima is None:
        return False
    return abs((fecha - ultima).days) == 1


def _score_cercania(residente_pk, fecha, fechas_ocupadas):
    """
    Penalización por proximidad: retorna 1 si el residente tiene otra guardia
    a exactamente 2 días de distancia (ej. martes-jueves), 0 en caso contrario.

    Usado como clave secundaria de ordenamiento en slots no feriado.
    Es una restricción *blanda*: solo afecta el orden de prioridad,
    nunca excluye al candidato del pool.
    """
    dos_antes = fecha - timedelta(days=2)
    dos_despues = fecha + timedelta(days=2)
    ocupadas = fechas_ocupadas[residente_pk]
    return 1 if (dos_antes in ocupadas or dos_despues in ocupadas) else 0


def _clave_semana(fecha):
    """Identifica la semana calendario de una fecha sin confundir cambios de año."""
    calendario_iso = fecha.isocalendar()
    return calendario_iso.year, calendario_iso.week


def _intercalar_slots_por_semana(slots):
    """
    Reparte el orden de procesamiento entre semanas.

    Dentro de cada semana conserva azar, pero toma como máximo un slot de cada
    semana por vuelta. Así, si la cuota total no alcanza para todos los slots,
    no se agota accidentalmente en una sola parte del mes.
    """
    por_semana = defaultdict(list)
    for slot in slots:
        por_semana[_clave_semana(slot[0])].append(slot)

    semanas = list(por_semana)
    random.shuffle(semanas)
    for grupo in por_semana.values():
        random.shuffle(grupo)

    intercalados = []
    while any(por_semana[semana] for semana in semanas):
        random.shuffle(semanas)
        for semana in semanas:
            if por_semana[semana]:
                intercalados.append(por_semana[semana].pop())
    return intercalados


def _elegir_candidato_priorizado(candidatos, prioridad):
    """Elige al azar solo entre candidatos con la mejor prioridad completa."""
    mejor_prioridad = min(prioridad(candidato) for candidato in candidatos)
    grupo_empate = [
        candidato for candidato in candidatos
        if prioridad(candidato) == mejor_prioridad
    ]
    return random.choice(grupo_empate)


def _anio_puede_cubrir_slot(anio_residencia, weekday, es_feriado):
    """
    Restricciones opcionales por año de residencia:
      R1  → solo Viernes (4), Domingos (6), o cualquier Feriado
      R2  → solo Sábados no feriado (5)
      R3/R4 → solo Lunes–Jueves no feriado (0–3)
      Otros → sin restricción (True)

    weekday: int 0=Lunes … 6=Domingo (fecha.weekday())
    """
    if anio_residencia == 'R1':
        return weekday in (4, 6) or es_feriado
    if anio_residencia == 'R2':
        return weekday == 5 and not es_feriado
    if anio_residencia in ('R3', 'R4'):
        return weekday in (0, 1, 2, 3) and not es_feriado
    return True


def _desviacion_std(valores):
    """Desviación estándar poblacional de una lista de enteros."""
    if not valores:
        return 0.0
    n = len(valores)
    media = sum(valores) / n
    varianza = sum((x - media) ** 2 for x in valores) / n
    return varianza ** 0.5


def _nombre_mes(mes):
    MESES = [
        '', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
        'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'
    ]
    return MESES[mes]


# ==========================================================================
# Fase 5: Ausencias y cambios de guardia
# ==========================================================================

class CambioGuardiaError(Exception):
    """Error controlado en el flujo de cambios o ausencias."""
    pass


def crear_notificacion(destinatario, tipo, mensaje, asignacion=None, solicitud=None):
    """Crea una NotificacionGuardia para el destinatario y envía email si aplica."""
    from .models import NotificacionGuardia
    notif = NotificacionGuardia.objects.create(
        destinatario=destinatario,
        tipo=tipo,
        mensaje=mensaje,
        asignacion=asignacion,
        solicitud_cambio=solicitud,
    )
    _enviar_notificacion_email(destinatario, tipo, mensaje)
    return notif


def _enviar_notificacion_email(destinatario, tipo, mensaje):
    """Envía correo para una notificación de guardia según preferencia del usuario."""
    if not getattr(destinatario, 'is_active', False):
        return
    if not getattr(destinatario, 'recibir_notificaciones', True):
        return
    email = (getattr(destinatario, 'email', '') or '').strip()
    if not email:
        return

    from .models import NotificacionGuardia

    tipo_display = dict(NotificacionGuardia.TIPO_CHOICES).get(tipo, tipo)
    subject = f"[Guardias] {tipo_display}"
    nombre = destinatario.get_full_name() or destinatario.username
    portal_url = _url_portal_guardias(destinatario)
    body = (
        f"Hola {nombre},\n\n"
        f"{mensaje}\n\n"
        f"Ingresá directo al sistema desde este enlace: {portal_url}\n\n"
        "Este es un mensaje automático del sistema."
    )
    send_mail(
        subject=subject,
        message=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
        fail_silently=True,
    )


def _url_portal_guardias(destinatario=None):
    """Retorna URL absoluta de guardias para emails según rol del destinatario."""
    base_url = getattr(settings, 'SITE_URL', '') or getattr(settings, 'BASE_URL', '') or 'http://localhost:8000'
    if destinatario is not None and getattr(destinatario, 'rol', '') == 'medico_residente':
        path = reverse('control_guardias:mis_guardias')
    else:
        path = reverse('control_guardias:index')
    return f"{base_url.rstrip('/')}{path}"


def _notificar_gestores(tipo, mensaje, solicitud=None):
    """Crea la notificación para todos los jefes/instructores activos."""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    gestores = User.objects.filter(
        rol__in=['jefe_residentes', 'instructor_residentes'],
        is_active=True,
    )
    for g in gestores:
        crear_notificacion(g, tipo, mensaje, solicitud=solicitud)


def solicitar_slot_vacante(residente, guardia, slot_fecha, tipo_guardia, notas=''):
    """Crea un pedido de slot vacante validado, único y visible para los gestores."""
    if guardia.residente_id != residente.pk or guardia.estado != 'PUBLICADA':
        raise CambioGuardiaError('Solo podés solicitar un slot vacante desde una guardia propia publicada.')
    if tipo_guardia.pk != guardia.tipo_guardia_id:
        raise CambioGuardiaError('El slot debe ser del mismo tipo que la guardia original.')
    if (slot_fecha.year, slot_fecha.month) != (guardia.fecha.year, guardia.fecha.month):
        raise CambioGuardiaError('El slot debe pertenecer al mismo mes que la guardia original.')
    if slot_fecha == guardia.fecha:
        raise CambioGuardiaError('El slot destino debe ser una fecha diferente.')

    with transaction.atomic():
        guardia = AsignacionGuardia.objects.select_for_update().get(pk=guardia.pk)
        if guardia.residente_id != residente.pk or guardia.estado != 'PUBLICADA':
            raise CambioGuardiaError('La guardia original ya no está disponible para este pedido.')
        if AsignacionGuardia.objects.filter(
            fecha=slot_fecha, tipo_guardia=tipo_guardia,
            estado__in=['BORRADOR', 'PUBLICADA'],
        ).exists():
            raise CambioGuardiaError('Ese slot ya no está disponible.')
        if SolicitudSlotVacante.objects.filter(
            guardia_ceder=guardia, estado='PENDIENTE'
        ).exists():
            raise CambioGuardiaError('Ya existe una solicitud pendiente para esta guardia.')
        if SolicitudSlotVacante.objects.filter(
            slot_fecha=slot_fecha, slot_tipo_guardia=tipo_guardia, estado='PENDIENTE'
        ).exists():
            raise CambioGuardiaError('Ese slot ya fue solicitado y está pendiente de revisión.')
        try:
            solicitud = SolicitudSlotVacante.objects.create(
                solicitante=residente, guardia_ceder=guardia,
                slot_fecha=slot_fecha, slot_tipo_guardia=tipo_guardia,
                notas_solicitante=notas,
            )
        except IntegrityError as exc:
            raise CambioGuardiaError(
                'La solicitud ya fue registrada o el slot acaba de ser solicitado.'
            ) from exc

    nombre = residente.get_full_name() or residente.username
    _notificar_gestores(
        'CAMBIO_SOLICITADO',
        f"Nueva solicitud de slot vacante #{solicitud.pk}: {nombre} solicita mover "
        f"su guardia del {guardia.fecha.strftime('%d/%m/%Y')} al "
        f"{slot_fecha.strftime('%d/%m/%Y')}. Requiere validación.",
    )
    return solicitud


# --------------------------------------------------------------------------
# Ausencias
# --------------------------------------------------------------------------

def reportar_ausencia(
    residente,
    fecha_inicio,
    fecha_fin,
    motivo,
    descripcion='',
    certificado=None,
    certificados_adicionales=None,
):
    """
    Registra una ausencia del residente y vincula las guardias PUBLICADAS afectadas.

    Retorna:
        AusenciaResidente creada
    """
    from .models import AusenciaDocumento, AusenciaResidente

    with transaction.atomic():
        ausencia = AusenciaResidente.objects.create(
            residente=residente,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            motivo=motivo,
            descripcion=descripcion,
            certificado=certificado,
        )

        documentos = certificados_adicionales or []
        if documentos:
            for doc in documentos:
                AusenciaDocumento.objects.create(
                    ausencia=ausencia,
                    archivo=doc,
                    tipo_documento='CERTIFICADO',
                )

        # Detectar y vincular guardias publicadas afectadas
        guardias_afectadas = AsignacionGuardia.objects.filter(
            residente=residente,
            fecha__gte=fecha_inicio,
            fecha__lte=fecha_fin,
            estado='PUBLICADA',
        )
        ausencia.guardias_afectadas.set(guardias_afectadas)

        nombre = residente.get_full_name()
        motivo_display = dict(AusenciaResidente.MOTIVO_CHOICES).get(motivo, motivo)
        n = guardias_afectadas.count()
        _notificar_gestores(
            'GUARDIA_REASIGNADA',
            f"{nombre} reportó ausencia por {motivo_display} "
            f"({fecha_inicio.strftime('%d/%m')} – {fecha_fin.strftime('%d/%m/%Y')}). "
            f"{n} guardia(s) afectada(s).",
        )

    return ausencia


def sugerir_reemplazo(guardia):
    """
    Sugiere el mejor candidato para cubrir una guardia por ausencia.

    Usa las mismas reglas del algoritmo de distribución:
      - No tiene otra guardia ese mismo día.
      - No tiene guardia en días consecutivos (anterior ni siguiente).
      - Preferencia: quien menos guardias tiene publicadas/cumplidas en el mismo mes.
      - Empate: orden alfabético (estable, no aleatorio para que la UI sea predecible).

    Retorna:
        (candidatos, sugerido)
        - candidatos: lista de dicts {'residente': obj, 'guardias_mes': int}
          ordenada de menor a mayor carga mensual.
        - sugerido: el primer residente de esa lista, o None si no hay candidatos.
    """
    from django.contrib.auth import get_user_model
    User = get_user_model()

    fecha = guardia.fecha
    mes, anio = fecha.month, fecha.year
    dia_anterior = fecha - timedelta(days=1)
    dia_siguiente = fecha + timedelta(days=1)

    primer_dia = date(anio, mes, 1)
    ultimo_dia = date(anio, mes, calendar.monthrange(anio, mes)[1])

    residentes = list(
        User.objects.filter(
            rol='medico_residente', estado_residencia='ACTIVO',
            perfil_completo=True, is_active=True,
        )
        .exclude(pk=guardia.residente_id)
        .order_by('last_name', 'first_name')
    )
    residentes_ausentes = set(
        AusenciaResidente.objects.filter(
            residente_id__in=[r.pk for r in residentes],
            fecha_inicio__lte=fecha,
            fecha_fin__gte=fecha,
            estado='PENDIENTE',
        ).values_list('residente_id', flat=True)
    )

    fechas_ocupadas = defaultdict(set)
    guardias_mes_count = defaultdict(int)
    for asig in AsignacionGuardia.objects.filter(
        fecha__gte=primer_dia, fecha__lte=ultimo_dia,
        estado__in=['PUBLICADA', 'CUMPLIDA'],
    ).values('residente_id', 'fecha'):
        fechas_ocupadas[asig['residente_id']].add(asig['fecha'])
        guardias_mes_count[asig['residente_id']] += 1

    elegibles = [
        r for r in residentes
        if fecha not in fechas_ocupadas[r.pk]
        and dia_anterior not in fechas_ocupadas[r.pk]
        and dia_siguiente not in fechas_ocupadas[r.pk]
        and r.pk not in residentes_ausentes
    ]

    # Ordenar: menor carga mensual primero; empate → alfabético (ya viene así)
    elegibles.sort(key=lambda r: guardias_mes_count[r.pk])

    candidatos = [
        {'residente': r, 'guardias_mes': guardias_mes_count[r.pk]}
        for r in elegibles
    ]
    sugerido = elegibles[0] if elegibles else None
    return candidatos, sugerido


def resolver_ausencia(ausencia, jefe, reasignaciones=None):
    """
    Resuelve una ausencia y gestiona las guardias afectadas.

    reasignaciones: dict opcional {guardia_pk (int): residente_pk (int)}
      - Si residente_pk para una guardia: guardia original → REASIGNADA
        + nueva AsignacionGuardia PUBLICADA para el reemplazante.
      - Si guardia_pk no está en el dict (o valor es falso): guardia → AUSENTE.
      - Si reasignaciones=None: todas las guardias → AUSENTE.

    Notifica al ausente y a cada reemplazante elegido.
    """
    reasig = reasignaciones or {}

    with transaction.atomic():
        ausencia = (
            AusenciaResidente.objects
            .select_for_update()
            .get(pk=ausencia.pk)
        )
        if ausencia.estado != 'PENDIENTE':
            raise CambioGuardiaError("La ausencia ya fue resuelta.")

        guardias_afectadas = list(
            ausencia.guardias_afectadas
            .select_for_update()
            .select_related('tipo_guardia', 'residente')
        )
        guardias_ids = {guardia.pk for guardia in guardias_afectadas}
        if set(reasig) - guardias_ids:
            raise CambioGuardiaError(
                "Se intentó reasignar una guardia que no pertenece a esta ausencia."
            )

        for guardia in guardias_afectadas:
            reemplazante_pk = reasig.get(guardia.pk)
            if reemplazante_pk:
                candidatos, _ = sugerir_reemplazo(guardia)
                candidatos_por_id = {
                    candidato['residente'].pk: candidato['residente']
                    for candidato in candidatos
                }
                try:
                    reemplazante = candidatos_por_id[int(reemplazante_pk)]
                except (KeyError, TypeError, ValueError):
                    raise CambioGuardiaError(
                        "El reemplazante seleccionado ya no está disponible "
                        "o no cumple las reglas de guardias."
                    )

                # Guardia original → REASIGNADA
                guardia.estado = 'REASIGNADA'
                guardia.notas = (
                    f"Reasignada por ausencia. "
                    f"Reemplazante: {reemplazante.get_full_name()}"
                )
                guardia.save(update_fields=['estado', 'notas', 'fecha_actualizacion'])

                # Nueva guardia PUBLICADA para el reemplazante
                nueva = AsignacionGuardia.objects.create(
                    residente=reemplazante,
                    tipo_guardia=guardia.tipo_guardia,
                    fecha=guardia.fecha,
                    estado='PUBLICADA',
                    creada_por=jefe,
                    notas=(
                        f"Cobertura por ausencia de "
                        f"{guardia.residente.get_full_name()}"
                    ),
                )

                # Notificar al reemplazante
                crear_notificacion(
                    reemplazante,
                    'GUARDIA_REASIGNADA',
                    f"Se te asignó una guardia el {guardia.fecha.strftime('%d/%m/%Y')} "
                    f"({guardia.tipo_guardia.nombre}) por ausencia de "
                    f"{guardia.residente.get_full_name()}.",
                    asignacion=nueva,
                )
                # Notificar al residente ausente (por cada guardia cubierta)
                crear_notificacion(
                    ausencia.residente,
                    'GUARDIA_REASIGNADA',
                    f"Tu guardia del {guardia.fecha.strftime('%d/%m/%Y')} "
                    f"({guardia.tipo_guardia.nombre}) fue cubierta por "
                    f"{reemplazante.get_full_name()}.",
                    asignacion=guardia,
                )
            else:
                # Sin reemplazante: marcar como ausente
                guardia.estado = 'AUSENTE'
                guardia.save(update_fields=['estado', 'fecha_actualizacion'])

        # Cerrar la ausencia
        ausencia.estado = 'RESUELTA'
        ausencia.resuelta_por = jefe
        ausencia.save(update_fields=['estado', 'resuelta_por'])

        crear_notificacion(
            ausencia.residente,
            'AUSENCIA_RESUELTA',
            f"Tu ausencia del {ausencia.fecha_inicio.strftime('%d/%m')} "
            f"al {ausencia.fecha_fin.strftime('%d/%m/%Y')} fue procesada por "
            f"{jefe.get_full_name()}.",
        )


# --------------------------------------------------------------------------
# Cambios de guardia
# --------------------------------------------------------------------------

def solicitar_cambio(solicitante, guardia_solicitante, guardia_receptor):
    """
    Crea una SolicitudCambioGuardia y notifica al receptor.

    Lanza:
        CambioGuardiaError si las guardias no son válidas para el intercambio.
    """
    from .models import SolicitudCambioGuardia

    if guardia_solicitante.residente != solicitante:
        raise CambioGuardiaError("Solo podés solicitar cambio de tus propias guardias.")
    if guardia_solicitante.estado != 'PUBLICADA':
        raise CambioGuardiaError("Solo se pueden solicitar cambios de guardias publicadas.")
    if guardia_receptor.estado != 'PUBLICADA':
        raise CambioGuardiaError("La guardia del receptor debe estar publicada.")
    if guardia_solicitante == guardia_receptor:
        raise CambioGuardiaError("No podés solicitar cambio con la misma guardia.")

    receptor = guardia_receptor.residente

    with transaction.atomic():
        solicitud = SolicitudCambioGuardia.objects.create(
            solicitante=solicitante,
            receptor=receptor,
            guardia_solicitante=guardia_solicitante,
            guardia_receptor=guardia_receptor,
        )
        crear_notificacion(
            receptor,
            'CAMBIO_SOLICITADO',
            f"{solicitante.get_full_name()} solicita cambiar su guardia del "
            f"{guardia_solicitante.fecha.strftime('%d/%m/%Y')} "
            f"({guardia_solicitante.tipo_guardia.nombre}) "
            f"por tu guardia del {guardia_receptor.fecha.strftime('%d/%m/%Y')} "
            f"({guardia_receptor.tipo_guardia.nombre}).",
            solicitud=solicitud,
        )

    return solicitud


def aceptar_cambio_receptor(solicitud, receptor):
    """
    Receptor acepta el cambio: pasa a PENDIENTE_JEFE y notifica a los gestores.

    Lanza:
        CambioGuardiaError si el receptor no es el correcto o el estado no es el esperado.
    """
    if solicitud.receptor != receptor:
        raise CambioGuardiaError("No tenés permiso para responder esta solicitud.")
    if solicitud.estado != 'PENDIENTE_RECEPTOR':
        raise CambioGuardiaError("Esta solicitud ya fue respondida.")

    solicitud.estado = 'PENDIENTE_JEFE'
    solicitud.save(update_fields=['estado'])

    crear_notificacion(
        solicitud.solicitante,
        'CAMBIO_ACEPTADO',
        f"{receptor.get_full_name()} aceptó tu propuesta de cambio. "
        f"Está pendiente de validación por jefe/instructor.",
        solicitud=solicitud,
    )
    _notificar_gestores(
        'CAMBIO_SOLICITADO',
        f"Hay un cambio de guardia pendiente de validación entre "
        f"{solicitud.solicitante.get_full_name()} y {receptor.get_full_name()}.",
        solicitud=solicitud,
    )


def rechazar_cambio_receptor(solicitud, receptor):
    """Receptor rechaza el cambio."""
    if solicitud.receptor != receptor:
        raise CambioGuardiaError("No tenés permiso para responder esta solicitud.")
    if solicitud.estado != 'PENDIENTE_RECEPTOR':
        raise CambioGuardiaError("Esta solicitud ya fue respondida.")

    solicitud.estado = 'RECHAZADA'
    solicitud.save(update_fields=['estado'])

    crear_notificacion(
        solicitud.solicitante,
        'CAMBIO_RECHAZADO',
        f"{receptor.get_full_name()} rechazó tu propuesta de cambio de guardia "
        f"del {solicitud.guardia_solicitante.fecha.strftime('%d/%m/%Y')}.",
        solicitud=solicitud,
    )


def aprobar_cambio(solicitud, jefe, notas=''):
    """
    Jefe aprueba el cambio: intercambia los residentes en las asignaciones.

    Lanza:
        CambioGuardiaError si el estado no es PENDIENTE_JEFE.
    """
    from django.utils import timezone as tz

    if solicitud.estado != 'PENDIENTE_JEFE':
        raise CambioGuardiaError("Esta solicitud no está pendiente de validación por jefe.")

    g_sol = solicitud.guardia_solicitante
    g_rec = solicitud.guardia_receptor

    with transaction.atomic():
        # Intercambiar residentes
        g_sol.residente, g_rec.residente = g_rec.residente, g_sol.residente
        AsignacionGuardia.objects.filter(pk=g_sol.pk).update(residente=g_sol.residente)
        AsignacionGuardia.objects.filter(pk=g_rec.pk).update(residente=g_rec.residente)

        solicitud.estado = 'APROBADA'
        solicitud.revisado_por = jefe
        solicitud.notas_jefe = notas
        solicitud.fecha_resolucion = tz.now()
        solicitud.save(update_fields=['estado', 'revisado_por', 'notas_jefe', 'fecha_resolucion'])

    for destinatario in [solicitud.solicitante, solicitud.receptor]:
        crear_notificacion(
            destinatario,
            'CAMBIO_APROBADO',
            f"El cambio de guardia entre {solicitud.solicitante.get_full_name()} "
            f"y {solicitud.receptor.get_full_name()} fue aprobado.",
            solicitud=solicitud,
        )


def rechazar_cambio_jefe(solicitud, jefe, notas=''):
    """Jefe rechaza el cambio."""
    from django.utils import timezone as tz

    if solicitud.estado != 'PENDIENTE_JEFE':
        raise CambioGuardiaError("Esta solicitud no está pendiente de validación por jefe.")

    solicitud.estado = 'RECHAZADA'
    solicitud.revisado_por = jefe
    solicitud.notas_jefe = notas
    solicitud.fecha_resolucion = tz.now()
    solicitud.save(update_fields=['estado', 'revisado_por', 'notas_jefe', 'fecha_resolucion'])

    for destinatario in [solicitud.solicitante, solicitud.receptor]:
        crear_notificacion(
            destinatario,
            'CAMBIO_RECHAZADO',
            f"El cambio de guardia entre {solicitud.solicitante.get_full_name()} "
            f"y {solicitud.receptor.get_full_name()} fue rechazado por el jefe/instructor."
            + (f" Motivo: {notas}" if notas else ''),
            solicitud=solicitud,
        )


def cancelar_cambio(solicitud, solicitante):
    """Solicitante cancela su propia solicitud (si está PENDIENTE_RECEPTOR o PENDIENTE_JEFE)."""
    if solicitud.solicitante != solicitante:
        raise CambioGuardiaError("Solo el solicitante puede cancelar la solicitud.")
    if solicitud.estado not in ('PENDIENTE_RECEPTOR', 'PENDIENTE_JEFE'):
        raise CambioGuardiaError("Solo se puede cancelar si aún no fue aprobada por los jefes.")

    solicitud.estado = 'CANCELADA'
    solicitud.save(update_fields=['estado'])

    crear_notificacion(
        solicitud.receptor,
        'CAMBIO_RECHAZADO',
        f"{solicitante.get_full_name()} canceló la solicitud de cambio de guardia "
        f"del {solicitud.guardia_solicitante.fecha.strftime('%d/%m/%Y')}.",
        solicitud=solicitud,
    )

def cancelar_ausencia(ausencia, residente):
    """Residente cancela su propia ausencia reportada (si aún está PENDIENTE)."""
    if ausencia.residente != residente:
        raise DistribucionError("Solo el residente puede cancelar su ausencia.")
    if ausencia.estado != 'PENDIENTE':
        raise DistribucionError("Solo se puede cancelar una ausencia si aún no fue resuelta.")

    ausencia.estado = 'RESUELTA'
    ausencia.resuelta_por = residente  # El residente mismo la cancela
    ausencia.save(update_fields=['estado', 'resuelta_por'])

    # Desvincula las guardias afectadas (se mantienen asignadas al residente)
    ausencia.guardias_afectadas.clear()


# ==========================================================================
# Nuevos servicios: carry-over, slot vacante
# ==========================================================================

def eliminar_guardia_excepcion(guardia, jefe, trasladar_cuota=True, motivo=''):
    """
    Elimina una guardia PUBLICADA por excepción (decisión del jefe).

    Si trasladar_cuota=True (default), crea automáticamente un AjusteCuotaGuardia
    tipo CARRYOVER para el mes siguiente, compensando al residente por la guardia
    eliminada sin posibilidad de cambio.

    Retorna:
        dict con claves 'guardia_eliminada' (pk) y 'ajuste_creado' (AjusteCuotaGuardia|None)

    Lanza:
        CambioGuardiaError si la guardia no está en estado PUBLICADA.
    """
    if guardia.estado != 'PUBLICADA':
        raise CambioGuardiaError(
            f"Solo se pueden eliminar por excepción guardias PUBLICADAS. "
            f"Esta guardia está en estado: {guardia.get_estado_display()}."
        )

    residente = guardia.residente
    fecha_guardia = guardia.fecha

    # Calcular mes siguiente para el carry-over
    if fecha_guardia.month == 12:
        mes_carryover = 1
        anio_carryover = fecha_guardia.year + 1
    else:
        mes_carryover = fecha_guardia.month + 1
        anio_carryover = fecha_guardia.year

    guardia_pk = guardia.pk

    with transaction.atomic():
        guardia.delete()

        ajuste = None
        if trasladar_cuota:
            motivo_ajuste = (
                motivo or
                f"Guardia del {fecha_guardia.strftime('%d/%m/%Y')} eliminada por excepción "
                f"por {jefe.get_full_name()}."
            )
            ajuste = AjusteCuotaGuardia.objects.create(
                residente=residente,
                mes=mes_carryover,
                anio=anio_carryover,
                cantidad=1,
                tipo='CARRYOVER',
                motivo=motivo_ajuste,
                creado_por=jefe,
            )

        crear_notificacion(
            residente,
            'GUARDIA_REASIGNADA',
            f"Tu guardia del {fecha_guardia.strftime('%d/%m/%Y')} fue eliminada por el jefe."
            + (f" Se acreditó una guardia extra para {_nombre_mes(mes_carryover)} {anio_carryover}." if ajuste else ''),
        )

    return {'guardia_eliminada': guardia_pk, 'ajuste_creado': ajuste}


def aprobar_slot_vacante(solicitud, jefe, notas=''):
    """
    Jefe aprueba una SolicitudSlotVacante.

    Efectos:
      - guardia_ceder → estado REASIGNADA
      - Nueva AsignacionGuardia PUBLICADA para el mismo residente en slot_fecha/slot_tipo
      - solicitud → APROBADA, guardia_creada asignada

    La cuota queda neutra (cede una, toma una).

    Lanza:
        CambioGuardiaError si el estado no es PENDIENTE o el slot ya fue ocupado.
    """
    from django.utils import timezone as tz

    if solicitud.estado != 'PENDIENTE':
        raise CambioGuardiaError(
            f"Solo se puede aprobar una solicitud PENDIENTE. Estado actual: {solicitud.get_estado_display()}."
        )

    # Verificar que el slot destino sigue vacante
    slot_ocupado = AsignacionGuardia.objects.filter(
        fecha=solicitud.slot_fecha,
        tipo_guardia=solicitud.slot_tipo_guardia,
        estado__in=['PUBLICADA', 'BORRADOR'],
    ).exists()
    if slot_ocupado:
        raise CambioGuardiaError(
            f"El slot del {solicitud.slot_fecha.strftime('%d/%m/%Y')} "
            f"({solicitud.slot_tipo_guardia.nombre}) ya no está disponible."
        )

    with transaction.atomic():
        # Marcar guardia original como reasignada
        guardia_cedida = solicitud.guardia_ceder
        guardia_cedida.estado = 'REASIGNADA'
        guardia_cedida.notas = (
            f"Movida al {solicitud.slot_fecha.strftime('%d/%m/%Y')} "
            f"por solicitud de slot vacante aprobada por {jefe.get_full_name()}."
        )
        guardia_cedida.save(update_fields=['estado', 'notas', 'fecha_actualizacion'])

        # Crear nueva guardia en el slot destino
        nueva_guardia = AsignacionGuardia.objects.create(
            residente=solicitud.solicitante,
            tipo_guardia=solicitud.slot_tipo_guardia,
            fecha=solicitud.slot_fecha,
            estado='PUBLICADA',
            creada_por=jefe,
            notas=(
                f"Creada por aprobación de solicitud de slot vacante "
                f"(reemplaza guardia del {guardia_cedida.fecha.strftime('%d/%m/%Y')})."
            ),
        )

        # Actualizar solicitud
        solicitud.estado = 'APROBADA'
        solicitud.revisado_por = jefe
        solicitud.notas_jefe = notas
        solicitud.guardia_creada = nueva_guardia
        solicitud.fecha_resolucion = tz.now()
        solicitud.save(update_fields=[
            'estado', 'revisado_por', 'notas_jefe', 'guardia_creada', 'fecha_resolucion'
        ])

    crear_notificacion(
        solicitud.solicitante,
        'CAMBIO_APROBADO',
        f"Tu solicitud de slot vacante fue aprobada. "
        f"Tu guardia del {guardia_cedida.fecha.strftime('%d/%m/%Y')} fue movida al "
        f"{solicitud.slot_fecha.strftime('%d/%m/%Y')} ({solicitud.slot_tipo_guardia.nombre}).",
    )

    return solicitud


def rechazar_slot_vacante(solicitud, jefe, notas=''):
    """
    Jefe rechaza una SolicitudSlotVacante.

    Lanza:
        CambioGuardiaError si el estado no es PENDIENTE.
    """
    from django.utils import timezone as tz

    if solicitud.estado != 'PENDIENTE':
        raise CambioGuardiaError(
            f"Solo se puede rechazar una solicitud PENDIENTE. Estado actual: {solicitud.get_estado_display()}."
        )

    solicitud.estado = 'RECHAZADA'
    solicitud.revisado_por = jefe
    solicitud.notas_jefe = notas
    solicitud.fecha_resolucion = tz.now()
    solicitud.save(update_fields=['estado', 'revisado_por', 'notas_jefe', 'fecha_resolucion'])

    crear_notificacion(
        solicitud.solicitante,
        'CAMBIO_RECHAZADO',
        f"Tu solicitud de slot vacante del "
        f"{solicitud.guardia_ceder.fecha.strftime('%d/%m/%Y')} → "
        f"{solicitud.slot_fecha.strftime('%d/%m/%Y')} fue rechazada."
        + (f" Motivo: {notas}" if notas else ''),
    )

    return solicitud


def cancelar_slot_vacante(solicitud, solicitante):
    """
    Residente cancela su propia solicitud de slot vacante (si está PENDIENTE).

    Lanza:
        CambioGuardiaError si el solicitante no es el dueño o el estado no permite cancelar.
    """
    if solicitud.solicitante != solicitante:
        raise CambioGuardiaError("Solo el solicitante puede cancelar esta solicitud.")
    if solicitud.estado != 'PENDIENTE':
        raise CambioGuardiaError(
            f"Solo se puede cancelar una solicitud PENDIENTE. Estado actual: {solicitud.get_estado_display()}."
        )

    solicitud.estado = 'CANCELADA'
    solicitud.fecha_resolucion = timezone.now()
    solicitud.save(update_fields=['estado', 'fecha_resolucion'])

    return solicitud
