from decimal import Decimal
from collections import defaultdict

from django.utils import timezone

from .models import GrupoTarifario
from control_guardias.models import Feriado


TIPO_SIN_REGISTRO_ESTUDIO = 'sin_registro_estudio'
TIPO_MONTO_CERO_CON_ESTUDIOS = 'monto_cero_con_estudios'
TIPO_GUARDIA_MONTO_INVALIDO = 'guardia_monto_invalido'
TIPO_SESION_VACIA = 'sesion_vacia'
TIPO_SIN_GRUPO_CON_FALLBACK = 'sin_grupo_con_fallback'
TIPO_SIN_PRECIO_RESOLUBLE = 'sin_precio_resoluble'
TIPO_SIN_TARIFA_VIGENTE_GRUPO = 'sin_tarifa_vigente_grupo'
TIPO_CONTEXTUAL_SIN_GRUPO = 'contextual_sin_grupo'
TIPO_CONTEXTUAL_SIN_TARIFA = 'contextual_sin_tarifa'


# Auditoría administrativa residentes ECO (PR2)
ROLES_AUDITORIA_RESIDENCIA_ECO = {
    'medico_residente',
    'jefe_residentes',
    'instructor_residentes',
}

AUDIT_EXTRA_MENSUAL_AMARILLA = 35
AUDIT_EXTRA_MENSUAL_ROJA = 50
AUDIT_PROP_EXTRA_AMARILLA = 0.35
AUDIT_PROP_EXTRA_ROJA = 0.50
AUDIT_NOCTURNOS_AMARILLA = 6
AUDIT_NOCTURNOS_ROJA = 10
AUDIT_FINDE_FERIADO_AMARILLA = 8
AUDIT_FINDE_FERIADO_ROJA = 15
AUDIT_MAX_ECO_DIA_AMARILLA = 14
AUDIT_MAX_ECO_DIA_ROJA = 20
AUDIT_HORA_NOCTURNA_DESDE = 22
AUDIT_HORA_NOCTURNA_HASTA = 6
AUDIT_HORA_POST_17 = 17


def _es_monto_cero(monto):
    try:
        return Decimal(str(monto or 0)) <= Decimal('0')
    except Exception:
        return True


def _debe_bloquear(tipo, estado_destino):
    # ABIERTA -> REVISION: solo advertencias
    if estado_destino == 'REVISION':
        return False

    # REVISION -> CERRADA: bloqueos estructurales
    if estado_destino == 'CERRADA':
        return tipo in {
            TIPO_SIN_REGISTRO_ESTUDIO,
            TIPO_MONTO_CERO_CON_ESTUDIOS,
            TIPO_GUARDIA_MONTO_INVALIDO,
        }

    # CERRADA -> FACTURADA: bloqueos financieros + sesión vacía
    if estado_destino == 'FACTURADA':
        return tipo in {
            TIPO_SESION_VACIA,
            TIPO_SIN_PRECIO_RESOLUBLE,
            TIPO_SIN_TARIFA_VIGENTE_GRUPO,
            TIPO_CONTEXTUAL_SIN_GRUPO,
            TIPO_CONTEXTUAL_SIN_TARIFA,
        }

    # FACTURADA -> PAGADA: sesión vacía o remanentes críticos
    if estado_destino == 'PAGADA':
        return tipo in {
            TIPO_SESION_VACIA,
            TIPO_SIN_REGISTRO_ESTUDIO,
            TIPO_MONTO_CERO_CON_ESTUDIOS,
            TIPO_GUARDIA_MONTO_INVALIDO,
            TIPO_SIN_PRECIO_RESOLUBLE,
            TIPO_SIN_TARIFA_VIGENTE_GRUPO,
            TIPO_CONTEXTUAL_SIN_GRUPO,
            TIPO_CONTEXTUAL_SIN_TARIFA,
        }

    return False


