---
applyTo: "control_guardias/**/*.py"
---

# Instrucciones para control_guardias

> Última actualización: 06/04/2026

## Modelos

- **No existe R5**. Los años de residencia son solo R1/R2/R3/R4. No agregar R5 ni en models, ni en templates, ni en tests.
- Al agregar campos a `AsignacionGuardia`, recordar el constraint `unique_residente_fecha_tipo` — cualquier test que cree asignaciones debe respetar esa unicidad.
- `duracion_horas` en `ConfiguracionTipoGuardia` usa `.total_seconds() / 3600`. **No usar `.seconds`** — devuelve 0 para turnos de 24h.
- `CuotaMensualGuardia.guardias_efectivas` es una property calculada. No es un campo de BD.
- Al consultar residentes elegibles para distribución: `rol='medico_residente', perfil_completo=True, is_active=True`.

## Vistas

- Autorización estándar: `JefeInstructorMixin` (jefe/instructor/superuser). Para vistas solo de residentes: `LoginRequiredMixin`.
- Vistas que renderizan el mismo template con dos bases (superuser dark / portal light) usan `get_template_names()` con `if self.request.user.is_superuser`.
- Nueva lógica de negocio de distribución va en `services.py`, no en views.
- `CuotaMensualFormView` usa `get_or_create` con `anio_residencia`. URL es `<str:anio>`, no `<int:pk>`.
- `ConfiguracionView.get_context_data` pasa `cuotas_filas` (lista de dicts `{'anio', 'cuota'}`), **no** `cuotas`. Nunca volver a pasar `cuotas` como queryset plano.

## Servicios (`services.py`)

- `generar_distribucion`: pre-cargar `fechas_asignadas` desde BD **antes** del loop greedy. Sin eso, `bulk_create` falla con IntegrityError en períodos con guardias ya publicadas.
- Para 2 residentes el mismo día: usar 2 `ConfiguracionTipoGuardia` distintos con los mismos días/horario (ej: "Día de semana" + "Día de semana (2)"). El algoritmo los trata como slots independientes.
- `_es_consecutivo` retorna True si dos fechas difieren exactamente 1 día (en cualquier dirección).

## Formularios

- `GenerarDistribucionForm` tiene un `ModelMultipleChoiceField` de tipos activos — el jefe selecciona cuáles incluir por corrida.
- `CuotaMensualGuardiaForm` trabaja sobre `CuotaMensualGuardia`. Siempre se pasa con `instance=obj` después del `get_or_create`.

## Migraciones

- Al agregar campos, siempre `python manage.py makemigrations control_guardias` antes de cualquier otra cosa.
- Nunca modificar migraciones ya aplicadas.
- Estado actual: 7 migraciones aplicadas.

## Tests (`tests.py`)

- Naming: `test_<vista_o_modelo>_<escenario>_<resultado>`
- Para tests de `CuotaMensualFormView`: la URL usa `kwargs={'anio': 'R1'}`, **no** `kwargs={'pk': ...}`.
- Estado actual: 70 tests, todos OK.
- Siempre correr `python manage.py test control_guardias` antes de hacer commit.

## Templates

- Layout estándar: `<div class="max-w-full px-4 sm:px-6 lg:px-10 py-4">`.
- Todos los templates de detalle/form tienen botón "← Volver" que apunta a `control_guardias:index` o a la vista padre.
- Superuser: dark theme (`bg-gray-800`, `text-white`), extiende `base_with_sidebar.html`.
- Portal: light theme (`bg-white`, `text-gray-900`), extiende `base_tailwind.html`.
- **Encoding**: guardar siempre en UTF-8. Si aparecen `Ã³` / `Ã¡` en pantalla, el archivo fue guardado con Latin-1.
