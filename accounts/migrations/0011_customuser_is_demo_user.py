from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0010_notificacion_ciclo_residencia'),
    ]

    operations = [
        migrations.AddField(
            model_name='customuser',
            name='is_demo_user',
            field=models.BooleanField(
                db_index=True,
                default=False,
                help_text='Aplica restricciones de privacidad para demostraciones sin modificar el rol.',
            ),
        ),
    ]
