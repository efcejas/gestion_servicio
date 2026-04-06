# Rediseño control_guardias — Planificación

## Estado: ARQUITECTURA DEFINIDA — pendiente confirmación de reglas de negocio

---

## Contexto del negocio (relevado 05/04/2026)

- Los **residentes** tienen una cantidad fija de guardias obligatorias por año (reglamento).
- Los **R4** hacen menos guardias que R1/R2/R3 (beneficio de antigüedad).
- La cantidad exacta por año/beneficio está pendiente de confirmar con el usuario.
- **No hay facturación** de guardias por ahora.
- **No hay portal público** — acceso solo con login.
- La imagen de referencia muestra el esquema actual: calendario mensual por equipos (ej: TOMOGRAFÍA), con apellidos asignados por día. Puede haber más de un residente por día (ej: "PRIETO/DIAZ").

## Roles del nuevo sistema

| Rol | Qué puede hacer |
|-----|----------------|
| **Residente** | Ver sus guardias asignadas, reportar ausencia (enfermedad/vacaciones) |
| **Jefe de residentes** | Configurar reglas, generar distribución automática, validar, reasignar |
| **Instructor** | Igual que jefe de residentes |
| **Superuser** | Supervisión total, ver métricas de equidad, override manual |

## Features del nuevo sistema

### Módulo 1: Configuración de reglas
- [ ] Definir tipos de guardia (nombre, días de la semana aplicables, hora inicio/fin)
- [ ] Definir feriados
- [ ] Definir cantidad de guardias obligatorias por año de residencia (R1, R2, R3, R4)
- [ ] Definir período de vigencia (mes o ciclo anual)

### Módulo 2: Distribución automática
- [ ] Generación automática randomizada y equitativa para un período
- [ ] Restricciones: no asignar dos guardias consecutivas al mismo residente
- [ ] Restricciones: respetar cuota máxima por año de residencia
- [ ] Vista de "borrador" para que jefe/instructor valide antes de publicar
- [ ] Indicador de equidad (desvío estándar de horas/guardias por residente)

### Módulo 3: Gestión de ausencias y reasignación
- [ ] Residente puede reportar ausencia (enfermedad / vacaciones) con fecha(s)
- [ ] El sistema detecta guardias afectadas y genera alerta al jefe/instructor
- [ ] Jefe/instructor puede: reasignar manualmente, o pedir nueva distribución automática para los días afectados
- [ ] Historial de ausencias y reasignaciones

### Módulo 4: Calendario interactivo
- [x] Vista mensual tipo grilla con FullCalendar (`/guardias/calendario/`)
- [x] Chips por guardia con nombre abreviado del residente y color por estado
- [x] Tooltip flotante con detalle: residente, tipo, horario, estado / feriado
- [x] Filtro por residente (solo visible para jefes/instructores)
- [x] Dark mode completo
- [x] Leyenda de colores: azul=publicada, ámbar=feriado, gris=borrador
- [x] `GuardiasApiView` segmentada: residentes ven solo sus PUBLICADAS; gestores ven todas + ?residente_id

### Módulo 5: Dashboard de equidad (superuser / jefe)
- [ ] Resumen por residente: guardias asignadas vs. completadas vs. faltantes
- [ ] Alerta si un residente tiene desvío significativo respecto al promedio
- [ ] Export a Excel

## Decisiones de diseño tomadas

| Decisión | Resolución |
|----------|-----------|
| ¿Integración con liquidación? | No, por ahora |
| ¿Portal público? | No — solo con login |
| ¿`MedicoGuardia` sigue? | No — reemplazado por relación directa con `CustomUser` (rol residente) |
| ¿Calendario? | FullCalendar (ya usado) — no Google Calendar API |
| ¿Quién asigna? | Jefe de residentes e instructor. Sistema propone, humano valida |
| ¿Pool único o por equipo? | **Pool único** — todas las guardias en un solo conjunto |
| ¿Cuántas guardias? | **Configurable** por jefes/instructores en módulo "Configuración". Cantidad mensual por año de residencia (R1/R2/R3/R4) + atenuante de antigüedad |
| ¿Cambio de guardia entre residentes? | **Sí** — residente solicita cambio con otro residente, se notifica al jefe/instructor, quien valida o rechaza |

## Reglas de negocio confirmadas

### Cuotas de guardias
- Configurables en un módulo "Configuración" accesible solo para jefes/instructores/superuser
- Se define: cantidad de guardias **por mes** por año de residencia
- Se puede definir un **atenuante de antigüedad**: conforme avanza el año de residencia, la cuota mensual disminuye
- Ejemplo de estructura: `R1 = 8/mes`, `R2 = 7/mes`, `R3 = 6/mes`, `R4 = 4/mes`
- La cantidad exacta la configuran los jefes — el sistema no tiene valores fijos

### Cambio de guardia entre residentes
- Flujo:
  1. Residente A solicita cambio con Residente B para una fecha específica
  2. Residente B debe **aceptar** la solicitud desde su vista
  3. Una vez aceptada por B, se notifica al jefe/instructor
  4. El jefe/instructor **valida o rechaza** definitivamente
  5. Si se aprueba, el sistema actualiza las asignaciones automáticamente
