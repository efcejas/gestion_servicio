"""
Script para actualizar plantillas existentes y marcarlas como públicas
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_estudios.settings')
django.setup()

from preinformes.models import PlantillaPreinforme

def actualizar_plantillas():
    """Actualizar todas las plantillas existentes a estado 'publica'"""
    plantillas = PlantillaPreinforme.objects.filter(estado='borrador')
    count = plantillas.count()
    
    if count > 0:
        plantillas.update(estado='publica')
        print(f"✅ {count} plantillas actualizadas a estado 'pública'")
    else:
        print("ℹ️  No hay plantillas con estado 'borrador' para actualizar")
    
    # Mostrar resumen
    total = PlantillaPreinforme.objects.count()
    publicas = PlantillaPreinforme.objects.filter(estado='publica').count()
    borradores = PlantillaPreinforme.objects.filter(estado='borrador').count()
    
    print(f"\n📊 Resumen:")
    print(f"   Total de plantillas: {total}")
    print(f"   Públicas: {publicas}")
    print(f"   Borradores: {borradores}")

if __name__ == '__main__':
    print("🔄 Actualizando plantillas existentes...\n")
    actualizar_plantillas()
    print("\n✅ Proceso completado")
