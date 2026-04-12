# 📋 RESUMEN: Lógica de Registro de Estudios y Contabilización

**Última actualización:** 1 de marzo de 2026  
**Versión:** 3.1  
**Propósito:** Entender el flujo completo de registro de prácticas médicas y su relación con la contabilización

---

## 📜 HISTORIAL DE VERSIONES

### v3.1 - 1 de marzo de 2026
**Through Model para Cantidades Individuales**
- ✅ Creado modelo intermedio `RegistroEstudio` con campo `cantidad`
- ✅ Migración 0028: Convertido M2M simple → M2M through (preservando datos)
- ✅ Actualizado `calcular_monto()` para leer cantidades de tabla intermedia
- ✅ Vistas Create/Update guardan cantidades individuales por estudio
- ✅ Templates cargan cantidades desde BD al editar
- ✅ **Bug Fix**: Campos bonus urgencia ahora se guardan correctamente en BD
- ✅ **Bug Fix**: Vista guardias pasivas muestra últimos 3 meses (no solo mes actual)

### v2.0 - 28 de febrero de 2026
**Análisis inicial del sistema**
- Documentado flujo completo de registro de estudios
- Identificados problemas potenciales en secuencia M2M
- Documentado algoritmo de cálculo de montos

---

## 🎯 RESUMEN EJECUTIVO

El sistema permite que los **médicos registren prácticas** (estudios) que realizan, y automáticamente:
1. **Calcula el monto** a pagar según múltiples factores (OS, horario, regiones, urgencia)
2. **Asigna a una Sesión Contable** (período mensual de facturación)
3. **Valida permisos** según el estado de la sesión contable
4. **Genera reportes** para liquidación de honorarios

---

## 📊 COMPONENTES PRINCIPALES

### 1. **Modelo: `SesionContable`** (Período de Facturación)

**Ubicación:** `liquidacion/models.py` líneas 215-280

**¿Qué es?**  
Un período mensual que agrupa TODAS las prácticas registradas ese mes.

**Estados del ciclo de vida:**
```plaintext
ABIERTA → REVISION → CERRADA → FACTURADA → PAGADA
   ↓         ↓          ↓           ↓          ↓
Médicos   Médicos    Solo      Montos     Ya se
pueden    pueden     Admin    calculados   pagó
registrar registrar  puede      finales
                     cargar
```

**Campos clave:**
- `mes` / `año`: Identifica el período (ej: Febrero 2026)
- `estado`: Controla quién puede hacer qué
- `fecha_apertura`, `fecha_cierre`, `fecha_facturacion`, `fecha_pago`
- `cerrada_por`: Auditoría de quién cerró

**Lógica importante:**
```python
def puede_registrar_practicas(self, usuario):
    # Médicos: solo en ABIERTA o REVISION
    if usuario.rol in ['jefe_residentes', 'instructor_residentes', ...]:
        return self.estado in ['ABIERTA', 'REVISION']
    
    # Admin: puede cargar incluso en CERRADA (no en PAGADA)
    if usuario.is_superuser or usuario.rol == 'administrativo':
        return self.estado != 'PAGADA'
```

---

### 2. **Modelo: `RegistroEstudiosPorMedico`** (Práctica Individual)

**Ubicación:** `liquidacion/models.py` líneas 353-670

**¿Qué es?**  
Representa UNA práctica médica realizada por UN médico a UN paciente.

**Campos principales:**

#### A) Relaciones
- `sesion_contable` → ForeignKey a SesionContable
- `medico` → ForeignKey al User que realizó la práctica

#### B) Datos del paciente
- `nombre_paciente`, `apellido_paciente`, `dni_paciente`
- `fecha_del_informe`: Cuándo se emitió el informe

#### C) Datos del estudio
- `estudio` → **ManyToMany** a modelo `Estudios` (puede ser más de uno!)
  - **v3.1:** Usa tabla intermedia `RegistroEstudio` con campo `cantidad`
  - Permite especificar cantidad individual por estudio (ej: "RM RODILLA ×2" para bilateral)
- `cantidad_regiones`: Campo **informativo** con suma automática (contempla cantidades)

#### D) Facturación
- `tipo_obra_social`: COBER o OTRAS_OS (determina precio)
- `horario`: INTRA (50%), EXTRA (100%), NA (staff)
- `monto_calculado`: **INMUTABLE** - se guarda al crear/editar

