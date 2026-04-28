# Sistema de Preinformes - Correcciones de Formato para Word/EGES

## Pendiente Abierto (27/04/2026)

### Autoguardado en edicion/revision
- Estado actual: pendiente de resolucion definitiva.
- Sintoma reportado en entorno real: al escribir no cambia el indicador a "Editando..." y no se observa guardado automatico tras el intervalo.
- Alcance: edicion de preinforme por residente y pantalla de revision por staff (integracion con CKEditor5 de django_ckeditor_5).

### Contexto de intento previo
- Se ajustaron endpoints y condiciones de estados editables.
- Se reforzo el binding del editor para tomar la instancia desde el registry del widget.
- Persisten reportes de no activacion del estado visual de autoguardado en algunos escenarios.

### Plan de reanudacion sugerido
1. Verificar en navegador (Network + Console) que haya evento de cambio del editor y POST al endpoint de autosave.
2. Confirmar en runtime que la instancia activa corresponda al campo correcto (`id_informe_html` / `id_informe_final_html`).
3. Agregar trazas temporales de diagnostico en frontend (sin dejar logs permanentes en produccion).
4. Cubrir con test E2E de frontend (Playwright) para validar transiciones del indicador: `Listo -> Editando -> Guardando -> Guardado`.
5. Luego remover trazas temporales y documentar fix final.

## 🎯 Objetivo
Garantizar que el formato de los preinformes se preserve correctamente al copiar a Word/EGES, con:
- Título alineado a la izquierda (no centrado)
- Párrafos correctamente separados
- Conclusión condicional (solo si tiene contenido real)
- Estilos inline para compatibilidad con Word

## ✅ Cambios Implementados

### A) Models (`preinformes/models.py`)
✅ **Helper functions ya implementadas:**
- `has_real_text(html)` - Detecta si hay texto real en HTML (ignora `<p>&nbsp;</p>`, `<p><br></p>`, etc.)
- `sanitize_center_alignment(html)` - Elimina todo tipo de centrado (styles, tags, classes)
- `normalize_html_content(content)` - Convierte saltos de línea a párrafos `<p>` separados

✅ **Método mejorado:**
- `RevisionPreinforme.generar_informe_original_residente()` - Genera HTML con:
  - Título alineado a la izquierda
  - Párrafos correctamente separados
  - Conclusión solo si `has_real_text()` devuelve True
  - Sin alineación centrada

### B) Templates (`templates/preinformes/revisar_preinforme.html`)
✅ **Cambios aplicados:**
- Título cambiado de `text-center` a `text-left`
- Conclusión renderizada solo si `preinforme.conclusion|has_real_text`
- JS `copiarInformeFinal()` mejorado:
  - Agrega estilos inline a todos los `<p>`: `margin: 0 0 10px 0; line-height: 1.5;`
  - Copia con `ClipboardItem` (text/html + text/plain)
  - Fallbacks para navegadores antiguos

### C) Template Tags (`preinformes/templatetags/preinformes_tags.py`)
✅ **Nuevo filtro creado:**
- `has_real_text` - Permite usar en templates: `{% if campo|has_real_text %}`

### D) Management Commands
✅ **Comandos ya disponibles:**

#### 1. `test_html_preinforme.py` - Validar HTML generado
```bash
python manage.py test_html_preinforme <numero_estudio>
```
**Muestra:**
- HTML completo generado
- Validaciones:
  - ❌/✅ Presencia de `text-align:center`
  - ❌/✅ Presencia de tags `<center>`
  - ❌/✅ Presencia de clase `text-center`
  - 📊 Cantidad de tags `<p>`
  - 📊 Presencia de header "CONCLUSIÓN"
- Estadísticas (caracteres, palabras, párrafos)

#### 2. `regenerar_snapshots.py` - Migrar datos viejos
```bash
# Modo dry-run (muestra qué haría sin cambiar nada)
python manage.py regenerar_snapshots --dry-run

# Aplicar regeneración real
python manage.py regenerar_snapshots
```
**Características:**
- Solo procesa preinformes en `borrador` o `pendiente_revision`
- Regenera `informe_residente_snapshot` con nuevo formato
- Actualiza `informe_final_html` si no fue editado por staff
- Muestra resumen de regenerados vs saltados

#### 3. `test_normalize_html.py` - Probar normalización de HTML
```bash
python manage.py test_normalize_html
```
**Características:**
- Prueba la función `normalize_html_content()` con diferentes casos
- Verifica que `<br>` se conviertan a `<p>` separados
- Verifica que `\n` se conviertan a `<p>` separados
- Muestra análisis de cada caso de prueba

#### 4. `normalizar_informe_final.py` - Normalizar informe_final_html existentes
```bash
# Modo dry-run (muestra qué haría sin cambiar nada)
python manage.py normalizar_informe_final --dry-run

# Aplicar normalización real
python manage.py normalizar_informe_final

# Incluir preinformes en_revision (usar con cuidado)
python manage.py normalizar_informe_final --force --dry-run
```
**Características:**
- Convierte `<br>` a `<p>` separados en `informe_final_html`
- Solo procesa `borrador` y `pendiente_revision` (sin --force)
- Con `--force`: incluye `en_revision` (usar solo si es necesario)
- Muestra análisis antes/después (cantidad de `<p>` y `<br>`)
- Modo dry-run para revisar antes de aplicar

