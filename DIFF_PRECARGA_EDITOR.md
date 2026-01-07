# DIFF: Implementación de Pre-carga del Editor de Revisión

## Fecha: 7 de enero de 2026

---

## 1. VIEWS.PY - Vista `revisar_preinforme`

### ANTES:
```python
# Obtener o crear revisión
revision, created = RevisionPreinforme.objects.get_or_create(
    preinforme=preinforme,
    defaults={'revisor': request.user}
)

if request.method == 'POST':
    form = RevisionPreinformeForm(request.POST, instance=revision, preinforme=preinforme)
    # ... resto del POST ...
else:
    form = RevisionPreinformeForm(instance=revision, preinforme=preinforme)
    # Inicializar revisión si es necesario
    if not revision.informe_final_html:
        revision.inicializar_revision()
        revision.save()
```

### DESPUÉS:
```python
# Obtener o crear revisión
revision, created = RevisionPreinforme.objects.get_or_create(
    preinforme=preinforme,
    defaults={'revisor': request.user}
)

# CRÍTICO: Asegurar que snapshot existe SIEMPRE
if not revision.informe_residente_snapshot:
    revision.crear_snapshot_residente()

# CRÍTICO: Pre-cargar informe_final_html si está vacío
# Esto debe hacerse ANTES de crear el form para que aparezca en el editor
if not revision.informe_final_html:
    revision.informe_final_html = revision.informe_residente_snapshot or revision.generar_informe_original_residente()
    revision.save()

if request.method == 'POST':
    form = RevisionPreinformeForm(request.POST, instance=revision, preinforme=preinforme)
    # ... resto del POST ...
else:
    # GET: El form se crea con la instancia que ya tiene informe_final_html cargado
    form = RevisionPreinformeForm(instance=revision, preinforme=preinforme)
```

### CAMBIOS CLAVE:
1. ✅ Snapshot se crea **ANTES** del form (si no existe)
2. ✅ `informe_final_html` se pre-carga **ANTES** del form (si está vacío)
3. ✅ Se usa `save()` para persistir el contenido pre-cargado
4. ✅ El form recibe una instancia con datos ya cargados
5. ✅ No hay lógica de inicialización en el bloque GET

---

## 2. FORMS.PY - Formulario `RevisionPreinformeForm`

### ANTES:
```python
def __init__(self, *args, **kwargs):
    preinforme = kwargs.pop('preinforme', None)
    super().__init__(*args, **kwargs)
    
    # Si es una nueva revisión, inicializar con datos del residente
    if preinforme and not self.instance.pk:
        self.instance.preinforme = preinforme
        self.instance.inicializar_revision()
    
    # Si ya existe la revisión pero no tiene informe final, inicializarlo
    elif self.instance.pk and not self.instance.informe_final_html:
        self.instance.inicializar_revision()
```

### DESPUÉS:
```python
def __init__(self, *args, **kwargs):
    preinforme = kwargs.pop('preinforme', None)
    super().__init__(*args, **kwargs)
    
    # La vista ya maneja la pre-carga de informe_final_html
    # Aquí solo necesitamos asignar el preinforme si es nuevo
    if preinforme and not self.instance.pk:
        self.instance.preinforme = preinforme
    
    # Seguridad adicional: si por alguna razón llegamos aquí sin contenido,
    # usar el snapshot como initial value
    if self.instance.pk and not self.instance.informe_final_html:
        if self.instance.informe_residente_snapshot:
            self.fields['informe_final_html'].initial = self.instance.informe_residente_snapshot
        elif hasattr(self.instance, 'preinforme'):
            self.fields['informe_final_html'].initial = self.instance.generar_informe_original_residente()
```

### CAMBIOS CLAVE:
1. ✅ La lógica principal de pre-carga se movió a la vista
2. ✅ El formulario solo maneja casos edge (seguridad adicional)
3. ✅ Se usa `initial` como fallback si el campo está vacío
4. ✅ No hay llamadas a `save()` en el formulario (evita side effects)

---

## 3. MODELS.PY - Modelo `RevisionPreinforme`

### ANTES:
```python
def inicializar_informe_final(self):
    """Inicializa el informe final del staff con el contenido del residente"""
    if not self.informe_final_html:
        self.informe_final_html = self.generar_informe_original_residente()
        self.save()

def inicializar_revision(self):
    """Inicializa la revisión creando snapshot y preparando informe final"""
    self.crear_snapshot_residente()
    self.inicializar_informe_final()
```

### DESPUÉS:
```python
def inicializar_informe_final(self, save=True):
    """Inicializa el informe final del staff con el contenido del residente"""
    if not self.informe_final_html:
        # Preferir snapshot si existe, sino generar
        self.informe_final_html = self.informe_residente_snapshot or self.generar_informe_original_residente()
        if save:
            self.save()

def inicializar_revision(self, save=True):
    """Inicializa la revisión creando snapshot y preparando informe final"""
    self.crear_snapshot_residente()
    self.inicializar_informe_final(save=save)
    return self.informe_final_html
```

