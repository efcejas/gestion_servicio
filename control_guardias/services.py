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
from django.db import transaction
from django.urls import reverse

from .models import AsignacionGuardia, ConfiguracionTipoGuardia, CuotaMensualGuardia, Feriado

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
            perfil_completo=True,
            is_active=True,
        ).order_by('last_name', 'first_name')
    )
    if not residentes:
        raise DistribucionError("No hay residentes activos con perfil completo para asignar.")

    primer_dia = date(anio, mes, 1)
    ultimo_dia = date(anio, mes, calendar.monthrange(anio, mes)[1])

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
        grupo = slots_por_ronda[ronda]
        random.shuffle(grupo)   # fechas en orden aleatorio dentro de la ronda
        slots.extend(grupo)

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
    if reemplazar_borradores and borradores_existentes.exists():
        borradores_existentes.delete()

    # ------------------------------------------------------------------
    # 7. Algoritmo de asignación greedy equitativo
    # ------------------------------------------------------------------
    # Mezclar la lista de residentes al inicio para romper cualquier sesgo
    # de orden (alfabético, fecha de ingreso, etc.) en los grupos de empate.
    random.shuffle(residentes)

    guardias_en_borrador = defaultdict(int)   # residente_pk → guardias generadas en esta corrida
    anio_por_fecha = defaultdict(set)         # fecha → set de anio_residencia ya asignados ese día

    # Pre-cargar fechas ya asignadas en BD para el período (publicadas o borradores restantes)
    # Evita IntegrityError por violación del unique_together (residente, fecha, tipo_guardia)
    fechas_asignadas = defaultdict(set)   # residente_pk → set(fecha, tipo_guardia_id)
    fechas_ocupadas = defaultdict(set)    # residente_pk → set(fecha) — un residente no puede tener 2 guardias el mismo día
    for asig in AsignacionGuardia.objects.filter(
        fecha__gte=primer_dia,
        fecha__lte=ultimo_dia,
    ).select_related('residente').values('residente_id', 'fecha', 'tipo_guardia_id', 'residente__anio_residencia'):
        fechas_asignadas[asig['residente_id']].add((asig['fecha'], asig['tipo_guardia_id']))
        fechas_ocupadas[asig['residente_id']].add(asig['fecha'])
        anio_por_fecha[asig['fecha']].add(asig['residente__anio_residencia'])

    asignaciones_a_crear = []
    slots_sin_cubrir = []
    slots_fallback_anio = 0   # contador de slots cubiertos fuera de restricción de año

    for fecha, tipo, es_feriado_slot in slots:
        weekday = fecha.weekday()  # 0=Lunes … 6=Domingo
        # Candidatos elegibles: cuota disponible, sin guardia ese día (ningún tipo), sin día consecutivo
        dia_anterior = fecha - timedelta(days=1)
        dia_siguiente = fecha + timedelta(days=1)
        candidatos = [
            r for r in residentes
            if cuota_disponible[r.pk] > 0
            and fecha not in fechas_ocupadas[r.pk]
            and dia_anterior not in fechas_ocupadas[r.pk]
            and dia_siguiente not in fechas_ocupadas[r.pk]
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
            candidatos.sort(key=lambda r: (
                guardias_en_borrador[r.pk],
                feriados_historicos[r.pk],
            ))
        else:
            candidatos.sort(key=lambda r: guardias_en_borrador[r.pk])

        # Tomar el grupo de empate y elegir al azar para evitar sesgo
        min_count = guardias_en_borrador[candidatos[0].pk]
        grupo_empate = [r for r in candidatos if guardias_en_borrador[r.pk] == min_count]
        elegido = random.choice(grupo_empate)

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
        AsignacionGuardia.objects.bulk_create(asignaciones_a_crear)

    advertencias = []
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
        User.objects.filter(rol='medico_residente', perfil_completo=True, is_active=True)
        .exclude(pk=guardia.residente_id)
        .order_by('last_name', 'first_name')
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
    from django.contrib.auth import get_user_model
    User = get_user_model()

    reasig = reasignaciones or {}

    with transaction.atomic():
        for guardia in ausencia.guardias_afectadas.select_related('tipo_guardia', 'residente'):
            reemplazante_pk = reasig.get(guardia.pk)
            if reemplazante_pk:
                reemplazante = User.objects.get(pk=reemplazante_pk)

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
    """Solicitante cancela su propia solicitud (solo si está PENDIENTE_RECEPTOR)."""
    if solicitud.solicitante != solicitante:
        raise CambioGuardiaError("Solo el solicitante puede cancelar la solicitud.")
    if solicitud.estado != 'PENDIENTE_RECEPTOR':
        raise CambioGuardiaError("Solo se puede cancelar si todavía no fue respondida por el receptor.")

    solicitud.estado = 'CANCELADA'
    solicitud.save(update_fields=['estado'])

    crear_notificacion(
        solicitud.receptor,
        'CAMBIO_RECHAZADO',
        f"{solicitante.get_full_name()} canceló la solicitud de cambio de guardia "
        f"del {solicitud.guardia_solicitante.fecha.strftime('%d/%m/%Y')}.",
        solicitud=solicitud,
    )
