---
name: control-guardias
description: "Skill para desarrollar y rediseñar el módulo control_guardias. Usar cuando: se agreguen modelos o fields a guardias, se creen nuevas vistas, se refactorice lógica de coberturas, se trabajen ausencias o reasignaciones de guardias de residentes, se configure la distribución automática equitativa, se diseñen reglas de guardia, se trabaje el calendario interactivo, se escriban tests del módulo."
---

# Skill: Control de Guardias Médicas

> Última actualización: 06/04/2026

## Estado del módulo

- **Tests**: 70 pasando, 0 errores (`python manage.py test control_guardias`)
- **Migraciones**: 7 aplicadas (todas `[X]`)
- **Branch activa**: `feature/colegiales`

---

## Modelos (`models.py`)

### `ConfiguracionTipoGuardia`
Define los tipos de guardia. Los jefes configuran horarios y días aplicables.

| Campo | Tipo | Notas |
|---|---|---|
| `nombre` | CharField(100) | unique |
| `hora_inicio` / `hora_fin` | TimeField | soporta cruce de medianoche |
| `dias_semana` | CharField(20) | Ej: `"L,M,X,J,V"` — valores: L/M/X/J/V/S/D |
| `aplica_feriados` | BooleanField | Si True, aplica en feriados además de los días configurados |
| `activo` | BooleanField | Solo activos aparecen en el formulario de distribución |
| `creado_por` | FK CustomUser | SET_NULL |

**`duracion_horas` (property)**: usa `total_seconds() / 3600` — soporta turnos que cruzan medianoche.

**Datos reales en producción (Colegiales):**

| Nombre | Días | Horario | Feriados |
|---|---|---|---|
| Día de semana | L,M,X,J,V | 17:00–08:00 | No |
| Día de semana (2) | L,M,X,J,V | 17:00–08:00 | No |
| SADOFE | S,D | 08:00–08:00 (24h) | Sí |
| SADOFE (2) | S,D | 08:00–08:00 (24h) | Sí |

> Los tipos `(2)` permiten asignar 2 residentes el mismo día. El jefe los selecciona al generar distribución cuando la cuota total lo requiere.

---

### `AsignacionGuardia`
Asignación de un turno a un residente.

| Campo | Tipo | Notas |
|---|---|---|
| `residente` | FK CustomUser | PROTECT, limit_choices_to rol=medico_residente |
| `tipo_guardia` | FK ConfiguracionTipoGuardia | PROTECT |
| `fecha` | DateField | |
| `estado` | CharField | BORRADOR / PUBLICADA / CUMPLIDA / AUSENTE / REASIGNADA |
| `es_feriado` | BooleanField | Se marca automáticamente en `save()` |
| `creada_por` | FK CustomUser | SET_NULL |
| `notas` | TextField | blank |

**Constraint**: `UniqueConstraint(fields=['residente', 'fecha', 'tipo_guardia'])` — nombre: `unique_residente_fecha_tipo`

---

### `CuotaMensualGuardia`
Cuota de guardias por año de residencia.

| Campo | Tipo | Notas |
|---|---|---|
| `anio_residencia` | CharField | choices: R1/R2/R3/R4 (R5 **no existe**) |
| `guardias_por_mes` | PositiveIntegerField | base |
| `atenuante_porcentaje` | DecimalField | 0–100%, reduce la cuota base |

**`guardias_efectivas` (property)**: `int(guardias_por_mes * (1 - atenuante/100))`

---

### `Feriado`
Días feriados. `fecha` es unique.

### `AusenciaResidente`
Ausencia reportada por un residente. Tiene `motivo` (ENFERMEDAD/PERSONAL/CONGRESO/OTRO) y `guardias_afectadas` (M2M a `AsignacionGuardia`).

### `SolicitudCambioGuardia`
Solicitud de cambio entre dos residentes. Estados: PENDIENTE / APROBADA / RECHAZADA / CANCELADA. Tiene FK a `jefe` (quien aprueba) y dos FKs a `AsignacionGuardia` (solicitante y receptor).

---

## Vistas (`views.py`)

### Mixin de autorización
```python
class JefeInstructorMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return self.request.user.rol in ['jefe_residentes', 'instructor_residentes'] \
               or self.request.user.is_superuser
```

### Tabla de vistas

