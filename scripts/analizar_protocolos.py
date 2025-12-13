import os
import sys
import django

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_estudios.settings')
django.setup()

from protocolos.models import Protocolo, FaseAdquisicion, Modalidad, RegionAnatomica, Tag

print("=" * 100)
print("ANÁLISIS DE PROTOCOLOS RADIOLÓGICOS")
print("=" * 100)
print()

# Contar totales
total_protocolos = Protocolo.objects.count()
total_modalidades = Modalidad.objects.count()
total_regiones = RegionAnatomica.objects.count()
total_tags = Tag.objects.count()

print(f"📊 RESUMEN GENERAL:")
print(f"  • {total_protocolos} protocolos")
print(f"  • {total_modalidades} modalidades")
print(f"  • {total_regiones} regiones anatómicas")
print(f"  • {total_tags} tags")
print()
print("=" * 100)
print()

# Listar todos los protocolos
protocolos = Protocolo.objects.select_related('modalidad', 'region').prefetch_related('tags', 'fases__region').all()

for i, p in enumerate(protocolos, 1):
    print(f"{'=' * 100}")
    print(f"PROTOCOLO #{i}: {p.nombre}")
    print(f"{'=' * 100}")
    print()
    
    # Información básica
    print(f"🔹 MODALIDAD: {p.modalidad.codigo} ({p.modalidad.nombre})")
    print(f"🔹 REGIÓN: {p.region.codigo} ({p.region.nombre})")
    print(f"🔹 ESTADO: {'✅ ACTIVO' if p.es_activo else '❌ INACTIVO'}")
    print()
    
    # Tags
    tags_list = [t.nombre for t in p.tags.all()]
    if tags_list:
        print(f"🏷️  TAGS: {', '.join(tags_list)}")
    else:
        print(f"🏷️  TAGS: (ninguno)")
    print()
    
    # Requisitos
    print(f"💉 REQUISITOS:")
    print(f"   • Contraste EV: {'SÍ' if p.requiere_contraste_ev else 'NO'}")
    print(f"   • Contraste Oral: {'SÍ' if p.requiere_contraste_oral else 'NO'}")
    print(f"   • Ayuno: {'SÍ' if p.requiere_ayuno else 'NO'}")
    if p.calibre_via_minimo:
        print(f"   • Calibre vía: {p.calibre_via_minimo}")
    if p.sitio_via_preferido:
        print(f"   • Sitio vía: {p.sitio_via_preferido}")
    print()
    
    # Fases de adquisición
    fases = p.fases.all().order_by('orden')
    if fases:
        print(f"🔬 FASES DE ADQUISICIÓN ({fases.count()}):")
        print()
        for f in fases:
            region_str = f.region.codigo if f.region else 'N/A'
            delay_str = f"{f.delay_segundos}s" if f.delay_segundos else "N/A"
            print(f"   [{f.orden}] {f.nombre}")
            print(f"       Tipo: {f.get_tipo_fase_display()}")
            print(f"       Región: {region_str}")
            print(f"       Delay: {delay_str}")
            if f.cobertura_desde or f.cobertura_hasta:
                print(f"       Cobertura: {f.cobertura_desde or '?'} → {f.cobertura_hasta or '?'}")
            print()
    else:
        print(f"🔬 FASES: (ninguna definida)")
        print()
    
    print()

print("=" * 100)
print("ANÁLISIS COMPLETADO")
print("=" * 100)