## 🧪 Cómo Probar

### Paso 1: Validar HTML de un preinforme existente
```bash
python manage.py test_html_preinforme 12345
```
**Verificar que:**
- ✅ NO aparece "text-align:center"
- ✅ NO aparece tags `<center>`
- ✅ Hay múltiples tags `<p>` (párrafos separados)
- ✅ "CONCLUSIÓN" solo aparece si el campo tiene contenido

### Paso 2: Regenerar snapshots viejos (opcional)
```bash
# Primero ver qué se modificaría
python manage.py regenerar_snapshots --dry-run

# Si todo se ve bien, aplicar cambios
python manage.py regenerar_snapshots
```

### Paso 3: Test end-to-end
1. **Crear nuevo preinforme** como residente:
   - Aplicar plantilla
   - Redactar técnica con varios párrafos (usar Enter entre líneas)
   - Redactar hallazgos con varios párrafos
   - Dejar conclusión vacía o agregar texto

2. **Enviar a revisión**

3. **Revisar como staff**:
   - Verificar que el "Preinforme Original" muestra:
     - Título alineado a la izquierda
     - Párrafos separados
     - "CONCLUSIÓN" solo si tiene contenido
   - Editar el "Informe Final"
   - Usar botón "Copiar"

4. **Pegar en Word**:
   - Verificar que los párrafos se mantienen separados
   - Verificar que el título está alineado a la izquierda
   - Verificar que las negritas se mantienen

## 🔧 Detalles Técnicos

### Problema: CKEditor y Párrafos con `<br>`

**Síntoma:** El editor CKEditor no separaba párrafos visualmente aunque el contenido original tenía saltos de línea.

**Causa raíz:** Cuando se precargaba `informe_final_html`, el contenido podía tener:
- Texto plano con `\n` (no interpretado como HTML)
- Un solo `<p>` con múltiples `<br>` dentro
- CKEditor interpreta `<br>` como saltos de línea dentro del mismo párrafo, no como párrafos separados

**Solución implementada:**
1. **Mejorada `normalize_html_content()`** para:
   - Convertir todos los `<br>`, `<br/>`, `<BR>` a saltos de línea temporales
   - Procesar todos los tags `<p>` que contengan `\n` dentro
   - Dividir el contenido en líneas y crear un `<p>` por cada línea
   - Resultado: Múltiples `<p>...</p>` separados sin `<br>`

2. **Actualizada vista `revisar_preinforme`** para:
   - Aplicar `normalize_html_content()` al precargar `informe_final_html`
   - Esto asegura que CKEditor reciba HTML con párrafos ya separados

3. **Actualizado método `inicializar_informe_final()`** para:
   - Normalizar el contenido antes de asignarlo
   - Mantener consistencia en toda la aplicación

### Flujo de HTML
```
1. Residente crea preinforme (CKEditor) → Guarda en BD
2. Staff inicia revisión → Se genera snapshot con generar_informe_original_residente()
3. Snapshot se precarga en editor del staff → staff edita
4. Staff copia informe → JS agrega estilos inline a <p>
5. ClipboardItem copia text/html + text/plain → Pega en Word
```

### Estilos Inline para Word
El JS `copiarInformeFinal()` transforma:
```html
<p>Texto del párrafo</p>
```
En:
```html
<p style="margin: 0 0 10px 0; line-height: 1.5;">Texto del párrafo</p>
```

Esto garantiza que Word respete el espaciado entre párrafos.

### Detección de HTML Vacío
`has_real_text()` considera vacío:
- `<p></p>`
- `<p>&nbsp;</p>`
- `<p><br></p>`
- `<p> </p>`
- `<p><br>&nbsp;</p>`

Solo devuelve `True` si hay texto alfanumérico real.

## 📝 Notas Importantes

1. **No se modifican plantillas existentes** - Los helpers solo afectan el HTML generado, no el contenido guardado en BD
2. **Regeneración es segura** - Solo afecta preinformes en `borrador` o `pendiente_revision`
3. **Staff puede seguir editando** - El informe final es un campo CKEditor independiente
4. **Compatibilidad navegadores** - El JS tiene fallbacks para ClipboardItem, execCommand, y textarea

## 🎓 Testing Recomendado

1. ✅ Validar HTML con `test_html_preinforme`
2. ✅ Crear nuevo preinforme con plantilla
3. ✅ Verificar que párrafos se separan al enviar a revisión
4. ✅ Copiar y pegar en Word
5. ✅ Regenerar snapshots viejos (--dry-run primero)
6. ✅ Verificar que conclusión vacía no muestra header

---
**Estado:** ✅ Implementado y listo para testing
**Fecha:** 8 de enero de 2026
