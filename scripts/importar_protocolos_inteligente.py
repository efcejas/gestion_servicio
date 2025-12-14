"""
Script para importar protocolos desde JSON sin conflictos de ID.
Usar en el proyecto Colegiales (destino).

Uso:
    python manage.py shell
    >>> exec(open('scripts/importar_protocolos_inteligente.py').read())
"""

import json
import os
from protocolos.models import Protocolo, FaseAdquisicion, Modalidad, RegionAnatomica, Tag

def importar_protocolos_inteligente():
    """
    Importa protocolos desde JSON manejando conflictos de ID automáticamente.
    """
    
    # Buscar archivo JSON
    json_file = 'scripts/protocolos_export_full.json'
    
    if not os.path.exists(json_file):
        print(f"❌ ERROR: No se encontró el archivo {json_file}")
        print(f"   Primero debes exportar los datos desde el proyecto Dupuytren")
        return
    
    print(f"📥 Importando datos desde {json_file}...")
    
    # Leer JSON
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print(f"📦 Total de registros en archivo: {len(data)}")
    
    # Separar por modelo
    modalidades_data = [d for d in data if d['model'] == 'protocolos.modalidad']
    regiones_data = [d for d in data if d['model'] == 'protocolos.regionanatomica']
    tags_data = [d for d in data if d['model'] == 'protocolos.tag']
    protocolos_data = [d for d in data if d['model'] == 'protocolos.protocolo']
    fases_data = [d for d in data if d['model'] == 'protocolos.faseadquisicion']
    
    print(f"\n📊 Distribución:")
    print(f"  - Modalidades: {len(modalidades_data)}")
    print(f"  - Regiones: {len(regiones_data)}")
    print(f"  - Tags: {len(tags_data)}")
    print(f"  - Protocolos: {len(protocolos_data)}")
    print(f"  - Fases: {len(fases_data)}")
    
    # Mapeo de IDs viejos a nuevos
    id_map = {}
    
    # 1. Importar Modalidades
    print("\n1️⃣ Importando Modalidades...")
    for item in modalidades_data:
        fields = item['fields']
        obj, created = Modalidad.objects.get_or_create(
            codigo=fields['codigo'],
            defaults={'nombre': fields['nombre']}
        )
        id_map[f"modalidad_{item['pk']}"] = obj.id
        status = '✅ Creado' if created else '⚠️ Existía'
        print(f"  {status} {obj.codigo} (ID: {obj.id})")
    
    # 2. Importar Regiones
    print("\n2️⃣ Importando Regiones Anatómicas...")
    for item in regiones_data:
        fields = item['fields']
        obj, created = RegionAnatomica.objects.get_or_create(
            nombre=fields['nombre'],
            defaults={'descripcion': fields.get('descripcion', '')}
        )
        id_map[f"region_{item['pk']}"] = obj.id
        status = '✅ Creado' if created else '⚠️ Existía'
        print(f"  {status} {obj.nombre} (ID: {obj.id})")
    
    # 3. Importar Tags
    print("\n3️⃣ Importando Tags...")
    for item in tags_data:
        fields = item['fields']
        obj, created = Tag.objects.get_or_create(
            nombre=fields['nombre'],
            defaults={'color': fields.get('color', '#3b82f6')}
        )
        id_map[f"tag_{item['pk']}"] = obj.id
        status = '✅ Creado' if created else '⚠️ Existía'
        print(f"  {status} {obj.nombre} (ID: {obj.id})")
    
    # 4. Importar Protocolos
    print("\n4️⃣ Importando Protocolos...")
    creados = 0
    existian = 0
    
    for item in protocolos_data:
        fields = item['fields']
        
        # Buscar si ya existe por nombre
        protocolo = Protocolo.objects.filter(nombre=fields['nombre']).first()
        
        if protocolo:
            print(f"  ⚠️ Ya existe: {protocolo.nombre} (ID: {protocolo.id})")
            id_map[f"protocolo_{item['pk']}"] = protocolo.id
            existian += 1
            continue
        
        # Crear nuevo
        protocolo = Protocolo.objects.create(
            nombre=fields['nombre'],
            descripcion=fields.get('descripcion', ''),
            modalidad_id=id_map.get(f"modalidad_{fields['modalidad']}"),
            region_id=id_map.get(f"region_{fields['region']}"),
            requiere_contraste_ev=fields.get('requiere_contraste_ev', False),
            requiere_contraste_oral=fields.get('requiere_contraste_oral', False),
            es_activo=fields.get('es_activo', True),
        )
        
        # Agregar tags
        if 'tags' in fields and fields['tags']:
            for tag_id in fields['tags']:
                tag_nuevo_id = id_map.get(f"tag_{tag_id}")
                if tag_nuevo_id:
                    protocolo.tags.add(tag_nuevo_id)
        
        id_map[f"protocolo_{item['pk']}"] = protocolo.id
        print(f"  ✅ Creado: {protocolo.nombre} (ID: {protocolo.id})")
        creados += 1
    
    print(f"\n  📊 Protocolos: {creados} creados, {existian} ya existían")
    
    # 5. Importar Fases
    print("\n5️⃣ Importando Fases de Adquisición...")
    fases_creadas = 0
    fases_error = 0
    
    for item in fases_data:
        fields = item['fields']
        
        protocolo_nuevo_id = id_map.get(f"protocolo_{fields['protocolo']}")
        region_nuevo_id = id_map.get(f"region_{fields.get('region')}")
        
        if not protocolo_nuevo_id:
            print(f"  ❌ Error: protocolo no encontrado para fase {fields['nombre']}")
            fases_error += 1
            continue
        
        # Verificar si ya existe esta fase
        fase_existe = FaseAdquisicion.objects.filter(
            protocolo_id=protocolo_nuevo_id,
            nombre=fields['nombre'],
            orden=fields.get('orden', 1)
        ).first()
        
        if fase_existe:
            print(f"  ⚠️ Fase ya existe: {fase_existe.nombre}")
            continue
        
        fase = FaseAdquisicion.objects.create(
            protocolo_id=protocolo_nuevo_id,
            nombre=fields['nombre'],
            orden=fields.get('orden', 1),
            delay_segundos=fields.get('delay_segundos'),
            region_id=region_nuevo_id,
        )
        print(f"  ✅ {fase.nombre} → {fase.protocolo.nombre} (ID: {fase.id})")
        fases_creadas += 1
    
    print(f"\n  📊 Fases: {fases_creadas} creadas, {fases_error} errores")
    
    # Resumen final
    print("\n" + "="*60)
    print("🎉 IMPORTACIÓN COMPLETADA")
    print("="*60)
    print(f"\n📊 Estado final de la BD:")
    print(f"  - Modalidades: {Modalidad.objects.count()}")
    print(f"  - Regiones: {RegionAnatomica.objects.count()}")
    print(f"  - Tags: {Tag.objects.count()}")
    print(f"  - Protocolos: {Protocolo.objects.count()}")
    print(f"  - Fases: {FaseAdquisicion.objects.count()}")
    
    print(f"\n✅ Próximos pasos:")
    print(f"  1. Verificar: python manage.py check")
    print(f"  2. Iniciar servidor: python manage.py runserver")
    print(f"  3. Probar: http://localhost:8000/protocolos/elegir/")

# Ejecutar importación
importar_protocolos_inteligente()
