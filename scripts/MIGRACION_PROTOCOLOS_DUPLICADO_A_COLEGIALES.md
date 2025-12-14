# 🔄 Migración de Protocolos: Dupuytren → Colegiales

## ⚠️ PROBLEMA DETECTADO

Los protocolos se guardaron en la base de datos del proyecto **Dupuytren** en lugar de **Colegiales**.

**Objetivo**: Migrar todos los datos de la app `protocolos` de una BD a otra.

---

## 📋 Plan de Migración Paso a Paso

### ✅ Paso 1: BACKUP de seguridad (CRÍTICO)

```bash
# Hacer backup de ambas bases de datos ANTES de cualquier operación
cd c:\Dev\GitHub\gestion_servicio

# Backup de Colegiales (destino)
copy db.sqlite3 db.sqlite3.backup_colegiales_%date:~-4,4%%date:~-10,2%%date:~-7,2%

# Si la BD de Dupuytren está en otra ubicación, hacer backup también
# copy C:\ruta\dupuytren\db.sqlite3 C:\ruta\dupuytren\db.sqlite3.backup
```

---

### 🔍 Paso 2: Verificar qué BD tiene los protocolos

```bash
cd c:\Dev\GitHub\gestion_servicio
gestion_env\Scripts\activate

# Verificar BD ACTUAL de Colegiales
python manage.py shell
```

```python
from protocolos.models import Protocolo, FaseAdquisicion, Modalidad, RegionAnatomica, Tag

# Contar registros en BD actual
print(f"Protocolos: {Protocolo.objects.count()}")
print(f"Fases: {FaseAdquisicion.objects.count()}")
print(f"Modalidades: {Modalidad.objects.count()}")
print(f"Regiones: {RegionAnatomica.objects.count()}")
print(f"Tags: {Tag.objects.count()}")

# Listar primeros 3 protocolos para confirmar
for p in Protocolo.objects.all()[:3]:
    print(f"- {p.nombre}")

exit()
```

**Resultado esperado en Colegiales (vacío o con pocos datos)**:
```
Protocolos: 0 (o pocos)
Fases: 0
Modalidades: 0-2
Regiones: 0-3
Tags: 0-4
```

**Resultado esperado en Dupuytren (con todos los datos)**:
```
Protocolos: 17
Fases: 27
Modalidades: 2-3
Regiones: 10+
Tags: 4+
```

---

### 📤 Paso 3: EXPORTAR datos desde BD de Dupuytren

**Opción A: Si tienes acceso al proyecto Dupuytren**

```bash
# Ir al proyecto Dupuytren
cd C:\ruta\al\proyecto\dupuytren
dupuytren_env\Scripts\activate  # O el nombre de su venv

# Exportar TODOS los modelos de protocolos
python manage.py dumpdata protocolos --indent 2 --output=protocolos_export_full.json

# Verificar que el archivo se creó
dir protocolos_export_full.json

# Copiar archivo al proyecto Colegiales
copy protocolos_export_full.json C:\Dev\GitHub\gestion_servicio\scripts\
```

**Opción B: Si NO tienes acceso (BD SQLite directa)**

```bash
cd c:\Dev\GitHub\gestion_servicio\scripts

# Usar SQLite para extraer datos directamente
# (Crear script Python para leer la BD de Dupuytren)
```

---

### 📥 Paso 4: IMPORTAR datos en BD de Colegiales

```bash
cd c:\Dev\GitHub\gestion_servicio
gestion_env\Scripts\activate

# Verificar que el archivo existe
dir scripts\protocolos_export_full.json

# OPCIÓN 1: Importar TODO (recomendado si BD está vacía)
python manage.py loaddata scripts\protocolos_export_full.json

# OPCIÓN 2: Importar selectivo (si hay datos parciales)
# Ver Paso 5 para script de importación inteligente
```

---

### 🧪 Paso 5: VERIFICAR importación

```bash
python manage.py shell
```

