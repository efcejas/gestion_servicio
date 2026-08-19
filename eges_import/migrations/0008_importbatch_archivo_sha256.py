from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('eges_import', '0007_eges_campos_auditoria_pacs'),
    ]

    operations = [
        migrations.AddField(
            model_name='importbatch',
            name='archivo_sha256',
            field=models.CharField(
                blank=True,
                help_text='Permite rechazar reimportaciones exactas sin alterar lotes históricos.',
                max_length=64,
                null=True,
                unique=True,
                verbose_name='Huella SHA-256 del archivo',
            ),
        ),
    ]
