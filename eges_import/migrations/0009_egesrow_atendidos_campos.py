from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('eges_import', '0008_importbatch_archivo_sha256'),
    ]

    operations = [
        migrations.AddField(
            model_name='egesrow',
            name='protocolo',
            field=models.CharField(blank=True, db_index=True, max_length=80, null=True),
        ),
        migrations.AddField(
            model_name='egesrow',
            name='tecnico',
            field=models.CharField(blank=True, max_length=200, null=True),
        ),
        migrations.AddField(
            model_name='egesrow',
            name='duracion_minutos',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=8, null=True),
        ),
        migrations.AddField(
            model_name='egesrow',
            name='contraste_eges',
            field=models.CharField(blank=True, max_length=30, null=True),
        ),
        migrations.AddField(
            model_name='egesrow',
            name='anestesia_eges',
            field=models.CharField(blank=True, max_length=30, null=True),
        ),
        migrations.AddField(
            model_name='egesrow',
            name='aplicacion_origen',
            field=models.CharField(blank=True, max_length=80, null=True),
        ),
    ]
