from decimal import Decimal, ROUND_HALF_UP

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.utils import timezone

from .exceptions import (
    EvaluacionNoDisponibleError,
    PermisoEvaluacionError,
    RespuestasInvalidasError,
    TransicionEvaluacionError,
)
from .models import (
    DestinatarioExamen,
    Examen,
    IntentoExamen,
    Opcion,
    Pregunta,
    Respuesta,
    RespuestaOpcion,
)


ROLES_PUBLICADORES = {
    'instructor_residentes',
    'jefe_residentes',
    'jefe_servicio',
}
User = get_user_model()


def _puede_gestionar_examen(usuario, examen):
    return (
        usuario.is_superuser
        or usuario == examen.creador
        or usuario.rol in ROLES_PUBLICADORES
    )


def publicar_examen(examen, usuario, ahora=None):
    """Valida y publica un borrador; desde ese momento queda congelado."""
    with transaction.atomic():
        examen = Examen.objects.select_for_update().get(pk=examen.pk)
        if not _puede_gestionar_examen(usuario, examen):
            raise PermisoEvaluacionError('El usuario no puede publicar este examen.')
        if examen.estado != Examen.BORRADOR:
            raise TransicionEvaluacionError('Solo se puede publicar un examen borrador.')

        preguntas = list(examen.preguntas.prefetch_related('opciones').all())
        if not preguntas:
            raise TransicionEvaluacionError('El examen debe tener al menos una pregunta.')
        if not examen.ciclo_lectivo.strip() or examen.ciclo_lectivo == 'SIN_DEFINIR':
            raise TransicionEvaluacionError('El examen debe tener un ciclo lectivo.')

        for pregunta in preguntas:
            opciones = list(pregunta.opciones.all())
            correctas = [opcion for opcion in opciones if opcion.es_correcta]
            if pregunta.tipo == Pregunta.DESARROLLO and opciones:
                raise TransicionEvaluacionError(
                    f'La pregunta {pregunta.orden} no puede tener opciones.'
                )
            if pregunta.tipo != Pregunta.DESARROLLO and len(opciones) < 2:
                raise TransicionEvaluacionError(
                    f'La pregunta {pregunta.orden} debe tener al menos dos opciones.'
                )
            if pregunta.tipo in {Pregunta.OPCION_UNICA, Pregunta.VERDADERO_FALSO} and len(correctas) != 1:
                raise TransicionEvaluacionError(
                    f'La pregunta {pregunta.orden} debe tener exactamente una correcta.'
                )
            if pregunta.tipo == Pregunta.OPCION_MULTIPLE and not correctas:
                raise TransicionEvaluacionError(
                    f'La pregunta {pregunta.orden} debe tener al menos una correcta.'
                )

        if examen.modo_destinatarios == Examen.TODOS:
            if examen.anios_destinatarios or examen.residentes_destinatarios.exists():
                raise TransicionEvaluacionError('El modo Todos no admite filtros adicionales.')
            destinatarios = User.objects.filter(
                is_active=True,
                rol='medico_residente',
                estado_residencia='ACTIVO',
                anio_residencia__in=[anio for anio, _ in Examen.ANIOS_RESIDENCIA],
            )
        elif examen.modo_destinatarios == Examen.ANIOS:
            if not examen.anios_destinatarios or examen.residentes_destinatarios.exists():
                raise TransicionEvaluacionError('El modo por años requiere solo uno o varios años.')
            destinatarios = User.objects.filter(
                is_active=True,
                rol='medico_residente',
                estado_residencia='ACTIVO',
                anio_residencia__in=examen.anios_destinatarios,
            )
        elif examen.modo_destinatarios == Examen.RESIDENTES:
            if examen.anios_destinatarios:
                raise TransicionEvaluacionError('El modo por residentes no admite años.')
            destinatarios = examen.residentes_destinatarios.filter(
                is_active=True,
                rol='medico_residente',
                estado_residencia='ACTIVO',
            )
            seleccionados = examen.residentes_destinatarios.count()
            if destinatarios.count() != seleccionados:
                raise TransicionEvaluacionError('Todos los residentes seleccionados deben estar activos.')
        else:
            raise TransicionEvaluacionError('El modo de destinatarios no es válido.')

        destinatarios = list(destinatarios)
        if not destinatarios:
            raise TransicionEvaluacionError('El examen no tiene residentes activos destinatarios.')

        ahora = ahora or timezone.now()
        examen.estado = Examen.PUBLICADO
        examen.fecha_publicacion = ahora
        examen.save(update_fields=['estado', 'fecha_publicacion', 'actualizado_en'])
        DestinatarioExamen.objects.bulk_create([
            DestinatarioExamen(
                examen=examen,
                residente=residente,
                anio_residencia_al_asignar=residente.anio_residencia,
                ciclo_lectivo=examen.ciclo_lectivo,
                criterio_origen=examen.modo_destinatarios,
            )
            for residente in destinatarios
        ])
    return examen


