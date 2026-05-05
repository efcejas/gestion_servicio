---
applyTo: "preinformes/**/*.py"
---

# Instrucciones para preinformes

> Ultima actualizacion: 03/05/2026

## Dominio y permisos

- Respetar control de acceso por rol en todas las vistas.
- Para flujos de residente, validar ownership del preinforme antes de permitir editar.
- No agregar bypass de permisos en endpoints AJAX o autosave.
- Si hay cambios de permisos, actualizar tests de autorizacion.

## Autosave

- Mantener rutas oficiales:
  - Residente: `POST /preinformes/<pk>/autosave/`
  - Revisor: `POST /preinformes/revision/<pk>/autosave/`
- Nunca hardcodear rutas inexistentes como `/preinformes/autosave-revision/...`.
- Mantener compatibilidad con CKEditor 5 y el acceso a instancia via `.ck-content`.

## Timezone

- En backend: siempre `timezone.now()`.
- En UI para timestamp de edicion: usar `timezone.localtime(...)` antes de `strftime`.

## Arquitectura

- Si la logica crece, mover reglas de negocio fuera de vistas.
- Mantener vistas delgadas y mensajes UX claros para guardar/enviar/revisar.
- Evitar logica de negocio en templates.

## Tests minimos cuando cambie comportamiento

- Permisos por rol (residente, instructor, jefe, staff).
- Transiciones de estado relevantes (borrador, pendiente_revision, etc.).
- Endpoints de autosave (residente y revision).

## Seguridad y datos

- No exponer texto clinico sensible en logs.
- Validar payloads de autosave en servidor.
- Mantener cambios pequenos y reversibles en flujos clinicos criticos.
