from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dictado_informes', '0022_correccionaprendizaje_lateralidad_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='eventoaprendizajedictado',
            name='tipo_evento',
            field=models.CharField(
                choices=[
                    ('plantilla_confirmada', 'Plantilla confirmada'),
                    ('correccion_voz_aplicada', 'Correccion por voz aplicada'),
                    ('correccion_voz_deshecha', 'Correccion por voz deshecha'),
                    ('correccion_voz_rehecha', 'Correccion por voz rehecha'),
                    ('informe_aceptado', 'Informe aceptado'),
                    ('informe_corregido', 'Informe que requirio correccion'),
                    ('aprendizaje_confirmado', 'Correccion manual guardada'),
                ],
                max_length=40,
            ),
        ),
    ]