| Vista | URL name | Auth | Template |
|---|---|---|---|
| `IndexView` | `index` | Login | `index.html` (super) / `portal/index.html` |
| `ConfiguracionView` | `configuracion` | Jefe | `configuracion.html` (super) / `portal/configuracion.html` |
| `CuotaMensualFormView` | `cuota_editar` | Jefe | `cuota_mensual_form.html` |
| `TipoGuardiaCreateView` | `tipo_guardia_crear` | Jefe | (en configuracion.html) |
| `TipoGuardiaUpdateView` | `tipo_guardia_editar` | Jefe | |
| `TipoGuardiaDeleteView` | `tipo_guardia_eliminar` | Jefe | |
| `FeriadoCreateView` | `feriado_crear` | Jefe | (en configuracion.html) |
| `FeriadoDeleteView` | `feriado_eliminar` | Jefe | |
| `DistribucionView` | `distribucion` | Jefe | `portal/distribucion_form.html` |
| `DistribucionBorradorView` | `distribucion_borrador` | Jefe | `portal/distribucion_borrador.html` |
| `MisGuardiasView` | `mis_guardias` | Login | `mis_guardias.html` (super) / `portal/mis_guardias.html` |
| `AusenciasView` | `ausencias` | Login | `portal/ausencias.html` |
| `ReportarAusenciaView` | `reportar_ausencia` | Login | `portal/reportar_ausencia_form.html` |
| `ResolverAusenciaView` | `resolver_ausencia` | Jefe | `portal/resolver_ausencia_form.html` |
| `CambiosView` | `cambios` | Login | `portal/cambios.html` |
| `SolicitarCambioView` | `solicitar_cambio` | Login | `portal/solicitar_cambio_form.html` |
| `RevisarCambioView` | `revisar_cambio` | Login | `portal/revisar_cambio_form.html` |
| `CalendarioView` | `calendario` | Login | `portal/calendario.html` |
| `GuardiasApiView` | `guardias_api` | Login | JSON |
| `NotificacionesView` | `notificaciones` | Login | `portal/notificaciones.html` |

### `CuotaMensualFormView` (TemplateView, get_or_create)
- URL: `configuracion/cuotas/<str:anio>/editar/` — anio en ['R1','R2','R3','R4']
- Si la cuota no existe, la crea con defaults (`guardias_por_mes=4`, `atenuante_porcentaje=0`)
- Contexto: `object`, `is_new` (bool), `form`
- Template muestra "Configurar cuota" si `is_new`, "Editar cuota" si no

### `ConfiguracionView` (TemplateView)
Pasa al contexto:
```python
context['tipos_guardia']   # ConfiguracionTipoGuardia.objects.select_related(...)
context['cuotas_filas']    # lista de {'anio': 'R1', 'cuota': obj_or_None} para R1-R4
context['feriados']        # Feriado.objects.order_by('fecha')
context['feriado_form']    # FeriadoForm()
```
> **Nota**: La tabla de cuotas siempre muestra las 4 filas (R1-R4) aunque alguna no tenga cuota configurada. Años sin cuota muestran "—" y botón "+".

---

## Servicio de distribución (`services.py`)

### `generar_distribucion(mes, anio, tipos_guardia, creado_por, reemplazar_borradores=False)`

**Algoritmo greedy equitativo (7 pasos):**
1. Validaciones (mes válido, tipos activos, residentes con perfil completo)
2. Cuotas por `anio_residencia` desde `CuotaMensualGuardia`
3. Feriados del período
4. Construir slots: `(fecha, tipo_guardia, es_feriado)` — 1 slot = 1 posible asignación
5. Contadores históricos de feriados por residente
6. Eliminar borradores previos si `reemplazar_borradores=True`
7. Loop greedy: para cada slot, elegir residente con menor carga; empate → `random.choice`

**Restricciones por candidato:**
- `cuota_disponible[r.pk] > 0`
- `(fecha, tipo.pk) not in fechas_asignadas[r.pk]` (pre-cargado desde BD)
- `not _es_consecutivo(fecha, ultima_fecha_asignada[r.pk])` — no dos días seguidos

**Para cobertura doble el mismo día**: configurar 2 tipos con los mismos días/horario (ej: "Día de semana" + "Día de semana (2)"). El jefe los selecciona en el formulario de distribución según la cuota total del mes.

**Retorna** dict con: `asignaciones_creadas`, `slots_sin_cubrir`, `metricas`, `advertencias`

---

## Templates

### Estructura y convenciones

- **Superuser** (`templates/control_guardias/*.html`): extienden `base_with_sidebar.html`, dark theme (grays oscuros, texto blanco)
- **Portal** (`templates/control_guardias/portal/*.html`): extienden `base_tailwind.html`, light theme

