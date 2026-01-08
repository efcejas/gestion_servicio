from preinformes.models import PlantillaPreinforme

# Actualizar todas las plantillas existentes a público
count = PlantillaPreinforme.objects.filter(estado='borrador').update(estado='publica')
print(f'✅ {count} plantillas actualizadas a estado público')

# Mostrar resumen
total = PlantillaPreinforme.objects.count()
publicas = PlantillaPreinforme.objects.filter(estado='publica').count()
print(f'Total: {total} plantillas, {publicas} públicas')
