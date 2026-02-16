# ANÁLISIS DEL SISTEMA DE LIQUIDACIÓN
## Sanatorio Colegiales - Febrero 2026

---

## 1. FLUJO DE NEGOCIO ACTUAL (Lo que DEBE pasar)

### Actores:
- **Médico/Profesional:** Registra prácticas realizadas (estudios, procedimientos)
- **Coordinador/Admin:** Revisa, valida, cierra mes
- **Director/Administrativo:** Factura a profesional, ve reportes

### Flujo Ideal:

```
MOMENTO 0: Inicio del mes (1º de mes)
├─ Catálogos cargados: Tipos de estudios, precios, convenios
└─ Sesión contable abierta

MOMENTO 1: Durante el mes (1-30)
├─ Profesional: Registra prácticas (vía web, sin logs complejos)
│  ├─ Datos mínimos: Paciente, DNI, Estudio/Procedimiento, Fecha
│  └─ Sin obligaciones contables aún (solo registro)
│
├─ Sistema: Valida en tiempo real
│  ├─ DNI correcto (11 caracteres, sin duplicados en 5 min)
│  ├─ Estudio existe en catálogo
│  ├─ Fecha no es futura
│  └─ Paciente + Fecha + Estudio única (evita duplicados)
│
└─ Coordinador: Monitorea en tiempo real (dashboard)
   ├─ Prácticas del día
   ├─ Alertas: Profesional sin movimiento >24h
   └─ Reparto por servicio/especialidad

MOMENTO 2: Cierre de mes (últimos 2 días)
├─ Admin bloquea nuevas carga (estado de sesión = "closed")
├─ Sistema totaliza:
│  ├─ Total de prácticas por profesional
│  ├─ Total por tipo de estudio
│  ├─ Total por servicio
│  └─ Reconoce fuera de término (no hizo en 24h → alerta)
│
├─ Profesional: Ve su resumen (qué se le facturará)
│  ├─ Listado de prácticas registradas
│  ├─ Total de regiones liquidables
│  └─ Monto estimado a recibir
│
└─ Admin: Exporta para facturación
   ├─ Excel por profesional
   ├─ Excel por servicio
   └─ PDF con firmantes (director, responsable)

MOMENTO 3: Después del cierre
├─ Sesión contable cerrada (read-only)
├─ Historial disponible para auditoría
└─ Próxima sesión = 1º del próximo mes
```

---

## 2. ANÁLISIS DEL CÓDIGO ACTUAL

### 🟢 LO QUE ESTÁ BIEN (Mantener)

#### MODELOS:
```python
✅ Estudios
   - Nombre, tipo (ECO, RAD, TOM, RES)
   - Conteo de regiones (para facturación)
   - Bien definido, completo

✅ RegistroEstudiosPorMedico
   - Médico (FK)
   - Paciente (nombre, apellido, DNI)
   - Fecha del informe
   - Estudio (M2M)
   - Cantidad de estudio
   - Lógica de total_regiones() está buena
   
   ⚠️ Mejorable: Necesita campos de auditoría (created_at, updated_by)

✅ DiaSinPacientes
   - Buena para dar crédito a médico sin pacientes
   - Bien estructurado
```

#### VISTAS:
```python
✅ RegistroEstudiosPorMedicoCreateView
   - Validación de duplicados (5 min)
   - Reasignación automática de médico logueado
   - Buena UX: pre-rellena último tipo usado
   
✅ RegistroEstudiosPorMedicoListView
   - Filtros por mes/año
   - Búsqueda por paciente/DNI
   - Orden configurable
   - Separación por tipo de estudio
   - Total de regiones bien calculado
   
✅ RegistroEstudiosPorMedicoUpdateView
   - Permite corregir errores
   - Reasigna a usuario logueado
```

