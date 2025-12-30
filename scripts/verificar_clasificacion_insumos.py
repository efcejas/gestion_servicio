"""
Script para verificar la clasificación de estudios vs insumos en EGES
"""
from eges_import.models import EgesRow

# Contar estudios e insumos
estudios = EgesRow.objects.filter(es_insumo=False).count()
insumos = EgesRow.objects.filter(es_insumo=True).count()

print(f"📊 Clasificación actual:")
print(f"   Estudios: {estudios}")
print(f"   Insumos: {insumos}")
print(f"   Total: {estudios + insumos}")

# Mostrar ejemplos de insumos detectados
print(f"\n🔍 Ejemplos de insumos detectados (primeros 10):")
for fila in EgesRow.objects.filter(es_insumo=True)[:10]:
    print(f"   ✓ {fila.servicio}")

# Mostrar ejemplos de estudios (no insumos)
print(f"\n🏥 Ejemplos de estudios (primeros 10):")
for fila in EgesRow.objects.filter(es_insumo=False)[:10]:
    print(f"   • {fila.servicio}")

# Buscar casos que podrían ser insumos pero no están detectados
print(f"\n⚠️ Verificando casos sospechosos que podrían ser insumos:")
sospechosos = EgesRow.objects.filter(
    es_insumo=False
).filter(
    servicio__icontains='ml'
) | EgesRow.objects.filter(
    es_insumo=False
).filter(
    servicio__iregex=r'E-\d+'
)

if sospechosos.exists():
    for fila in sospechosos[:15]:
        print(f"   ? {fila.servicio}")
else:
    print("   ✓ No se encontraron casos sospechosos")
