# Generated by Django 5.1.4 on 2025-01-14 19:47

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('liquidacion', '0006_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='medico',
            name='matricula',
            field=models.CharField(blank=True, max_length=6, null=True, unique=True, verbose_name='Matrícula'),
        ),
    ]