### CAMBIOS CLAVE:
1. ✅ Parámetro `save` opcional para controlar persistencia
2. ✅ `inicializar_informe_final` prefiere snapshot si existe
3. ✅ `inicializar_revision` retorna el contenido generado
4. ✅ Más flexible para uso en diferentes contextos

---

## 4. TEMPLATE - revisar_preinforme.html

### YA ESTABA CORRECTO:
```html
<label for="{{ form.informe_final_html.id_for_label }}" 
       class="block text-sm font-semibold text-gray-700 mb-2">
    Informe Final para EGES
</label>
{{ form.informe_final_html }}
{% if form.informe_final_html.errors %}
    <div class="text-red-600 text-sm mt-1">
        {{ form.informe_final_html.errors.0 }}
    </div>
{% endif %}
```

### VERIFICACIÓN:
- ✅ Renderiza el campo correcto: `{{ form.informe_final_html }}`
- ✅ CKEditor5 se inicializa automáticamente en ese campo
- ✅ El label tiene el `id_for_label` correcto
- ✅ Los errores se muestran correctamente

---

## FLUJO COMPLETO DE PRE-CARGA

### 1. Usuario accede a `/preinformes/revisar/<id>/` (GET)

```python
# Vista revisar_preinforme():

1. Get preinforme by pk
2. Verificar permisos y estado
3. get_or_create RevisionPreinforme
4. ⭐ if not snapshot → crear_snapshot_residente()
5. ⭐ if not informe_final_html → pre-cargar desde snapshot
6. ⭐ save() para persistir
7. Crear form con instance pre-cargada
8. Render template
```

### 2. Template renderiza el formulario

```html
1. Django form rendering: {{ form.informe_final_html }}
2. CKEditor5 detecta el campo por id
3. CKEditor5 carga el contenido del value/initial
4. ⭐ El editor aparece con TODO el texto del residente
5. Staff puede editar directamente
```

### 3. Staff modifica y guarda (POST)

```python
# Vista revisar_preinforme():

1. Recibe POST data
2. form.is_valid() → valida contenido
3. form.save() → guarda informe_final_html editado
4. ⭐ El snapshot permanece intacto (para comparación)
5. Redirect según botón presionado
```

---

## TEST REALIZADO

```bash
$ python manage.py shell -c "..."

Resultados:
✓ Preinforme encontrado: 2025-002345
✓ Revision creada: True, ID: 4
✓ Snapshot length: 619 caracteres
✓ informe_final_html before: 0 (vacío)
✓ informe_final_html after: 619 (pre-cargado)
```

---

## PRUEBA MANUAL

### Pasos:
1. Iniciar servidor: `python manage.py runserver`
2. Acceder a: `http://127.0.0.1:8000/preinformes/revisar/<id>/`
3. Verificar que el editor CKEditor5:
   - ✅ Aparece con contenido visible
   - ✅ Muestra los títulos (TÉCNICA, HALLAZGOS, CONCLUSIÓN)
   - ✅ Muestra el contenido completo del residente
   - ✅ Es editable inmediatamente
   - ✅ NO requiere copiar/pegar

### Resultado Esperado:
El staff ve inmediatamente el contenido completo del residente en el editor y solo necesita hacer las correcciones necesarias.

---

## CASOS EDGE MANEJADOS

### 1. Primera vez que se accede a una revisión:
- ✅ Se crea snapshot automáticamente
- ✅ Se pre-carga informe_final_html
- ✅ Se persiste en BD
- ✅ Editor muestra contenido

### 2. Revisión ya iniciada (staff vuelve a editar):
- ✅ Snapshot ya existe (no se sobrescribe)
- ✅ informe_final_html ya tiene contenido (sus ediciones previas)
- ✅ Editor muestra su trabajo anterior
- ✅ Puede continuar editando

### 3. Snapshot no existe pero informe_final_html sí:
- ✅ Se crea snapshot retroactivamente
- ✅ Se respeta informe_final_html existente
- ✅ No se sobrescribe trabajo del staff

### 4. Ambos vacíos (caso raro):
- ✅ Se genera snapshot desde preinforme
- ✅ Se pre-carga informe_final_html
- ✅ Sistema funciona correctamente

---

## RESUMEN DE CAMBIOS

### Archivos Modificados:
1. ✅ `preinformes/views.py` - Vista con pre-carga en GET
2. ✅ `preinformes/forms.py` - Formulario simplificado
3. ✅ `preinformes/models.py` - Métodos más robustos
4. ✅ `templates/preinformes/revisar_preinforme.html` - Ya correcto

### Tests:
- ✅ Test programático ejecutado
- ⏳ Prueba manual pendiente (navegador)

### Estado:
✅ **IMPLEMENTACIÓN COMPLETA Y ROBUSTA**

---

**Última actualización:** 7 de enero de 2026