```python
from protocolos.models import Protocolo, FaseAdquisicion, Modalidad, RegionAnatomica, Tag

# Contar registros importados
print(f"✅ Protocolos: {Protocolo.objects.count()}")
print(f"✅ Fases: {FaseAdquisicion.objects.count()}")
print(f"✅ Modalidades: {Modalidad.objects.count()}")
print(f"✅ Regiones: {RegionAnatomica.objects.count()}")
print(f"✅ Tags: {Tag.objects.count()}")

# Listar todos los protocolos para confirmar
print("\n📋 Protocolos importados:")
for p in Protocolo.objects.all():
    print(f"- {p.nombre} ({p.fases.count()} fases)")

# Verificar integridad de relaciones
print("\n🔗 Verificar relaciones:")
for p in Protocolo.objects.all()[:3]:
    print(f"\n{p.nombre}:")
    print(f"  Modalidad: {p.modalidad.codigo if p.modalidad else 'SIN MODALIDAD ❌'}")
    print(f"  Región: {p.region.nombre if p.region else 'SIN REGIÓN ❌'}")
    print(f"  Tags: {', '.join(t.nombre for t in p.tags.all())}")
    print(f"  Fases: {p.fases.count()}")

exit()
```

**Resultado esperado**:
```
✅ Protocolos: 17
✅ Fases: 27
✅ Modalidades: 2-3
✅ Regiones: 10+
✅ Tags: 4+

📋 Protocolos importados:
- TC Hígado trifásico (caracterización de lesión focal) (3 fases)
- TC Riñón multifásico (renal mass protocol) (4 fases)
- ...
```

---

### ✅ Paso 6: PROBAR sistema completo

```bash
# Verificar Django
python manage.py check

# Iniciar servidor
python manage.py runserver
```

**Probar en navegador**:
1. http://localhost:8000/protocolos/ → Ver lista completa
2. http://localhost:8000/protocolos/elegir/ → Ver página de decisión
3. Verificar que todos los escenarios tienen botón verde
4. Probar filtros (search, tags, fases)

---

## 🚨 Si hay conflictos de ID

### Problema: "IntegrityError: UNIQUE constraint failed"

**Causa**: Ya existen algunos registros en Colegiales con los mismos IDs.

**Solución A: Limpiar BD de Colegiales y reimportar**

```bash
python manage.py shell
```

```python
from protocolos.models import Protocolo, FaseAdquisicion, Modalidad, RegionAnatomica, Tag

# CUIDADO: Esto borra TODO de protocolos
print("⚠️ ELIMINANDO TODOS LOS DATOS DE PROTOCOLOS...")

FaseAdquisicion.objects.all().delete()
Protocolo.objects.all().delete()
Tag.objects.all().delete()
RegionAnatomica.objects.all().delete()
Modalidad.objects.all().delete()

print("✅ BD limpia. Saliendo...")
exit()
```

```bash
# Ahora reimportar
python manage.py loaddata scripts\protocolos_export_full.json
```

**Solución B: Importación inteligente (preservando IDs existentes)**

```python
# Ver script en Paso 7
```

---

## 🔧 Paso 7: Script de Importación Inteligente

**Si necesitas importar sin conflictos de ID** (crea archivo: `scripts/importar_protocolos_sin_conflictos.py`):

