---
applyTo: "control_guardias/**/*.py"
---

# Instrucciones para control_guardias

## Modelos
- Al consultar `Guardia`, siempre usar `select_related('medico__user')` para evitar N+1.
- `cubierta_real = bool(g.cubierta and g.medico and g.medico.user)` — el campo `cubierta` solo es confiable si el médico tiene usuario asociado.
- La lógica de horas por franja debería vivir en el modelo como propiedad, no en las vistas.

## Vistas
- Las URLs `/portal/` son públicas intencionalmente.
- `TailwindCalendarView` solo accesible para `is_superuser`.
- Nueva lógica de negocio va en `services.py`, no en las views directamente.

## Formularios
- Usar `label_from_instance` para mostrar nombre completo del médico en selects.
- El campo `cubierta` no se expone en `GuardiaForm` — se maneja por lógica.

## Migraciones
- Al agregar campos al modelo, siempre crear migración explícita antes de cualquier otra cosa.
- Nunca modificar migraciones existentes.

## Testing (pytest-django)
- Naming: `test_<modelo_o_vista>_<escenario>_<resultado>` 
- Siempre crear usuario con `cargo='médico'` para tests de guardias.
- Usar `Client()` para tests de views, verificar status code + contexto.