### Layout estándar del módulo
```html
<!-- Contenedor principal -->
<div class="max-w-full px-4 sm:px-6 lg:px-10 py-4">

    <!-- Encabezado con botón volver -->
    <div class="flex items-center justify-between mb-6">
        <div>
            <h1 class="text-2xl font-bold text-gray-900">Título</h1>
            <p class="text-gray-500 mt-1 text-sm">Subtítulo</p>
        </div>
        <a href="{% url 'control_guardias:...' %}"
           class="inline-flex items-center px-4 py-2 text-sm text-gray-600 hover:text-gray-900 border border-gray-300 rounded-lg hover:border-gray-400 bg-white transition-colors shadow-sm">
            <i class="fas fa-arrow-left mr-2"></i> Volver
        </a>
    </div>
```

### Navegación de vuelta atrás
Todos los templates tienen botón "← Volver" apuntando a `control_guardias:index` o a la vista padre correspondiente.

---

## Integración con `CustomUser`

```python
# Residentes elegibles para distribución:
CustomUser.objects.filter(rol='medico_residente', perfil_completo=True, is_active=True)

# Año de residencia (R1-R4, calculado por fecha_ingreso_residencia):
user.anio_residencia        # 'R1' | 'R2' | 'R3' | 'R4'
user.actualizar_anio_residencia()  # recalcula y guarda

# Gestores (acceso a vistas con JefeInstructorMixin):
user.rol in ['jefe_residentes', 'instructor_residentes'] or user.is_superuser
```

**Cálculo de año de residencia (`accounts/models.py`):**
- < 12 meses → R1
- 12–23 meses → R2
- 24–35 meses → R3
- ≥ 36 meses → R4

> R5 **no existe** en este sistema. Fue eliminado. No agregarlo.

---

## URLs (completo)

| url name | path completo |
|---|---|
| `control_guardias:index` | `/control_guardias/` |
| `control_guardias:configuracion` | `/control_guardias/configuracion/` |
| `control_guardias:cuota_editar` | `/control_guardias/configuracion/cuotas/<str:anio>/editar/` |
| `control_guardias:tipo_guardia_crear` | `/control_guardias/configuracion/tipos/nuevo/` |
| `control_guardias:tipo_guardia_editar` | `/control_guardias/configuracion/tipos/<pk>/` |
| `control_guardias:tipo_guardia_eliminar` | `/control_guardias/configuracion/tipos/<pk>/eliminar/` |
| `control_guardias:feriado_crear` | `/control_guardias/configuracion/feriados/nuevo/` |
| `control_guardias:feriado_eliminar` | `/control_guardias/configuracion/feriados/<pk>/eliminar/` |
| `control_guardias:distribucion` | `/control_guardias/configuracion/distribucion/` |
| `control_guardias:distribucion_borrador` | (ver urls.py) |
| `control_guardias:mis_guardias` | `/control_guardias/mis-guardias/` |
| `control_guardias:ausencias` | `/control_guardias/ausencias/` |
| `control_guardias:reportar_ausencia` | `/control_guardias/ausencias/reportar/` |
| `control_guardias:resolver_ausencia` | `/control_guardias/ausencias/<pk>/resolver/` |
| `control_guardias:cambios` | `/control_guardias/cambios/` |
| `control_guardias:solicitar_cambio` | `/control_guardias/cambios/solicitar/<pk>/` |
| `control_guardias:revisar_cambio` | `/control_guardias/cambios/<pk>/revisar/` |
| `control_guardias:calendario` | `/control_guardias/calendario/` |
| `control_guardias:guardias_api` | `/control_guardias/api/guardias/` |
| `control_guardias:notificaciones` | `/control_guardias/notificaciones/` |

---

## Problemas resueltos (historial)

### `duracion_horas = 0` para guardias de 24h (resuelto 06/04/2026)
`(fin - inicio).seconds` → `(fin - inicio).total_seconds()`. `.seconds` solo devuelve la fracción de segundos dentro del día, `.total_seconds()` incluye días completos.

### `IntegrityError` en `generar_distribucion` (resuelto 05/04/2026)
El set `fechas_asignadas` se inicializaba vacío sin pre-cargar desde BD. Fix en paso 7 de `services.py`: pre-cargar guardias existentes del período antes del loop.

### `CuotaMensualUpdateView` daba 404 si la cuota no existía (resuelto 06/04/2026)
Reemplazado con `CuotaMensualFormView` (TemplateView + `get_or_create`). URL cambió de `<int:pk>` a `<str:anio>`.

### Sidebar de borradores mostraba "4/2026" en vez de "Abril 2026" (resuelto 06/04/2026)
Agregado `min_fecha=Min('fecha')` al queryset de borradores. Template usa `{{ b.min_fecha|date:"F Y"|capfirst }}`. Requiere `LANGUAGE_CODE = 'es-ar'` en settings.

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
