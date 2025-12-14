"""
Script para exportar TODOS los datos de protocolos desde la BD actual.
Usar en el proyecto que tiene los datos (Dupuytren).
"""

import json
from protocolos.models import Protocolo, FaseAdquisicion, Modalidad, RegionAnatomica, Tag

def exportar_protocolos():
    data = []
    
    print("📤 Exportando datos de protocolos...")
    
    # 1. Modalidades
    print("\n1️⃣ Exportando Modalidades...")
    for obj in Modalidad.objects.all():
        data.append({
            'model': 'protocolos.modalidad',
            'pk': obj.id,
            'fields': {
                'codigo': obj.codigo,
                'nombre': obj.nombre,
            }
        })
        print(f"  ✅ {obj.codigo}")
    
    # 2. Regiones
    print("\n2️⃣ Exportando Regiones Anatómicas...")
    for obj in RegionAnatomica.objects.all():
        data.append({
            'model': 'protocolos.regionanatomica',
            'pk': obj.id,
            'fields': {
                'nombre': obj.nombre,
                'descripcion': obj.descripcion if hasattr(obj, 'descripcion') else '',
            }
        })
        print(f"  ✅ {obj.nombre}")
    
    # 3. Tags
    print("\n3️⃣ Exportando Tags...")
    for obj in Tag.objects.all():
        data.append({
            'model': 'protocolos.tag',
            'pk': obj.id,
            'fields': {
                'nombre': obj.nombre,
                'color': obj.color if hasattr(obj, 'color') else '#3b82f6',
            }
        })
        print(f"  ✅ {obj.nombre}")
    
    # 4. Protocolos
    print("\n4️⃣ Exportando Protocolos...")
    for obj in Protocolo.objects.all():
        data.append({
            'model': 'protocolos.protocolo',
            'pk': obj.id,
            'fields': {
                'nombre': obj.nombre,
                'descripcion': obj.descripcion,
                'modalidad': obj.modalidad.id if obj.modalidad else None,
                'region': obj.region.id if obj.region else None,
                'requiere_contraste_ev': obj.requiere_contraste_ev,
                'requiere_contraste_oral': obj.requiere_contraste_oral,
                'es_activo': obj.es_activo,
                'tags': [t.id for t in obj.tags.all()],
            }
        })
        print(f"  ✅ {obj.nombre}")
    
    # 5. Fases
    print("\n5️⃣ Exportando Fases de Adquisición...")
    for obj in FaseAdquisicion.objects.all():
        data.append({
            'model': 'protocolos.faseadquisicion',
            'pk': obj.id,
            'fields': {
                'protocolo': obj.protocolo.id,
                'nombre': obj.nombre,
                'orden': obj.orden,
                'delay_segundos': obj.delay_segundos,
                'region': obj.region.id if obj.region else None,
            }
        })
        print(f"  ✅ {obj.nombre} ({obj.protocolo.nombre})")
    
    # Guardar archivo
    output_file = 'protocolos_export_full.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"\n🎉 Exportación completa: {len(data)} registros")
    print(f"📁 Archivo creado: {output_file}")
    print(f"\n📋 Resumen:")
    print(f"  - Modalidades: {Modalidad.objects.count()}")
    print(f"  - Regiones: {RegionAnatomica.objects.count()}")
    print(f"  - Tags: {Tag.objects.count()}")
    print(f"  - Protocolos: {Protocolo.objects.count()}")
    print(f"  - Fases: {FaseAdquisicion.objects.count()}")
    print(f"\n✅ Ahora copia este archivo al proyecto Colegiales:")
    print(f"   copy {output_file} C:\\Dev\\GitHub\\gestion_servicio\\scripts\\")

# Ejecutar
exportar_protocolos()