def _agregar_issue(resultado, tipo, mensaje, estado_destino):
    destino = resultado['bloqueantes'] if _debe_bloquear(tipo, estado_destino) else resultado['advertencias']
    destino.append(mensaje)


def evaluar_gate_consistencia_sesion(sesion, estado_destino):
    """
    Evalua consistencia administrativa de una sesion antes de transicionar de estado.

    Retorna:
      {
        'bloqueantes': [...],
        'advertencias': [...],
      }
    """
    resultado = {'bloqueantes': [], 'advertencias': []}

    practicas = list(
        sesion.practicas.select_related('medico', 'sesion_contable').prefetch_related('registroestudio_set__estudio')
    )
    guardias = list(sesion.guardias_pasivas.all())

    if estado_destino in {'FACTURADA', 'PAGADA'} and not practicas and not guardias:
        _agregar_issue(
            resultado,
            TIPO_SESION_VACIA,
            'Sesion vacia: no hay practicas ni guardias para transicionar.',
            estado_destino,
        )

    for registro in practicas:
        relaciones = list(registro.registroestudio_set.all())

        if not relaciones:
            _agregar_issue(
                resultado,
                TIPO_SIN_REGISTRO_ESTUDIO,
                f'Registro #{registro.pk} sin estudios asociados en RegistroEstudio.',
                estado_destino,
            )
            continue

        if _es_monto_cero(registro.monto_calculado):
            _agregar_issue(
                resultado,
                TIPO_MONTO_CERO_CON_ESTUDIOS,
                f'Registro #{registro.pk} con estudios asociados y monto_calculado <= 0.',
                estado_destino,
            )

        for rel in relaciones:
            estudio = rel.estudio
            fecha_ref = registro.fecha_del_informe
            contexto = (rel.contexto or 'SERVICIO').upper()

            if estudio.grupo_tarifario_id:
                tarifa_base = estudio.grupo_tarifario.get_tarifa_vigente(fecha=fecha_ref)
                if not tarifa_base:
                    _agregar_issue(
                        resultado,
                        TIPO_SIN_TARIFA_VIGENTE_GRUPO,
                        (
                            f'Registro #{registro.pk} estudio {estudio.nombre}: '
                            f'grupo {estudio.grupo_tarifario.codigo} sin tarifa vigente para {fecha_ref}.'
                        ),
                        estado_destino,
                    )

                if contexto in {'LECHO', 'QUIROFANO'}:
                    codigo_ctx = f'{estudio.grupo_tarifario.codigo}_{contexto}'
                    grupo_ctx = GrupoTarifario.objects.filter(codigo=codigo_ctx, activo=True).first()
                    if not grupo_ctx:
                        _agregar_issue(
                            resultado,
                            TIPO_CONTEXTUAL_SIN_GRUPO,
                            (
                                f'Registro #{registro.pk} estudio {estudio.nombre}: '
                                f'contexto {contexto} sin grupo contextual {codigo_ctx}.'
                            ),
                            estado_destino,
                        )
                    else:
                        tarifa_ctx = grupo_ctx.get_tarifa_vigente(fecha=fecha_ref)
                        if not tarifa_ctx:
                            _agregar_issue(
                                resultado,
                                TIPO_CONTEXTUAL_SIN_TARIFA,
                                (
                                    f'Registro #{registro.pk} estudio {estudio.nombre}: '
                                    f'grupo contextual {codigo_ctx} sin tarifa vigente para {fecha_ref}.'
                                ),
                                estado_destino,
                            )
            else:
                precio_legado = estudio.precio_para_os(
                    registro.tipo_obra_social,
                    fecha=fecha_ref,
                    contexto=contexto,
                )
                if _es_monto_cero(precio_legado):
                    _agregar_issue(
                        resultado,
                        TIPO_SIN_PRECIO_RESOLUBLE,
                        (
                            f'Registro #{registro.pk} estudio {estudio.nombre}: '
                            'sin grupo y sin precio legado valido (>0).'
                        ),
                        estado_destino,
                    )
                else:
                    _agregar_issue(
                        resultado,
                        TIPO_SIN_GRUPO_CON_FALLBACK,
                        (
                            f'Registro #{registro.pk} estudio {estudio.nombre}: '
                            'sin grupo tarifario (se usa fallback legado).'
                        ),
                        estado_destino,
                    )

    for guardia in guardias:
        if _es_monto_cero(guardia.monto):
            _agregar_issue(
                resultado,
                TIPO_GUARDIA_MONTO_INVALIDO,
                f'Guardia #{guardia.pk} con monto <= 0.',
                estado_destino,
            )

    return resultado