#### E) Bonus Urgencia (solo para RM remotos)
- `paciente_internado`: Boolean
- `fecha_hora_solicitud`: Cuándo se pidió el estudio
- `fecha_hora_informe`: Cuándo se entregó el informe
- **v3.1:** Estos campos ahora se persisten correctamente en BD

#### F) Auditoría
- `modificado_por`, `fecha_modificacion`, `motivo_modificacion`

---

### 2.1. **Modelo Intermedio: `RegistroEstudio`** (v3.1)

**Ubicación:** `liquidacion/models.py` líneas 352-395

**¿Qué es?**  
Tabla intermedia que relaciona `RegistroEstudiosPorMedico` con `Estudios`, agregando el campo `cantidad`.

**¿Por qué existe?**  
- Django M2M simple solo guarda IDs (sin metadata adicional)
- Necesitamos guardar "cuántas veces" se hizo cada estudio
- Ejemplo: RM de ambas rodillas → 1 estudio, cantidad = 2

**Campos:**
- `registro` → FK a RegistroEstudiosPorMedico
- `estudio` → FK a Estudios
- `cantidad` → PositiveSmallIntegerField (default=1, min=1, max=10)
- `fecha_agregado` → DateTimeField (auditoría)

**Constraints:**
- `unique_together = ['registro', 'estudio']` (no duplicados)

**Ejemplo de uso:**
```python
# Crear registro con 2 estudios (RM bilateral + ECO single)
registro = RegistroEstudiosPorMedico.objects.create(...)
RegistroEstudio.objects.create(registro=registro, estudio=rm_rodilla, cantidad=2)
RegistroEstudio.objects.create(registro=registro, estudio=eco_abdomen, cantidad=1)

# Leer cantidades
for rel in registro.registroestudio_set.all():
    print(f"{rel.estudio.nombre} ×{rel.cantidad}")
```

---

### 3. **Cálculo de Montos: `calcular_monto()`** (v3.1)

**Ubicación:** `liquidacion/models.py` líneas 522-565

**Algoritmo de cálculo:**

```plaintext
PASO 1: Sumar precios base × cantidades de TODOS los estudios
        ↓
        Para cada RegistroEstudio en registroestudio_set:
            cantidad = rel.cantidad  # ← v3.1: Lee de tabla intermedia
            Si tipo_obra_social == 'COBER':
                precio_base_total += (estudio.precio_cober × cantidad)
            Sino:
                precio_base_total += (estudio.precio_otras_os × cantidad)

PASO 2: cantidad_regiones es SOLO INFORMATIVO (no se multiplica extra)
        ↓
        subtotal = precio_base_total

PASO 3: Aplicar porcentaje según horario (solo para residentes)
        ↓
        Si médico es residente/instructor:
            Si horario == 'INTRA':  subtotal *= 50%
            Si horario == 'EXTRA':  subtotal *= 100%
        Sino (staff/cardiólogo):
            subtotal *= 100% (siempre)

PASO 4: Bonus urgencia (solo RM remotos con paciente internado)
        ↓
        Si médico.trabaja_remoto AND tiene_resonancia 
           AND paciente_internado AND informe < 24hs:
            monto_final = subtotal * 1.20  (bonus +20%)
        Sino:
            monto_final = subtotal

RESULTADO: monto_calculado
```

**Ejemplo real v3.1:**
```python
# Caso: Residente, RMN bilateral de rodillas, paciente COBER, horario INTRA
precio_base = 50000  # RMN precio_cober
cantidad = 2  # ← v3.1: Bilateral (ambas rodillas)
precio_total = 50000 * 2 = 100000
porcentaje_horario = 0.5  # INTRA para residentes
monto_final = 100000 * 0.5 = 50000

# Si fuera staff: 100000 * 1.0 = 100000 (no se aplica reducción)
```

**Cambios en v3.1:**
- Ahora lee `cantidad` de tabla intermedia `RegistroEstudio`
- Se multiplica precio por cantidad **dentro** del loop de estudios
- `cantidad_regiones` se calcula también contemplando cantidades: `sum(conteo × cantidad)`

---

### 4. **Método `save()` del Modelo**

**Ubicación:** `liquidacion/models.py` líneas 647-667

**Flujo al guardar:**

