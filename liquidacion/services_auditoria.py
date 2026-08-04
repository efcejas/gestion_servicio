from decimal import Decimal
from collections import defaultdict

from django.utils import timezone

from .models import GrupoTarifario, RevisionCruceEgesRegistro
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
TIPOS_AUDITORIA_RESIDENCIA_ECO = {'ECO', 'DOP', 'ECOCAR'}

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


def _serializar_metadata_issue(metadata):
    serializada = {}
    for key, value in metadata.items():
        if hasattr(value, 'isoformat'):
            serializada[key] = value.isoformat()
        else:
            serializada[key] = value
    return serializada


def _agregar_issue(resultado, tipo, mensaje, estado_destino, **metadata):
    es_bloqueante = _debe_bloquear(tipo, estado_destino)
    destino = resultado['bloqueantes'] if es_bloqueante else resultado['advertencias']
    destino.append(mensaje)
    resultado.setdefault('items', []).append({
        'tipo': tipo,
        'mensaje': mensaje,
        'estado': 'bloqueante' if es_bloqueante else 'advertencia',
        **_serializar_metadata_issue(metadata),
    })


def evaluar_gate_consistencia_sesion(sesion, estado_destino):
    """
    Evalua consistencia administrativa de una sesion antes de transicionar de estado.

    Retorna:
      {
        'bloqueantes': [...],
        'advertencias': [...],
      }
    """
    resultado = {'bloqueantes': [], 'advertencias': [], 'items': []}

    practicas = list(
        sesion.practicas.filter(anulado=False).select_related('medico', 'sesion_contable').prefetch_related('registroestudio_set__estudio')
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
                registro_id=registro.pk,
                fecha=registro.fecha_del_informe,
            )
            continue

        if _es_monto_cero(registro.monto_calculado):
            _agregar_issue(
                resultado,
                TIPO_MONTO_CERO_CON_ESTUDIOS,
                f'Registro #{registro.pk} con estudios asociados y monto_calculado <= 0.',
                estado_destino,
                registro_id=registro.pk,
                fecha=registro.fecha_del_informe,
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
                            registro_id=registro.pk,
                            estudio_id=estudio.pk,
                            grupo_id=estudio.grupo_tarifario_id,
                            grupo_codigo=estudio.grupo_tarifario.codigo,
                            fecha=fecha_ref,
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
                                registro_id=registro.pk,
                                estudio_id=estudio.pk,
                                grupo_codigo=codigo_ctx,
                                contexto=contexto,
                                fecha=fecha_ref,
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
                                registro_id=registro.pk,
                                estudio_id=estudio.pk,
                                grupo_id=grupo_ctx.pk,
                                grupo_codigo=codigo_ctx,
                                contexto=contexto,
                                fecha=fecha_ref,
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
                        registro_id=registro.pk,
                        estudio_id=estudio.pk,
                        fecha=fecha_ref,
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
                        registro_id=registro.pk,
                        estudio_id=estudio.pk,
                        fecha=fecha_ref,
                    )

    for guardia in guardias:
        if _es_monto_cero(guardia.monto):
            _agregar_issue(
                resultado,
                TIPO_GUARDIA_MONTO_INVALIDO,
                f'Guardia #{guardia.pk} con monto <= 0.',
                estado_destino,
                guardia_id=guardia.pk,
                fecha=getattr(guardia, 'fecha_guardia', None),
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
        sesion.practicas.filter(anulado=False).select_related('medico').prefetch_related('registroestudio_set__estudio')
        .filter(medico__rol__in=ROLES_AUDITORIA_RESIDENCIA_ECO)
    )
    if not practicas:
        return resultado

    registro_ids = [registro.pk for registro in practicas]
    revisiones_eges_requieren_correccion = set()
    revisiones_eges = (
        RevisionCruceEgesRegistro.objects
        .filter(sesion_contable=sesion, registro_id__in=registro_ids)
        .order_by('registro_id', '-fecha_revision')
    )
    ultimas_revisiones_eges = {}
    for revision in revisiones_eges:
        ultimas_revisiones_eges.setdefault(revision.registro_id, revision)
    revisiones_eges_requieren_correccion = {
        registro_id
        for registro_id, revision in ultimas_revisiones_eges.items()
        if revision.estado == RevisionCruceEgesRegistro.ESTADO_REQUIERE_CORRECCION
    }

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

        if not any(rel.estudio.tipo in TIPOS_AUDITORIA_RESIDENCIA_ECO for rel in relaciones):
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
                '_registros_eco': [],
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
        motivos_registro = []
        if registro.pk in revisiones_eges_requieren_correccion:
            motivos_registro.append('EGES requiere correccion')
        if registro.horario == 'EXTRA':
            motivos_registro.append('EXTRA')
        if hora_local >= AUDIT_HORA_NOCTURNA_DESDE or hora_local < AUDIT_HORA_NOCTURNA_HASTA:
            motivos_registro.append('Nocturno')
        if es_finde or es_feriado:
            motivos_registro.append('Finde/Feriado')
        elif hora_local >= AUDIT_HORA_POST_17:
            motivos_registro.append('Post 17')

        item['_registros_eco'].append({
            'registro_id': registro.pk,
            'fecha_informe': registro.fecha_del_informe.isoformat() if registro.fecha_del_informe else '',
            'fecha_carga': dt.isoformat(),
            'fecha_local': fecha_local.isoformat(),
            'estudios': ', '.join(
                rel.estudio.nombre
                for rel in relaciones
                if rel.estudio.tipo in TIPOS_AUDITORIA_RESIDENCIA_ECO
            ),
            'paciente': f'{registro.apellido_paciente}, {registro.nombre_paciente}',
            'dni_paciente': registro.dni_paciente,
            'horario': registro.horario,
            'monto_calculado': registro.monto_calculado,
            'motivos': motivos_registro,
        })

    items = []
    for item in acumulado.values():
        total_eco = item['total_eco']
        if total_eco <= 0:
            continue

        item['proporcion_extra'] = item['extra'] / total_eco

        eco_por_dia = item.pop('_eco_por_dia')
        registros_eco = item.pop('_registros_eco')
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
        registros_eges_requieren_correccion = sum(
            1
            for registro_alerta in registros_eco
            if 'EGES requiere correccion' in registro_alerta.get('motivos', [])
        )
        _agregar_alerta(
            item['alertas'],
            'eges_requiere_correccion',
            registros_eges_requieren_correccion,
            1,
            1,
            'Cruce EGES requiere correccion',
        )

        if any(alerta['severidad'] == 'roja' for alerta in item['alertas']):
            item['severidad'] = 'roja'
        elif item['alertas']:
            item['severidad'] = 'amarilla'
        else:
            item['severidad'] = 'ok'

        dias_pico = set(item['dias_pico'])
        for registro_alerta in registros_eco:
            if registro_alerta['fecha_local'] in dias_pico and 'Dia pico' not in registro_alerta['motivos']:
                registro_alerta['motivos'].append('Dia pico')

        tipos_alerta = {alerta['tipo'] for alerta in item['alertas']}
        registros_alerta = []
        for registro_alerta in registros_eco:
            motivos = set(registro_alerta['motivos'])
            aporta = (
                ({'extra_mensual', 'proporcion_extra'} & tipos_alerta and 'EXTRA' in motivos)
                or ('nocturnos' in tipos_alerta and 'Nocturno' in motivos)
                or ('finde_feriado' in tipos_alerta and 'Finde/Feriado' in motivos)
                or ('volumen_diario' in tipos_alerta and 'Dia pico' in motivos)
                or ('eges_requiere_correccion' in tipos_alerta and 'EGES requiere correccion' in motivos)
            )
            if aporta:
                registros_alerta.append(registro_alerta)

        registros_alerta.sort(key=lambda registro: registro['fecha_carga'], reverse=True)
        item['registros_alerta'] = registros_alerta
        item['registros_alerta_total'] = len(registros_alerta)

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


