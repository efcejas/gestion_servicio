# Generated migration for TerminoMedico model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dictado_informes', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='TerminoMedico',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('termino_incorrecto', models.CharField(help_text='Término como lo transcribe el navegador (ej: "con artrosis")', max_length=200, unique=True, verbose_name='Término Incorrecto')),
                ('termino_correcto', models.CharField(help_text='Término médico correcto (ej: "gonartrosis")', max_length=200, verbose_name='Término Correcto')),
                ('categoria', models.CharField(choices=[('ORTOPEDIA', 'Ortopedia'), ('RADIOLOGIA', 'Radiología'), ('GENERAL', 'General'), ('ANATOMIA', 'Anatomía')], default='GENERAL', max_length=50, verbose_name='Categoría')),
                ('frecuencia_uso', models.IntegerField(default=0, help_text='Contador automático de veces que se aplicó esta corrección', verbose_name='Frecuencia de Uso')),
                ('activo', models.BooleanField(default=True, verbose_name='Activo')),
                ('fecha_creacion', models.DateTimeField(auto_now_add=True)),
                ('fecha_modificacion', models.DateTimeField(auto_now=True)),
                ('notas', models.TextField(blank=True, help_text='Notas adicionales sobre el término', null=True, verbose_name='Notas')),
            ],
            options={
                'verbose_name': 'Término Médico',
                'verbose_name_plural': 'Términos Médicos',
                'ordering': ['-frecuencia_uso', 'termino_incorrecto'],
            },
        ),
        migrations.AddIndex(
            model_name='terminomedico',
            index=models.Index(fields=['termino_incorrecto'], name='dictado_inf_termino_idx'),
        ),
    ]
