---
name: control-guardias
description: "Skill para desarrollar y rediseñar el módulo control_guardias. Usar cuando: se agreguen modelos o fields a guardias, se creen nuevas vistas, se refactorice lógica de coberturas, se trabajen ausencias o reasignaciones de guardias de residentes, se configure la distribución automática equitativa, se diseñen reglas de guardia, se trabaje el calendario interactivo, se escriban tests del módulo."
---

# Skill: Control de Guardias Médicas

## Estado actual del módulo

### Modelos (`models.py`)
- **`MedicoGuardia`**: Tabla puente entre `CustomUser` y el sistema de guardias. Tiene `dni`, `matricula`, y FK a `CustomUser`. Es redundante: solo existe para aislar la lógica de guardias del modelo de usuario general.
- **`Guardia`**: Fecha + franja horaria + `cubierta (bool)` + FK a `MedicoGuardia`.

**Franjas horarias disponibles:**
```
NOCHE            → 20:00 - 08:00 (lunes a viernes) = 12hs
DIA_COMPLETO     → 24 horas (sábados, domingos, feriados)
DIA              → 08:00 - 20:00 (lunes a viernes) = 12hs
NOCHE_FIN_SEMANA → 20:00 - 08:00 (sábados, domingos, feriados) = 12hs
DIA_FIN_SEMANA   → 08:00 - 20:00 (sábados, domingos, feriados) = 12hs
```

### Vistas (`views.py`)
| Vista | URL | Auth | Descripción |
|-------|-----|------|-------------|
| `GuardiasIndexView` | `/` | Login | Dispatcher: superuser → `index.html` (sidebar), otros → `portal/index.html` (navbar) |
| `CalendarioView` | `/calendario/` | Login | Calendario FullCalendar |
| `GuardiasApiView` | `/api/guardias/` | Login | JSON para FullCalendar (segmentado por rol) |
| `DistribucionView` | `/distribucion/` | Jefe/Instructor/Superuser | Genera distribución automática |
| `DistribucionBorradorView` | `/distribucion/borrador/` | Jefe/Instructor/Superuser | Revisa y publica borrador |
| `MisGuardiasView` | `/mis-guardias/` | Login | Vista personal de guardias del residente |
| `AusenciasView` | `/ausencias/` | Login | Lista/reporta ausencias |
| `ReportarAusenciaView` | `/ausencias/reportar/` | Login | Formulario de ausencia |
| `ResolverAusenciaView` | `/ausencias/<id>/resolver/` | Jefe/Instructor | Acepta o rechaza ausencia |
| `CambiosView` | `/cambios/` | Login | Lista de solicitudes de cambio |
| `SolicitarCambioView` | `/cambios/solicitar/<guardia_id>/` | Residente | Crea solicitud |
| `RevisarCambioView` | `/cambios/<id>/revisar/` | Login | Acepta/rechaza como receptor o jefe |
| `ConfiguracionView` | `/configuracion/` | Jefe/Instructor/Superuser | Tipos de guardia, cuotas, feriados |
| `TipoGuardiaCreateView` | `/configuracion/tipos/nuevo/` | Jefe/Instructor/Superuser | Crear tipo |
| `TipoGuardiaUpdateView` | `/configuracion/tipos/<id>/` | Jefe/Instructor/Superuser | Editar tipo |
| `TipoGuardiaDeleteView` | `/configuracion/tipos/<id>/eliminar/` | Superuser | Borrar tipo |
| `CuotaMensualFormView` | `/configuracion/cuotas/` | Jefe/Instructor/Superuser | Definir cuotas por año de residencia |
| `NotificacionesView` | `/notificaciones/` | Login | Notificaciones del usuario |

### Templates

- `templates/control_guardias/index.html` — vista superuser (extiende `base_with_sidebar.html`, dark)
- `templates/control_guardias/portal/index.html` — vista residentes/jefes (extiende `base_tailwind.html`, light)
- Todos los demás templates bajo `portal/` extienden `base_tailwind.html`
- Los templates bajo la raíz `control_guardias/` extienden `base_with_sidebar.html` (solo superuser)

## Navegación

- **Superuser**: sidebar (`includes/sidebar.html`) — link "Control Guardias" + sub-nav expandido cuando `app_name == 'control_guardias'`
- **Jefe/Instructor/Residente**: navbar `base_tailwind.html` — link "Guardias" con ícono `fa-shield-alt` (agregado 05/04/2026)

## Formularios (`forms.py`)
- `GuardiaForm`: Crear/editar guardia (franja, médico, fecha)
- `FiltroGuardiasPorMedicoForm`: Filtro por médico/mes/año (para admin)
- `FiltroMisGuardiasForm`: Filtro mes/año (para médico personal)

---

## Problemas conocidos / deuda técnica

1. **Bug potencial**: `cubierta=True` sin `medico` asignado es un estado inconsistente. En `GuardiaEventsView` se corrige con `cubierta_real`, pero no hay validación en el modelo.
2. **Lógica de horas hardcodeada en views**: El dict `franja_horaria_horas` en `ResumenGuardiasView` debería ser un método del modelo.
3. **Sin `services.py`**: Toda la lógica de negocio está en las views.
4. **Sin integración con liquidación**: Las horas de guardia no se exportan a `liquidacion/`.
5. **`GuardiaEventsView` sin auth**: La API JSON de FullCalendar no requiere autenticación.
6. **`MedicoGuardia` redundante**: El DNI y matrícula podrían estar directamente en `CustomUser` o en una extensión de perfil.

---

## Convenciones del módulo

