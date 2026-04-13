# Control de Guardias - Matriz de Notificaciones por Email

## Objetivo
Asegurar que residentes, jefes de residentes e instructores reciban notificaciones por email segun el evento del modulo, usando el mail registrado del usuario.

## Regla general de envio
Se envia email cuando se crea una `NotificacionGuardia` y se cumplen estas condiciones:
- Usuario activo (`is_active=True`)
- Tiene mail cargado (`email` no vacio)
- Tiene habilitada la preferencia `recibir_notificaciones=True`

Implementacion: [control_guardias/services.py](control_guardias/services.py#L485)

## Matriz evento -> destinatarios
1. Reporte de ausencia (`reportar_ausencia`)
- Destinatarios: jefes de residentes + instructores activos
- Tipo notificacion: `GUARDIA_REASIGNADA`
- Archivo: [control_guardias/services.py](control_guardias/services.py#L531)

2. Resolucion de ausencia con reemplazo (`resolver_ausencia`)
- Destinatarios:
  - Reemplazante asignado
  - Residente ausente (por cada guardia cubierta)
  - Residente ausente (confirmacion final de ausencia resuelta)
- Tipos: `GUARDIA_REASIGNADA`, `AUSENCIA_RESUELTA`
- Archivo: [control_guardias/services.py](control_guardias/services.py#L590)

3. Solicitud de cambio (`solicitar_cambio`)
- Destinatario: receptor de la propuesta
- Tipo: `CAMBIO_SOLICITADO`
- Archivo: [control_guardias/services.py](control_guardias/services.py#L673)

4. Receptor acepta cambio (`aceptar_cambio_receptor`)
- Destinatarios:
  - Solicitante
  - Jefes/instructores (para validacion)
- Tipos: `CAMBIO_ACEPTADO`, `CAMBIO_SOLICITADO`
- Archivo: [control_guardias/services.py](control_guardias/services.py#L711)

5. Receptor rechaza cambio (`rechazar_cambio_receptor`)
- Destinatario: solicitante
- Tipo: `CAMBIO_RECHAZADO`
- Archivo: [control_guardias/services.py](control_guardias/services.py#L739)

6. Jefe/instructor aprueba cambio (`aprobar_cambio`)
- Destinatarios: solicitante + receptor
- Tipo: `CAMBIO_APROBADO`
- Archivo: [control_guardias/services.py](control_guardias/services.py#L768)

7. Jefe/instructor rechaza cambio (`rechazar_cambio_jefe`)
- Destinatarios: solicitante + receptor
- Tipo: `CAMBIO_RECHAZADO`
- Archivo: [control_guardias/services.py](control_guardias/services.py#L792)

8. Solicitante cancela cambio (`cancelar_cambio`)
- Destinatario: receptor
- Tipo: `CAMBIO_RECHAZADO`
- Archivo: [control_guardias/services.py](control_guardias/services.py#L815)

9. Publicacion de borrador mensual (`publicar_borrador`)
- Destinatarios: cada residente incluido en el borrador publicado
- Tipo: `PUBLICACION`
- El email incluye enlace directo a Mis Guardias: `SITE_URL/BASE_URL + /control_guardias/mis-guardias/`
- Archivo: [control_guardias/services.py](control_guardias/services.py#L331)

## Ausentismo con certificado
Se agrego adjunto opcional de certificado en ausencia.

### UX actual de carga de documentos (13/04/2026)
- Se usa una sola lista de `Documentos de respaldo`.
- Carga con enfoque "un campo por archivo" y boton "Agregar archivo".
- El selector es custom (Tailwind), sin el texto nativo "No se eligió ningún archivo".
- El usuario puede agregar hasta 5 campos y quitar cada fila.
- Cada archivo permite imagen/PDF/doc y se valida limite de 10 MB por archivo.

- Modelo: [control_guardias/models.py](control_guardias/models.py#L189)
- Formulario: [control_guardias/forms.py](control_guardias/forms.py#L82)
- Vista de carga: [control_guardias/views.py](control_guardias/views.py#L765)
- UI reporte (portal): [templates/control_guardias/portal/reportar_ausencia_form.html](templates/control_guardias/portal/reportar_ausencia_form.html#L28)
- UI listado (portal): [templates/control_guardias/portal/ausencias.html](templates/control_guardias/portal/ausencias.html#L77)
- UI resolver (portal): [templates/control_guardias/portal/resolver_ausencia_form.html](templates/control_guardias/portal/resolver_ausencia_form.html#L56)

## Verificacion actual de datos de usuarios (13/04/2026)
Usuarios objetivo activos (`medico_residente`, `jefe_residentes`, `instructor_residentes`):
- Total: 7
- Sin email: 0
- Con notificaciones desactivadas: 0

## Tests relevantes
- Certificado + email en ausencias: [control_guardias/tests.py](control_guardias/tests.py#L716)
- Email en solicitud de cambio: [control_guardias/tests.py](control_guardias/tests.py#L951)
- Publicacion de borrador notifica y envia mail: [control_guardias/tests.py](control_guardias/tests.py#L623)