```python
import json
from django.core.management.base import BaseCommand
from protocolos.models import Protocolo, FaseAdquisicion, Modalidad, RegionAnatomica, Tag

# Leer JSON exportado
with open('scripts/protocolos_export_full.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# Separar por modelo
modalidades_data = [d for d in data if d['model'] == 'protocolos.modalidad']
regiones_data = [d for d in data if d['model'] == 'protocolos.regionanatomica']
tags_data = [d for d in data if d['model'] == 'protocolos.tag']
protocolos_data = [d for d in data if d['model'] == 'protocolos.protocolo']
fases_data = [d for d in data if d['model'] == 'protocolos.faseadquisicion']

# Mapeo de IDs viejos a nuevos
id_map = {}

# Importar Modalidades
for item in modalidades_data:
    fields = item['fields']
    obj, created = Modalidad.objects.get_or_create(
        codigo=fields['codigo'],
        defaults={'nombre': fields['nombre']}
    )
    id_map[f"modalidad_{item['pk']}"] = obj.id
    print(f"{'✅ Creado' if created else '⚠️ Existía'} Modalidad: {obj.codigo}")

# Importar Regiones
for item in regiones_data:
    fields = item['fields']
    obj, created = RegionAnatomica.objects.get_or_create(
        nombre=fields['nombre'],
        defaults={'descripcion': fields.get('descripcion', '')}
    )
    id_map[f"region_{item['pk']}"] = obj.id
    print(f"{'✅ Creado' if created else '⚠️ Existía'} Región: {obj.nombre}")

# Importar Tags
for item in tags_data:
    fields = item['fields']
    obj, created = Tag.objects.get_or_create(
        nombre=fields['nombre'],
        defaults={'color': fields.get('color', '#3b82f6')}
    )
    id_map[f"tag_{item['pk']}"] = obj.id
    print(f"{'✅ Creado' if created else '⚠️ Existía'} Tag: {obj.nombre}")

# Importar Protocolos
for item in protocolos_data:
    fields = item['fields']
    
    # Buscar si ya existe por nombre
    protocolo = Protocolo.objects.filter(nombre=fields['nombre']).first()
    
    if protocolo:
        print(f"⚠️ Protocolo ya existe: {protocolo.nombre} (ID: {protocolo.id})")
        id_map[f"protocolo_{item['pk']}"] = protocolo.id
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
    if 'tags' in fields:
        for tag_id in fields['tags']:
            tag_nuevo_id = id_map.get(f"tag_{tag_id}")
            if tag_nuevo_id:
                protocolo.tags.add(tag_nuevo_id)
    
    id_map[f"protocolo_{item['pk']}"] = protocolo.id
    print(f"✅ Creado Protocolo: {protocolo.nombre} (ID: {protocolo.id})")

# Importar Fases
for item in fases_data:
    fields = item['fields']
    
    protocolo_nuevo_id = id_map.get(f"protocolo_{fields['protocolo']}")
    region_nuevo_id = id_map.get(f"region_{fields.get('region')}")
    
    if not protocolo_nuevo_id:
        print(f"❌ No se pudo importar fase: protocolo no encontrado")
        continue
    
    fase = FaseAdquisicion.objects.create(
        protocolo_id=protocolo_nuevo_id,
        nombre=fields['nombre'],
        orden=fields.get('orden', 1),
        delay_segundos=fields.get('delay_segundos'),
        region_id=region_nuevo_id,
    )
    print(f"✅ Creado Fase: {fase.nombre} para {fase.protocolo.nombre}")

print("\n🎉 IMPORTACIÓN COMPLETA")
```

**Ejecutar**:
```bash
python manage.py shell < scripts\importar_protocolos_sin_conflictos.py
```

---

## 📊 Checklist Final

```
[ ] Backup de db.sqlite3 creado
[ ] Conteo de registros en BD Dupuytren verificado
[ ] Conteo de registros en BD Colegiales verificado
[ ] Archivo protocolos_export_full.json exportado
[ ] Archivo copiado a scripts/ de Colegiales
[ ] Importación ejecutada (loaddata o script inteligente)
[ ] Conteo post-importación verificado (17 protocolos, 27 fases)
[ ] python manage.py check ✅
[ ] Servidor funcionando
[ ] /protocolos/ muestra lista completa
[ ] /protocolos/elegir/ muestra 10 escenarios con botones verdes
[ ] Filtros funcionando correctamente
```

---

## 🐛 Troubleshooting

### Error: "No such table: protocolos_protocolo"

**Causa**: Migraciones no aplicadas en BD de Colegiales

**Solución**:
```bash
python manage.py migrate protocolos
# Luego reintentar importación
```

### Error: "Foreign key constraint failed"

**Causa**: Orden incorrecto de importación (protocolos antes que modalidades)

**Solución**: Usar script inteligente del Paso 7

### Archivo JSON vacío o con error

**Causa**: Exportación incompleta desde Dupuytren

**Solución**:
```bash
# En proyecto Dupuytren, verificar:
python manage.py shell
>>> from protocolos.models import Protocolo
>>> Protocolo.objects.count()  # Debe ser > 0
```

---

## 🔄 Alternativa: Migración Manual (si todo falla)

Si los métodos anteriores fallan, usar comandos de seed existentes:

```bash
cd c:\Dev\GitHub\gestion_servicio
gestion_env\Scripts\activate

# Ejecutar en orden:
python manage.py shell
```

```python
# Copiar contenido de:
exec(open('protocolos/management/commands/cargar_protocolos_base.py').read())
exec(open('protocolos/management/commands/seed_protocolos_tc_core.py').read())
exec(open('protocolos/management/commands/seed_protocolos_tc_multifasicos.py').read())
```

Esto recreará los 17 protocolos desde cero en la BD correcta.

---

**Creado**: 2025-12-13  
**Propósito**: Migración segura de datos de protocolos entre bases de datos  
**Tiempo estimado**: 15-30 minutos
