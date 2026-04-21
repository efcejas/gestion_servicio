from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dictado_informes', '0012_import_plantillas_legacy'),
    ]

    operations = [
        migrations.AddField(
            model_name='plantillaestructurada',
            name='compartida',
            field=models.BooleanField(
                db_index=True,
                default=True,
                help_text='Si está activa y compartida, queda disponible para otros usuarios de Dictado IA',
                verbose_name='Compartida',
            ),
        ),
    ]