#### FORMULARIOS:
```python
✅ RegistroEstudiosPorMedicoCreateViewForm
   - Validaciones básicas
   - Tailwind CSS bien aplicado
   - Select2 para estudios es buen UX
   
✅ FiltroEstudiosPorMedicoForm
   - Mes/año funcionan
   - Búsqueda es útil
   - Orden flexible
```

---

### 🔴 LO QUE NO SIRVE (Eliminar)

#### MODELOS:
```python
❌ RegistroProcedimientosIntervensionismo
   ¿Por qué?: 
   - Duplica la funcionalidad de RegistroEstudiosPorMedico
   - "Procedimiento" es lo mismo que "Estudio" en contexto de liquidación
   - Tiene campos raros: "conteo_regiones" (por qué aquí y no solo en Estudios?)
   - Crea complejidad innecesaria
   
   ✅ Solución: 
   - Absorber en Estudios como tipo = 'PROC' o 'INT' 
   - Usar el mismo flujo de registro que estudios
   - Eliminar modelo completo
```

#### VISTAS:
```python
❌ PortalLiquidacionInicioView (portal sin login)
   ¿Por qué?: 
   - Exposición de información sensible (salarios, facturación)
   - Sin autenticación = riesgo de compliance
   - "Administrativo sin login" contradice seguridad
   
   ✅ Solución: 
   - Mover a login requerido
   - Crear grupo "Administrativo Liquidación"
   - Con permisos granulares (View solo, NO create/modify)

❌ InformadosPorMedicoPorMesListView
❌ ProcedimientosIntervensionismoListCreateView
❌ ProcedimientosIntervensionismoListView
❌ ProcedimientosIntervensionismoUpdateView
❌ ProcedimientosIntervensionismoDeleteView
❌ ProcedimientosPorMedicoPorMesListView
❌ EcografiasPorMedicoPorMesListView
   ¿Por qué?: 
   - Muchas vistas que hace lo mismo (listar + filtrar)
   - Si absorbes procedimientos en Estudios, estas desaparecen
   - Separar por tipo de estudio crea mantenimiento múltiple
   
   ✅ Solución: 
   - Una sola ListaView: ReporteEstudiosPorMedicoMes
   - Filtros en formulario: tipo_estudio, mes, año, médico
   - Exportadores que usan la misma lista

❌ CargaMasivaView (carga excel)
   ¿Por qué?: 
   - No está integrada en el flujo principal
   - Genera más punto de entrada para datos inconsistentes
   - Sin validación aparente
   - Mejor: entrada manual + validación inmediata
   
   ✅ Solución: 
   - Eliminar por ahora
   - Agregar más tarde si hay caso de uso comprobado
```

#### FORMULARIOS:
```python
❌ RegistroProcedimientosIntervensionismoCreateViewForm
   → Eliminar con modelo

❌ FiltroProcedimientosIntervensionismoForm
   → Consolidar en única forma de filtrar

❌ CargaExcelForm
   → Eliminar por ahora
```

#### RUTAS:
```python
❌ /portal/*  (rutas sin login)
❌ /procedimientos-intervensionismo/*
❌ /mis-procedimientos/
❌ /procedimientos_intervensionismo/*
❌ /ecografias-por-medico-por-mes/
❌ /informados-por-medico-por-mes/
❌ /procedimientos-por-medico-por-mes/
❌ /carga-excel/
```

---

### 🟡 LO QUE NECESITA AJUSTE (Mejorar)

#### MODELOS:
```python
⚠️ Estudios
   ├─ Agregar: estado (activo/inactivo) por fecha vigencia
   ├─ Agregar: valor base para liquidación (o relación con Arancel)
   ├─ Agregar: requiere autorización previa (works comp, etc)
   └─ Agregar: timestamp (created_at, modified_at)

⚠️ RegistroEstudiosPorMedico
   ├─ Renombrar a: PracticaRealizada (es más claro)
   ├─ Agregar: SesionContable FK (para asociar a período de facturación)
   ├─ Agregar: estado (registrada, validada, liquidada, debitada)
   ├─ Agregar: edited_by, edited_at (auditoría)
   ├─ Agregar: motivo_ajuste (si se modifica después)
   └─ Añadir validador: no permita fecha futura

⚠️ DiaSinPacientes
   ├─ Agregar: SesionContable FK (para cierre de mes)
   └─ Está bien, solo emprolijarlo
```

