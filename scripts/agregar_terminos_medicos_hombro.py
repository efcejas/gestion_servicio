"""
Script para agregar términos médicos comunes del hombro al diccionario
Ejecutar con: python manage.py shell < scripts/agregar_terminos_medicos_hombro.py
"""

from dictado_informes.models import TerminoMedico, CategoriaTerminoMedico

# Términos que necesitan corrección
terminos = [
    # Errores ortográficos comunes
    ('pasiente', 'paciente', 'GENERAL'),
    ('Pasiente', 'Paciente', 'GENERAL'),
    ('homalgia', 'omalgia', 'SINTOMA'),
    ('Homalgia', 'Omalgia', 'SINTOMA'),
    
    # Anatomía del hombro
    ('subescapular', 'subescapular', 'ANATOMIA'),  # Por si viene mal
    ('supraespinoso', 'supraespinoso', 'ANATOMIA'),
    ('supraespinosa', 'supraespinoso', 'ANATOMIA'),
    ('infraespinoso', 'infraespinoso', 'ANATOMIA'),
    ('subescapularis', 'subescapular', 'ANATOMIA'),
    
    # Accidentes óseos
    ('troquini', 'troquín', 'ANATOMIA'),
    ('troquiter', 'troquíter', 'ANATOMIA'),
    ('trochiter', 'troquíter', 'ANATOMIA'),
    ('troquin', 'troquín', 'ANATOMIA'),
    ('troiter', 'troquíter', 'ANATOMIA'),
    
    # Bursas
    ('bursa subacromia', 'bursa subacromial', 'ANATOMIA'),
    ('bursa subacromio', 'bursa subacromial', 'ANATOMIA'),
    ('subacromia', 'subacromial', 'ANATOMIA'),
    ('subeltoidea', 'subdeltoidea', 'ANATOMIA'),
    ('subacromiodeltoidea', 'subacromio-deltoidea', 'ANATOMIA'),
    
    # Patologías
    ('tendinopatia', 'tendinopatía', 'PATOLOGIA'),
    ('tendinopatía', 'tendinopatía', 'PATOLOGIA'),
    ('entesitis', 'entesopatía', 'PATOLOGIA'),
    ('entesitis en las facetas', 'entesopatía de las inserciones', 'PATOLOGIA'),
    ('sinovitis', 'sinovitis', 'PATOLOGIA'),
    
    # Errores de concordancia
    ('edema ósea', 'edema óseo', 'HALLAZGO'),
    ('señal aumentada', 'señal aumentada', 'HALLAZGO'),
    ('grosor conservado', 'grosor conservado', 'HALLAZGO'),
    
    # Términos compuestos mal transcritos
    ('trofio facetoligamentaria', 'trofismo faceto-ligamentario', 'ANATOMIA'),
    ('facetoligamentaria', 'faceto-ligamentaria', 'ANATOMIA'),
    ('acromioclavicular', 'acromioclavicular', 'ANATOMIA'),
    
    # Hallazgos comunes
    ('desgarro parcial intrasustancia', 'desgarro parcial intrasustancial', 'HALLAZGO'),
    ('intrasustancia', 'intrasustancial', 'HALLAZGO'),
    ('intrasustancial', 'intrasustancial', 'HALLAZGO'),
    ('bursal', 'bursal', 'ANATOMIA'),
    ('articular', 'articular', 'ANATOMIA'),
    
    # Direcciones anatómicas
    ('subtercio lateral', 'tercio lateral', 'ANATOMIA'),
    ('tercio proximal', 'tercio proximal', 'ANATOMIA'),
    ('tercio distal', 'tercio distal', 'ANATOMIA'),
    ('cuerno posterior', 'cuerno posterior', 'ANATOMIA'),
    ('cuerno anterior', 'cuerno anterior', 'ANATOMIA'),
]

# Agregar términos al diccionario
contador_nuevos = 0
contador_existentes = 0

for incorrecto, correcto, categoria in terminos:
    termino, created = TerminoMedico.objects.get_or_create(
        termino_incorrecto=incorrecto,
        defaults={
            'termino_correcto': correcto,
            'categoria': categoria,
            'activo': True
        }
    )
    
    if created:
        contador_nuevos += 1
        print(f"✅ Nuevo: {incorrecto} → {correcto}")
    else:
        # Actualizar si cambió la corrección
        if termino.termino_correcto != correcto:
            termino.termino_correcto = correcto
            termino.categoria = categoria
            termino.save()
            print(f"🔄 Actualizado: {incorrecto} → {correcto}")
        else:
            contador_existentes += 1

print(f"\n📊 Resumen:")
print(f"   Nuevos términos agregados: {contador_nuevos}")
print(f"   Términos ya existentes: {contador_existentes}")
print(f"   Total en diccionario: {TerminoMedico.objects.filter(activo=True).count()}")