```plaintext
1. Auto-asignar sesion_contable
   ↓
   Si no tiene sesion_contable asignada:
       mes = fecha_del_informe.month
       año = fecha_del_informe.year
       sesion, created = SesionContable.objects.get_or_create(mes, año)
       self.sesion_contable = sesion

2. Auto-asignar horario (solo si está vacío)
   ↓
   Si médico es staff:
       horario = 'NA'
   Sino (residente):
       hora_actual = timezone.now().hour
       Si 8 <= hora < 17:
           horario = 'INTRA'
       Sino:
           horario = 'EXTRA'

3. Calcular monto (SOLO si ya tiene ID o estudios asignados)
   ↓
   if self.pk or _estudios_temp:
       self.monto_calculado = self.calcular_monto()

4. Guardar en DB
   ↓
   super().save()
```

**⚠️ IMPORTANTE:** El monto se calcula **ANTES** de guardar y queda **INMUTABLE**.

---

## 🖥️ FLUJO EN LA VISTA DE CREACIÓN

**Ubicación:** `liquidacion/views.py` líneas 61-210

### A) Validación inicial (`dispatch`)
```python
# Solo médicos pueden acceder
if not request.user.es_medico():
    redirect('home')
```

### B) Contexto del formulario (`get_context_data`)
```python
# 1. Obtener/crear sesión contable del mes actual
sesion, created = SesionContable.objects.get_or_create(
    mes=today.month, año=today.year
)

# 2. Verificar si puede registrar
puede_registrar = sesion.puede_registrar_practicas(user)

# 3. Serializar estudios para JavaScript
estudios_data = Estudios.objects.filter(activo=True).values(...)
context['estudios'] = json.dumps(estudios_data)

# 4. Mostrar registros del mes
registros = RegistroEstudiosPorMedico.objects.filter(
    medico=user, sesion_contable=sesion
)

# 5. Calcular totales del mes
total_regiones_mes = sum(reg.cantidad_regiones for reg in registros)
total_monto_mes = sum(reg.monto_calculado for reg in registros)
```

### C) Validación del formulario (`form_valid`)

**Paso 1: Validar sesión contable**
```python
sesion, created = SesionContable.objects.get_or_create(...)

if not sesion.puede_registrar_practicas(user):
    messages.error(...)
    return redirect(success_url)
```

**Paso 2: Verificar duplicados (últimos 5 minutos)**
```python
hace_5_minutos = timezone.now() - timedelta(minutes=5)
registros_recientes = RegistroEstudiosPorMedico.objects.filter(
    medico=user,
    dni_paciente=dni_paciente,
    fecha_del_informe=fecha_informe,
    fecha_registro__gte=hace_5_minutos
)

# Si el mismo paciente + mismo estudio + misma fecha:
if estudios_existentes == set(estudios_seleccionados):
    messages.warning(...)
    return redirect(success_url)
```

**Paso 3: Guardar con secuencia especial (ManyToMany + Through Model)**
```python
# CRÍTICO: Secuencia en 4 pasos (v3.1)
self.object = form.save(commit=False)
self.object.medico = user
self.object.sesion_contable = sesion

# 1. Guardar primero (obtener ID)
self.object.save()

# 2. Crear relaciones en tabla intermedia con cantidades
from liquidacion.models import RegistroEstudio
cantidades_estudios = {}  # Leído desde POST: cantidad_estudio_X
for estudio in estudios_seleccionados:
    cantidad = cantidades_estudios.get(estudio.id, 1)
    RegistroEstudio.objects.create(
        registro=self.object,
        estudio=estudio,
        cantidad=cantidad
    )

# 3. Calcular cantidad_regiones (contempla cantidades)
total_regiones = 0
for estudio in estudios_seleccionados:
    cantidad = cantidades_estudios.get(estudio.id, 1)
    total_regiones += (estudio.conteo_regiones_default * cantidad)
self.object.cantidad_regiones = total_regiones

# 4. Calcular y guardar monto + campos bonus urgencia
self.object.monto_calculado = self.object.calcular_monto()
self.object.save(update_fields=[
    'cantidad_regiones', 
    'monto_calculado',
    'paciente_internado',      # v3.1: Fix bug
    'fecha_hora_solicitud',    # v3.1: Fix bug
    'fecha_hora_informe'       # v3.1: Fix bug
])
```

**⚠️ ¿Por qué esta secuencia?**  
- Django no permite acceder a through model antes de guardar el objeto (necesita ID)
- Cantidades deben guardarse en tabla intermedia `RegistroEstudio`
- Bonus urgencia debe persistirse en BD (bug corregido v3.1)

