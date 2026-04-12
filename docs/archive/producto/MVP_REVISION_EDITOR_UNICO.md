# Refactorización MVP Correcta: Sistema de Revisión con Editor Único

## Fecha: 7 de enero de 2026

## Problema Identificado

El sistema anterior tenía un flujo de trabajo que **NO** reflejaba la práctica médica real:

### ❌ Enfoque Anterior (Incorrecto):
- El staff debía reescribir TÉCNICA, HALLAZGOS y CONCLUSIÓN en 3 editores separados
- Incluso para cambiar una sola palabra, había que copiar/pegar todo el contenido
- Generaba trabajo duplicado e ineficiente
- No coincidía con el flujo de trabajo médico real

### ✅ Enfoque Actual (Correcto):
- El residente crea el preinforme estructurado (técnica, hallazgos, conclusión)
- El staff ve el informe completo en formato lectura
- El staff edita un **SOLO** editor pre-cargado con todo el contenido
- El staff solo modifica lo que necesita (palabras, frases, párrafos)
- El residente puede ver la comparación lado a lado

## Cambios Implementados

### 1. Modelo `RevisionPreinforme` (models.py)

#### Campos Eliminados:
```python
# ❌ ELIMINADOS
tecnica_staff (CKEditor5Field)
hallazgos_staff (CKEditor5Field)
conclusion_staff (CKEditor5Field)
informe_final (TextField)
```

#### Campos Nuevos:
```python
# ✅ NUEVOS
informe_residente_snapshot (TextField)
  - Snapshot del informe completo del residente
  - Se crea automáticamente al iniciar revisión
  - Permite comparaciones futuras

informe_final_html (CKEditor5Field)
  - Editor único con TODO el contenido
  - Pre-cargado con técnica + hallazgos + conclusión
  - El staff solo corrige lo necesario
```

#### Métodos Nuevos:
```python
generar_informe_original_residente()
  - Genera HTML con títulos y contenido completo
  - Formato: <h3>TÉCNICA</h3> + contenido + ...

crear_snapshot_residente()
  - Guarda snapshot del informe original
  - Solo se crea una vez

inicializar_informe_final()
  - Pre-carga el editor del staff con contenido del residente
  - Se ejecuta automáticamente al crear revisión

inicializar_revision()
  - Método principal que ejecuta snapshot + inicialización
```

### 2. Formulario `RevisionPreinformeForm` (forms.py)

**Antes:**
```python
fields = ['tecnica_staff', 'hallazgos_staff', 'conclusion_staff', 'comentarios_generales', 'puntuacion']
```

**Ahora:**
```python
fields = ['informe_final_html', 'comentarios_generales', 'puntuacion']
```

**Auto-inicialización:** El formulario automáticamente llama a `inicializar_revision()` si es nueva revisión.

### 3. Vista `revisar_preinforme` (views.py)

**Cambios:**
- Eliminada generación de informe final (ya no es necesario)
- El `informe_final_html` es el campo que se edita directamente
- Auto-inicialización verificada en GET request

**Flujo:**
1. GET: Verifica si existe revisión, si no tiene `informe_final_html`, inicializa
2. POST: Guarda directamente el `informe_final_html` (ya editado por el staff)
3. Finalización: Marca preinforme como finalizado, actualiza estadísticas

### 4. Nueva Vista `ver_comparacion_revision` (views.py)

**Funcionalidad:**
- Permite al residente ver su versión original vs versión del staff
- Muestra lado a lado: snapshot original y versión final
- Incluye comentarios del revisor y puntuación
- Botón para copiar informe final a EGES

**Permisos:**
- Residente autor del preinforme
- Staff que revisó
- Jefes y instructores

### 5. Templates

#### `revisar_preinforme.html` (Refactorizado Completo)

**Estructura:**
```
1. Header con información del estudio
2. Información del paciente
3. Preinforme Original del Residente
   └─ HTML formateado en solo lectura
   └─ Prose styling para mejor legibilidad

4. Editor del Staff
   └─ UN SOLO CKEditor5
   └─ Pre-cargado con contenido completo
   └─ Instrucción clara: "Modifique solo lo necesario"

5. Feedback para el Residente
   └─ Comentarios generales
   └─ Puntuación (opcional)

6. Vista Previa para EGES
   └─ Muestra el informe final
   └─ Botón copiar al portapapeles
```

**Características:**
- Tema limpio y claro (blanco)
- Secciones bien diferenciadas con colores
- Indicadores visuales (badges) para estado
- Botones con iconos Font Awesome
- Responsive design (mobile-friendly)

#### `comparacion_revision.html` (Nuevo)

**Estructura:**
```
1. Header
2. Información del estudio y revisión
3. Grid 2 columnas (lado a lado):
   ├─ Izquierda: Versión Original Residente
   └─ Derecha: Versión Final Staff
4. Comentarios del revisor
5. Informe final para copiar
6. Botones de navegación
```

**Características:**
- Colores diferenciados: azul (residente) vs verde (staff)
- Prose styling para mejor legibilidad
- Botón copiar con notificaciones
- Links de navegación claros

#### `ver_preinforme.html` (Actualizado)

