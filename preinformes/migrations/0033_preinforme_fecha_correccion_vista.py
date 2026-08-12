from django.db import migrations, models


def marcar_historicos_como_vistos(apps, schema_editor):
    Preinforme = apps.get_model('preinformes', 'Preinforme')
    Preinforme.objects.filter(
        estado='finalizado',
        fecha_finalizacion__isnull=False,
    ).update(fecha_correccion_vista=models.F('fecha_finalizacion'))


class Migration(migrations.Migration):

    dependencies = [
        ('preinformes', '0032_revisionpreinforme_embedding_semantico'),
    ]

    operations = [
        migrations.AddField(
            model_name='preinforme',
            name='fecha_correccion_vista',
            field=models.DateTimeField(
                blank=True,
                help_text='Momento en que el residente confirmó haber revisado la corrección.',
                null=True,
            ),
        ),
        migrations.RunPython(
            marcar_historicos_como_vistos,
            migrations.RunPython.noop,
        ),
    ]