---

## 🔄 FLUJO COMPLETO: Registro de una Práctica

```plaintext
┌─────────────────────────────────────────────────────────────┐
│ 1. USUARIO ACCEDE AL FORMULARIO                            │
│    GET /liquidacion/registrar/                              │
└────────────┬────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. VISTA CARGA CONTEXTO                                     │
│    • Obtiene/crea SesionContable del mes actual            │
│    • Verifica puede_registrar_practicas()                  │
│    • Carga catálogo de estudios (JSON para JS)            │
│    • Muestra registros del mes                             │
└────────────┬────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. USUARIO COMPLETA FORMULARIO                             │
│    • Selecciona modalidad (ECO, TOM, RES, etc.)           │
│    • Selecciona estudio(s) - puede ser múltiple!          │
│    • Ingresa datos del paciente                            │
│    • Selecciona tipo de OS (COBER / OTRAS_OS)             │
│    • cantidad_regiones se calcula automáticamente          │
└────────────┬────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. ENVÍO DEL FORMULARIO                                     │
│    POST /liquidacion/registrar/                             │
└────────────┬────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. FORMULARIO VALIDA (forms.py)                            │
│    • clean_cantidad_regiones(): > 0, debe ser entero      │
│    • clean(): Si paciente_internado, validar fechas       │
└────────────┬────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────┐
│ 6. VISTA VALIDA (form_valid)                               │
│    ✓ Sesión contable permite registrar?                    │
│    ✓ No es duplicado reciente (5 min)?                     │
└────────────┬────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────┐
│ 7. GUARDAR EN DB - SECUENCIA CRÍTICA (v3.1)               │
│                                                             │
│    self.object = form.save(commit=False)                   │
│    self.object.medico = user                               │
│    self.object.sesion_contable = sesion                    │
│                                                             │
│    # PASO 1: Guardar objeto                                │
│    self.object.save()  # → activa model.save()            │
│                                                             │
│        [En model.save():]                                  │
│        • Auto-asigna sesion_contable (si no tiene)        │
│        • Auto-asigna horario según hora actual            │
│        • monto_calculado = 0 (aún no hay estudios)       │
│        • super().save()                                    │
│                                                             │
│    # PASO 2: Crear relaciones en tabla intermedia         │
│    for estudio in estudios_seleccionados:                 │
│        cantidad = cantidades_estudios.get(estudio.id, 1) │
│        RegistroEstudio.objects.create(                    │
│            registro=self.object,                          │
│            estudio=estudio,                               │
│            cantidad=cantidad                              │
│        )                                                   │
│                                                             │
│    # PASO 3: Calcular cantidad_regiones (con cantidades) │
│    total_regiones = 0                                      │
│    for estudio in estudios_seleccionados:                 │
│        cantidad = cantidades_estudios.get(estudio.id, 1) │
│        total_regiones += (conteo × cantidad)              │
│    self.object.cantidad_regiones = total_regiones         │
│                                                             │
│    # PASO 4: Calcular y guardar monto + bonus urgencia   │
│    self.object.monto_calculado = calcular_monto()         │
│    self.object.save(update_fields=[...])                  │
└────────────┬────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────┐
│ 8. CÁLCULO DE MONTO (calcular_monto) - v3.1               │
│                                                             │
│    precio_base_total = 0                                   │
│    for rel in registroestudio_set.all():                  │
│        estudio = rel.estudio                               │
│        cantidad = rel.cantidad  # ← Lee de tabla interm. │
│        precio = precio según OS                            │
│        precio_base_total += (precio × cantidad)           │
│                                                             │
│    subtotal = precio_base_total                            │
│                                                             │
│    if medico es residente:                                 │
│        if horario == 'INTRA': subtotal *= 0.5             │
│        if horario == 'EXTRA': subtotal *= 1.0             │
│                                                             │
│    if bonus_urgencia aplica:                               │
│        monto_final = subtotal * 1.20                       │
│    else:                                                    │
│        monto_final = subtotal                              │
│                                                             │
│    return monto_final                                      │
└────────────┬────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────┐
│ 9. MENSAJE DE ÉXITO + REDIRECCIÓN                         │
│    "✅ Registro guardado exitosamente"                     │
│    redirect → formulario de nuevo registro                 │
└─────────────────────────────────────────────────────────────┘
```