def cerrar_examenes_vencidos(ahora=None):
    """Marca como cerradas las evaluaciones publicadas cuyo plazo ya venció."""
    ahora = ahora or timezone.now()
    return Examen.objects.filter(
        estado=Examen.PUBLICADO,
        fecha_vencimiento__lte=ahora,
    ).update(
        estado=Examen.CERRADO,
        fecha_cierre=ahora,
        actualizado_en=ahora,
    )


def iniciar_examen_manual(examen, usuario, ahora=None):
    ahora = ahora or timezone.now()
    if not _puede_gestionar_examen(usuario, examen):
        raise PermisoEvaluacionError('El usuario no puede iniciar este examen.')
    if examen.estado != Examen.PUBLICADO:
        raise TransicionEvaluacionError('Solo se puede iniciar un examen publicado.')
    if examen.modo_inicio != Examen.INICIO_MANUAL:
        raise TransicionEvaluacionError('Este examen se inicia automáticamente por fecha.')
    if examen.iniciado_en:
        raise TransicionEvaluacionError('El examen ya fue iniciado.')
    if ahora >= examen.fecha_vencimiento:
        raise EvaluacionNoDisponibleError('El plazo del examen ya venció.')

    examen.iniciado_en = ahora
    examen.save(update_fields=['iniciado_en', 'actualizado_en'])
    return examen


def finalizar_examen(examen, usuario, ahora=None):
    ahora = ahora or timezone.now()
    if not _puede_gestionar_examen(usuario, examen):
        raise PermisoEvaluacionError('El usuario no puede finalizar este examen.')
    if examen.estado != Examen.PUBLICADO:
        raise TransicionEvaluacionError('Solo se puede finalizar un examen publicado.')

    examen.estado = Examen.CERRADO
    examen.fecha_cierre = ahora
    examen.save(update_fields=['estado', 'fecha_cierre', 'actualizado_en'])
    return examen


def anular_intento(intento, usuario, motivo, ahora=None):
    """Anula un intento sin borrar respuestas ni alterar su historial."""
    ahora = ahora or timezone.now()
    motivo = str(motivo or '').strip()
    if not _puede_gestionar_examen(usuario, intento.examen):
        raise PermisoEvaluacionError('El usuario no puede anular este intento.')
    if not motivo:
        raise RespuestasInvalidasError('La anulación requiere un motivo.')
    if intento.estado == IntentoExamen.ANULADO:
        raise TransicionEvaluacionError('El intento ya está anulado.')

    with transaction.atomic():
        intento = IntentoExamen.objects.select_for_update().get(pk=intento.pk)
        if intento.estado == IntentoExamen.ANULADO:
            raise TransicionEvaluacionError('El intento ya está anulado.')
        intento.estado = IntentoExamen.ANULADO
        intento.anulado_en = ahora
        intento.anulado_por = usuario
        intento.motivo_anulacion = motivo
        intento.resultado_publicado_en = None
        intento.save(update_fields=[
            'estado', 'anulado_en', 'anulado_por', 'motivo_anulacion',
            'resultado_publicado_en',
        ])
    return intento


