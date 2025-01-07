# Generated by Django 5.1.4 on 2024-12-31 02:15

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tasks', '0001_initial'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='tarea',
            options={},
        ),
        migrations.AlterField(
            model_name='tarea',
            name='estado',
            field=models.CharField(choices=[('pendiente', 'Pendiente'), ('completada', 'Completada')], max_length=20),
        ),
        migrations.AlterField(
            model_name='tarea',
            name='prioridad',
            field=models.PositiveSmallIntegerField(choices=[(1, 'Alta'), (2, 'Media'), (3, 'Baja')]),
        ),
    ]
