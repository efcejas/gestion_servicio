from protocolos.models import Protocolo, FaseAdquisicion, Modalidad, RegionAnatomica, Tag

print("\n" + "="*60)
print("📊 ESTADO ACTUAL DE LA BASE DE DATOS")
print("="*60)

print(f"\n✅ Modalidades: {Modalidad.objects.count()}")
print(f"✅ Regiones: {RegionAnatomica.objects.count()}")
print(f"✅ Tags: {Tag.objects.count()}")
print(f"✅ Protocolos: {Protocolo.objects.count()}")
print(f"✅ Fases: {FaseAdquisicion.objects.count()}")

print("\n📋 PROTOCOLOS ACTIVOS:")
for p in Protocolo.objects.filter(es_activo=True).order_by('nombre'):
    print(f"  ✓ {p.nombre} ({p.fases.count()} fases)")

print("\n" + "="*60)
print("🎉 TODO CARGADO CORRECTAMENTE")
print("="*60)
print("\n🌐 Probar en: http://localhost:8000/protocolos/elegir/")