def recuperar_intento(intento, usuario, motivo, ahora=None):
    """Reabre un intento anulado dentro del período vigente, sin crear otro."""
    ahora = ahora or timezone.now()
    motivo = str(motivo or '').strip()
    if not _puede_gestionar_examen(usuario, intento.examen):
        raise PermisoEvaluacionError('El usuario no puede recuperar este intento.')
    if not motivo:
        raise RespuestasInvalidasError('La recuperación requiere un motivo.')
    if intento.estado != IntentoExamen.ANULADO:
        raise TransicionEvaluacionError('Solo se puede recuperar un intento anulado.')
    if intento.examen.estado != Examen.PUBLICADO or not intento.examen.esta_disponible_para(
        intento.residente,
        ahora=ahora,
    ):
        raise EvaluacionNoDisponibleError(
            'El examen no está disponible para recuperar este intento.'
        )

    with transaction.atomic():
        intento = IntentoExamen.objects.select_for_update().get(pk=intento.pk)
        if intento.estado != IntentoExamen.ANULADO:
            raise TransicionEvaluacionError('El intento ya no está anulado.')
        intento.estado = IntentoExamen.INICIADO
        intento.entregado_en = None
        intento.puntaje_obtenido = None
        intento.porcentaje = None
        intento.nota_final = None
        intento.resultado_publicado_en = None
        intento.recuperado_en = ahora
        intento.recuperado_por = usuario
        intento.motivo_recuperacion = motivo
        intento.save(update_fields=[
            'estado', 'entregado_en', 'puntaje_obtenido', 'porcentaje',
            'nota_final', 'resultado_publicado_en', 'recuperado_en',
            'recuperado_por', 'motivo_recuperacion',
        ])
    return intento


def eliminar_borrador(examen, usuario):
    """Elimina un borrador y sus archivos asociados de forma controlada."""
    if not _puede_gestionar_examen(usuario, examen):
        raise PermisoEvaluacionError('El usuario no puede eliminar este examen.')
    if examen.estado != Examen.BORRADOR:
        raise TransicionEvaluacionError('Solo se pueden eliminar evaluaciones en borrador.')

    with transaction.atomic():
        examen = Examen.objects.select_for_update().get(pk=examen.pk)
        if examen.estado != Examen.BORRADOR:
            raise TransicionEvaluacionError('Solo se pueden eliminar evaluaciones en borrador.')

        preguntas = list(examen.preguntas.prefetch_related('imagenes').all())
        for pregunta in preguntas:
            if pregunta.imagen:
                pregunta.imagen.delete(save=False)
            for imagen in pregunta.imagenes.all():
                imagen.archivo.delete(save=False)
        examen.delete()


def iniciar_intento(examen, residente, ahora=None):
    ahora = ahora or timezone.now()
    if not examen.esta_disponible_para(residente, ahora=ahora):
        raise EvaluacionNoDisponibleError('El examen no está disponible para este residente.')

    try:
        with transaction.atomic():
            return IntentoExamen.objects.create(examen=examen, residente=residente)
    except IntegrityError as exc:
        raise TransicionEvaluacionError('El residente ya tiene un intento para este examen.') from exc


def iniciar_o_reanudar_intento(examen, residente, ahora=None):
    ahora = ahora or timezone.now()
    if not examen.esta_disponible_para(residente, ahora=ahora):
        raise EvaluacionNoDisponibleError('El examen no está disponible en este momento.')
    intento = examen.intentos.filter(
        residente=residente,
        estado=IntentoExamen.INICIADO,
    ).first()
    if intento:
        return intento
    return iniciar_intento(examen, residente, ahora=ahora)


