"""
Script simple para agregar términos médicos básicos al diccionario
Ejecutar: python manage.py shell < agregar_terminos_basicos.py
"""

from dictado_informes.models import TerminoMedico

# Términos más comunes que necesitas corregir
terminos = [
    ('Jofa', 'Hoffa'),
    ('jofa', 'Hoffa'),
    ('de la jofa', 'de la Hoffa'),
    ('grasa de la jofa', 'grasa de la Hoffa'),
    ('oligamentaria', 'ligamentaria'),
    ('trick', 'tricompartimental'),
    ('artrosis trick', 'artrosis tricompartimental'),
]

print("🔧 Agregando términos al diccionario médico...")
creados = 0
existentes = 0

for incorrecto, correcto in terminos:
    termino, created = TerminoMedico.objects.get_or_create(
        termino_incorrecto=incorrecto,
        defaults={
            'termino_correcto': correcto,
            'activo': True,
            'frecuencia_uso': 0
        }
    )
    
    if created:
        print(f"  ✅ {incorrecto} → {correcto}")
        creados += 1
    else:
        print(f"  ℹ️  {incorrecto} (ya existe)")
        existentes += 1

print(f"\n📊 Resumen:")
print(f"  Creados: {creados}")
print(f"  Ya existentes: {existentes}")
print(f"  Total en diccionario: {TerminoMedico.objects.count()}")
