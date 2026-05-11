# 🏥 Consultorios - Guía de Operación

## 📊 FASE 2 COMPLETADA: Gestión Operativa desde UI

El módulo `consultorios` ofrece ahora un **tablero operativo completo** sin necesidad de entrar al admin Django. Todas las operaciones se hacen desde la grilla semanal visual.

---

## 🎯 Flujo Principal: Grilla Semanal

### Acceso
```
http://localhost:8000/consultorios/grilla/
```

### Controles Principales

| Control | Función |
|---------|---------|
| **← Previa / Próxima →** | Navega semanas completas |
| **Hoy** | Vuelve a la semana actual |
| **Selector de fecha** | Elige cualquier fecha (la grilla se ajusta a esa semana) |
| **Ver franjas libres** | Muestra espacios de 08:00-20:00 disponibles |
| **+ Bloque** | Crea un bloque nuevo en la semana operativa |

### Lectura de la Grilla

```
┌─ Profesional = color único (mismo profesional siempre mismo color)
├─ Blanda: bloques de residentes (R1-R4) — pueden desplazarse si nuevo staff ocupa espacio
├─ Dura: bloques de jefes/instructores — no se desplazan
├─ cobertura: el bloque permite cubrir con residente
└─ Reportar ausencia: abre circuito de reemplazo/cobertura
```

---

## 🔄 Ciclo de Migración: El Ajuste Operativo

### Concepto
Una **migración** es reubicar un bloque a otro consultorio, día u horario. Útil cuando:
- Necesitas mover un bloque de staff a mejor horario
- Un residente desocupa espacio y necesitas reorganizar
- Un bloque futuro debe comenzar en otra fecha

### Pasos de Migración

#### 1. Selecciona bloque en grilla → **Migrar** (ícono ↔️)

#### 2. Pantalla de Migración
```
Destino propuesto
├─ Consultorio destino
├─ Fecha destino (define el día de semana)
├─ Hora inicio destino
└─ Hora fin destino

Resultado: [Evaluar migración]
└─ LIBRE: sin conflictos
└─ BLANDO: ocupado por residente (se pausará si aplicas)
└─ BLOQUEADO: imposible (superposición con jefe/instructor)
```

#### 3. Si LIBRE o BLANDO → **Aplicar migración**
```
Sucede:
├─ Se crea bloque destino (ACTIVO)
├─ Bloque origen se libera (FINALIZADO)
├─ Si hay blandos ocupando: se pausan (PAUSADO)
└─ Vuelves a la grilla con foco en bloque nuevo

Si es migración FUTURA (fecha > hoy):
├─ Origen queda ACTIVO hasta día previo
├─ Blandos se "recortan de vigencia" automáticamente
└─ El nuevo bloque arranca en fecha destino
```

#### 4. Reubicación de Blandos Afectados
Después de aplicar migración, la grilla muestra:
```
Bloques blandos pausados
└─ [nombre bloque] [consultorio] [horario]
    └─ [Reabrir] para restituir (vuelve a ACTIVO)
```

---

## ➕ Crear Bloque desde Grilla

### Opción A: Franja Libre
```
Grilla → Ver franjas libres → [Tomar] en franja elegida
└─ Form pre-lleno con:
   ├─ Consultorio
   ├─ Día semana
   ├─ Hora inicio/fin
   └─ Fecha inicio vigencia (la semana operativa)
```

### Opción B: Celda Vacía
```
Grilla → [+] en celda vacía
└─ Form con:
   ├─ Consultorio (pre-lleno)
   ├─ Día semana (pre-lleno)
   └─ Hora/vigencia a elegir
```

### Opción C: "Nuevo Bloque"
```
Grilla → [+ Bloque]
└─ Form en blanco (todos los campos)
```

---

## ✏️ Editar / Eliminar Bloques

### Editar (desde grilla)
```
Bloque → [⌨️ ícono] → Editar
```
El formulario conserva la fecha operativa de la grilla.

### Eliminar (desde grilla, solo superuser)
```
Bloque → [🗑️ ícono] → Confirmar eliminación
```

---

## 📋 Vista Diaria: Detalle de Consultorio × Día

### Acceso
```
Grilla → Clic en bloque → Vista diaria
O
Grilla → Consultorio → Día específico
```

### Qué ves
```
┌─ Bloques del día (cronológicos)
├─ Horarios sugeridos disponibles (si hay espacio)
├─ Equipos del consultorio
└─ Botón: Nuevo bloque (pre-lleno con consultorio/día/fecha)
```

