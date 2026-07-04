"""
services.py — Lógica de negocio del módulo preinformes.

Funciones que operan sobre datos y aplican reglas de negocio sin depender
del ciclo HTTP. Son reutilizables desde vistas, tareas async y tests.
"""
import logging

from django.db.models import Q
from django.utils import timezone

logger = logging.getLogger(__name__)


def evaluar_sesion_mentor(preinforme, conversacion_id=None):
    """
    Intenta evaluar automáticamente la sesión del Mentor IA asociada al envío.

    No bloquea el envío a revisión si falla la IA o si no hay conversación
    evaluable. En todos los casos deja trazabilidad en logs.

    Parámetros:
        preinforme      : instancia de Preinforme recién enviada a revisión
        conversacion_id : pk opcional de ConversacionAsistentePreinforme
                          a evaluar; si es None se busca la más reciente

    Retorna:
        dict con clave 'success' (bool) y opcionalmente 'skipped' / 'error'
    """
    from .models import ConversacionAsistentePreinforme
    from .asistente_service import AsistenteRadiologicoBot

    conversaciones = ConversacionAsistentePreinforme.objects.filter(
        usuario=preinforme.residente,
        fecha_actualizacion__gte=timezone.now() - timezone.timedelta(hours=24),
    ).order_by('-fecha_actualizacion')

    conversacion = None
    if conversacion_id:
        conversacion = conversaciones.filter(id=conversacion_id).first()

    if conversacion is None:
        conversacion = conversaciones.filter(
            Q(preinforme=preinforme) | Q(preinforme__isnull=True)
        ).first()

    if conversacion is None:
        logger.info(
            'Mentor IA: no se encontró conversación evaluable para preinforme %s',
            preinforme.pk,
        )
        return {'success': False, 'skipped': 'no_conversation'}

    if conversacion.preinforme_id != preinforme.id:
        conversacion.preinforme = preinforme
        conversacion.save(update_fields=['preinforme'])

    if conversacion.evaluada:
        logger.info(
            'Mentor IA: conversación %s ya estaba evaluada para preinforme %s',
            conversacion.id,
            preinforme.pk,
        )
        return {'success': True, 'skipped': 'already_evaluated'}

    resultado = AsistenteRadiologicoBot().evaluar_conversacion(conversacion.id)
    if resultado.get('success'):
        logger.info(
            'Mentor IA: autoevaluación generada para conversación %s (preinforme %s)',
            conversacion.id,
            preinforme.pk,
        )
    elif resultado.get('insufficient'):
        logger.info(
            'Mentor IA: conversación %s no reúne mensajes suficientes para evaluar',
            conversacion.id,
        )
    else:
        logger.warning(
            'Mentor IA: fallo autoevaluación de conversación %s para preinforme %s: %s',
            conversacion.id,
            preinforme.pk,
            resultado.get('error'),
        )

    return resultado


def obtener_o_preparar_revision(preinforme, revisor):
    """
    Devuelve la RevisionPreinforme lista para editar.

    Responsabilidades:
    - crear la revision si todavia no existe;
    - congelar una vez el informe enviado por el residente;
    - precargar el editor del staff si aun no tiene contenido.

    Mantener esta regla fuera de la vista evita divergencias entre revision
    inicial, continuacion y edicion posterior de finalizados.
    """
    from .models import RevisionPreinforme

    revision, created = RevisionPreinforme.objects.get_or_create(
        preinforme=preinforme,
        defaults={'revisor': revisor},
    )

    campos_actualizados = []

    if not revision.informe_residente_snapshot:
        revision.informe_residente_snapshot = preinforme.get_informe_html_or_legacy() or ""
        campos_actualizados.append('informe_residente_snapshot')

    if not revision.informe_final_html:
        revision.informe_final_html = revision.informe_residente_snapshot
        campos_actualizados.append('informe_final_html')

    if campos_actualizados:
        revision.save(update_fields=campos_actualizados)

    return revision, created
