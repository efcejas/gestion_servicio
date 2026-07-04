# Preinformes - Circuito de revision staff

Documento vigente para entender el flujo de usuarios revisores de preinformes.

Ultima actualizacion: 2026-07-03.

## Objetivo del circuito

Permitir que un usuario revisor revise, corrija, comente y finalice preinformes enviados por residentes. El circuito debe responder rapido a tres preguntas:

- que tengo asignado;
- que esta disponible para tomar;
- que ya revise y puedo consultar o corregir.

## Roles que revisan

- `medico_staff`
- `jefe_residentes`
- `instructor_residentes`
- `jefe_servicio`

Los roles `jefe_residentes` e `instructor_residentes` tienen ademas acceso al pool compartido.

## Entrada de navegacion

Navbar:

- `Docencia > Revision`
- URL base: `preinformes:dashboard_staff`
- Vista: `preinformes.views.dashboard_staff`
- Template: `templates/preinformes/dashboard_staff.html`

Desde el dashboard el usuario llega a:

- `Mis Asignados`
- `Sin Asignar`
- `Asignados a otros`
- `Corregidos por mi`
- `Pool Compartido`, solo jefes/instructores
- `Todos`

## Bandejas operativas

La vista principal es `preinformes:lista_revision`.

Parametro `mostrar`:

- `asignados`: preinformes activos asignados al revisor actual.
- `sin_asignar`: preinformes activos sin revisor y no compartidos.
- `asignados_otros`: preinformes activos asignados a otro revisor.
- `compartidos`: pool compartido visible para jefes/instructores.
- `todos`: mis activos + disponibles para tomar segun rol.
- `finalizados`: preinformes finalizados por el revisor actual.

La regla base de cada bandeja vive en `preinformes/selectors.py`, funcion `get_revision_queryset(usuario, mostrar)`.

## Flujo feliz

1. El residente envia un preinforme a revision.
2. El revisor entra a `Revision`.
3. Si el estudio esta asignado, usa `Revisar` o `Continuar`.
4. Si el estudio no tiene revisor, usa `Tomar y revisar`.
5. La vista `revisar_preinforme` crea o recupera `RevisionPreinforme`.
6. El sistema congela un snapshot del texto del residente.
7. El editor del staff se precarga con ese snapshot si aun no habia edicion.
8. El revisor corrige el informe, agrega feedback, puntuacion opcional e imagenes si corresponde.
9. Puede guardar cambios y continuar.
10. Al finalizar, el preinforme pasa a `finalizado` y se actualiza el historial del residente.

## Edicion posterior

Desde `Corregidos por mi`, el revisor asignado puede volver a editar un preinforme finalizado. Esto cubre olvidos o comentarios tardios.

Reglas:

- solo puede editarlo el revisor asignado;
- el estado se mantiene `finalizado`;
- al guardar vuelve a la bandeja `finalizados`;
- el autosave tambien esta habilitado para el revisor asignado.

## Error de asignacion

Caso frecuente: el residente asigna el estudio al staff incorrecto.

Flujo:

1. El staff entra en `Asignados a otros`.
2. Busca por paciente, numero de estudio, residente, tipo o fechas.
3. Si confirma que corresponde tomarlo y sigue pendiente, usa `Tomar para mi`.
4. El sistema reasigna el preinforme al staff actual y lo mantiene activo.
5. El estudio queda disponible en `Mis asignados` para revisar o continuar.

Reglas:

- se puede tomar solo si esta `pendiente_revision`;
- si esta `en_revision` por otro staff, se puede ver en la bandeja pero no tomar;
- no incluye finalizados de otros revisores;
- la accion pide confirmacion para evitar tomar estudios por error;
- no borra historial ni cambia el residente ni el contenido del preinforme.

## Intencion de acciones

Norma vigente:

- `Revisar`: el estudio ya esta asignado al usuario o esta en su flujo natural.
- `Continuar`: el estudio ya esta en revision por el usuario.
- `Tomar y revisar`: el estudio no tiene revisor y se va a abrir inmediatamente.
- `Asignarme para despues`: reservar un estudio sin abrir el editor.
- `Tomar para mi`: reasignar a mi usuario un estudio pendiente que estaba con otro revisor.
- `Editar`: corregir una revision ya finalizada.
- `Ver comparacion`: contrastar snapshot del residente contra informe final.

Evitar mostrar dos acciones principales que parezcan hacer lo mismo.

## Puntos de refactor actuales

Ya centralizado:

- Queries de bandejas en `preinformes/selectors.py`.
- Preparacion de revision en `preinformes/services.py`, funcion `obtener_o_preparar_revision`.

Pendiente recomendable:

- reducir el bloque heredado de compatibilidad en `lista_revision`;
- extraer filtros del formulario a un helper testeable;
- dividir `revisar_preinforme.html` en parciales: datos, editor, evidencia, feedback y acciones;
- unificar colores/estados con clases o componentes compartidos.

## Tests recomendados

Tests de referencia:

```bash
python manage.py test preinformes.tests.RevisionStaffWorkflowRefactorTest
python manage.py test preinformes.tests.RevisionFinalizadaEditTest preinformes.tests.AutosaveRevisionSmokeTest
```

En entorno local puede haber configuraciones productivas que fuercen HTTPS o storage remoto. Para tests de vistas, preferir `override_settings` cuando el objetivo no sea probar infraestructura.