### Navegación
```
Selector de días (arriba)
├─ Lun / Mar / ... / Dom
└─ "Volver a grilla" conserva fecha operativa
```

---

## 🏗️ Modelos y Conceptos

### BloqueHorario
```python
consultorio              # FK a Consultorio
dia_semana              # 0-6 (Lun-Dom)
hora_inicio, hora_fin   # time fields
tipo_actividad          # ECO_GENERAL, DOPPLER, OBSTETRICA, etc.
tipo_lista              # ABIERTA, CERRADA
estado                  # ACTIVO, PAUSADO, FINALIZADO

# Profesional (uno u otro)
profesional_interno          # FK a CustomUser
profesional_externo          # FK a ProfesionalExterno
profesional_asignado_temporal # nombre libre para bloques genéricos

# Vigencia (clave para futuras/programadas)
fecha_inicio_vigencia   # default: today
fecha_fin_vigencia      # default: None (indefinida)

# Operativas
permite_cobertura_residente
prioridad_cobertura
tipo_titular            # NOMINAL, R1, R2, R3, R4, JEFES_RES, DOCENTE
```

### Clasificación "Blando" vs "Dura"
```
BLANDO:
├─ tipo_titular in [R1, R2, R3, R4]
└─ Se puede pausar si nuevo staff ocupa lugar

DURA:
├─ tipo_titular in [JEFES_RES, DOCENTE, ...]
└─ No se pausa; genera conflicto (BLOQUEADO)
```

---

## 🔍 Detección de Conflictos

Aplica automáticamente en:
- **Crear bloque**
- **Editar bloque**
- **Evaluar migración**

Detecta:
```
✓ Mismo consultorio, día, horario superpuesto
✓ Mismo profesional en dos lugares a mismo tiempo
✓ Vigencia: dos bloques con vigencias solapadas
```

Resultado:
```
LIBRE:     sin conflictos → puedes guardar
BLANDO:    conflicto con residente → se pausará si aplicas
BLOQUEADO: conflicto con jefe/staff → no permitido
```

---

## 📝 Deuda Técnica Conocida

| Tema | Estado | Nota |
|------|--------|------|
| Permisos UI por rol | ✅ Básico | Superuser puede todo; otros usuarios pueden ver/crear |
| Migraciones futuras | ✅ Implementado | Vigencia recortada automáticamente |
| Sugerencias reubicación | ✅ Implementado | Se muestran destinos alternativos para blandos |
| Re-abrir blandos pausados | ✅ Implementado | POST view en grilla |
| Fecha operativa persistente | ✅ Implementado | Se arrastra entre vistas |

---

## 🚀 Próximos Pasos Sugeridos

1. **Tests adicionales:** Cobertura de migración futura + reubicación
2. **Resumen semanal:** Dashboard resumido de bloques por tipo
3. **Reportes:** Export de grilla (PDF/Excel)
4. **Notificaciones:** Alerta cuando blandos se pausan
5. **Visor DICOM:** Integración con CornerstoneJS (futura)

---

## ⚠️ Restricciones y Notas

- **Vigencia:** Un bloque marcado como FINALIZADO o fuera de vigencia **no aparece en la grilla**
- **Fecha operativa:** Persiste mientras navegas (se rompe si cierras/reloads sin parametrizar)
- **Migración futura:** Recorta vigencia de blandos conflictivos (no los pausa)
- **Superuser:** Solo superuser puede eliminar y migrar bloques
- **Profesionales:** Un bloque siempre tiene exactamente 1 profesional (interno, externo, o genérico temporal)

---

## 🛠️ Comandos Útiles

```bash
# Ver detalles del módulo
python manage.py check consultorios

# Cargar datos de demo
python manage.py cargar_consultorios_ejemplo

# Seed de escenarios de migración
python manage.py cargar_escenarios_migracion --reset

# Tests del módulo
python manage.py test consultorios
```

---

**Última actualización:** 10 de mayo de 2026  
**Versión:** Fase 2 - Gestión Operativa  
**Estado:** ✅ Producción — Fecha Operativa Activa  
**Changelog Reciente:**
- ✅ Sistema de fecha operativa en grilla
- ✅ Migración futura con vigencia inteligente
- ✅ Reubicación sugerida de blandos
- ✅ UI compacta y mejorada
- ✅ Propagación de fecha en todas las vistas
