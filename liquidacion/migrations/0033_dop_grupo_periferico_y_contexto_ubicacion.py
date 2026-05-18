from django.db import migrations


def migrar_dop_a_grupo_periferico(apps, schema_editor):
    """
    Corrige estudios de tipo DOP:
    - Asigna grupo_tarifario = DOP_PERIFERICO (en lugar de ECO_DOPPLER)
    - Activa tiene_contexto_ubicacion = True para que precio_para_os()
      resuelva correctamente DOP_PERIFERICO_LECHO cuando contexto='LECHO'
    """
    Estudios = apps.get_model('liquidacion', 'Estudios')
    GrupoTarifario = apps.get_model('liquidacion', 'GrupoTarifario')

    try:
        grupo_periferico = GrupoTarifario.objects.get(codigo='DOP_PERIFERICO')
    except GrupoTarifario.DoesNotExist:
        # Si no existe en este entorno, no hay nada que corregir
        return

    Estudios.objects.filter(tipo='DOP').update(
        grupo_tarifario=grupo_periferico,
        tiene_contexto_ubicacion=True,
    )


def revertir_dop_a_eco_doppler(apps, schema_editor):
    Estudios = apps.get_model('liquidacion', 'Estudios')
    GrupoTarifario = apps.get_model('liquidacion', 'GrupoTarifario')

    try:
        grupo_eco_doppler = GrupoTarifario.objects.get(codigo='ECO_DOPPLER')
    except GrupoTarifario.DoesNotExist:
        return

    Estudios.objects.filter(tipo='DOP').update(
        grupo_tarifario=grupo_eco_doppler,
        tiene_contexto_ubicacion=False,
    )


class Migration(migrations.Migration):

    dependencies = [
        ('liquidacion', '0032_alter_guardiapasiva_monto_configuracionguardiapasiva_and_more'),
    ]

    operations = [
        migrations.RunPython(
            migrar_dop_a_grupo_periferico,
            reverse_code=revertir_dop_a_eco_doppler,
        ),
    ]
