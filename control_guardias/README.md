# Módulo `control_guardias`

Módulo Django para planificar guardias de residentes, publicar el calendario y
resolver ausencias, cambios y excepciones.

## Documentación

- [Guía funcional principal](../docs/producto/CONTROL_GUARDIAS.md)
- [Lógica de distribución](../docs/operativa/CONTROL_GUARDIAS_DISTRIBUCION_MEJORAS.md)
- [Matriz de notificaciones por email](../docs/operativa/CONTROL_GUARDIAS_NOTIFICACIONES_EMAIL.md)
- [Reglas para cambios de código](../.github/instructions/control_guardias.instructions.md)
- [Skill de mantenimiento](../.github/skills/control-guardias/SKILL.md)

## Mapa del código

- `models.py`: tipos, cuotas, asignaciones, ausencias, cambios, notificaciones,
  ajustes, rotaciones y slots vacantes.
- `services.py`: distribución y reglas de negocio. La lógica nueva del dominio
  debe implementarse aquí.
- `views.py`: autorización, coordinación HTTP y construcción de contexto.
- `forms.py`: validación de entradas.
- `urls.py`: rutas públicas del módulo.
- `tests.py`: cobertura de modelos, servicios y vistas.
- `templates/control_guardias/`: interfaz administrativa y portal.

## Reglas críticas

- Los años de residencia válidos son R1, R2, R3 y R4.
- Un residente elegible debe tener rol `medico_residente`, perfil completo y
  usuario activo.
- La combinación residente, fecha y tipo de guardia es única.
- Se deben preservar las restricciones de conflictos y días consecutivos.
- Las mutaciones de distribución, ausencias y cambios deben ser transaccionales
  cuando involucren varias escrituras.
- Los permisos se validan en backend. La gestión corresponde a jefe,
  instructor o superusuario.
- Las fechas del calendario deben construirse como fechas locales, sin
  desplazamientos accidentales por UTC.

Antes de modificar el módulo, leer las
[instrucciones específicas](../.github/instructions/control_guardias.instructions.md).

## Verificación

Desde la raíz del repositorio:

```bash
python manage.py test control_guardias
```

Para cambios acotados puede ejecutarse primero una clase o caso puntual, pero la
suite completa del módulo debe correrse antes de integrar el cambio.
