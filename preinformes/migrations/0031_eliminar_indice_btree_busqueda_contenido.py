from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('preinformes', '0030_revisionpreinforme_busqueda_contenido'),
    ]

    operations = [
        migrations.RunSQL(
            sql=(
                'DROP INDEX IF EXISTS '
                '"preinformes_revisionpreinforme_informe_final_busqueda_25be9c84"'
            ),
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
