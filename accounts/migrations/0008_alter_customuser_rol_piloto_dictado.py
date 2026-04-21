from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0007_add_avatar_to_customuser'),
    ]

    operations = [
        migrations.AlterField(
            model_name='customuser',
            name='rol',
            field=models.CharField(
                blank=True,
                choices=[
                    ('medico_staff', 'Médico de Staff'),
                    ('medico_residente', 'Médico Residente'),
                    ('jefe_residentes', 'Jefe de Residentes'),
                    ('instructor_residentes', 'Instructor de Residentes'),
                    ('jefe_servicio', 'Jefe de Servicio'),
                    ('piloto_dictado', 'Piloto Dictado IA'),
                    ('cardiologo', 'Cardiólogo'),
                    ('tecnico', 'Técnico Radiólogo'),
                    ('administrativo', 'Administrativo'),
                    ('enfermeria', 'Enfermería'),
                    ('otro', 'Otro'),
                ],
                help_text='Rol principal del usuario en el servicio',
                max_length=30,
                null=True,
            ),
        ),
    ]