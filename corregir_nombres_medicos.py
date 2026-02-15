# -*- coding: utf-8 -*-
from pedidos_estudios.models import MedicoGuardia

# Corregir nombres de médicos con encoding correcto
medicos_data = [
    {'id': 1, 'nombre': 'Dr. Juan Pérez'},
    {'id': 2, 'nombre': 'Dra. María González'},
    {'id': 3, 'nombre': 'Dr. Carlos Rodríguez'},
]

print("\n=== CORRIGIENDO NOMBRES DE MÉDICOS ===\n")

for data in medicos_data:
    try:
        medico = MedicoGuardia.objects.get(id=data['id'])
        nombre_anterior = medico.nombre_completo
        medico.nombre_completo = data['nombre']
        medico.save()
        print(f"✓ Actualizado ID {data['id']}")
        print(f"  Anterior: {nombre_anterior}")
        print(f"  Nuevo: {medico.nombre_completo}")
        print()
    except MedicoGuardia.DoesNotExist:
        print(f"✗ No existe médico con ID {data['id']}")
        print()

print("=== VERIFICACIÓN FINAL ===\n")
medicos = MedicoGuardia.objects.all()
for medico in medicos:
    print(f"• {medico.nombre_completo} - {medico.get_especialidad_display()}")
