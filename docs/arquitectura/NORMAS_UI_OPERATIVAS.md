# Normas UI operativas

Guia corta para refactors de pantallas internas del sistema.

Ultima actualizacion: 2026-07-03.

## Principios

1. La pantalla operativa debe responder primero "que hago ahora".
2. Los estados deben explicar disponibilidad, no decorar.
3. Las acciones primarias deben expresar intencion, no solo recurso tecnico.
4. Si dos botones parecen hacer lo mismo, uno debe renombrarse, degradarse o desaparecer.
5. Los filtros deben preservar el contexto de bandeja o modo.
6. Las vistas con reglas de negocio no deben duplicar queries complejas: usar selectors/services.

## Vocabulario recomendado

Usar verbos concretos:

- `Tomar y revisar`: asigna al usuario y abre el editor.
- `Asignarme para despues`: asigna al usuario sin abrir el editor.
- `Tomar para mi`: reasigna un item activo que estaba con otro usuario.
- `Continuar`: vuelve a una tarea ya iniciada.
- `Finalizar`: cierra un flujo activo.
- `Guardar cambios`: persiste sin cambiar de estado.
- `Editar`: reabre algo cerrado o ya existente.
- `Ver comparacion`: abre lectura/contraste, no edicion.

Evitar:

- `Procesar`, `Gestionar`, `Ir`, `Accion`, cuando hay un verbo mas claro.
- Dos acciones primarias en el mismo item.
- Botones con texto largo si la accion puede resolverse con verbo + sustantivo corto.

## Bandejas y tabs

Una bandeja representa una pregunta operativa estable.

Ejemplos:

- `Mis asignados`: trabajo que depende de mi.
- `Sin asignar`: trabajo disponible para tomar.
- `Asignados a otros`: trabajo activo con otro responsable, util para corregir errores de asignacion.
- `Corregidos por mi`: historial editable/consultable propio.
- `Todos`: vista amplia para busqueda o supervision.

Reglas:

- El tab activo debe coincidir con el filtro real del backend.
- Las acciones dentro de una bandeja deben respetar esa pregunta. En `Sin asignar`, la accion primaria no deberia llamarse solo `Revisar`, sino `Tomar y revisar`.
- Al volver desde una accion, preservar la bandeja de origen cuando sea relevante.

## Estados

Los estados deben tener semantica estable:

- `pendiente_revision`: disponible para iniciar revision.
- `en_revision`: tomado o en curso.
- `finalizado`: cerrado, visible en historial, editable solo si la regla de negocio lo permite.

Cuando un estado aparece en una card o fila, el boton debe complementar el estado:

- `pendiente_revision` sin revisor -> `Tomar y revisar`.
- `pendiente_revision` con revisor actual -> `Revisar`.
- `pendiente_revision` o `en_revision` con otro revisor -> `Tomar para mi` con confirmacion.
- `en_revision` con revisor actual -> `Continuar`.
- `finalizado` propio -> `Editar` / `Ver comparacion`.

## Refactor por capas

Orden recomendado:

1. Selectors: centralizar QuerySets y modos de bandeja.
2. Services: mover reglas de transicion/preparacion fuera de views.
3. Views: dejar orquestacion HTTP, mensajes y redirects.
4. Templates: renombrar acciones y, si crece, dividir parciales.
5. Tests: cubrir selectors/services antes de tests completos de UI.

## Criterio de documentacion

Cada modulo operativo importante deberia tener:

- documento funcional en `docs/producto/`;
- documento tecnico/refactor en `docs/arquitectura/` si hay reglas reusable;
- comandos de test recomendados;
- lista corta de decisiones de vocabulario.

Esta guia nacio del refactor del circuito de revision staff de preinformes y se puede reutilizar en liquidacion, guardias, consultorios y otros tableros internos.