def guardar_respuesta(intento, pregunta, respuesta_recibida):
    if intento.estado != IntentoExamen.INICIADO:
        raise TransicionEvaluacionError('El intento no está activo.')
    if intento.examen_id != pregunta.examen_id:
        raise RespuestasInvalidasError('La pregunta no pertenece a este examen.')
    if timezone.now() >= intento.examen.fecha_vencimiento:
        raise EvaluacionNoDisponibleError('El período de la evaluación ya terminó.')

    with transaction.atomic():
        respuesta, _ = Respuesta.objects.update_or_create(
            intento=intento,
            pregunta=pregunta,
            defaults={'texto_desarrollo': '', 'puntaje_obtenido': Decimal('0'), 'es_correcta': False, 'requiere_correccion': False},
        )
        RespuestaOpcion.objects.filter(respuesta=respuesta).delete()
        if pregunta.tipo == Pregunta.DESARROLLO:
            respuesta.texto_desarrollo = str(respuesta_recibida or '').strip()
            respuesta.requiere_correccion = True
            respuesta.save(update_fields=['texto_desarrollo', 'requiere_correccion'])
            return respuesta

        if isinstance(respuesta_recibida, (list, tuple)):
            ids = {int(opcion_id) for opcion_id in respuesta_recibida}
        elif respuesta_recibida:
            ids = {int(respuesta_recibida)}
        else:
            ids = set()
        opciones = list(pregunta.opciones.filter(pk__in=ids))
        if len(opciones) != len(ids):
            raise RespuestasInvalidasError('Hay opciones inválidas para esta pregunta.')
        if pregunta.tipo in {Pregunta.OPCION_UNICA, Pregunta.VERDADERO_FALSO} and len(ids) > 1:
            raise RespuestasInvalidasError('La pregunta admite una sola opción.')
        RespuestaOpcion.objects.bulk_create([RespuestaOpcion(respuesta=respuesta, opcion=opcion) for opcion in opciones])
        return respuesta


def entregar_intento(intento, respuestas, ahora=None):
    """Guarda, corrige y cierra un intento de forma atómica."""
    ahora = ahora or timezone.now()
    if intento.estado != IntentoExamen.INICIADO:
        raise TransicionEvaluacionError('Solo se puede entregar un intento iniciado.')
    if ahora >= intento.examen.fecha_vencimiento:
        raise EvaluacionNoDisponibleError('El plazo de entrega ya venció.')

    preguntas = list(intento.examen.preguntas.prefetch_related('opciones').all())
    preguntas_por_id = {pregunta.pk: pregunta for pregunta in preguntas}
    respuestas_normalizadas = {
        int(pregunta_id): respuesta
        for pregunta_id, respuesta in respuestas.items()
    }
    ids_invalidos = set(respuestas_normalizadas) - set(preguntas_por_id)
    if ids_invalidos:
        raise RespuestasInvalidasError('Hay respuestas para preguntas ajenas al examen.')

    opciones_por_id = {
        opcion.pk: opcion
        for pregunta in preguntas
        for opcion in pregunta.opciones.all()
    }
    with transaction.atomic():
        intento = IntentoExamen.objects.select_for_update().select_related('examen').get(pk=intento.pk)
        if intento.estado != IntentoExamen.INICIADO:
            raise TransicionEvaluacionError('El intento ya fue entregado.')
        if ahora >= intento.examen.fecha_vencimiento:
            raise EvaluacionNoDisponibleError('El plazo de entrega ya venció.')

        puntaje_total = Decimal('0')
        requiere_correccion = False
        for pregunta in preguntas:
            respuesta_recibida = respuestas_normalizadas.get(pregunta.pk)
            if pregunta.tipo == Pregunta.DESARROLLO:
                texto = str(respuesta_recibida or '').strip()
                requiere_correccion = True
                Respuesta.objects.update_or_create(
                    intento=intento,
                    pregunta=pregunta,
                    defaults={
                        'texto_desarrollo': texto,
                        'puntaje_obtenido': Decimal('0'),
                        'es_correcta': False,
                        'requiere_correccion': True,
                    },
                )
                continue

            if respuesta_recibida is None:
                ids_seleccionados = set()
            elif isinstance(respuesta_recibida, (list, tuple, set)):
                ids_seleccionados = {int(opcion_id) for opcion_id in respuesta_recibida}
            else:
                ids_seleccionados = {int(respuesta_recibida)}
            opciones_seleccionadas = {
                opciones_por_id.get(opcion_id) for opcion_id in ids_seleccionados
            }
            if None in opciones_seleccionadas or any(
                opcion.pregunta_id != pregunta.pk for opcion in opciones_seleccionadas
            ):
                raise RespuestasInvalidasError('Hay opciones ajenas a la pregunta.')
            if pregunta.tipo in {Pregunta.OPCION_UNICA, Pregunta.VERDADERO_FALSO} and len(ids_seleccionados) > 1:
                raise RespuestasInvalidasError('La pregunta admite una sola opción.')

            correctas = {
                opcion.pk for opcion in pregunta.opciones.all() if opcion.es_correcta
            }
            es_correcta = ids_seleccionados == correctas and bool(ids_seleccionados)
            puntaje = pregunta.puntaje if es_correcta else Decimal('0')
            puntaje_total += puntaje
            respuesta, _ = Respuesta.objects.update_or_create(
                intento=intento,
                pregunta=pregunta,
                defaults={
                    'texto_desarrollo': '',
                    'puntaje_obtenido': puntaje,
                    'es_correcta': es_correcta,
                    'requiere_correccion': False,
                },
            )
            RespuestaOpcion.objects.filter(respuesta=respuesta).delete()
            RespuestaOpcion.objects.bulk_create([
                RespuestaOpcion(respuesta=respuesta, opcion_id=opcion_id)
                for opcion_id in ids_seleccionados
            ])

        puntaje_maximo = intento.examen.puntaje_maximo
        porcentaje = (
            (puntaje_total / puntaje_maximo * Decimal('100')).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            )
            if puntaje_maximo
            else Decimal('0')
        )
        intento.estado = (
            IntentoExamen.PENDIENTE_CORRECCION
            if requiere_correccion
            else IntentoExamen.CORREGIDO
        )
        intento.entregado_en = ahora
        intento.puntaje_obtenido = puntaje_total
        intento.porcentaje = porcentaje
        intento.nota_final = (porcentaje / Decimal('10')).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )
        intento.save(update_fields=[
            'estado', 'entregado_en', 'puntaje_obtenido', 'porcentaje', 'nota_final',
        ])

    return intento


