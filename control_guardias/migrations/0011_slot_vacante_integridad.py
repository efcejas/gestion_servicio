from django.db import migrations, models
from django.utils import timezone


def cancelar_pendientes_duplicadas(apps, schema_editor):
    Solicitud = apps.get_model('control_guardias', 'SolicitudSlotVacante')
    vistas_guardia = set()
    vistas_slot = set()
    pendientes = Solicitud.objects.filter(estado='PENDIENTE').order_by('fecha_solicitud', 'pk')
    for solicitud in pendientes.iterator():
        clave_guardia = solicitud.guardia_ceder_id
        clave_slot = (solicitud.slot_fecha, solicitud.slot_tipo_guardia_id)
        if clave_guardia in vistas_guardia or clave_slot in vistas_slot:
            nota = 'Cancelada automáticamente al instalar la protección contra solicitudes duplicadas.'
            solicitud.estado = 'CANCELADA'
            solicitud.notas_jefe = f'{solicitud.notas_jefe}\n{nota}'.strip()
            solicitud.fecha_resolucion = timezone.now()
            solicitud.save(update_fields=['estado', 'notas_jefe', 'fecha_resolucion'])
            continue
        vistas_guardia.add(clave_guardia)
        vistas_slot.add(clave_slot)


class Migration(migrations.Migration):

    dependencies = [
        ('control_guardias', '0010_ajuste_cuota_rotacion_slot_vacante'),
    ]

    operations = [
        migrations.RunPython(cancelar_pendientes_duplicadas, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='solicitudslotvacante',
            constraint=models.UniqueConstraint(
                condition=models.Q(('estado', 'PENDIENTE')),
                fields=('guardia_ceder',),
                name='uniq_slot_pendiente_por_guardia',
            ),
        ),
        migrations.AddConstraint(
            model_name='solicitudslotvacante',
            constraint=models.UniqueConstraint(
                condition=models.Q(('estado', 'PENDIENTE')),
                fields=('slot_fecha', 'slot_tipo_guardia'),
                name='uniq_slot_destino_pendiente',
            ),
        ),
    ]