**Cambios:**
- Botón nuevo: "Ver Comparación Completa"
- Eliminadas secciones de correcciones separadas
- Muestra solo: comentarios + informe final
- Informe final renderizado como HTML con prose

### 6. Migración 0006

**Operaciones:**
```sql
-- Eliminar campos antiguos
ALTER TABLE preinformes_revisionpreinforme 
  DROP COLUMN tecnica_staff,
  DROP COLUMN hallazgos_staff,
  DROP COLUMN conclusion_staff,
  DROP COLUMN informe_final;

-- Agregar campos nuevos
ALTER TABLE preinformes_revisionpreinforme
  ADD COLUMN informe_residente_snapshot TEXT,
  ADD COLUMN informe_final_html TEXT;
```

**Estado:** ✅ Aplicada exitosamente

### 7. URLs

**Nueva URL:**
```python
path('comparacion/<int:pk>/', views.ver_comparacion_revision, name='comparacion_revision')
```

## Flujo de Trabajo Completo

### Para el Residente:

1. **Crear Preinforme:**
   - Llena técnica, hallazgos, conclusión en editores separados
   - Envía a revisión

2. **Ver Revisión:**
   - Accede a "Ver Preinforme"
   - Ve sección "Revisión del Staff" con:
     - Comentarios del revisor
     - Informe final corregido
     - Botón "Ver Comparación Completa"

3. **Ver Comparación:**
   - Accede a vista de comparación
   - Ve lado a lado: su versión vs versión staff
   - Puede copiar informe final

### Para el Staff:

1. **Revisar Preinforme:**
   - Accede desde lista de revisión
   - Ve información del estudio y paciente
   - Ve preinforme original del residente (solo lectura)

2. **Editar:**
   - Editor CKEditor5 PRE-CARGADO con todo el contenido
   - Modifica SOLO lo que necesita:
     - Cambiar una palabra → solo cambia esa palabra
     - Corregir frase → solo corrige esa frase
     - Reescribir sección → reescribe esa sección
   - NO necesita copiar/pegar nada

3. **Feedback:**
   - Agrega comentarios generales para el residente
   - Asigna puntuación (opcional)

4. **Guardar:**
   - "Guardar y Continuar" → guarda sin finalizar
   - "Finalizar Revisión" → marca como completo

## Beneficios del Nuevo Sistema

### 1. Eficiencia
- ✅ El staff solo corrige lo necesario
- ✅ No más copy/paste de contenido completo
- ✅ Trabajo más rápido y directo

### 2. UX Mejorado
- ✅ Flujo natural de trabajo médico
- ✅ Interface limpia y clara
- ✅ Comparación visual lado a lado

### 3. Trazabilidad
- ✅ Snapshot del informe original
- ✅ Versión final claramente identificada
- ✅ Historial de cambios preservado

### 4. Educación
- ✅ Residente ve qué se corrigió
- ✅ Comparación clara entre versiones
- ✅ Comentarios específicos del revisor

## Testing

### Casos de Prueba:

1. **Crear nueva revisión:**
   - ✅ Verificar que `informe_final_html` se inicializa
   - ✅ Verificar que snapshot se crea

2. **Editar revisión:**
   - ✅ Modificar solo una palabra
   - ✅ Guardar y verificar cambio
   - ✅ Verificar que snapshot permanece intacto

3. **Ver comparación:**
   - ✅ Acceder como residente
   - ✅ Verificar versión original
   - ✅ Verificar versión final
   - ✅ Copiar informe final

4. **Finalizar revisión:**
   - ✅ Finalizar como staff
   - ✅ Verificar estado preinforme
   - ✅ Verificar actualización de estadísticas

## Archivos Modificados

```
preinformes/
├── models.py                           # RevisionPreinforme refactorizado
├── forms.py                            # RevisionPreinformeForm simplificado
├── views.py                            # revisar_preinforme + ver_comparacion_revision
├── urls.py                             # Nueva URL comparacion_revision
├── migrations/
│   └── 0006_remove_revision...py       # Migración de campos
└── templates/preinformes/
    ├── revisar_preinforme.html         # Refactorizado completo
    ├── comparacion_revision.html       # Nuevo template
    └── ver_preinforme.html             # Actualizado
```

## Estado Final

✅ **COMPLETO Y FUNCIONAL**

- Modelo migrado
- Formularios actualizados
- Vistas implementadas
- Templates creados/actualizados
- URLs configuradas
- Sistema probado

## Próximos Pasos (Fase 2 - Opcional)

1. **Diff Highlighting:**
   - Implementar resaltado de diferencias entre versiones
   - Usar librerías como `difflib` o `diff-match-patch`
   - Mostrar cambios con colores (agregado verde, eliminado rojo)

2. **Historial de Revisiones:**
   - Si un preinforme pasa por múltiples revisiones
   - Mantener historial de versiones
   - Permitir ver evolución del documento

3. **Comentarios Inline:**
   - Permitir comentarios específicos en párrafos
   - Similar a Google Docs
   - Mejor feedback contextual

---

**Documentación actualizada:** 7 de enero de 2026  
**Estado:** Sistema MVP funcionando correctamente  
**Próxima revisión:** Testing exhaustivo con usuarios reales