def corregir_respuesta_desarrollo(respuesta, puntaje, comentario, usuario):
    if not _puede_gestionar_examen(usuario, respuesta.intento.examen):
        raise PermisoEvaluacionError('El usuario no puede corregir esta respuesta.')
    if respuesta.pregunta.tipo != Pregunta.DESARROLLO:
        raise TransicionEvaluacionError('La respuesta no requiere corrección manual.')
    if puntaje < 0 or puntaje > respuesta.pregunta.puntaje:
        raise RespuestasInvalidasError('El puntaje está fuera del rango de la pregunta.')

    respuesta.puntaje_obtenido = puntaje
    respuesta.es_correcta = puntaje == respuesta.pregunta.puntaje
    respuesta.requiere_correccion = False
    respuesta.comentario_docente = comentario or ''
    respuesta.save(update_fields=[
        'puntaje_obtenido', 'es_correcta', 'requiere_correccion', 'comentario_docente',
    ])
    return respuesta


def finalizar_correccion_manual(intento, usuario):
    if not _puede_gestionar_examen(usuario, intento.examen):
        raise PermisoEvaluacionError('El usuario no puede finalizar esta corrección.')
    if intento.estado != IntentoExamen.PENDIENTE_CORRECCION:
        raise TransicionEvaluacionError('El intento no está pendiente de corrección.')
    if intento.respuestas.filter(requiere_correccion=True).exists():
        raise TransicionEvaluacionError('Aún quedan respuestas por corregir.')

    puntaje_total = sum(
        (respuesta.puntaje_obtenido for respuesta in intento.respuestas.all()),
        Decimal('0'),
    )
    puntaje_maximo = intento.examen.puntaje_maximo
    porcentaje = (
        (puntaje_total / puntaje_maximo * Decimal('100')).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )
        if puntaje_maximo
        else Decimal('0')
    )
    intento.estado = IntentoExamen.CORREGIDO
    intento.puntaje_obtenido = puntaje_total
    intento.porcentaje = porcentaje
    intento.nota_final = (porcentaje / Decimal('10')).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP
    )
    intento.save(update_fields=['estado', 'puntaje_obtenido', 'porcentaje', 'nota_final'])
    return intento


def publicar_resultado(intento, usuario, ahora=None):
    if not _puede_gestionar_examen(usuario, intento.examen):
        raise PermisoEvaluacionError('El usuario no puede publicar este resultado.')
    if intento.estado != IntentoExamen.CORREGIDO:
        raise TransicionEvaluacionError('Solo se puede publicar un resultado corregido.')

    intento.resultado_publicado_en = ahora or timezone.now()
    intento.save(update_fields=['resultado_publicado_en'])
    return intento
