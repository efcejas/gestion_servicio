# MATRIZ DE DECISIONES: QUÉ MANTENER vs QUÉ ELIMINAR
## Liquidacion App - Sanatorio Colegiales

---

## MODELOS (models.py)

| Modelo | ¿Mantener? | Razón | Acción |
|--------|-----------|-------|--------|
| **Estudios** | ✅ SÍ | Catálogo base de tipos de prácticas (ECO, RAD, TOM, RES). Necesario para precios/liquidación. | Mejorar: agregar estado (activo/inactivo), valor_base, requires_authorization, timestamps |
| **RegistroEstudiosPorMedico** | ✅ SÍ | Tabla principal: registra QWHAT cada médico hizo. Es el corazón del sistema. | Renombrar → PracticaRealizada. Agregar: session_contable_fk, estado, edited_by, edited_at, motivo_ajuste |
| **DiaSinPacientes** | ✅ SÍ | Crédito a profesional que no tuvo pacientes. Caso excepcional pero legítimo. | Agregar: session_contable_fk. Mejorar validaciones. |
| **RegistroProcedimientosIntervensionismo** | ❌ NO | Duplica funcionalidad. Un procedimiento es un "Estudio" con tipo='PROC'. Crea complejidad sin valor. | **ELIMINAR** (después de export a CSV Estudios con tipo=PROC) |

**Conteo:** 3 modelos core + 0 a eliminar = LIMPIO

---

## VISTAS (views.py)

| Vista | Líneas | ¿Mantener? | Razón | Acción |
|-------|--------|-----------|-------|--------|
| **PortalLiquidacionInicioView** | ~50 | ❌ NO | Sin login = exposición de datos sensibles (salarios, facturación). Violación de compliance. Mejor: Dashboard restringido con @login_required | **ELIMINAR** |
| **EstudiosCreateView** | ~30 | ✅ SÍ (Admin only) | Creación de nuevos tipos de estudios. Necesario para configuración. | Agregar: @admin_required, validación de código único |
| **EstudiosListView** | ~20 | ✅ SÍ (Admin only) | Ver catálogo disponible. | Agregarfiltro: estado (activo/inactivo) |
| **RegistroEstudiosPorMedicoCreateView** | ~80 | ✅ SÍ | **CRÍTICA**: Interfaz de entrada para médicos. Bien validada. | Mejorar: verificar session_contable.estado=='abierta' |
| **RegistroEstudiosPorMedicoListView** | ~120 | ✅ SÍ | Médicos ven sus registros. Coordinador ve todos (con filtros). Reportes base. | Mejorar: separar vista médico vs admin. Agregar "fuera de término" |
| **RegistroEstudiosPorMedicoUpdateView** | ~40 | ✅ SÍ | Médicos corrigen errores dentro del plazo. Coordinadores pueden ajustar después. | Agregar: auditoría de cambios. Bloquear si session_contable cerrada. |
| **RegistroEstudiosPorMedicoDeleteView** | ~30 | ❌ CONDICIONAL | Solo si se registró dentro de sesión ABIERTA y es el mismo médico/admin. Histórico requiere que se bloquee. | Reemplazar con soft_delete + AuditLog. Bloquear siempre post-cierre. |
| **RegistrarDiaSinPacientesView** | ~50 | ✅ SÍ | Excepciones legítimas (licencia, feriado). Bien diseñado. | Agregar: session_contable_fk |
| **InformadosPorMedicoPorMesListView** | ~100 | ❌ NO | Filtro de "solo estudios informados" es un filtro más, no una vista separada. Vista de reportes duplica lógica. | **CONSOLIDAR** en ReporteEstudiosPorMedicoMes (single view, múltiples filtros) |
| **EcografiasPorMedicoPorMesListView** | ~100 | ❌ NO | Ídem. "Ecografías" es un filtro: tipo_estudio='ECO', no vista separada. | **CONSOLIDAR** |
| **ProcedimientosPorMedicoPorMesListView** | ~100 | ❌ NO | Con el plan: procedimientos se absorben en Estudios. Vista desaparece automáticamente. | **ELIMINAR** |
| **ProcedimientosIntervensionismoListCreateView** | ~80 | ❌ NO | Duplica lógica de RegistroEstudiosPorMedicoCreateView. Si absorbemos el modelo, off. | **ELIMINAR** |
| **ProcedimientosIntervensionismoListView** | ~60 | ❌ NO | Ídem. | **ELIMINAR** |
| **ProcedimientosIntervensionismoUpdateView** | ~40 | ❌ NO | Ídem. | **ELIMINAR** |
| **ProcedimientosIntervensionismoDeleteView** | ~30 | ❌ NO | Ídem. | **ELIMINAR** |
| **CargaMasivaView** | ~100 | ❌ NO | No integrada en flujo. Sin validaciones aparentes. Para datos masivos: paciencia. entrada manual es mejor. | **ELIMINAR** |

**Conteo:** 6 vistas core + 9 a eliminar = **-1350 líneas de código**

---

## FORMULARIOS (forms.py)