#### VISTAS:
```python
⚠️ RegistroEstudiosPorMedicoCreateView
   ├─ Agregar: verificación de SesionContable.estado == 'abierta'
   ├─ Agregar: Bloquear si sesión está cerrada
   ├─ Agregar: Límite de 5k registros/día por médico (prevención de errores)
   └─ Mensaje: "Sesión de facturación cierra el 28 de febrero"

⚠️ Reportes de exportación
   ├─ Agregar: Filtro por SesionContable (no por mes/año manual)
   ├─ Agregar: Opciones de firmas digitales
   ├─ Agregar: Totales por servicio
   ├─ Agregar: Flag de "Pendiente de validación"
   └─ Formato: PDF embebido con datos auditables

⚠️ ListaView actual (RegistroEstudiosPorMedicoListView)
   ├─ Agregar: Vista de Admin (todos los médicos, filtrable)
   ├─ Agregar: Vista de Médico (solo sus propios registros)
   └─ Agregar: Indicador de "fuera de término" (<24h sin cerrar)
```

#### SEGURIDAD:
```python
⚠️ Permisos
   ├─ Remover hardcoding de 'Médicos de staff - informes'
   ├─ Crear: @require_group_membership decorator
   ├─ Definir roles:
   │  ├─ MEDICO: Create=self only, Read=self only, Update=self, Delete=NO
   │  ├─ COORDINADOR: Create/Read=all, Update=all, Delete=NO
   │  ├─ ADMINISTRATIVO: Read=all, Update=all (auditable), Export=YES, Delete=NO
   │  └─ DIRECTOR: Read=all, Approve=month-close, Delete=only in current open month
   └─ Implementar: AuditLog para todo cambio
```

---

## 3. CATÁLOGO DE CAMBIOS (Prioridad)

### PRIMERA SEMANA (MVP limpio):

#### Sprint 1: **Ordenar dominio** (no tocás código aún)
```
□ Definir: ¿Un "procedimiento de intervensionismo" es distinto de un "estudio"?
  └─ Si no: absorber en Estudios
  └─ Si sí: ¿qué diferencia hay en liquidación?

□ Definir: SesionContable (período de facturación)
  ├─ Fecha inicio (1º de mes)
  ├─ Fecha cierre (última fecha para registrar)
  ├─ Estado (abierta/cerrada)
  ├─ Quién cierra (Director?)
  └─ Qué pasó con mes anterior?

□ Definir: Ciclo de vida de una Práctica
  ├─ Registrada (médico ingresa)
  ├─ Validada (coordinador revisa duplicados?)
  ├─ Liquidada (se incluye en facturación)
  ├─ Debitada (quedó fuera de término)
  └─ Pagada (facturación completada)

□ Definir: "Fuera de término" 
  ├─ ¿24 horas desde qué? (desde solicitud en Netterm?)
  ├─ ¿O es automático si no se registra en 24h?
  ├─ ¿Quién envía alerta?
```

#### Sprint 2: **Eliminar lo muerto** (refactor seguro)
```
□ Eliminar Vista: PortalLiquidacionInicioView
□ Eliminar Vista: ProcedimientosIntervensionismoListCreateView + delete + update
□ Eliminar Vista: CargaMasivaView
□ Eliminar Formulario: RegistroProcedimientosIntervensionismoCreateViewForm
□ Eliminar Formulario: FiltroProcedimientosIntervensionismoForm
□ Eliminar Formulario: CargaExcelForm
□ Eliminar URLs relativas a lo anterior
□ Eliminar Modelo: RegistroProcedimientosIntervensionismo (o absorber en Estudios)

⚠️ Antes de esto: Exportar datos de RegistroProcedimientosIntervensionismo a CSV
   (por si hay datos históricos que necesites)
```