- Siempre usar `select_related('medico__user')` al consultar `Guardia`.
- `cubierta_real = bool(g.cubierta and g.medico and g.medico.user)` — no confiar solo en el campo `cubierta`.
- Las vistas de portal (`/portal/`) son públicas intencionalmente para que el personal vea coberturas sin login.
- El calendario FullCalendar usa la API `GuardiaEventsView` en `/api/guardias/`.

---

## Navegación

- **Superuser**: sidebar (`includes/sidebar.html`) — link "Control Guardias" → `control_guardias:index` + sub-nav expandido cuando `app_name == 'control_guardias'` (Calendario, Distribución, Ausencias, Cambios, Configuración, Notificaciones)
- **Jefe/Instructor/Residente**: navbar `base_tailwind.html` — link "Guardias" con ícono `fa-shield-alt` en la rama `{% if user.es_medico %}`
- **Módulo activo en Colegiales**: `guardias: True` en `gestion_estudios/config_sanatorio.py` > `CONFIG_COLEGIALES`

## Problemas conocidos resueltos

### IntegrityError en `generar_distribucion` (resuelto 05/04/2026)
**Causa**: `fechas_asignadas` se inicializaba vacío — el algoritmo greedy no consultaba la BD, por lo que no detectaba guardias ya publicadas en el mismo período. Al hacer `bulk_create`, violaba el `unique_together (residente, fecha, tipo_guardia)`.

**Fix** (`services.py`, paso 7): Pre-cargar desde la BD con clave `(fecha, tipo_guardia_id)`:
```python
fechas_asignadas = defaultdict(set)
for asig in AsignacionGuardia.objects.filter(
    fecha__gte=primer_dia, fecha__lte=ultimo_dia,
).values('residente_id', 'fecha', 'tipo_guardia_id'):
    fechas_asignadas[asig['residente_id']].add((asig['fecha'], asig['tipo_guardia_id']))
```
El chequeo en el loop usa `(fecha, tipo.pk) not in fechas_asignadas[r.pk]`.

---

## URLs del módulo (válidas)

Siempre usar estas URLs — las antiguas (`portal_coberturas_semanal`, `calendario_guardias_full_tw`, `resumen_guardias_portal`) ya NO existen:

| url name | path |
|---|---|
| `control_guardias:index` | `/control_guardias/` |
| `control_guardias:calendario` | `/control_guardias/calendario/` |
| `control_guardias:mis_guardias` | `/control_guardias/mis-guardias/` |
| `control_guardias:distribucion` | `/control_guardias/configuracion/distribucion/` |
| `control_guardias:ausencias` | `/control_guardias/ausencias/` |
| `control_guardias:cambios` | `/control_guardias/cambios/` |
| `control_guardias:configuracion` | `/control_guardias/configuracion/` |
| `control_guardias:notificaciones` | `/control_guardias/notificaciones/` |
| `control_guardias:guardias_api` | `/control_guardias/api/guardias/` |

## Integración con CustomUser

El modelo de usuarios ya tiene todo lo necesario. **No se requiere campo nuevo.**

```python
# Residentes elegibles para guardias:
CustomUser.objects.filter(rol='medico_residente', perfil_completo=True)

# El año de residencia está en:
user.anio_residencia  # 'R1', 'R2', 'R3', 'R4', 'R5' — calculado automáticamente

# Gestores (pueden asignar y validar):
user.rol in ['jefe_residentes', 'instructor_residentes']

# MedicoGuardia (modelo viejo) → OBSOLETO
# Reemplazado por FK directa a CustomUser en AsignacionGuardia
```

El cálculo de año se actualiza via `user.actualizar_anio_residencia()` — conviene llamarlo antes de generar una distribución automática para garantizar que todos los residentes estén en el año correcto.


1. Agregar field en `models.py`
2. Crear y aplicar migración: `python manage.py makemigrations control_guardias`
3. Actualizar `GuardiaForm` si el campo es editable por el usuario
4. Actualizar `GuardiaAdmin` si necesita verse en el panel
5. Actualizar `GuardiaEventsView` si afecta al calendario (extendedProps)
6. Escribir test en `tests.py`

### Agregar integración con liquidación
Ver [referencia de integración](./references/integracion_liquidacion.md)

### Agregar notificaciones de guardias no cubiertas
1. Crear señal en `signals.py` que dispare cuando `cubierta=False` y la fecha es próxima
2. Integrar con el sistema de emails del proyecto
3. Considerar una tarea periódica (cron/celery) para alertas preventivas

---

## Tests

Ubicación: `control_guardias/tests.py`

Cobertura actual (70 tests, todos OK):
- Modelos: `AsignacionGuardia`, `TipoGuardia`, `ConfiguracionGuardias`, `CuotaMensual`
- `services.py`: distribución automática, ausencias, cambios de guardia
- Flujo completo de `SolicitudCambioGuardia` (PENDIENTE_RECEPTOR → PENDIENTE_JEFE → APROBADA/RECHAZADA)
- `AusenciaResidente`: reportar e resolver
- `GuardiasApiView`: segmentación por rol

---

## Archivos de referencia

- [Rediseño funcional planificado](./references/rediseno.md)

## URLs rotas conocidas (templates legacy)

Si aparece `NoReverseMatch` con alguna de estas, reemplazar por la URL válida de la tabla anterior:
- `portal_coberturas_semanal` → `control_guardias:index`
- `calendario_guardias_full_tw` → `control_guardias:calendario`
- `resumen_guardias_portal` → `control_guardias:index`
- `coberturas_semanal` → `control_guardias:calendario`
