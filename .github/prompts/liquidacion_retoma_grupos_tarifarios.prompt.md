---
description: "Prompt de retoma para el módulo liquidacion — contexto de grupos tarifarios y pendientes resueltos/abiertos"
name: "Liquidacion Retoma Grupos Tarifarios"
argument-hint: "Opcional: indicá en qué parte querés continuar (tarifas Doppler, nuevos grupos, carga de datos, etc.)"
agent: "agent"
---

# Retoma: Módulo Liquidación — Grupos Tarifarios

## Estado al 14 de mayo de 2026

### ✅ Lo que está funcionando

El sistema de **grupos tarifarios** está implementado y desplegado en producción (Heroku).

| Componente | Estado |
|------------|--------|
| `GrupoTarifario` (model) | ✅ En producción, 10 grupos activos |
| `TarifaGrupoTarifario` (model) | ✅ 10 tarifas vigentes cargadas |
| `Estudios.grupo_tarifario` (FK nullable) | ✅ 257/257 estudios clasificados (100%) |
| `Estudios.precio_para_os()` | ✅ Prioriza tarifa vigente del grupo; fallback a precio legado |
| `RegistroEstudiosPorMedico.calcular_monto()` | ✅ Usa el resolver |
| `grupo_tarifario_mapping.py` | ✅ Función `inferir_codigo_grupo()` centralizada y testeada |
| `backfill_grupo_tarifario_estudios.py` | ✅ Idempotente, 257 estudios asignados |
| Tests (18 en total) | ✅ Todos pasan en SQLite local |

### ❌ Problema pendiente: Doppler con contexto LECHO vs SERVICIO

La matriz tarifaria real (Abril 2026) tiene precios **distintos** según dónde se realiza el Doppler:

| Estudio | COBER | VARIAS (otras OS) |
|---------|-------|-------------------|
| Doppler Periférico **en Servicio** | $9.400 | $11.000 |
| Doppler Periférico **en Lecho** | $11.600 | $13.200 |
| Doppler Cardíaco **en Servicio** | $11.600 | $13.200 |
| Doppler Cardíaco **en Lecho** | $13.200 | $15.400 |

El sistema actual tiene **un solo grupo** `ECO_DOPPLER` para todos, con tarifa plana `COBER $8.500`.

#### ¿Por qué existe esta diferencia?
- **En Servicio**: Doppler realizado en consultorio externo o ambulatorio.
- **En Lecho**: Doppler realizado en cama del paciente internado — mayor complejidad operativa, se cobra más.

Esta distinción aplica también para Doppler Cardíaco (Ecocardiograma Doppler).

---

### ❌ Otros grupos faltantes en la matriz

Estos estudios aparecen en la matriz real pero **no tienen grupo tarifario propio** en el sistema:

| Estudio | COBER | VARIAS |
|---------|-------|--------|
| Ecostress | $27.500 | $27.500 |
| Ecostress C/DOBUTA | $27.500 | $27.500 |
| Eco Burbuja | $26.500 | $30.500 |
| Transesofágico (ETE) | $27.500 | $33.000 |
| ETE en Quirófano | $49.500 | $55.000 |
| RMN Cardíaca | $73.500 | $73.500 |
| RMN Mamaria | $31.900 | $36.850 |
| ARTRO RMN | $36.600 | $42.500 |
| RMN Difusión | $8.800 | $8.800 |
| RMN Mama (informe) | — | — |
| Guardia Pasiva (valor día) | $40.200 | — |

---

### ❌ Las tarifas actuales en Heroku son placeholders

Los valores actuales en `TarifaGrupoTarifario` **NO son los reales**. Fueron cargados como datos de prueba:

```
TOM_SIMPLE:     COBER $4.000   ← Real COBER: $4.400 (INFORMES TAC)
TOM_CONTRASTE:  COBER $5.000   ← Real COBER: $5.500 (INFORMES TAC CON CTE)
RES_SIMPLE:     COBER $5.000   ← Real COBER: $5.500 (INFORMES RMN)
```

---

## 🎯 Trabajo pendiente (próxima sesión)

### Opción A — Mínima (sin nueva arquitectura)
Actualizar los valores de las tarifas existentes para que sean correctos.
- No resuelve Doppler LECHO/SERVICIO
- Es la forma más rápida de tener precios correctos para el grueso de estudios

### Opción B — Completa (nueva arquitectura de grupos)
Crear grupos tarifarios para los contextos faltantes:
```python
ECO_DOPPLER_SERVICIO   # Doppler periférico/cardíaco en consultorio
ECO_DOPPLER_LECHO      # Doppler periférico/cardíaco en cama de internado

ECO_ESPECIALES         # Ecostress, Burbuja, Transesofágico
ECO_QUIROFANO          # ETE en Quirófano
RES_CARDIACA           # RMN Cardíaca (precio único sin diferencia OS)
RES_MAMARIA            # RMN Mamaria
RES_ARTRO              # ARTRO RMN
RES_DIFUSION           # RMN Difusión
```

Esto requiere:
1. Ampliar `inferir_codigo_grupo()` con nuevos patrones (LECHO, EN CAMA, etc.)
2. Crear migración con los nuevos grupos
3. Cargar tarifas reales desde la matriz
4. Re-ejecutar backfill para reclasificar estudios ya existentes
5. Tests para los nuevos patrones

### Opción C — Separar ejecución de datos (recomendada)
1. Corregir tarifas existentes con valores reales (scripted o via admin)
2. Dejar Doppler contextual como "pendiente de política" hasta confirmar
   si el contexto (lecho/servicio) se registra o no en el informe

---

## 🔑 Pregunta de política sin resolver

> ¿El contexto de un Doppler (si fue en Lecho o en Consultorio) queda registrado
> en algún campo del informe o pedido? ¿O solo se sabe por el nombre del estudio?

Esto define si la diferenciación es automática (por nombre) o requiere un campo explícito.

---

## Archivos clave

- `liquidacion/models.py` — `precio_para_os()` (L161), `calcular_monto()` (L636)
- `liquidacion/grupo_tarifario_mapping.py` — `inferir_codigo_grupo()`
- `liquidacion/management/commands/backfill_grupo_tarifario_estudios.py`
- `liquidacion/management/commands/verificar_grupos.py`
- `docs/producto/SISTEMA_LIQUIDACION_COLEGIALES_V2.md` (sección 10.3)