#### Sprint 3: **Refactor seguro** (mantener funcionalidad, mejorar código)
```
□ Renombrar: RegistroEstudiosPorMedico → PracticaRealizada
  ├─ Crear migración
  ├─ Actualizar imports
  ├─ Actualizar vistas
  └─ Actualizar URLs

□ Partir views.py monolítica:
  ├─ views_captura.py: CreateView + ListaView (médicos)
  ├─ views_reportes.py: Reportes administrativos
  ├─ views_exportacion.py: Excel/PDF
  └─ views_admin.py: Cierre de sesión, auditoría

□ Crear: SesionContableModel
  ├─ FK a RegistroEstudios
  ├─ Validar: "¿puedo crear registro en esta sesión?"
  └─ Bloquear: si sesión está cerrada

□ Crear: decoradores de permisos
  @require_role('medico', 'coordinador', 'admin')
  @require_open_session
  @audit_changes
```

---

## 4. RESPUESTAS A PREGUNTAS CLAVE

### P: "¿Qué necesita un médico?"
A: 
- ✅ Formulario simple para registrar práctica (paciente, estudio, fecha)
- ✅ Ver sus registros del mes (checar qué registró)
- ✅ Corregir error si se equivocó
- ✅ Ver cuánto se le va a facturar (antes de cierre)
- ❌ NO necesita: ver a otros médicos, procedimientos complejos, carga masiva

### P: "¿Qué necesita el administrativo?"
A:
- ✅ Ver todos los registros (filtrable por médico/servicio/mes)
- ✅ Exportar para facturación (Excel/PDF)
- ✅ Dashboard: ¿quién registró hoy? ¿hay pendientes?
- ✅ Cerrar mes (bloquear nuevos registros)
- ✅ Auditoría: quién cambió qué y cuándo
- ❌ NO necesita: UI de carga masiva (código backend sí)

### P: "¿Qué es 'fuera de término'?"
A: Necesitás aclaración con tu equipo, pero probablemente:
- Netterm emite orden → se comunica a médico
- Si médico NO registra en 24h → Sistema alerta a coordinador
- Coordinador puede: esperar, marcar "DiaSinPacientes", o validar que se hizo pero no se cargó
- Si vence el mes sin registro → Se debita (pérdida de ingresos)

---

## 5. TAMAÑO DEL REFACTOR

```
Líneas de código a eliminar: ~400
Líneas a reorganizar: ~800
Nuevos modelos/decoradores: ~200
Nuevas vistas (mejor separadas): ~300

Esfuerzo total: 2-3 semanas (trabajando 2-3h diarias en esto)
Riesgo: BAJO (cambios incrementales, con tests)
Impacto: ALTO (sistema mucho más mantenible)
```

---

## 6. PLAN EJECUTABLE (Próximos pasos)

1. **Esta semana:**
   - [ ] Junta con director/administrativo: Validar "fuera de término" y ciclo de vida
   - [ ] Listar datos históricos de RegistroProcedimientosIntervensionismo (export a CSV)
   - [ ] Escribir tests para RegistroEstudiosPorMedicoCreateView (sin cambiar nada)

2. **Semana 2:**
   - [ ] Eliminar vistas/modelos muertos (con backup)
   - [ ] Renombrar RegistroEstudiosPorMedico → PracticaRealizada (safe migration)
   - [ ] Partir views.py

3. **Semana 3:**
   - [ ] Crear SesionContableModel
   - [ ] Integrar permisos por roles
   - [ ] Tests end-to-end

4. **Semana 4:**
   - [ ] Deploy a staging
   - [ ] UAT con coordinador/admin
   - [ ] Deploy a producción (feature flags)
