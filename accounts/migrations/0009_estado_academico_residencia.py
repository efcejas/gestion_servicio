from django.db import migrations, models


def inicializar_ultimo_cierre(apps, schema_editor):
    """Los años existentes ya representan el ciclo iniciado el 1/8/2025."""
    CustomUser = apps.get_model('accounts', 'CustomUser')
    CustomUser.objects.filter(rol='medico_residente').update(
        ultimo_cierre_residencia=2025,
    )


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0008_alter_customuser_rol_piloto_dictado'),
    ]

    operations = [
        migrations.AddField(
            model_name='customuser',
            name='estado_residencia',
            field=models.CharField(
                choices=[('ACTIVO', 'En curso'), ('EGRESADO', 'Egresado')],
                default='ACTIVO',
                help_text='Situación académica actual dentro de la residencia.',
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name='customuser',
            name='fecha_egreso_residencia',
            field=models.DateField(
                blank=True,
                help_text='Fecha en la que finalizó la residencia.',
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='customuser',
            name='repite_anio_residencia',
            field=models.BooleanField(
                default=False,
                help_text='Marcar antes del cierre del 31 de julio para que conserve su año. La marca se limpia al procesar el cierre.',
            ),
        ),
        migrations.AddField(
            model_name='customuser',
            name='ultimo_cierre_residencia',
            field=models.PositiveSmallIntegerField(
                blank=True,
                help_text='Año del último cierre académico procesado para este residente.',
                null=True,
            ),
        ),
        migrations.RunPython(inicializar_ultimo_cierre, migrations.RunPython.noop),
    ]
