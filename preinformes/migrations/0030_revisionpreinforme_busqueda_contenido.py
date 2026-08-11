import html
import re
import unicodedata

from django.db import migrations, models


def _texto_plano(html_content):
    if not html_content:
        return ''
    texto = re.sub(r'<[^>]+>', ' ', html_content)
    texto = html.unescape(texto).replace('\xa0', ' ')
    return re.sub(r'\s+', ' ', texto).strip()


def _normalizar(texto):
    texto = unicodedata.normalize('NFKD', texto or '')
    texto = ''.join(char for char in texto if not unicodedata.combining(char))
    return re.sub(r'\s+', ' ', texto.casefold()).strip()


def poblar_textos_busqueda(apps, schema_editor):
    Revision = apps.get_model('preinformes', 'RevisionPreinforme')
    for revision in Revision.objects.all().iterator(chunk_size=500):
        texto = _texto_plano(revision.informe_final_html)
        revision.informe_final_texto = texto
        revision.informe_final_busqueda = _normalizar(texto)
        revision.save(update_fields=['informe_final_texto', 'informe_final_busqueda'])


class Migration(migrations.Migration):

    dependencies = [
        ('preinformes', '0029_aplicacionplantillapreinforme_marca_contraste'),
    ]

    operations = [
        migrations.AddField(
            model_name='revisionpreinforme',
            name='informe_final_texto',
            field=models.TextField(
                blank=True,
                default='',
                editable=False,
                help_text='Versión en texto plano del informe final para extractos de búsqueda',
            ),
        ),
        migrations.AddField(
            model_name='revisionpreinforme',
            name='informe_final_busqueda',
            field=models.TextField(
                blank=True,
                default='',
                editable=False,
                help_text='Versión normalizada del informe final para búsqueda de contenido',
            ),
        ),
        migrations.RunPython(poblar_textos_busqueda, migrations.RunPython.noop),
    ]
