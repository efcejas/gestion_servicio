from eges_import.models import EgesRow, ImportBatch
from django.db.models import Count

print("=== BATCHES ===")
for b in ImportBatch.objects.all().order_by('id'):
    rows = b.filas.count()
    print(f"  Batch #{b.id} | {b.archivo_nombre}")
    print(f"    filas en DB: {rows}  |  total_filas(cached): {b.total_filas}")
    print(f"    total_rx={b.total_rx}  total_serie={b.total_serie}  total_otros={b.total_otros}")
    print(f"    total_rx_sin_informe={b.total_rx_sin_informe}")

print()
print("=== TOTAL EgesRow en DB ===")
print("  Total:", EgesRow.objects.count())

print()
print("=== DISTRIBUCION POR MODALIDAD (DB real) ===")
for r in EgesRow.objects.values('modalidad').annotate(n=Count('id')).order_by('-n'):
    print(f"  {r['modalidad']:>6}: {r['n']}")

print()
print("=== DISTRIBUCION POR ESTADO ===")
for r in EgesRow.objects.values('estado_turno').annotate(n=Count('id')).order_by('-n'):
    print(f"  {str(r['estado_turno']):>30}: {r['n']}")
