from decimal import Decimal

from .models import GrupoTarifario


TIPO_SIN_REGISTRO_ESTUDIO = 'sin_registro_estudio'
TIPO_MONTO_CERO_CON_ESTUDIOS = 'monto_cero_con_estudios'
TIPO_GUARDIA_MONTO_INVALIDO = 'guardia_monto_invalido'
TIPO_SESION_VACIA = 'sesion_vacia'
TIPO_SIN_GRUPO_CON_FALLBACK = 'sin_grupo_con_fallback'
TIPO_SIN_PRECIO_RESOLUBLE = 'sin_precio_resoluble'
TIPO_SIN_TARIFA_VIGENTE_GRUPO = 'sin_tarifa_vigente_grupo'
TIPO_CONTEXTUAL_SIN_GRUPO = 'contextual_sin_grupo'
TIPO_CONTEXTUAL_SIN_TARIFA = 'contextual_sin_tarifa'


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
