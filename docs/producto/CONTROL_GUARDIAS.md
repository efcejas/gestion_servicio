# Control de Guardias

Fuente funcional principal del módulo Django `control_guardias`.

## Objetivo y alcance

El módulo organiza las guardias médicas de residentes. Permite configurar los
turnos, generar y publicar la distribución mensual, consultar el calendario,
gestionar ausencias y cambios, y mantener la trazabilidad de las excepciones.

No debe confundirse con las guardias pasivas de `liquidacion`, que pertenecen al
circuito de honorarios.

## Roles

| Rol | Capacidades principales |
| --- | --- |
| Residente | Consultar guardias publicadas, calendario y notificaciones; reportar o cancelar ausencias; solicitar cambios o un slot vacante. |
| Jefe de residentes | Configurar el módulo, generar y publicar distribuciones, resolver ausencias, revisar cambios y excepciones. |
| Instructor de residentes | Tiene las mismas capacidades operativas de gestión que el jefe. |
| Superusuario | Acceso de gestión y visualización administrativa. |

Las operaciones de gestión se protegen en backend mediante
`JefeInstructorMixin`. Las acciones exclusivas de residentes usan
`ResidenteMixin` o validaciones equivalentes. Los permisos no deben depender
solo de que una acción esté oculta en la interfaz.

## Configuración

Antes de distribuir guardias, un gestor configura:

- Tipos de guardia: nombre, días de semana, horario, aplicación en feriados y
  estado activo.
- Cuotas mensuales para R1, R2, R3 y R4. No existe R5 en este módulo.
- Feriados, que se marcan automáticamente en las asignaciones.
- Penalizaciones o ajustes que agregan guardias a la cuota de un residente.
- Rotaciones externas, utilizadas por la distribución para contemplar
  disponibilidad reducida.

Para representar dos puestos el mismo día se crean dos tipos activos con los
mismos días y horarios. No se duplica una asignación idéntica.

## Distribución mensual

El flujo operativo es:

1. Un jefe o instructor selecciona mes, año y tipos de guardia activos.
2. El servicio construye los slots del período.
3. Se consideran residentes activos con rol `medico_residente` y perfil
   completo.
4. Se aplican cuotas, ajustes, feriados, rotaciones y restricciones de
   compatibilidad.
5. Se genera un borrador con métricas, advertencias y slots sin cubrir.
6. El gestor revisa el resultado y lo publica o cancela.
7. Al publicar, las asignaciones quedan disponibles para residentes y se
   generan las notificaciones correspondientes.

Entre las restricciones centrales se encuentran evitar una asignación duplicada
del mismo residente, fecha y tipo, y evitar guardias en días consecutivos. La
implementación vigente está en
[`control_guardias/services.py`](../../control_guardias/services.py).

La explicación específica de mejoras del algoritmo se conserva en
[Control de Guardias - Distribución](../operativa/CONTROL_GUARDIAS_DISTRIBUCION_MEJORAS.md).

## Calendario y consulta personal

- `Calendario` presenta las asignaciones visibles para el usuario.
- `Mis guardias` lista las guardias publicadas del residente.
- La API JSON `guardias_api` alimenta el calendario.
- Jefes, instructores y superusuarios pueden acceder a información operativa
  adicional según los filtros disponibles.

Las fechas del calendario se manejan como fechas locales. No deben convertirse
mediante UTC de una forma que cambie el día en la zona horaria local.

## Ausencias

Un residente puede reportar un período de ausencia, indicar el motivo y adjuntar
documentación respaldatoria. El sistema relaciona las guardias afectadas.

El jefe o instructor revisa el caso y puede resolverlo con las reasignaciones
correspondientes. La sugerencia de reemplazos excluye conflictos del mismo día,
días consecutivos y al residente ausente. La resolución conserva trazabilidad y
genera notificaciones.

Una ausencia pendiente puede cancelarse por su autor dentro de las reglas del
servicio.

## Cambios entre residentes

El cambio bilateral sigue este circuito:

1. El residente solicitante propone intercambiar una guardia con otro
   residente.
2. El receptor acepta o rechaza la propuesta.
3. Si acepta, un jefe o instructor aprueba o rechaza el cambio.
4. Al aprobarse se actualizan las asignaciones y se conserva la trazabilidad.

El solicitante puede cancelar una solicitud mientras su estado lo permita.

## Slots vacantes

Un residente también puede solicitar mover una guardia a un slot libre del mismo
mes sin una contraparte. El jefe o instructor revisa la solicitud. Al aprobarse,
la guardia original queda reasignada y se crea la nueva asignación publicada,
sin aumentar la cuota del residente.

Solo puede existir una solicitud pendiente por guardia de origen y por slot de
destino.

## Excepciones y ajustes de cuota

Un gestor puede eliminar una guardia por excepción. Opcionalmente, el sistema
crea un ajuste `CARRYOVER` para trasladar esa obligación al mes siguiente.

Los ajustes `PENALIZACION` agregan guardias a la cuota del período indicado.
Ambos mecanismos mantienen el usuario creador, el motivo y, cuando corresponde,
la guardia de origen.

## Notificaciones

El módulo tiene una bandeja interna y puede enviar correo para asignaciones,
publicaciones, cambios, ausencias y reasignaciones. El envío requiere un usuario
activo, correo cargado y la preferencia de notificaciones habilitada.

La matriz detallada de eventos y destinatarios se mantiene en
[Control de Guardias - Notificaciones por email](../operativa/CONTROL_GUARDIAS_NOTIFICACIONES_EMAIL.md).

## Estados principales

- Asignación: `BORRADOR`, `PUBLICADA`, `CUMPLIDA`, `AUSENTE` o `REASIGNADA`.
- Ausencia: `PENDIENTE` o `RESUELTA`.
- Cambio: pendiente del receptor, pendiente del jefe, aprobado, rechazado o
  cancelado.
- Slot vacante: `PENDIENTE`, `APROBADA`, `RECHAZADA` o `CANCELADA`.

## Pantallas y rutas principales

| Pantalla | Ruta |
| --- | --- |
| Inicio | `/control_guardias/` |
| Calendario | `/control_guardias/calendario/` |
| Mis guardias | `/control_guardias/mis-guardias/` |
| Notificaciones | `/control_guardias/notificaciones/` |
| Configuración | `/control_guardias/configuracion/` |
| Distribución | `/control_guardias/configuracion/distribucion/` |
| Ausencias | `/control_guardias/ausencias/` |
| Cambios | `/control_guardias/cambios/` |
| Solicitudes de slots vacantes | `/control_guardias/slot-vacante/solicitudes/` |

La lista completa y vigente está en
[`control_guardias/urls.py`](../../control_guardias/urls.py).

## Fuentes técnicas

- [README técnico del módulo](../../control_guardias/README.md)
- [Modelos](../../control_guardias/models.py)
- [Servicios](../../control_guardias/services.py)
- [Vistas](../../control_guardias/views.py)
- [Formularios](../../control_guardias/forms.py)
- [URLs](../../control_guardias/urls.py)
- [Tests](../../control_guardias/tests.py)

## Mantenimiento documental

Este archivo es la fuente funcional principal. Las reglas implementadas se
validan contra modelos, servicios y tests. Los documentos de `docs/operativa/`
profundizan circuitos específicos y `docs/archive/` contiene material histórico
que no debe tratarse como comportamiento vigente.

Última revisión: julio de 2026.
