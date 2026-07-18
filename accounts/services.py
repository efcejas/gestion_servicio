from datetime import date

from django.db import transaction
from django.utils import timezone

from .models import CustomUser, NotificacionCicloResidencia


ANIOS_RESIDENCIA = ('R1', 'R2', 'R3', 'R4')


def ultimo_cierre_habilitado(fecha_referencia=None):
    """Devuelve el cierre más reciente (el cambio de ciclo ocurre el 1 de agosto)."""
    referencia = fecha_referencia or timezone.localdate()
    return referencia.year if (referencia.month, referencia.day) >= (8, 1) else referencia.year - 1


@transaction.atomic
def procesar_cierre_residencia(fecha_referencia=None, cierre_anio=None, dry_run=False):
    """Promueve, retiene o egresa residentes; puede ejecutarse varias veces sin duplicar cambios."""
    cierre = cierre_anio or ultimo_cierre_habilitado(fecha_referencia)
    fecha_egreso = date(cierre, 8, 1)
    resultado = {'cierre': cierre, 'promovidos': [], 'repetidores': [], 'egresados': [], 'omitidos': []}

    residentes = (
        CustomUser.objects.select_for_update()
        .filter(rol='medico_residente', estado_residencia='ACTIVO', is_active=True)
        .order_by('last_name', 'first_name', 'pk')
    )

    for residente in residentes:
        if residente.ultimo_cierre_residencia is not None and residente.ultimo_cierre_residencia >= cierre:
            resultado['omitidos'].append(residente)
            continue

        anio_actual = residente.anio_residencia
        if anio_actual not in ANIOS_RESIDENCIA:
            resultado['omitidos'].append(residente)
            continue

        if residente.repite_anio_residencia:
            resultado['repetidores'].append((residente, anio_actual))
            if not dry_run:
                residente.repite_anio_residencia = False
                residente.ultimo_cierre_residencia = cierre
                residente.save(update_fields=['repite_anio_residencia', 'ultimo_cierre_residencia'])
            continue

        if anio_actual == 'R4':
            resultado['egresados'].append(residente)
            if not dry_run:
                residente.estado_residencia = 'EGRESADO'
                residente.fecha_egreso_residencia = fecha_egreso
                residente.anio_residencia = None
                residente.ultimo_cierre_residencia = cierre
                residente.save(update_fields=[
                    'estado_residencia', 'fecha_egreso_residencia',
                    'anio_residencia', 'ultimo_cierre_residencia',
                ])
                NotificacionCicloResidencia.objects.update_or_create(
                    usuario=residente,
                    cierre_anio=cierre,
                    defaults={
                        'tipo': NotificacionCicloResidencia.TIPO_EGRESO,
                        'anio_anterior': anio_actual,
                        'anio_nuevo': None,
                        'vista_en': None,
                    },
                )
            continue

        anio_nuevo = ANIOS_RESIDENCIA[ANIOS_RESIDENCIA.index(anio_actual) + 1]
        resultado['promovidos'].append((residente, anio_actual, anio_nuevo))
        if not dry_run:
            residente.anio_residencia = anio_nuevo
            residente.ultimo_cierre_residencia = cierre
            residente.save(update_fields=['anio_residencia', 'ultimo_cierre_residencia'])
            NotificacionCicloResidencia.objects.update_or_create(
                usuario=residente,
                cierre_anio=cierre,
                defaults={
                    'tipo': NotificacionCicloResidencia.TIPO_PROMOCION,
                    'anio_anterior': anio_actual,
                    'anio_nuevo': anio_nuevo,
                    'vista_en': None,
                },
            )

    if dry_run:
        transaction.set_rollback(True)
    return resultado
