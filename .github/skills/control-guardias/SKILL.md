---
name: control-guardias
description: "Skill para cambios en control_guardias: distribucion automatica, cuotas R1-R4, tipos de guardia, ausencias, cambios, calendario FullCalendar, permisos de jefe/instructor/residente y tests del modulo. Usar antes de tocar modelos, services, views, templates o API JSON de guardias."
---

# Skill: Control de Guardias

Modulo Django para planificar guardias medicas de residentes, resolver ausencias/cambios y visualizar calendario operativo.

## Primero leer

- Reglas duras del modulo: `.github/instructions/control_guardias.instructions.md`.
- Si el pedido es de rediseno funcional amplio: `.github/skills/control-guardias/references/rediseno.md`.
- Fuente de verdad de logica: `control_guardias/services.py`.
- Modelos: `control_guardias/models.py`.
- Vistas/API: `control_guardias/views.py`.
- Tests: `control_guardias/tests.py`.

## Reglas actuales no negociables

- No existe R5. Usar solo R1/R2/R3/R4.
- Residentes elegibles: `rol='medico_residente'`, `perfil_completo=True`, `is_active=True`.
- Para dos residentes el mismo dia, usar dos `ConfiguracionTipoGuardia` activos con mismos dias/horarios; no duplicar una asignacion igual.
- `AsignacionGuardia` respeta `unique_residente_fecha_tipo`.
- `ConfiguracionTipoGuardia.duracion_horas` debe usar `total_seconds() / 3600`; no usar `.seconds`.
- Nueva logica de distribucion, ausencias o cambios va en `services.py`, no en templates ni views gordas.
- Permisos de gestion: `jefe_residentes`, `instructor_residentes` o `superuser` mediante `JefeInstructorMixin` o equivalente.
- APIs y vistas deben validar permisos en backend.

## Servicios criticos

### `generar_distribucion(...)`

Antes de modificarlo, preservar estas invariantes:

- Validar mes, tipos activos y residentes elegibles.
- Cargar cuotas desde `CuotaMensualGuardia`.
- Pre-cargar asignaciones existentes del periodo antes del loop greedy.
- Evitar dos guardias del mismo residente el mismo dia.
- Evitar dias consecutivos.
- Respetar diversidad de anio cuando `restricciones_anio=True`.
- Persistir dentro de `transaction.atomic()`.
- Retornar metricas, advertencias y slots sin cubrir.

### Ausencias y cambios

- `sugerir_reemplazo(guardia)` debe excluir al ausente, conflictos del mismo dia y dias consecutivos.
- `resolver_ausencia(...)` debe cerrar la ausencia y dejar trazabilidad de reasignacion o ausencia.
- Los cambios entre residentes deben preservar estados y aprobaciones existentes.

## Calendario FullCalendar

- API actual: `control_guardias:guardias_api`.
- Residentes ven sus guardias publicadas.
- Jefes/superuser pueden ver publicadas y borradores, con filtros si existen.
- No usar `toISOString()` ni `getUTCDay()` para fechas locales en UTC-3.
- Construir fecha local con `getFullYear()`, `getMonth()+1`, `getDate()`.
- Para feriados en template, usar `{{ feriados_json|safe }}`.
- Colores de eventos: mantener paleta estable por residente si ya existe en `views.py`.

## Templates y navegacion

- Superuser: `base_with_sidebar.html`.
- Portal: `base_tailwind.html`.
- Contenedor operativo: `<div class="max-w-full px-4 sm:px-6 lg:px-10 py-4">`.
- Para navbar, editar `accounts/context_processors.py`, no `includes/_nav.html`.
- URLs validas principales:
  - `control_guardias:index`
  - `control_guardias:calendario`
  - `control_guardias:mis_guardias`
  - `control_guardias:distribucion`
  - `control_guardias:ausencias`
  - `control_guardias:cambios`
  - `control_guardias:configuracion`
  - `control_guardias:notificaciones`
  - `control_guardias:guardias_api`

## Tests recomendados

Para cambios de codigo del modulo:

```bash
python manage.py test control_guardias --verbosity=1
python manage.py makemigrations --check --dry-run
```

Si el cambio es focal y la suite larga no es necesaria, ejecutar tests de clase/metodo afectado y explicitar el riesgo residual.

## Senales de riesgo

Tratar como cambio de mayor cuidado si:

- toca `generar_distribucion`;
- cambia cuotas o anio de residencia;
- cambia permisos de jefe/instructor/residente;
- modifica API JSON del calendario;
- altera estados de ausencias/cambios;
- toca migraciones o constraints.

## Salida esperada

Al terminar, informar:

- archivos tocados;
- regla operativa preservada;
- tests/comandos ejecutados;
- riesgos remanentes;
- si no se tocaron modelos, migraciones o permisos, decirlo explicitamente cuando sea relevante.