- El historial de cambios queda registrado

### Ausencias (enfermedad / vacaciones)
- El residente reporta ausencia con fechas
- El sistema detecta guardias afectadas y genera alerta
- El jefe/instructor reasigna manualmente o genera redistribución automática para esos días

## Integración con CustomUser (confirmado 05/04/2026)

`CustomUser` ya tiene todo lo necesario — no se necesita nuevo campo:

| Campo | Uso en guardias |
|-------|----------------|
| `rol == 'medico_residente'` | Identifica quién puede recibir asignaciones |
| `rol in ['jefe_residentes', 'instructor_residentes']` | Identifica quién puede gestionar |
| `anio_residencia` (R1..R5) | Determina cuota mensual aplicable |
| `fecha_ingreso_residencia` | Base del cálculo automático de año |
| `recibir_notificaciones` | Respeta preferencia del usuario para emails |

`anio_residencia` se calcula automáticamente via `calcular_anio_residencia()` usando `relativedelta`:
- R1: 0–12 meses, R2: 12–24, R3: 24–36, R4: 36–48, R5: 48–60

El modelo `MedicoGuardia` existente queda **obsoleto** — se reemplaza por FK directa a `CustomUser`.

## Decisiones finales cerradas (05/04/2026)

| Decisión | Resolución |
|----------|-----------|
| ¿Feriados regla especial? | **Sí** — el sistema prioriza para feriados a residentes con menos feriados cumplidos, evitando que siempre sean los mismos. Se registra `es_feriado=True` en cada `AsignacionGuardia`. |
| ¿Notificaciones? | **Email + Inbox interno** — modelo `NotificacionGuardia` dentro del módulo. Respeta `user.recibir_notificaciones` para el email. |
| ¿Atenuante configurable? | **Sí, libre** — los jefes ponen el porcentaje de reducción que quieran por año de residencia. |

## Estado de implementación

- [x] Fase 1 — Modelos base (05/04/2026)
- [x] Fase 2 — Módulo Configuración (vistas Settings) (05/04/2026)
- [x] Fase 3 — Distribución automática (services.py) (05/04/2026)
- [x] Fase 4 — Calendario interactivo (FullCalendar) (05/04/2026)
- [x] Fase 5 — Cambios y ausencias (06/04/2026)
  - `AusenciaResidente`: reportar (residente) → resolver (jefe). Vincula guardias PUBLICADAS afectadas vía M2M. Gestores notificados.
  - `SolicitudCambioGuardia`: flujo PENDIENTE_RECEPTOR → PENDIENTE_JEFE → APROBADA/RECHAZADA/CANCELADA. `aprobar_cambio()` hace el intercambio de residentes en ambas `AsignacionGuardia`.
  - 11 funciones en `services.py` (`reportar_ausencia`, `resolver_ausencia`, `solicitar_cambio`, `aceptar_cambio_receptor`, `rechazar_cambio_receptor`, `aprobar_cambio`, `rechazar_cambio_jefe`, `cancelar_cambio`, `crear_notificacion`, `_notificar_gestores`, `CambioGuardiaError`).
  - 8 vistas nuevas + 8 URLs en `control_guardias/`.
  - 6 templates nuevos + `mis_guardias.html` reescrito con layout dark sidebar y botón "Solicitar cambio" por guardia.
  - 27 tests nuevos (suite total: 70 tests, todos OK).
- [x] Fase 6 — Navegación, fix de templates y bug de distribución (05/04/2026)
  - `TemplateSyntaxError` corregido: `control_guardias/index.html` tenía ~145 líneas duplicadas después del `{% endblock %}`. Truncado a 299 líneas.
  - Link "Guardias" agregado en `base_tailwind.html` para `medico_residente`, `jefe_residentes` e `instructor_residentes`.
  - Sidebar (`includes/sidebar.html`): URL vieja `calendario_guardias_full_tw` → `control_guardias:index` + sub-nav completo expandido en contexto.
  - `admin_dashboard.html`: URL vieja `portal_coberturas_semanal` → `control_guardias:index`.
  - `gestion_estudios/config_sanatorio.py`: `guardias: True` en `CONFIG_COLEGIALES`.
  - **Bug fix `services.py`**: `IntegrityError` en `generar_distribucion` — `fechas_asignadas` ahora se pre-carga desde BD con clave `(fecha, tipo_guardia_id)` antes de ejecutar el algoritmo greedy. Respeta el `unique_together (residente, fecha, tipo_guardia)` del modelo.
  - 70 tests — OK. Sin regresiones.

## Pendiente — Optimizaciones (próxima sesión)
- Mejorar UI de templates bajo `control_guardias/portal/`
- UX del flujo borrador → publicar distribución
- Revisar navbar/hamburguesa `base_tailwind.html` (postergado por el usuario)
- Dashboard de equidad (métricas), export Excel, filtros en calendario
