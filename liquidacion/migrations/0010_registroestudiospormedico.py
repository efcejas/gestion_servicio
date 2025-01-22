# Generated by Django 5.1.4 on 2025-01-18 20:33

import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('liquidacion', '0009_alter_estudios_nombre'),
    ]

    operations = [
        migrations.CreateModel(
            name='RegistroEstudiosPorMedico',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre_paciente', models.CharField(max_length=50, verbose_name='Nombre del paciente')),
                ('apellido_paciente', models.CharField(max_length=50, verbose_name='Apellido del paciente')),
                ('dni_paciente', models.CharField(max_length=8, verbose_name='DNI del paciente')),
                ('fecha_registro', models.DateTimeField(default=django.utils.timezone.now, verbose_name='Fecha de registro')),
                ('fecha_del_informe', models.DateField(blank=True, null=True, verbose_name='Fecha del informe')),
                ('estudio', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='liquidacion.estudios', verbose_name='Estudio')),
                ('medico', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='liquidacion.medico', verbose_name='Médico')),
            ],
            options={
                'verbose_name': 'Registro de estudio por médico',
                'verbose_name_plural': 'Registros de estudios por médico',
            },
        ),
    ]