"""
Diagnóstico: qué hay en los estudios clasificados como OTROS.
Uso: python manage.py shell < scripts/diagnostico_otros.py
"""
import django
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_estudios.settings')

from eges_import.models import EgesRow
from django.db.models import Count

otros = EgesRow.objects.filter(modalidad='OTROS', es_insumo=False)
print('Total OTROS (no insumos):', otros.count())

print('\n=== TOP 30 SERVICIOS ===')
for r in otros.values('servicio').annotate(n=Count('id')).order_by('-n')[:30]:
    print(f"  {r['n']:>5}x  {r['servicio']}")

print('\n=== TOP 20 EQUIPOS ===')
for r in otros.values('equipo').annotate(n=Count('id')).order_by('-n')[:20]:
    print(f"  {r['n']:>5}x  {r['equipo']}")

print('\n=== TOP 40 PRACTICAS ===')
for r in otros.values('practica').annotate(n=Count('id')).order_by('-n')[:40]:
    print(f"  {r['n']:>5}x  {r['practica']}")

print('\n=== ESTADOS (para ver si hay sin informe mezclados) ===')
for r in otros.values('estado_turno').annotate(n=Count('id')).order_by('-n'):
    print(f"  {r['n']:>5}x  {r['estado_turno']}")
