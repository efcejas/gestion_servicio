"""
Reclasifica TODOS los EgesRow existentes y recalcula métricas de batches.
Uso: Get-Content scripts/reclasificar_todos.py | python manage.py shell
"""
from eges_import.models import EgesRow, ImportBatch
from django.db import transaction

print("Cargando filas...")
filas = list(EgesRow.objects.all().only(
    'id', 'practica', 'servicio', 'equipo', 'modalidad', 'sub_modalidad', 'es_insumo'
))
print(f"Total filas: {len(filas)}")

cambios = []
conteo = {'RX': 0, 'SERIE': 0, 'ECO': 0, 'TC': 0, 'RM': 0, 'DX': 0, 'MAM': 0, 'OTROS': 0}

for fila in filas:
    nueva_mod = fila.clasificar_modalidad()
    if nueva_mod != fila.modalidad:
        fila.modalidad = nueva_mod
        if nueva_mod == 'ECO':
            fila.sub_modalidad = fila.clasificar_sub_modalidad()
        else:
            fila.sub_modalidad = None
        cambios.append(fila)
    conteo[nueva_mod] = conteo.get(nueva_mod, 0) + 1

print(f"\nNueva distribución de modalidades:")
for mod, n in sorted(conteo.items(), key=lambda x: -x[1]):
    print(f"  {mod:>6}: {n:>6}")

print(f"\nFilas a actualizar: {len(cambios)}")

if cambios:
    with transaction.atomic():
        batch_size = 500
        for i in range(0, len(cambios), batch_size):
            lote = cambios[i:i+batch_size]
            EgesRow.objects.bulk_update(lote, ['modalidad', 'sub_modalidad'], batch_size=batch_size)
            print(f"  Actualizadas {min(i+batch_size, len(cambios))}/{len(cambios)}...")
    print("Reclasificación completada.")
else:
    print("Ninguna fila necesitó cambios de modalidad.")

print("\nRecalculando métricas de batches...")
for batch in ImportBatch.objects.all():
    batch.calcular_metricas()
    print(f"  Batch #{batch.id} ({batch.archivo_nombre}): "
          f"RX={batch.total_rx}, SERIE={batch.total_serie}, "
          f"RX_sin_informe={batch.total_rx_sin_informe}, OTROS={batch.total_otros}")

print("\nDone.")
