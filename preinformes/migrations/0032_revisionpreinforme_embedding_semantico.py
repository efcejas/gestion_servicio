from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('preinformes', '0031_eliminar_indice_btree_busqueda_contenido'),
    ]

    operations = [
        migrations.AddField(
            model_name='revisionpreinforme',
            name='embedding_busqueda',
            field=models.BinaryField(
                blank=True,
                editable=False,
                help_text='Vector semántico compacto del informe definitivo anonimizado',
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='revisionpreinforme',
            name='embedding_modelo',
            field=models.CharField(blank=True, default='', editable=False, max_length=80),
        ),
        migrations.AddField(
            model_name='revisionpreinforme',
            name='embedding_fuente_hash',
            field=models.CharField(blank=True, default='', editable=False, max_length=64),
        ),
        migrations.AddField(
            model_name='revisionpreinforme',
            name='embedding_actualizado_en',
            field=models.DateTimeField(blank=True, editable=False, null=True),
        ),
    ]