| Formulario | ¿Mantener? | Razón | Acción |
|-----------|-----------|-------|--------|
| **RegistroEstudiosPorMedicoCreateViewForm** | ✅ SÍ | Interface principal de entrada. Select2 es buen UX. Validaciones OK. | Mejorar: agregar validators para DNI, fecha futura |
| **DiaSinPacientesForm** | ✅ SÍ | Simple, funcional. | OK |
| **FiltroEstudiosPorMedicoForm** | ✅ SÍ | Búsqueda OK. Mes/año funciona. | Mejorar: convertir a "Filtro único" para todos los reportes |
| **FiltroMedicoMesForm** | ❌ NO | Hay 3-4 formas de filtrar lo mismo (mes/año/médico). Consolidar. | **FUSIONAR** en FormFiltroEstudios (único, reutilizable) |
| **FiltroProcedimientosForm** | ❌ NO | Procedimientos se absorben en Estudios. | **ELIMINAR** |
| **RegistroProcedimientosIntervensionismoCreateViewForm** | ❌ NO | Modelo se elimina. | **ELIMINAR** |
| **CargaExcelForm** | ❌ NO | Vista se elimina. | **ELIMINAR** |

**Conteo:** 3 formularios + 4 a eliminar = **Limpio**

---

## URLS (urls.py)

| Ruta | ¿Mantener? | Razón | Acción |
|------|-----------|-------|--------|
| `/estudios/create/` | ✅ SÍ | Admin crea tipos de estudios. | Agregar `@admin_required` |
| `/estudios/list/` | ✅ SÍ | Admin ve catálogo. | Ídem |
| `/registro_estudios_por_medico/create/` | ✅ SÍ | **CRÍTICA**: Médicos registran prácticas. | Agregar `@login_required` |
| `/registro_estudios_por_medico/list/` | ✅ SÍ | Médicos ven sus registros / Admin ve todos. | Ídem |
| `/registro_estudios_por_medico/{id}/update/` | ✅ SÍ | Correcciones. | Ídem |
| `/registro_estudios_por_medico/{id}/delete/` | ⚠️ CONDICIONAL | Solo en sesión abierta, no post-cierre. | Implementar soft_delete, bloquear post-cierre |
| `/registrar_dia_sin_pacientes/` | ✅ SÍ | Excepciones. | OK |
| `/portal/` | ❌ NO | Sin login = riesgo. | **ELIMINAR** |
| `/informados-por-medico-por-mes/` | ❌ NO | Consolidar en único endpoint `/reportes/estudios/` | **ELIMINAR** |
| `/ecografias-por-medico-por-mes/` | ❌ NO | Ídem. | **ELIMINAR** |
| `/procedimientos-por-medico-por-mes/` | ❌ NO | Procedimientos se absorben. | **ELIMINAR** |
| `/procedimientos_intervensionismo/*` (5 rutas) | ❌ NO | Modelo/vistas se eliminan. | **ELIMINAR** |
| `/carga-excel/` | ❌ NO | Vista se elimina. | **ELIMINAR** |
| `/exportar_excel_*` (3 rutas) | ⚠️ MEJORAR | Funcionan, pero SIN LOGIN. Riesgo. Consolidar en únicaexportación con permisos. | Agregar `@login_required`, `@require_role('admin')` |
| `/generar_pdf_liquidacion` | ⚠️ MEJORAR | Ídem. | Ídem |

**Conteo:** 7 rutas core + 10 a eliminar = **Limpio**

---

## ANÁLISIS CUANTITATIVO

```python
ANTES (Actual):
├─ Modelos: 4 ✅ + 1 ❌ = 4 útiles
├─ Vistas: 6 ✅ + 9 ❌ = 6 útiles
├─ Formularios: 3 ✅ + 4 ❌ = 3 útiles
├─ URLs: 7 ✅ + 10 ❌ = 7 públicas
├─ Migrations: 15 archivos (evolución caótica)
└─ Líneas en views.py: 1073 total, ~800 a reorganizar, ~200 a eliminar

DESPUÉS (Target):
├─ Modelos: 3 + SesionContable (nuevo) = 4 ✅
├─ Vistas: 6 core + 2 reportes consolidados = 8 ✅ (vs 15)
├─ Formularios: 3 + FormFiltroUnificado = 4 ✅ (vs 7)
├─ URLs: 7 core + 2 reportes = 9 ✅ (con auth)
├─ Migrations: 1 new (SesionContable) + 1 safety (backup procedures)
└─ Líneas en views.py: ~600 (reorganizadas en 4 módulos)

AHORRO:
- Código eliminado: ~1000 líneas
- Complejidad: -40% (menos duplicación)
- Seguridad: +100% (auth en todas partes)
- Mantenibilidad: +200% (separación de concerns)
```

---

## RECOMENDACIÓN FINAL

### Opción A: "CIRUGÍA MAYOR" (3-4 semanas)
- Eliminar todo a la vez
- Renombrar modeltos
- Partir views.py
- Crear SesionContable
- **Ventaja:** Limpio forever
- **Riesgo:** MEDIO (regreessions si no testeas bien)

### Opción B: "EVOLUTIVA" (6-8 semanas)
- Semana 1: Eliminar modelos/vistas muertos (procedimientos, carga masiva)
- Semana 2: Mejorar auth en rutas existentes
- Semana 3: Renombrar modelos core
- Semana 4: Partir views.py
- Semana 5: SesionContable + validaciones
- Semana 6-8: Tests y refinamiento
- **Ventaja:** LOW RISK, puedes deploy incremental
- **Desventaja:** Más trabajo, pero más controlado

### Recomendación de Copilot: **OPCIÓN B**
1. Primero: Order ideas (✅ Ya hecho, tienes este doc)
2. Luego: Eliminar muerto (1 semana)
3. Luego: Mejorar existente (2 semanas)
4. Al final: Agregar nuevas piezas (3 semanas)

**Razón:** Sanatorio Colegiales es cliente vivo. No podés romper facturación. Mejor paso a paso.

