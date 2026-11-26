from django.db import migrations, models
import re


def separar_subtipos(apps, schema_editor):
    Fila = apps.get_model('eges_import', 'EgesRow')
    db = schema_editor.connection.alias
    renal, vesical = [], []
    for fila in Fila.objects.using(db).filter(modalidad='ECO', sub_modalidad='ECO_ABDOMINAL').iterator(chunk_size=500):
        texto = f'{fila.practica or ""} {fila.servicio or ""} {fila.equipo or ""}'.upper()
        if any(kw in texto for kw in ('VEJIGA', 'VESICAL', 'PROSTAT', 'PRÓSTAT', 'VESICOPROST')):
            vesical.append(fila.pk)
        elif re.search(r'\bRENAL(?:ES)?\b|\bRIÑ[OÓ]N(?:ES)?\b', texto):
            renal.append(fila.pk)
    for ids, subtipo in ((renal, 'ECO_RENAL'), (vesical, 'ECO_VEJIGA_PROSTATA')):
        for i in range(0, len(ids), 500):
            Fila.objects.using(db).filter(pk__in=ids[i:i + 500]).update(sub_modalidad=subtipo)


def unir_subtipos(apps, schema_editor):
    apps.get_model('eges_import', 'EgesRow').objects.using(schema_editor.connection.alias).filter(
        sub_modalidad__in=['ECO_RENAL', 'ECO_VEJIGA_PROSTATA'],
    ).update(sub_modalidad='ECO_ABDOMINAL')


class Migration(migrations.Migration):
    dependencies = [('eges_import', '0013_produccionvalidada')]
    operations = [
        migrations.AlterField(
            model_name='egesrow', name='sub_modalidad',
            field=models.CharField(blank=True, null=True, max_length=30, choices=[
                ('ECOCARDIO', 'Ecocardiograma'), ('DOPPLER', 'Doppler / Dúplex'),
                ('ECO_MAMA', 'Ecografía Mamaria'), ('ECO_TIROIDES', 'Ecografía Tiroidea'),
                ('ECO_OBSTETRICA', 'Ecografía Obstétrica'), ('ECO_PELVIS', 'Ecografía Pelviana'),
                ('ECO_ABDOMINAL', 'Ecografía Abdominal'), ('ECO_RENAL', 'Ecografía Renal'),
                ('ECO_VEJIGA_PROSTATA', 'Ecografía de Vejiga / Próstata'),
                ('ECO_NEONATAL', 'Ecografía Neonatal'), ('ECO_PARTES_BLANDAS', 'Ecografía Partes Blandas'),
            ]),
        ),
        migrations.RunPython(separar_subtipos, unir_subtipos),
    ]
