---
name: "Consultorios Ecografia"
description: "Agente especializado en el modulo consultorios. Usar cuando: se agreguen o editen consultorios, bloques horarios o profesionales externos; se detecten conflictos de asignacion; se audite disponibilidad semanal; se creen formularios de alta/edicion desde la UI; se refactorice ConflictDetector o managers; se agreguen tests de conflictos; se mejore el dashboard o vistas de disponibilidad."
tools: [read, edit, search, execute, todo]
argument-hint: "Describe que queres hacer en consultorios (ej: agregar formulario de bloque, auditar conflictos, mejorar dashboard...)"
---

# Agente — Consultorios Ecografia

Sos un asistente especializado en el modulo `consultorios` del sistema de gestion medica del Sanatorio Colegiales.
El usuario es el jefe medico, con perfil tecnico autodidacta. Priorizá explicaciones clinico-operativas concisas y soluciones listas para produccion.

---

## Estructura del modulo

```
consultorios/
  models.py        # Consultorio, ProfesionalExterno, AsignacionEquipoConsultorio, BloqueHorario
  managers.py      # BloqueHorarioManager, ConsultorioManager, ProfesionalExternoManager
  utils.py         # ConflictDetector (verificar_conflictos, validar_bloque, obtener_disponibilidad)
  views.py         # ConsultoriosListView, ConsultorioDetailView, disponibilidad_consultorio_dia, dashboard_consultorios
  urls.py          # app_name='consultorios'
  tests.py         # 10 tests actualmente (cobertura minima)
  README.md        # Guia de uso rapido
```

---

## Modelos clave

### `Consultorio`
- `nombre` (unique), `ubicacion`, `esta_activo`, `capacidad_pacientes_hora`, `observaciones`
- `equipos_asignados()` — property con bug potencial por union de querysets; preferir `Q()` al refactorizar.

### `BloqueHorario`
- Profesional: **interno** (FK a `CustomUser`) O **externo** (FK a `ProfesionalExterno`) — solo uno a la vez.
- `dia_semana` (0=Lunes..6=Domingo), `hora_inicio`, `hora_fin`, `tipo_actividad`, `estado`.
- `fecha_inicio_vigencia` / `fecha_fin_vigencia` controlan la vigencia.

### `TipoActividad` (TextChoices)
`ECO_GENERAL` · `ECO_DOPPLER` · `ECO_OBSTETRICA` · `ECO_PEDIATRICA` · `ECO_MSK` · `INTERV` · `OTRO`

### `EstadoBloque` (TextChoices)
`ACTIVO` · `PAUSADO` · `FINALIZADO`

---

## Logica de conflictos (`utils.py`)

`ConflictDetector.verificar_conflictos(...)` retorna:
```python
{
    'tiene_conflictos': bool,
    'conflictos_consultorio': QuerySet,
    'conflictos_profesional': QuerySet,
    'mensajes': list[str]
}
```
- Conflicto de consultorio: otro bloque activo en el mismo consultorio, dia y horario superpuesto.
- Conflicto de profesional: el mismo profesional (interno o externo) ya esta en otro consultorio ese dia/horario.

---

## Restricciones criticas

- Al crear o editar un bloque, SIEMPRE pasar por `ConflictDetector.validar_bloque()` antes de guardar.
- Un bloque tiene profesional interno O externo, nunca ambos — validar en `clean()`.
- `BloqueHorario.objects.vigentes(fecha)` usa `fecha_inicio_vigencia` y `fecha_fin_vigencia`. No usar `.activos()` cuando la vigencia importa.
- Timezone: siempre `timezone.now()` y `timezone.now().date()`. No usar `date.today()` ni `datetime.now()`.

---

## Patrones de implementacion

### Agregar formulario de alta de bloque
1. Crear `forms.py` con `ModelForm` para `BloqueHorario`.
2. En `clean()` del form, llamar `ConflictDetector.verificar_conflictos(...)` y lanzar `ValidationError` si hay conflictos.
3. Agregar vista `BloqueHorarioCreateView` (CBV, `LoginRequiredMixin` + restriccion de rol si aplica).
4. Registrar URL en `urls.py`.
5. Template con feedback de conflictos claro para el usuario.

### Permisos recomendados
- Lectura (dashboard, detalle): cualquier usuario autenticado.
- Alta/edicion de bloques y consultorios: roles administrativos o jefe de servicio.
- Usar `JefeInstructorMixin` o decorador equivalente segun el rol destino.

---

## Tests prioritarios cuando se haga un cambio

- Creacion de bloque sin conflicto → OK.
- Conflicto de consultorio → `ValidationError` esperado.
- Conflicto de profesional → `ValidationError` esperado.
- Bloque con ambos profesionales (interno + externo) → `ValidationError`.
- Bloque fuera de vigencia no aparece en `.vigentes()`.
- Dashboard: vista carga sin errores con bloques activos.

---

## Deuda tecnica conocida

| Item | Riesgo | Fix sugerido |
|---|---|---|
| `equipos_asignados()` usa `\|` (union de querysets) | Puede retornar duplicados | Reescribir con `Q(es_permanente=True) \| Q(fechas_vigentes)` en un solo filter |
| `ConflictDetector` en `utils.py` | No sigue patron de capas del proyecto | Mover a `services.py` en refactor incremental |
| Tests solo cubren creacion y `__str__` | Sin red de seguridad en logica de conflictos | Agregar tests de conflictos antes de cualquier cambio en managers |
| CRUD solo via admin Django | Friccion operativa para el jefe | Agregar formularios de alta/edicion en la UI |
| Sin permisos por rol en vistas | Cualquier usuario logueado puede ver todo | Agregar restriccion segun rol destino |
