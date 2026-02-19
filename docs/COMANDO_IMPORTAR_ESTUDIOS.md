# 📚 **COMANDO IMPORTAR ESTUDIOS EGES**

## ✅ **CAMBIOS IMPLEMENTADOS**

### **1. Ecocardiograma Agregado**
- ✅ Modelo: `TIPO_ESTUDIO_CHOICES` ahora incluye `('ECOCAR', 'Ecocardiograma')`
- ✅ Templates: Dropdown en formularios de creación y edición
- ✅ Migración: `0024_alter_estudios_tipo.py` (campo `tipo` ahora max_length=6)

**Uso:** Ahora los cardiólogos pueden seleccionar "Ecocardiograma" al registrar estudios.

---

### **2. Comando de Importación Inteligente**

Archivo: `liquidacion/management/commands/importar_estudios_eges.py`

**Características:**
- 🧠 Parseo inteligente de variantes (con contraste, angio, difusión)
- 💰 Asignación automática de precios según reglas de negocio
- 🔄 Actualización de estudios existentes
- 🔍 Modo dry-run para previsualización
- 📊 Reporte detallado de operaciones

---

## 📖 **REGLAS DE NEGOCIO**

### **Precios Automáticos por Tipo:**

#### **Tomografía (TOM) - Precio Único**
- TAC sin contraste: **$4,000**
- TAC con contraste: **$5,000**
- Angio TAC: **$7,000**

#### **Resonancia (RES) - Precio Único**
- RMN sin contraste: **$5,000**
- RMN con contraste: **$6,000**
- Angio RMN: **$8,000**
- RMN Difusión: **$8,000**

#### **Ecografía (ECO) - Precio Diferenciado**
- COBER: **$8,500**
- Otras OS: **$10,000**

#### **Doppler (DOP) - Precio Diferenciado**
- COBER: **$8,500**
- Otras OS: **$10,000**

#### **Mamografía (MAM) - Precio Diferenciado**
- COBER: **$7,000**
- Otras OS: **$8,500**

#### **Ecocardiograma (ECOCAR) - Precio Diferenciado**
- COBER: **$9,000**
- Otras OS: **$11,000**

#### **Radiografía (RAD) - Precio Único**
- RX: **$3,000**

---

## 🚀 **EJEMPLOS DE USO**

### **1. Modo Dry-Run (Previsualizar sin guardar)**

```bash
# Local
python manage.py importar_estudios_eges estudios_tomografia.xlsx --tipo TOM --dry-run

# Heroku
heroku run python manage.py importar_estudios_eges estudios_tomografia.xlsx --tipo TOM --dry-run --app tu-app
```

**Salida:**
```
🔍 MODO DRY-RUN: No se escribirá en la base de datos
📂 Leyendo archivo: estudios_tomografia.xlsx
✅ Archivo leído: 50 filas
🔎 Filtrado por tipo TOM: 25 de 50 filas

====================================================
📊 REPORTE DE IMPORTACIÓN
====================================================

✅ 25 estudios creados:
   • 901322 - TAC (TOM) - $4000.00
   • 901323 - TAC CON CONTRASTE (TOM) - $5000.00 [con_contraste]
   • 901324 - ANGIO TAC (TOM) - $7000.00 [angio]
   ... y 22 más

====================================================
📈 TOTAL PROCESADOS: 25

⚠️  Modo DRY-RUN: Ningún cambio fue aplicado a la base de datos
Ejecuta sin --dry-run para aplicar los cambios
```

---

### **2. Importar solo Tomografías (crear nuevos)**

```bash
python manage.py importar_estudios_eges estudios_eges.xlsx --tipo TOM
```

---

### **3. Importar Resonancias y actualizar existentes**

```bash
python manage.py importar_estudios_eges estudios_eges.xlsx --tipo RES --actualizar
```

---

### **4. Importar TODO el catálogo**

```bash
python manage.py importar_estudios_eges estudios_completo.xlsx --tipo TODOS
```

---

### **5. Uso en Heroku**

**Opción A: Archivo local subido temporalmente**

```bash
# 1. Copiar archivo a Heroku (requiere heroku CLI con plugin)
heroku ps:copy estudios.xlsx --app tu-app

# 2. Ejecutar comando
heroku run python manage.py importar_estudios_eges estudios.xlsx --tipo TOM --app tu-app
```

**Opción B: URL pública (recomendado para Heroku)**

```bash
# Subir archivo a Dropbox/Google Drive/S3 y obtener URL pública
heroku run python manage.py importar_estudios_eges https://url-publica/estudios.xlsx --tipo TOM --app tu-app
```

---

## 🔍 **PARSEO INTELIGENTE DE VARIANTES**

El comando detecta automáticamente las siguientes variantes en el nombre:

### **1. Con Contraste**
Patrones detectados:
- "CON CONTRASTE"
- "CON / CTE"
- "CON C"
- "C/C"

**Ejemplo:**
- `TAC CON CONTRASTE` → Precio: $5,000 (en lugar de $4,000)

---

### **2. Angiografía**
Patrones detectados:
- "ANGIO"
- "ANGIOGRAFIA"
- "ANGIOGRAFÍA"

**Ejemplo:**
- `ANGIO TAC` → Precio: $7,000
- `ANGIO RMN` → Precio: $8,000

---

### **3. Difusión (solo RMN)**
Patrones detectados:
- "DIFUSION"
- "DIFUSIÓN"

**Ejemplo:**
- `RMN DIFUSION` → Precio: $8,000

---

## 📋 **FORMATO DEL EXCEL REQUERIDO**

### **Columnas Obligatorias:**