---

## ⚠️ PROBLEMAS POTENCIALES IDENTIFICADOS

### � PROBLEMA 1: Secuencia de cálculo de monto [PARCIALMENTE RESUELTO v3.1]

**Issue original:**  
El `monto_calculado` se intentaba calcular en `model.save()`, pero en ese momento las relaciones ManyToMany (`estudio`) aún no estaban guardadas.

**Estado actual (v3.1):**  
✅ Vistas `CreateView` y `UpdateView` manejan correctamente la secuencia:
1. Guardar objeto (obtener ID)
2. Crear relaciones `RegistroEstudio` con cantidades
3. Calcular cantidad_regiones (contempla multiplicadores)
4. Calcular y guardar monto + campos bonus urgencia

**Consecuencias resueltas:**
- ✅ Through model permite guardar cantidades individuales por estudio
- ✅ Campos bonus urgencia se persisten correctamente en BD
- ✅ Cantidad_regiones se calcula con multiplicadores

**Pendiente:**
- ⚠️ Si alguien guarda desde admin o django shell sin la secuencia correcta, el monto puede quedar en 0
- Sugerencia: Implementar señal `m2m_changed` para auto-recalcular

---

### ✅ BUG CORREGIDO v3.1: Campos bonus urgencia no se guardaban

**Issue:**  
Los campos `paciente_internado`, `fecha_hora_solicitud`, `fecha_hora_informe` se asignaban al objeto pero no se incluían en `update_fields`, por lo que nunca se persistían en BD.

**Código antes:**
```python
self.object.save(update_fields=['cantidad_regiones', 'monto_calculado'])
```

**Código después (v3.1):**
```python
self.object.save(update_fields=[
    'cantidad_regiones', 
    'monto_calculado',
    'paciente_internado',      # ✅ Ahora se guarda
    'fecha_hora_solicitud',    # ✅ Ahora se guarda
    'fecha_hora_informe'       # ✅ Ahora se guarda
])
```

**Ubicación:** `liquidacion/views.py` líneas 195-240 (CreateView) y 755-810 (UpdateView)

---

### ✅ BUG CORREGIDO v3.1: Guardias pasivas no se visualizaban

**Issue:**  
La vista de creación de guardias pasivas solo mostraba guardias del **mes actual**, pero permitía registrar guardias de cualquier mes. Si registrabas una guardia de febrero en marzo, se guardaba pero no aparecía en la lista.

**Código antes:**
```python
guardias = GuardiaPasiva.objects.filter(
    medico=user,
    sesion_contable=sesion  # ← Sesión del mes actual
)
```

**Código después (v3.1):**
```python
# Mostrar guardias de los últimos 3 meses
fecha_desde = today.replace(day=1) - timedelta(days=90)
guardias = GuardiaPasiva.objects.filter(
    medico=user,
    fecha_guardia__gte=fecha_desde
).order_by('-fecha_guardia')
```

**Ubicación:** `liquidacion/views.py` líneas 311-340 (RegistrarGuardiaPasivaView)

---

### � PROBLEMA 2: Campo `cantidad_regiones` confuso

**Issue:**  
En el formulario se llama "Regiones" y tiene un valor numérico, lo que hace pensar que:
- Se multiplica en el cálculo del precio (pero NO se hace)
- El usuario debe ajustarlo manualmente

**Realidad:**
- `cantidad_regiones` es **solo informativo**
- El precio ya incluye las regiones de cada estudio
- Se usa para mostrar en reportes, no para calcular
- **v3.1:** Ahora se calcula contemplando cantidades: `sum(conteo × cantidad)`

**Código del cálculo:**
```python
# v3.1 - views.py
total_regiones = 0
for estudio in estudios_seleccionados:
    cantidad = cantidades_estudios.get(estudio.id, 1)
    total_regiones += (estudio.conteo_regiones_default * cantidad)
self.object.cantidad_regiones = total_regiones
```

**Ejemplo v3.1:**
- RM RODILLA (conteo=5) ×2 → 5 × 2 = 10 regiones
- ECO ABDOMEN (conteo=1) ×1 → 1 × 1 = 1 región
- **Total:** 11 regiones (informativo, NO multiplica el precio)

**Sugerencias:**
1. Renombrar campo a `total_regiones_informativo`
2. Hacer campo read-only en el formulario
3. Aclarar en help_text que NO afecta el cálculo

