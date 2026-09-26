from django.db.models import Prefetch, Q

from .models import DestinatarioExamen, Examen, IntentoExamen


ROLES_DOCENTES = {
    'instructor_residentes',
    'jefe_residentes',
    'jefe_servicio',
}


def usuario_puede_gestionar(usuario):
    return usuario.is_superuser or usuario.rol in ROLES_DOCENTES


def examenes_para_docente(usuario):
    queryset = Examen.objects.select_related('creador').prefetch_related('preguntas')
    if usuario.is_superuser or usuario.rol in {'jefe_residentes', 'jefe_servicio'}:
        return queryset
    return queryset.filter(Q(creador=usuario) | Q(creador__rol__in=ROLES_DOCENTES)).distinct()


def examen_para_edicion(usuario, examen_id):
    return examenes_para_docente(usuario).filter(
        pk=examen_id,
        estado=Examen.BORRADOR,
    ).first()


def intentos_para_docente(usuario, examen_id):
    """Retorna los intentos del examen si el usuario puede gestionarlo."""
    examen_ids = examenes_para_docente(usuario).filter(pk=examen_id).values('pk')
    return (
        IntentoExamen.objects
        .filter(examen_id__in=examen_ids)
        .select_related('examen', 'residente')
        .prefetch_related('respuestas__pregunta')
    )


def asignaciones_para_residente(usuario):
    return DestinatarioExamen.objects.filter(
        residente=usuario,
        examen__estado__in=[Examen.PUBLICADO, Examen.CERRADO],
    ).select_related('examen').prefetch_related(
        'examen__preguntas',
        Prefetch(
            'examen__intentos',
            queryset=IntentoExamen.objects.filter(residente=usuario),
            to_attr='intento_del_residente',
        ),
    )


def asignacion_para_residente(usuario, examen_id):
    return asignaciones_para_residente(usuario).filter(examen_id=examen_id).first()


def intento_para_residente(usuario, examen_id):
    return (
        IntentoExamen.objects
        .filter(examen_id=examen_id, residente=usuario)
        .select_related('examen')
        .prefetch_related(
            'respuestas__pregunta__opciones',
            'respuestas__pregunta__imagenes',
            'respuestas__opciones_elegidas__opcion',
        )
        .first()
    )