| Columna | Descripción | Ejemplo |
|---------|-------------|---------|
| **Prestación** | Código único del estudio | 901322 |
| **Nombre** | Nombre del estudio | TAC |
| **Servicio** | Área/Especialidad | Tomografía |

### **Columnas Opcionales:**

| Columna | Descripción |
|---------|-------------|
| Interno | Descripción interna (se ignora) |
| Abreviación | Abreviación (se ignora) |
| Especialidad | Especialidad (se ignora) |
| Tipo | Tipo (se ignora) |

---

## 🗺️ **MAPEO SERVICIO → TIPO**

El comando mapea automáticamente:

| Servicio en Excel | Tipo en Sistema |
|-------------------|-----------------|
| TOMOGRAFIA, TAC | TOM |
| RESONANCIA, RMN, RM | RES |
| ECOGRAFIA, ECO | ECO |
| RADIOGRAFIA, RX | RAD |
| DOPPLER | DOP |
| MAMOGRAFIA | MAM |
| ECOCARDIOGRAMA, ECOCARDIO | ECOCAR |

**Case insensitive:** Funciona con mayúsculas, minúsculas o mixto.

---

## ⚙️ **OPCIONES DEL COMANDO**

```bash
python manage.py importar_estudios_eges [OPCIONES]
```

| Opción | Descripción | Default |
|--------|-------------|---------|
| `archivo` | Ruta al Excel (.xlsx) | **Obligatorio** |
| `--tipo` | Filtrar por tipo: TOM/RES/ECO/RAD/DOP/MAM/ECOCAR/TODOS | TODOS |
| `--dry-run` | Previsualizar sin guardar | False |
| `--actualizar` | Actualizar estudios existentes | False (solo crear) |

---

## 📊 **REPORTE DE SALIDA**

El comando genera un reporte detallado:

```
====================================================
📊 REPORTE DE IMPORTACIÓN
====================================================

✅ 45 estudios creados:
   • 901322 - TAC (TOM) - $4000.00
   • 901323 - TAC CON CONTRASTE (TOM) - $5000.00 [con_contraste]
   • 901324 - ANGIO TAC (TOM) - $7000.00 [angio]
   ... y 42 más

🔄 12 estudios actualizados:
   • 901111 - RMN
   ... y 11 más

⏭️  3 estudios sin cambios (ya existen)

❌ 2 errores:
   • Fila 15: No se pudo mapear servicio: Punción
   • Fila 28: Nombre vacío

====================================================
📈 TOTAL PROCESADOS: 60
```

---

## 🔧 **TROUBLESHOOTING**

### **Error: "Faltan columnas"**
**Causa:** El Excel no tiene las columnas requeridas.
**Solución:** Verificar que tenga: `Prestación`, `Nombre`, `Servicio`

---

### **Error: "No se pudo mapear servicio"**
**Causa:** El servicio no está en `MAPEO_SERVICIO_TIPO`.
**Solución:** 
1. Revisar el valor en la columna "Servicio"
2. Agregar mapeo en `importar_estudios_eges.py` línea 85

---

### **Estudios no se actualizan**
**Causa:** Falta flag `--actualizar`.
**Solución:** Agregar `--actualizar` al comando.

---

### **Precios incorrectos**
**Causa:** Reglas de negocio no coinciden.
**Solución:** Ajustar `PRECIOS_BASE` en `importar_estudios_eges.py` línea 36.

---

## 🎯 **WORKFLOW RECOMENDADO**

### **Importación Inicial:**

```bash
# 1. Previsualizar qué se importará
python manage.py importar_estudios_eges estudios.xlsx --tipo TOM --dry-run

# 2. Si todo se ve bien, importar
python manage.py importar_estudios_eges estudios.xlsx --tipo TOM

# 3. Verificar en el admin de Django
# http://localhost:8000/admin/liquidacion/estudios/
```

### **Actualización de Precios:**

```bash
# 1. Modificar precios en PRECIOS_BASE del comando
# 2. Ejecutar con --actualizar
python manage.py importar_estudios_eges estudios.xlsx --tipo TOM --actualizar
```

---

## 📝 **NOTAS IMPORTANTES**

1. **Código único:** Si dos estudios tienen el mismo código, se actualizará el primero.
2. **Nombre único:** Si dos estudios tienen el mismo nombre, se actualizará el primero.
3. **Regiones:** Siempre se crea con `conteo_regiones=1` por defecto.
4. **Activo:** Todos los estudios importados quedan `activo=True`.
5. **Auditoría:** Se guarda `fecha_actualizacion_precios` automáticamente.

---

## 🚀 **PRÓXIMOS PASOS**

### **1. Ejecutar Migración Local**
```bash
python manage.py migrate
```

### **2. Testing Local**
```bash
# Probar con tu Excel en modo dry-run
python manage.py importar_estudios_eges tu_archivo.xlsx --tipo TOM --dry-run
```

### **3. Deploy a Heroku**
```bash
git add -A
git commit -m "feat(liquidacion): Ecocardiograma + comando importación inteligente"
git push heroku feature/colegiales:main
heroku run python manage.py migrate --app tu-app
```

### **4. Ejecutar Importación en Heroku**
```bash
heroku run python manage.py importar_estudios_eges estudios.xlsx --tipo TOM --app tu-app
```

---

## 📧 **SOPORTE**

Si encontrás algún problema o necesitás ajustar las reglas de negocio, editá:
- **Precios:** `importar_estudios_eges.py` línea 36 (`PRECIOS_BASE`)
- **Mapeo servicios:** línea 85 (`MAPEO_SERVICIO_TIPO`)
- **Patrones variantes:** línea 104 (`PATRONES_VARIANTES`)
