from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('preinformes', '0026_revisionpreinforme_evaluacion_ia_final_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='preinforme',
            name='es_registro_demo',
            field=models.BooleanField(
                db_index=True,
                default=False,
                help_text='Identifica registros técnicos creados durante una demostración.',
            ),
        ),
    ]
