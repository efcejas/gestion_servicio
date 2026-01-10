# Generated manually for data migration
from django.db import migrations


def combinar_campos_plantillas(apps, schema_editor):
    """
    Migra datos de campos separados (tecnica/hallazgos/conclusion) 
    al campo único 'contenido' en PlantillaPreinforme.
    """
    PlantillaPreinforme = apps.get_model('preinformes', 'PlantillaPreinforme')
    
    for plantilla in PlantillaPreinforme.objects.all():
        # Si ya tiene contenido en el campo único, saltar
        if plantilla.contenido and plantilla.contenido.strip():
            continue
        
        # Combinar los 3 campos en uno solo
        partes = []
        
        if plantilla.tecnica_template:
            partes.append(f"<h5>TÉCNICA</h5>{plantilla.tecnica_template}")
        
        if plantilla.hallazgos_template:
            partes.append(f"<h5>HALLAZGOS</h5>{plantilla.hallazgos_template}")
        
        if plantilla.conclusion_template:
            partes.append(f"<h5>CONCLUSIÓN</h5>{plantilla.conclusion_template}")
        
        # Guardar en el campo único
        if partes:
            plantilla.contenido = '\n\n'.join(partes)
            plantilla.save(update_fields=['contenido'])


def combinar_campos_preinformes(apps, schema_editor):
    """
    Migra datos de campos separados (tecnica/hallazgos/conclusion)
    al campo único 'informe_html' en Preinforme.
    """
    Preinforme = apps.get_model('preinformes', 'Preinforme')
    
    for preinforme in Preinforme.objects.all():
        # Si ya tiene contenido en el campo único, saltar
        if preinforme.informe_html and preinforme.informe_html.strip():
            continue
        
        # Combinar los 3 campos en uno solo
        partes = []
        
        if preinforme.tecnica:
            partes.append(f"<h5>TÉCNICA</h5>{preinforme.tecnica}")
        
        if preinforme.hallazgos:
            partes.append(f"<h5>HALLAZGOS</h5>{preinforme.hallazgos}")
        
        if preinforme.conclusion:
            partes.append(f"<h5>CONCLUSIÓN</h5>{preinforme.conclusion}")
        
        # Guardar en el campo único
        if partes:
            preinforme.informe_html = '\n\n'.join(partes)
            preinforme.save(update_fields=['informe_html'])


def reverso_plantillas(apps, schema_editor):
    """
    Reversión: dividir contenido único en campos separados.
    """
    PlantillaPreinforme = apps.get_model('preinformes', 'PlantillaPreinforme')
    
    for plantilla in PlantillaPreinforme.objects.all():
        if not plantilla.contenido:
            continue
        
        # Intentar extraer secciones por títulos
        contenido = plantilla.contenido
        
        # Buscar sección TÉCNICA
        if '<h5>TÉCNICA</h5>' in contenido:
            partes = contenido.split('<h5>TÉCNICA</h5>', 1)
            resto = partes[1]
            if '<h5>HALLAZGOS</h5>' in resto:
                plantilla.tecnica_template = resto.split('<h5>HALLAZGOS</h5>')[0].strip()
            elif '<h5>CONCLUSIÓN</h5>' in resto:
                plantilla.tecnica_template = resto.split('<h5>CONCLUSIÓN</h5>')[0].strip()
            else:
                plantilla.tecnica_template = resto.strip()
        
        # Buscar sección HALLAZGOS
        if '<h5>HALLAZGOS</h5>' in contenido:
            partes = contenido.split('<h5>HALLAZGOS</h5>', 1)
            resto = partes[1]
            if '<h5>CONCLUSIÓN</h5>' in resto:
                plantilla.hallazgos_template = resto.split('<h5>CONCLUSIÓN</h5>')[0].strip()
            else:
                plantilla.hallazgos_template = resto.strip()
        
        # Buscar sección CONCLUSIÓN
        if '<h5>CONCLUSIÓN</h5>' in contenido:
            partes = contenido.split('<h5>CONCLUSIÓN</h5>', 1)
            plantilla.conclusion_template = partes[1].strip()
        
        plantilla.save(update_fields=['tecnica_template', 'hallazgos_template', 'conclusion_template'])


def reverso_preinformes(apps, schema_editor):
    """
    Reversión: dividir contenido único en campos separados.
    """
    Preinforme = apps.get_model('preinformes', 'Preinforme')
    
    for preinforme in Preinforme.objects.all():
        if not preinforme.informe_html:
            continue
        
        # Intentar extraer secciones por títulos
        contenido = preinforme.informe_html
        
        # Buscar sección TÉCNICA
        if '<h5>TÉCNICA</h5>' in contenido:
            partes = contenido.split('<h5>TÉCNICA</h5>', 1)
            resto = partes[1]
            if '<h5>HALLAZGOS</h5>' in resto:
                preinforme.tecnica = resto.split('<h5>HALLAZGOS</h5>')[0].strip()
            elif '<h5>CONCLUSIÓN</h5>' in resto:
                preinforme.tecnica = resto.split('<h5>CONCLUSIÓN</h5>')[0].strip()
            else:
                preinforme.tecnica = resto.strip()
        
        # Buscar sección HALLAZGOS
        if '<h5>HALLAZGOS</h5>' in contenido:
            partes = contenido.split('<h5>HALLAZGOS</h5>', 1)
            resto = partes[1]
            if '<h5>CONCLUSIÓN</h5>' in resto:
                preinforme.hallazgos = resto.split('<h5>CONCLUSIÓN</h5>')[0].strip()
            else:
                preinforme.hallazgos = resto.strip()
        
        # Buscar sección CONCLUSIÓN
        if '<h5>CONCLUSIÓN</h5>' in contenido:
            partes = contenido.split('<h5>CONCLUSIÓN</h5>', 1)
            preinforme.conclusion = partes[1].strip()
        
        preinforme.save(update_fields=['tecnica', 'hallazgos', 'conclusion'])


class Migration(migrations.Migration):

    dependencies = [
        ('preinformes', '0011_simplificar_campos_unicos'),
    ]

    operations = [
        migrations.RunPython(combinar_campos_plantillas, reverso_plantillas),
        migrations.RunPython(combinar_campos_preinformes, reverso_preinformes),
    ]
