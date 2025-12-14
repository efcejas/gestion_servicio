"""
Script para cargar TODOS los protocolos en la base de datos actual.
Ejecuta los comandos de seed existentes en orden correcto.
"""

print("🚀 Iniciando carga de protocolos...")
print("="*60)

# Importar los comandos de seed
from django.core.management import call_command

# Paso 1: Cargar protocolos base
print("\n1️⃣ Cargando protocolos base...")
try:
    call_command('cargar_protocolos_base')
    print("✅ Protocolos base cargados")
except Exception as e:
    print(f"⚠️ Error en protocolos base: {e}")

# Paso 2: Cargar protocolos TC core
print("\n2️⃣ Cargando protocolos TC core...")
try:
    call_command('seed_protocolos_tc_core')
    print("✅ Protocolos TC core cargados")
except Exception as e:
    print(f"⚠️ Error en protocolos TC core: {e}")

# Paso 3: Cargar protocolos TC multifásicos
print("\n3️⃣ Cargando protocolos TC multifásicos...")
try:
    call_command('seed_protocolos_tc_multifasicos')
    print("✅ Protocolos TC multifásicos cargados")
except Exception as e:
    print(f"⚠️ Error en protocolos TC multifásicos: {e}")

# Verificar resultado
print("\n" + "="*60)
print("📊 Verificando carga...")
print("="*60)

from protocolos.models import Protocolo, FaseAdquisicion, Modalidad, RegionAnatomica, Tag

print(f"\n✅ Modalidades: {Modalidad.objects.count()}")
print(f"✅ Regiones: {RegionAnatomica.objects.count()}")
print(f"✅ Tags: {Tag.objects.count()}")
print(f"✅ Protocolos: {Protocolo.objects.count()}")
print(f"✅ Fases: {FaseAdquisicion.objects.count()}")

print("\n📋 Protocolos cargados:")
for p in Protocolo.objects.filter(es_activo=True).order_by('nombre'):
    print(f"  ✓ {p.nombre} ({p.fases.count()} fases)")

print("\n🎉 CARGA COMPLETA")
print("🌐 Ahora puedes probar: http://localhost:8000/protocolos/elegir/")