def _nivel_alerta(valor, umbral_amarillo, umbral_rojo):
    if valor >= umbral_rojo:
        return 'roja'
    if valor >= umbral_amarillo:
        return 'amarilla'
    return None


def _agregar_alerta(alertas, tipo, valor, umbral_amarillo, umbral_rojo, mensaje):
    nivel = _nivel_alerta(valor, umbral_amarillo, umbral_rojo)
    if not nivel:
        return

    alertas.append({
        'tipo': tipo,
        'severidad': nivel,
        'valor': valor,
        'umbral': umbral_rojo if nivel == 'roja' else umbral_amarillo,
        'mensaje': mensaje,
    })


def auditar_residentes_eco_por_sesion(sesion):
    """
    Auditoría administrativa de patrones ECO en residentes para una sesión contable.

    Retorno (contrato):
      {
        'sesion_id': int,
        'periodo': str,
        'total_residentes': int,
        'residentes_con_alertas': int,
        'alertas_rojas': int,
        'alertas_amarillas': int,
        'items': [ ... ],
        'top_alertas': [ ... ],
      }
    """
    meses = ['', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
             'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
    periodo = f"{meses[sesion.mes] if 1 <= sesion.mes <= 12 else sesion.mes} {sesion.año}"

    resultado = {
        'sesion_id': sesion.id,
        'periodo': periodo,
        'total_residentes': 0,
        'residentes_con_alertas': 0,
        'alertas_rojas': 0,
        'alertas_amarillas': 0,
        'items': [],
        'top_alertas': [],
    }

    practicas = list(
        sesion.practicas.select_related('medico').prefetch_related('registroestudio_set__estudio')
        .filter(medico__rol__in=ROLES_AUDITORIA_RESIDENCIA_ECO)
    )
    if not practicas:
        return resultado

    fechas_locales = []
    for registro in practicas:
        dt = registro.fecha_registro
        if not dt:
            continue
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt, timezone.get_current_timezone())
        fechas_locales.append(timezone.localtime(dt).date())

    feriados = set(Feriado.objects.filter(fecha__in=fechas_locales).values_list('fecha', flat=True))

    acumulado = {}

    for registro in practicas:
        relaciones = list(registro.registroestudio_set.all())
        if not relaciones:
            continue

        if not any(rel.estudio.tipo == 'ECO' for rel in relaciones):
            continue

        medico = registro.medico
        item = acumulado.setdefault(
            medico.id,
            {
                'medico_id': medico.id,
                'medico_nombre': medico.get_full_name() or medico.username,
                'rol': medico.rol,
                'total_eco': 0,
                'intra': 0,
                'extra': 0,
                'proporcion_extra': 0,
                'nocturnos': 0,
                'finde_feriado': 0,
                'post_17': 0,
                'max_eco_dia': 0,
                'dias_pico': [],
                'severidad': 'ok',
                'alertas': [],
                '_eco_por_dia': defaultdict(int),
            },
        )

        item['total_eco'] += 1
        if registro.horario == 'INTRA':
            item['intra'] += 1
        elif registro.horario == 'EXTRA':
            item['extra'] += 1

        dt = registro.fecha_registro
        if not dt:
            continue
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt, timezone.get_current_timezone())
        dt = timezone.localtime(dt)

        fecha_local = dt.date()
        hora_local = dt.hour
        weekday = fecha_local.weekday()
        es_finde = weekday >= 5
        es_feriado = fecha_local in feriados

        if hora_local >= AUDIT_HORA_NOCTURNA_DESDE or hora_local < AUDIT_HORA_NOCTURNA_HASTA:
            item['nocturnos'] += 1

        if es_finde or es_feriado:
            item['finde_feriado'] += 1
        elif hora_local >= AUDIT_HORA_POST_17:
            item['post_17'] += 1

        item['_eco_por_dia'][fecha_local] += 1

    items = []
    for item in acumulado.values():
        total_eco = item['total_eco']
        if total_eco <= 0:
            continue

        item['proporcion_extra'] = item['extra'] / total_eco

        eco_por_dia = item.pop('_eco_por_dia')
        item['max_eco_dia'] = max(eco_por_dia.values()) if eco_por_dia else 0
        item['dias_pico'] = sorted(
            [
                fecha.isoformat()
                for fecha, cantidad in eco_por_dia.items()
                if cantidad >= AUDIT_MAX_ECO_DIA_AMARILLA
            ]
        )

        _agregar_alerta(
            item['alertas'],
            'extra_mensual',
            item['extra'],
            AUDIT_EXTRA_MENSUAL_AMARILLA,
            AUDIT_EXTRA_MENSUAL_ROJA,
            'Cantidad de registros EXTRA mensual elevada',
        )
        _agregar_alerta(
            item['alertas'],
            'proporcion_extra',
            item['proporcion_extra'],
            AUDIT_PROP_EXTRA_AMARILLA,
            AUDIT_PROP_EXTRA_ROJA,
            'Proporción EXTRA elevada',
        )
        _agregar_alerta(
            item['alertas'],
            'nocturnos',
            item['nocturnos'],
            AUDIT_NOCTURNOS_AMARILLA,
            AUDIT_NOCTURNOS_ROJA,
            'Cantidad de registros nocturnos elevada',
        )
        _agregar_alerta(
            item['alertas'],
            'finde_feriado',
            item['finde_feriado'],
            AUDIT_FINDE_FERIADO_AMARILLA,
            AUDIT_FINDE_FERIADO_ROJA,
            'Cantidad de registros en sábado/domingo/feriado elevada',
        )
        _agregar_alerta(
            item['alertas'],
            'volumen_diario',
            item['max_eco_dia'],
            AUDIT_MAX_ECO_DIA_AMARILLA,
            AUDIT_MAX_ECO_DIA_ROJA,
            'Volumen diario ECO inusual',
        )

        if any(alerta['severidad'] == 'roja' for alerta in item['alertas']):
            item['severidad'] = 'roja'
        elif item['alertas']:
            item['severidad'] = 'amarilla'
        else:
            item['severidad'] = 'ok'

        items.append(item)

    orden_severidad = {'roja': 0, 'amarilla': 1, 'ok': 2}
    items.sort(key=lambda x: (orden_severidad.get(x['severidad'], 9), x['medico_nombre']))

    resultado['items'] = items
    resultado['total_residentes'] = len(items)
    resultado['residentes_con_alertas'] = len([i for i in items if i['severidad'] in {'roja', 'amarilla'}])
    resultado['alertas_rojas'] = sum(1 for i in items for a in i['alertas'] if a['severidad'] == 'roja')
    resultado['alertas_amarillas'] = sum(1 for i in items for a in i['alertas'] if a['severidad'] == 'amarilla')

    top = [i for i in items if i['severidad'] in {'roja', 'amarilla'}]
    top.sort(key=lambda x: (orden_severidad[x['severidad']], -len(x['alertas']), x['medico_nombre']))
    resultado['top_alertas'] = [
        {
            'medico_id': i['medico_id'],
            'medico_nombre': i['medico_nombre'],
            'severidad': i['severidad'],
            'cantidad_alertas': len(i['alertas']),
        }
        for i in top[:3]
    ]

    return resultado
