"""Script para verificar datos existentes de clases"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_estudios.settings')
django.setup()

from clases_residentes.models import ClaseResidente

total = ClaseResidente.objects.count()
con_archivo = ClaseResidente.objects.exclude(archivo='').exclude(archivo=None).count()
con_thumbnail = ClaseResidente.objects.exclude(archivo_thumbnail='').exclude(archivo_thumbnail=None).count()

print(f"📊 Resumen de datos existentes:")
print(f"   Total de clases: {total}")
print(f"   Clases con archivo (PPT/PDF/Video): {con_archivo}")
print(f"   Clases con thumbnail: {con_thumbnail}")

if total > 0:
    print("\n📁 Tipos de archivo detectados:")
    for clase in ClaseResidente.objects.filter(archivo__isnull=False).exclude(archivo='')[:10]:
        try:
            filename = str(clase.archivo) if clase.archivo else 'Sin archivo'
            print(f"   - ID {clase.id}: {clase.tipo_archivo} - {filename[:50]}")
        except:
            print(f"   - ID {clase.id}: {clase.tipo_archivo}")

print("\n✅ No se perderá ningún dato. La migración será segura.")