---

### 🟡 PROBLEMA 3: Validación de duplicados limitada

**Issue:**  
Solo detecta duplicados en los últimos 5 minutos del mismo médico.

**Escenarios no cubiertos:**
- Usuario registra, cierra navegador, vuelve a entrar → puede duplicar
- Dos médicos registran el mismo paciente/estudio (válido, pero ¿es correcto?)

**Código actual:**
```python
# LÍNEA 174-185
hace_5_minutos = timezone.now() - timedelta(minutes=5)
registros_recientes = RegistroEstudiosPorMedico.objects.filter(
    medico=user,
    dni_paciente=dni_paciente,
    fecha_del_informe=fecha_informe,
    fecha_registro__gte=hace_5_minutos
)
```

---

### 🟡 PROBLEMA 4: Auto-asignación de horario inflexible

**Issue:**  
El horario se asigna según la hora del sistema en que se guarda:
- 8:00-16:59 → INTRA
- Resto → EXTRA

**Problemas:**
- Si el médico registra a las 18:00 una práctica que hizo a las 10:00, se marca EXTRA (incorrecto)
- No hay forma de override manual en el formulario

**Código:**
```python
# LÍNEA 653-662
hora_actual = timezone.localtime(timezone.now()).hour
if 8 <= hora_actual < 17:
    self.horario = 'INTRA'
else:
    self.horario = 'EXTRA'
```

**Sugerencias:**
1. Usar `fecha_del_informe` + hora en vez de hora actual
2. Agregar campo manual en formulario para override
3. Mostrar warning si hay discrepancia

---

### � PROBLEMA 5: Bonus urgencia no validado en formulario [PARCIALMENTE RESUELTO v3.1]

**Issue original:**  
Los campos de bonus urgencia (`fecha_hora_solicitud`, `fecha_hora_informe`) solo se validaban si `paciente_internado=True`, pero:
- No se validaba que sean coherentes con `fecha_del_informe`
- No se validaba que el estudio sea realmente RM
- No se validaba que el médico trabaje remoto
- **✅ v3.1:** Campos ahora se persisten correctamente en BD

**Código del formulario:**
```python
# LÍNEA 168-181 forms.py
if paciente_internado:
    if not fecha_hora_solicitud:
        self.add_error('fecha_hora_solicitud', 'Requerido...')
    if not fecha_hora_informe:
        self.add_error('fecha_hora_informe', 'Requerido...')
    if fecha_hora_informe <= fecha_hora_solicitud:
        self.add_error('fecha_hora_informe', '...')
```

**Estado actual v3.1:**
- ✅ Campos se guardan en BD correctamente
- ⚠️ Pendiente: Validar en formulario que el estudio sea RM
- ⚠️ Pendiente: Validar que el médico tenga `trabaja_remoto=True`
- ⚠️ Pendiente: Deshabilitar campos si no aplican (con JavaScript)

**Sugerencias:**
1. Validar en formulario que el estudio sea RM
2. Validar que el médico tenga `trabaja_remoto=True`
3. Deshabilitar campos si no aplican (con JavaScript)

---

## 📝 CHECKLIST PARA DEBUGGING

Si un médico reporta que el monto calculado es incorrecto:

### ✅ Paso 1: Verificar datos del registro
```sql
SELECT 
    id,
    medico_id,
    tipo_obra_social,
    horario,
    cantidad_regiones,
    monto_calculado,
    paciente_internado,
    fecha_del_informe
FROM liquidacion_registroestudiospormedico
WHERE id = [ID_DEL_REGISTRO];
```

### ✅ Paso 2: Verificar estudios asignados
```sql
SELECT 
    e.nombre,
    e.tipo,
    e.precio_cober,
    e.precio_otras_os,
    e.precio_unico,
    e.conteo_regiones
FROM liquidacion_estudios e
JOIN liquidacion_registroestudiospormedico_estudio re ON re.estudios_id = e.id
WHERE re.registroestudiospormedico_id = [ID_DEL_REGISTRO];
```

### ✅ Paso 3: Verificar perfil del médico
```sql
SELECT 
    rol,
    trabaja_remoto
FROM accounts_customuser
WHERE id = [MEDICO_ID];
```