def resumir_pendientes_auditoria_eco(auditoria):
    """
    Agrega una lectura operativa de pendientes sin alterar la auditoria bruta.

    La deteccion de patrones ECO conserva todos los hallazgos. Para paneles de
    cierre, en cambio, solo debe quedar pendiente lo que todavia requiere accion:
    registros sin revision o con revision "requiere correccion" sin ajuste PACS.
    """
    from .models import (
        CorreccionPacsRegistro,
        RevisionAuditoriaEcoRegistro,
        RevisionCruceEgesRegistro,
    )

    registro_ids = [
        registro_alerta.get('registro_id')
        for item in auditoria.get('items', [])
        for registro_alerta in item.get('registros_alerta', [])
        if registro_alerta.get('registro_id')
    ]
    registro_ids = list(dict.fromkeys(registro_ids))

    revisiones_por_registro = {}
    if registro_ids:
        revisiones = (
            RevisionAuditoriaEcoRegistro.objects
            .filter(registro_id__in=registro_ids)
            .order_by('registro_id', '-fecha_revision')
        )
        for revision in revisiones:
            revisiones_por_registro.setdefault(revision.registro_id, revision)

    revisiones_eges_por_registro = {}
    if registro_ids:
        revisiones_eges = (
            RevisionCruceEgesRegistro.objects
            .filter(registro_id__in=registro_ids)
            .order_by('registro_id', '-fecha_revision')
        )
        for revision in revisiones_eges:
            revisiones_eges_por_registro.setdefault(revision.registro_id, revision)

    registros_con_correccion = set()
    if registro_ids:
        registros_con_correccion = set(
            CorreccionPacsRegistro.objects
            .filter(registro_id__in=registro_ids)
            .values_list('registro_id', flat=True)
        )

    items_pendientes = []
    alertas_rojas_pendientes = 0
    alertas_amarillas_pendientes = 0
    registros_pendientes_total = 0

    for item in auditoria.get('items', []):
        registros_pendientes = []
        for registro_alerta in item.get('registros_alerta', []):
            registro_id = registro_alerta.get('registro_id')
            revision = revisiones_por_registro.get(registro_id)
            revision_eges = revisiones_eges_por_registro.get(registro_id)
            tiene_correccion = registro_id in registros_con_correccion

            pendiente = (
                revision is None
                or (
                    revision.estado == RevisionAuditoriaEcoRegistro.ESTADO_REQUIERE_CORRECCION
                    and not tiene_correccion
                )
            )
            if revision is None and revision_eges:
                pendiente = revision_eges.estado == RevisionCruceEgesRegistro.ESTADO_REQUIERE_CORRECCION
            registro_alerta['auditoria_eco_pendiente'] = pendiente
            if pendiente:
                registros_pendientes.append(registro_alerta)

        item['registros_alerta_pendientes'] = registros_pendientes
        item['registros_alerta_pendientes_total'] = len(registros_pendientes)
        item['auditoria_eco_pendiente'] = bool(registros_pendientes)

        if registros_pendientes:
            items_pendientes.append(item)
            registros_pendientes_total += len(registros_pendientes)
            alertas_rojas_pendientes += sum(
                1 for alerta in item.get('alertas', [])
                if alerta.get('severidad') == 'roja'
            )
            alertas_amarillas_pendientes += sum(
                1 for alerta in item.get('alertas', [])
                if alerta.get('severidad') == 'amarilla'
            )

    orden_severidad = {'roja': 0, 'amarilla': 1, 'ok': 2}
    top_pendientes = sorted(
        items_pendientes,
        key=lambda item: (
            orden_severidad.get(item.get('severidad'), 9),
            -item.get('registros_alerta_pendientes_total', 0),
            item.get('medico_nombre') or '',
        ),
    )

    auditoria['items_pendientes'] = items_pendientes
    auditoria['residentes_con_alertas_pendientes'] = len(items_pendientes)
    auditoria['registros_alerta_pendientes_total'] = registros_pendientes_total
    auditoria['alertas_rojas_pendientes'] = alertas_rojas_pendientes
    auditoria['alertas_amarillas_pendientes'] = alertas_amarillas_pendientes
    auditoria['top_alertas_pendientes'] = [
        {
            'medico_id': item.get('medico_id'),
            'medico_nombre': item.get('medico_nombre'),
            'severidad': item.get('severidad'),
            'cantidad_alertas': len(item.get('alertas', [])),
            'registros_pendientes': item.get('registros_alerta_pendientes_total', 0),
        }
        for item in top_pendientes[:3]
    ]

    return auditoria
