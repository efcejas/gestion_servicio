# Generated by Django 5.1.4 on 2024-12-31 02:21

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tasks', '0002_alter_tarea_options_alter_tarea_estado_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='tarea',
            name='estado',
            field=models.CharField(choices=[('pendiente', 'Pendiente'), ('en proceso', 'En proceso'), ('completada', 'Completada')], max_length=20),
        ),
    ]