### ✅ Paso 4: Recalcular manualmente
```python
# En Django shell
from liquidacion.models import RegistroEstudiosPorMedico

reg = RegistroEstudiosPorMedico.objects.get(id=[ID])
monto_esperado = reg.calcular_monto()
monto_guardado = reg.monto_calculado

print(f"Monto esperado: {monto_esperado}")
print(f"Monto guardado: {monto_guardado}")
print(f"Diferencia: {monto_guardado - monto_esperado}")

# Ver desglose
print(reg.get_desglose_monto())
```

### ✅ Paso 5: Verificar sesión contable
```sql
SELECT 
    mes,
    año,
    estado,
    fecha_apertura,
    fecha_cierre
FROM liquidacion_sesioncontable
WHERE id = [SESION_ID];
```

---

## 🎓 CONCEPTOS CLAVE PARA ENTENDER

### 1. **Sesión Contable = Mes de Facturación**
No es una "sesión" de usuario, es un **período de tiempo** (mes/año).

### 2. **ManyToMany permite múltiples estudios**
Un registro puede tener MUCHOS estudios asociados (ej: ECO abdomen + ECO hepática).

### 3. **Monto es INMUTABLE**
Una vez calculado y guardado, no cambia aunque cambien los precios del catálogo.

### 4. **Horario se asigna automáticamente**
Según la hora del sistema al momento de guardar (problema identificado).

### 5. **Bonus urgencia es muy específico**
Solo para: RM + paciente internado + médico remoto + < 24hs.

---

## 🔧 PRÓXIMOS PASOS SUGERIDOS

### Prioridad ALTA
1. ~~**Implementar through model para cantidades**~~ ✅ **COMPLETADO v3.1**
   - ✅ Tabla intermedia `RegistroEstudio` con campo `cantidad`
   - ✅ Vistas actualizadas para leer/escribir cantidades
   - ✅ Cálculo de monto contempla multiplicadores

2. ~~**Corregir persistencia de bonus urgencia**~~ ✅ **COMPLETADO v3.1**
   - ✅ Campos agregados a `update_fields` en ambas vistas

3. **Implementar señal `m2m_changed` para auto-recalcular monto**
   - Evitar que alguien guarde desde admin con monto=0
   - Recalcular automáticamente al cambiar estudios

### Prioridad MEDIA
4. **Clarificar campo cantidad_regiones**
   - Renombrar o hacer read-only (ya se calcula auto con v3.1)
   - Documentar mejor que NO se multiplica en precio

5. **Mejorar validación de horario**
   - Permitir override manual
   - Usar fecha_del_informe en vez de hora actual

6. **Mejorar detección de duplicados**
   - Extender ventana temporal
   - Agregar soft-delete en vez de hard-delete

7. **Validar bonus urgencia en frontend**
   - Mostrar/ocultar campos según estudio y médico
   - Validar coherencia de fechas

### Prioridad BAJA
8. **Agregar historial de cambios**
   - Auditoría completa de modificaciones
   - Django SimpleHistory?

9. ~~**Corregir bug vista guardias pasivas**~~ ✅ **COMPLETADO v3.1**
   - ✅ Ahora muestra últimos 3 meses (no solo mes actual)

---

## 📊 RESUMEN DE CAMBIOS v3.1

### ✅ Implementado
1. Through model `RegistroEstudio` con cantidades individuales
2. Migración 0028 (M2M simple → M2M through, preservando datos)
3. Vistas Create/Update guardan cantidades en tabla intermedia
4. Cálculo de monto multiplica precio × cantidad por estudio
5. Templates cargan cantidades desde BD al editar
6. Bug fix: Campos bonus urgencia se persisten en BD
7. Bug fix: Guardias pasivas muestran últimos 3 meses

### 📈 Resultados
- Registros con multiplicadores funcionan correctamente (ej: "RM RODILLA ×2")
- Edición preserva cantidades originales
- Liquidación mensual muestra cantidades individuales
- Sistema de guardias pasivas funcional

---

## 📞 CONTACTO / DUDAS

Si necesitas aclarar algo del sistema:
1. Revisa este documento primero
2. Busca en el código con los números de línea indicados (pueden haber cambiado ligeramente)
3. Prueba en Django shell con datos reales
4. Documenta lo que encuentres aquí para el próximo

---

**Última actualización:** 1 de marzo de 2026  
**Versión:** 3.1  
**Autor:** Análisis del sistema Liquidación  
**Próxima revisión:** Después de implementar señales m2m_changed
