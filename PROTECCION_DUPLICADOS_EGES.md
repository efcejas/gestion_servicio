# 🛡️ Sistema de Protección contra Duplicados - EGES Import

## Problema Original

Cuando se importan archivos Excel EGES que contienen datos de meses solapados (ej: archivo de octubre + archivo con datos de septiembre y octubre), el sistema podría crear filas duplicadas en la base de datos, inflando artificialmente las estadísticas.

**Ejemplo:**
- Importas `AtendidosOctubre.xlsx` → 1000 filas
- Importas `Atendidos_Sept_Oct.xlsx` → 1500 filas (500 de septiembre + 1000 de octubre)
- Sin protección: Tendrías 2500 filas (1000 duplicadas de octubre)
- Con protección: Tendrías 1500 filas únicas

## Solución Implementada

### 1. Constraint de Unicidad en Base de Datos

**Archivo:** `eges_import/models.py`

```python
class EgesRow(models.Model):
    # ... campos ...
    
    class Meta:
        unique_together = [
            ('historia_clinica', 'fecha_turno', 'hora_turno', 'centro_atencion', 'servicio')
        ]
```

Este constraint garantiza a nivel de base de datos que **no pueden existir dos filas** con la misma combinación de:
- Historia Clínica
- Fecha del turno
- Hora del turno
- Centro de atención
- Servicio/práctica

PostgreSQL rechazará cualquier intento de insertar un duplicado.

### 2. Detección Inteligente con `get_or_create`

**Archivo:** `eges_import/views.py` → función `procesar_excel_eges()`

```python
fila, created = EgesRow.objects.get_or_create(
    # Campos del unique_together
    historia_clinica=hc,
    fecha_turno=fecha_turno,
    hora_turno=hora_turno,
    centro_atencion=centro,
    servicio=servicio,
    # Defaults para el resto de campos si se crea
    defaults={
        'batch': batch,
        'numero_turno': numero_turno,
        # ... otros campos ...
    }
)

if created:
    filas_creadas += 1
else:
    filas_duplicadas += 1  # Ya existía
```

**Comportamiento:**
- Si la fila es **nueva** → `created=True` → Se crea en la base de datos
- Si la fila **ya existe** → `created=False` → Se cuenta como duplicada pero NO se crea

### 3. Feedback al Usuario

Después de la importación, el sistema muestra un mensaje diferenciado:

**Sin duplicados:**
```
✓ Archivo importado correctamente. 
  Se procesaron 1000 filas nuevas.
  0 filas con errores fueron omitidas.
```

**Con duplicados detectados:**
```
⚠️ Archivo importado. 
   Se procesaron 500 filas nuevas. 
   Se detectaron 1000 filas duplicadas (ya existían en la base de datos).
   0 filas con errores fueron omitidas.
```

Esto permite al usuario:
- Saber que importó el archivo correcto pero con datos solapados
- Confirmar que NO se duplicaron las estadísticas
- Entender cuántos datos realmente nuevos agregó

## Migración de Datos Existentes

**Archivo:** `eges_import/migrations/0003_remove_duplicates_before_constraint.py`

Antes de aplicar el constraint, ejecutamos una limpieza automática:

```python
def remove_duplicate_rows(apps, schema_editor):
    """Elimina duplicados manteniendo solo la primera aparición"""
    # Query SQL que encuentra todos los duplicados excepto el primero
    # Los elimina automáticamente
```

**Resultado en tu base de datos:** Eliminó 945 registros duplicados históricos.

## Casos de Uso Cubiertos

### ✅ Caso 1: Importación secuencial normal
1. Importas `Octubre.xlsx` → 1000 filas nuevas
2. Importas `Noviembre.xlsx` → 1200 filas nuevas
3. **Total:** 2200 filas únicas ✓

### ✅ Caso 2: Re-importación accidental
1. Importas `Octubre.xlsx` → 1000 filas nuevas
2. Por error, vuelves a importar `Octubre.xlsx` → 0 filas nuevas, 1000 duplicadas detectadas
3. **Total:** 1000 filas únicas ✓

### ✅ Caso 3: Archivo consolidado con solapamiento
1. Importas `Octubre.xlsx` → 1000 filas nuevas
2. Importas `Sept_Oct_Nov.xlsx` (3500 filas totales):
   - 800 de septiembre → 800 nuevas
   - 1000 de octubre → 1000 duplicadas (ignoradas)
   - 1700 de noviembre → 1700 nuevas
3. **Total:** 3500 filas únicas (800 + 1000 + 1700) ✓

### ✅ Caso 4: Actualización de datos
**IMPORTANTE:** Si la práctica cambió de estado (ej: de "Pendiente" a "Informado"), el sistema NO actualizará el registro existente. Solo detecta como duplicado y no lo re-crea.

**Comportamiento actual:**
- Primera importación: HC 12345, fecha 21/10, hora 14:10, estado "Pendiente"
- Segunda importación: HC 12345, fecha 21/10, hora 14:10, estado "Informado"
- **Resultado:** Se detecta como duplicado, NO se actualiza el estado

