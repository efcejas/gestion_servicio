# Generated by Django 5.1.4 on 2025-01-05 18:08

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Region',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(max_length=100, unique=True)),
                ('peso', models.PositiveIntegerField(default=1)),
            ],
            options={
                'verbose_name': 'Región',
                'verbose_name_plural': 'Regiones',
            },
        ),
        migrations.CreateModel(
            name='Estudio',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(max_length=100, unique=True)),
                ('modalidad', models.CharField(choices=[('RM', 'Resonancia Magnética'), ('TC', 'Tomografía Computada'), ('RX', 'Radiografía')], default='RX', max_length=2)),
                ('regiones', models.ManyToManyField(related_name='estudios', to='facturacion_regiones.region')),
            ],
            options={
                'verbose_name': 'Estudio',
                'verbose_name_plural': 'Estudios',
            },
        ),
        migrations.CreateModel(
            name='RegistroEstudio',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('paciente_nombre', models.CharField(max_length=100)),
                ('paciente_dni', models.CharField(max_length=15)),
                ('fecha_estudio', models.DateField()),
                ('total_regiones', models.PositiveIntegerField(default=0)),
                ('medico', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='RegistroEstudioDetalle',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('cantidad', models.PositiveIntegerField(default=1)),
                ('estudio', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='facturacion_regiones.estudio')),
                ('registro', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='facturacion_regiones.registroestudio')),
            ],
            options={
                'verbose_name': 'Detalle de Registro de Estudio',
                'verbose_name_plural': 'Detalles de Registro de Estudio',
            },
        ),
        migrations.AddField(
            model_name='registroestudio',
            name='estudios',
            field=models.ManyToManyField(through='facturacion_regiones.RegistroEstudioDetalle', to='facturacion_regiones.estudio'),
        ),
    ]
