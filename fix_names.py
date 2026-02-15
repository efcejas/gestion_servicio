# -*- coding: utf-8 -*-
import os
import sys
import django

# Setup Django
sys.path.append(r'C:\Dev\GitHub\gestion_servicio')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_estudios.settings')
django.setup()

from pedidos_estudios.models import MedicoGuardia

# Actualizar nombres corregidos
updates = [
    (1, 'Dr. Juan Pérez'),
    (2, 'Dra. María González'),
    (3, 'Dr. Carlos Rodríguez'),
]

print("\n=== ACTUALIZANDO NOMBRES ===\n")

for medico_id, nombre_correcto in updates:
    try:
        medico = MedicoGuardia.objects.get(id=medico_id)
        medico.nombre_completo = nombre_correcto
        medico.save()
        print(f"✓ ID {medico_id}: {nombre_correcto}")
    except Exception as e:
        print(f"✗ Error con ID {medico_id}: {e}")

print("\n=== VERIFICACIÓN ===\n")
for medico in MedicoGuardia.objects.all():
    print(f"ID {medico.id}: {medico.nombre_completo} ({medico.get_especialidad_display()})")

print("\n✓ Actualización completada")
