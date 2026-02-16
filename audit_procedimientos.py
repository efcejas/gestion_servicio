#!/usr/bin/env python
"""
Auditoría de RegistroProcedimientosIntervensionismo
Verificar datos antes de eliminar
"""
import os
import django
import json
from pathlib import Path

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_servicio.settings')
django.setup()

from liquidacion.models import RegistroProcedimientosIntervensionismo
from django.core import serializers

# Contar registros
count = RegistroProcedimientosIntervensionismo.objects.count()
print(f"\n{'='*60}")
print(f"AUDITORÍA: RegistroProcedimientosIntervensionismo")
print(f"{'='*60}\n")

print(f"Total de registros: {count}\n")

if count > 0:
    # Mostrar últimos 5
    print("Últimos 5 registros:")
    for proc in RegistroProcedimientosIntervensionismo.objects.order_by('-fecha_procedimiento')[:5]:
        print(f"  - ID {proc.id}: {proc.medico} | {proc.fecha_procedimiento} | {proc.procedimiento}")
    
    # Export a JSON (backup)
    backup_file = Path('liquidacion_procedimientos_backup.json')
    with open(backup_file, 'w', encoding='utf-8') as f:
        data = serializers.serialize('json', RegistroProcedimientosIntervensionismo.objects.all())
        f.write(data)
    
    print(f"\n✓ Backup guardado en: {backup_file.absolute()}")
    print(f"  → Usa este archivo si necesitas recuperar datos después\n")
else:
    print("✓ NO HAY registros de procedimientos intervensionismo")
    print("  → SEGURO eliminar las vistas/modelos\n")

print(f"{'='*60}\n")
