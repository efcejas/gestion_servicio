"""
Diagnóstico de médico informante: ver cuántos estudios tiene cada médico y con qué estado.
Uso: Get-Content scripts/diagnostico_medico.py | python manage.py shell
"""
from eges_import.models import EgesRow
from django.db.models import Count

print("=== MEDICOS INFORMANTES en DB (todos los estados) ===")
for r in (EgesRow.objects
          .exclude(medico_informante__isnull=True)
          .exclude(medico_informante='')
          .values('medico_informante', 'estado_turno', 'modalidad')
          .annotate(n=Count('id'))
          .order_by('medico_informante', '-n')[:60]):
    print(f"  {r['medico_informante']:<35} | {r['modalidad']:<6} | {r['estado_turno']:<30} | {r['n']}")

print()
print("=== ESTADOS DISTINTOS en DB ===")
for r in EgesRow.objects.values('estado_turno').annotate(n=Count('id')).order_by('-n'):
    print(f"  {str(r['estado_turno']):>35}: {r['n']}")
