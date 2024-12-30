# Generated by Django 5.1.4 on 2024-12-30 01:53

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
            name='Estudio',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(max_length=100, unique=True)),
            ],
        ),
        migrations.CreateModel(
            name='Paciente',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(max_length=100)),
                ('apellido', models.CharField(max_length=100)),
                ('fecha_nacimiento', models.DateField(blank=True, null=True)),
                ('dni', models.CharField(max_length=15, unique=True)),
                ('telefono', models.CharField(blank=True, max_length=20)),
                ('direccion', models.TextField(blank=True)),
            ],
        ),
        migrations.CreateModel(
            name='OrdenMedica',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('archivo', models.FileField(blank=True, null=True, upload_to='ordenes_medicas/')),
                ('fecha_emision', models.DateField(auto_now_add=True)),
                ('estudios', models.ManyToManyField(to='recepcion.estudio')),
                ('paciente', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='recepcion.paciente')),
            ],
        ),
        migrations.CreateModel(
            name='RegistroAtencion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('fecha_atencion', models.DateTimeField(auto_now_add=True)),
                ('medico', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ('ordenes_medicas', models.ManyToManyField(blank=True, to='recepcion.ordenmedica')),
                ('paciente', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='recepcion.paciente')),
            ],
        ),
    ]