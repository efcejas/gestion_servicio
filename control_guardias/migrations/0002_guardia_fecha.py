# Generated by Django 5.1.4 on 2025-01-06 23:22

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('control_guardias', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='guardia',
            name='fecha',
            field=models.DateField(default=None),
        ),
    ]