**Alternativa si se necesita actualización:**
```python
# En lugar de get_or_create, usar update_or_create:
fila, created = EgesRow.objects.update_or_create(
    # Campos del unique_together
    historia_clinica=hc,
    fecha_turno=fecha_turno,
    hora_turno=hora_turno,
    centro_atencion=centro,
    servicio=servicio,
    # Defaults que SE ACTUALIZAN si existe
    defaults={
        'batch': batch,
        'estado_turno': estado,  # Este campo se actualizaría
        # ...
    }
)
```

## Dashboard Global - Datos Consolidados

El Dashboard Global (`/eges/dashboard/`) **automáticamente ignora duplicados** porque:

1. El constraint `unique_together` garantiza que cada fila en `EgesRow` es única
2. Las métricas se calculan sobre `EgesRow.objects.all()` → solo filas únicas
3. No importa cuántos batches importes con datos solapados, las estadísticas siempre reflejan la realidad

**Ejemplo:**
- Batch #1 (Octubre.xlsx): 1000 filas → Dashboard muestra 1000 estudios
- Batch #2 (Sept_Oct.xlsx): 800 nuevas + 1000 duplicadas → Dashboard muestra 1800 estudios (NO 2800)

## Verificación Manual

Para verificar que no hay duplicados en la base de datos:

```python
from eges_import.models import EgesRow
from django.db.models import Count

# Buscar grupos con más de 1 registro (duplicados)
duplicados = EgesRow.objects.values(
    'historia_clinica', 'fecha_turno', 'hora_turno', 'centro_atencion', 'servicio'
).annotate(
    total=Count('id')
).filter(total__gt=1)

print(f"Duplicados encontrados: {duplicados.count()}")
# Debería ser 0 con el constraint activo
```

## Logs de Importación

Durante la importación, el sistema registra en consola:

```
[EGES] Iniciando importación: AtendidosOctubre.xlsx (269479 bytes)
[EGES] Batch #5 creado
[EGES] Procesando Excel...
[EGES] Encabezados encontrados: 15 columnas
[EGES] Procesadas 100 filas: 95 nuevas, 5 duplicadas, 0 errores...
[EGES] Procesadas 200 filas: 180 nuevas, 20 duplicadas, 0 errores...
...
[EGES] Workbook cerrado. Total: 850 nuevas, 150 duplicadas, 0 errores de 1000 procesadas
[EGES] Batch #5 completado exitosamente
```

Esto permite al administrador detectar rápidamente si un archivo tiene mucho solapamiento con datos existentes.

## Limitaciones y Consideraciones

### 1. Historia Clínica Vacía
Si dos filas tienen `historia_clinica=''` (vacío), pero el resto de campos idénticos, se consideran duplicadas.

**Solución:** Si este es un problema, agregar campo `numero_turno` al constraint:
```python
unique_together = [
    ('numero_turno', 'fecha_turno', 'hora_turno', 'centro_atencion', 'servicio')
]
```

### 2. Performance con Archivos Grandes
`get_or_create()` hace una consulta SELECT antes de cada INSERT. Para archivos de 10,000+ filas, puede ser lento.

**Optimización futura:**
- Hacer bulk_create de todas las filas nuevas
- Capturar IntegrityError de las duplicadas
- Reportar al final

### 3. No Actualiza Datos Existentes
Si un estudio cambió de estado, el sistema NO lo actualiza. Solo detecta el duplicado.

**Si se necesita actualización:** Cambiar a `update_or_create()` en lugar de `get_or_create()`.

## Testing

**Test 1: Importar el mismo archivo dos veces**
```bash
1. Navegar a /eges/importar/
2. Subir AtendidosOctubre.xlsx → Ver mensaje "1000 filas nuevas"
3. Subir nuevamente AtendidosOctubre.xlsx → Ver mensaje "0 filas nuevas, 1000 duplicadas"
4. Verificar Dashboard Global → Solo 1000 estudios
```

**Test 2: Archivo con solapamiento parcial**
```bash
1. Importar Octubre.xlsx (1000 filas)
2. Importar SeptiembreOctubre.xlsx (1800 filas totales)
3. Verificar mensaje: "800 nuevas, 1000 duplicadas"
4. Dashboard Global debe mostrar 1800 estudios únicos
```

## Mantenimiento

Si necesitas **borrar todos los duplicados manualmente** por alguna razón:

```python
# Shell de Django
from eges_import.models import EgesRow
from django.db import connection

with connection.cursor() as cursor:
    cursor.execute("""
        DELETE FROM eges_import_egesrow
        WHERE id NOT IN (
            SELECT MIN(id)
            FROM eges_import_egesrow
            GROUP BY historia_clinica, fecha_turno, hora_turno, centro_atencion, servicio
        )
    """)
    
print(f"Eliminados {cursor.rowcount} duplicados")
```

---

**Fecha de implementación:** 28 de diciembre de 2025  
**Registros duplicados eliminados en migración inicial:** 945  
**Estado:** ✅ Activo y funcionando
