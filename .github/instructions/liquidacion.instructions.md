---
applyTo: "liquidacion/**/*.py"
---

# Instrucciones para liquidacion

> Ultima actualizacion: 02/08/2026

## Prioridad del modulo

- `liquidacion/` afecta facturacion real. Todo cambio debe minimizar riesgo operativo, economico y de auditoria.
- Priorizar exactitud de calculo, permisos por rol, concurrencia y trazabilidad sobre comodidad o cambios cosmeticos.
- Implementar cambios incrementales, focales y testeables. Evitar redisenos grandes sin aprobacion explicita.
- No modificar migraciones ya aplicadas en produccion. Crear nuevas migraciones cuando el modelo lo requiera.

## Reglas de negocio obligatorias

- Estados de sesion contable: `ABIERTA -> REVISION -> CERRADA -> FACTURADA -> PAGADA`.
- Medicos, residentes, jefes/instructores y cardiologos registran practicas propias solo en `ABIERTA` o `REVISION`.
- Vista global operativa: `administrativo`, `jefe_servicio` y `superuser`.
- `PAGADA` es estado final bloqueado: no permitir nuevas practicas, correcciones economicas ni cambios silenciosos.
- Cardiologo se comporta como staff para calculo: sin INTRA/EXTRA residencia.
- `monto_calculado` es historico y persistido. No recalcular registros historicos masivamente.

## Calculo economico

- La unica fuente de calculo debe ser `RegistroEstudiosPorMedico.calcular_monto()`.
- No duplicar calculo en views, templates, exports o servicios.
- No tocar `calcular_monto()` salvo que la tarea lo pida explicitamente.
- `calcular_monto()` usa `ReglaDescuentoResidencia` mediante `estudio_aplica_descuento_residencia(estudio, rol, fecha)`.
- Fecha de vigencia para descuento residencia: `registro.fecha_del_informe or timezone.now().date()`.
- Descuento INTRA residencia solo aplica si:
  - `registro.horario == "INTRA"`;
  - el rol es `medico_residente`;
  - el servicio de reglas devuelve `aplica=True`.
- Fallback legado sin regla explicita:
  - ECO general real descuenta;
  - DOP/ECOCAR no descuenta;
  - roles no residencia no descuentan.
- Doppler solo descuenta con regla activa explicita por estudio o grupo tarifario para el rol correspondiente.
- `jefe_residentes` e `instructor_residentes` no aplican descuento INTRA, aunque existan flags historicos en reglas.
- `EXTRA` y `NA` liquidan al 100%.
- Bonus urgencia RM: respetar regla existente de remoto + paciente internado + ventana temporal definida.

## ReglaDescuentoResidencia C1/C2

- `ReglaDescuentoResidencia` puede apuntar a `estudio` o `grupo_tarifario`, nunca ambos.
- La regla por estudio tiene prioridad sobre la regla por grupo.
- Respetar `activo`, `vigencia_desde` y `vigencia_hasta`.
- `medico_residente` aplica si la regla lo permite.
- `jefe_residentes` e `instructor_residentes` no aplican descuento INTRA.
- No modificar `ReglaDescuentoResidencia` ni `services.py` salvo tarea explicita sobre reglas de descuento.

## Override Extra Residencia

- `liquidar_como_extra_residencia` existe solo para `jefe_residentes` e `instructor_residentes`.
- Si esta activo, el registro debe liquidarse como `EXTRA` aunque la hora normal indicaria `INTRA`.
- Usuarios no autorizados no deben poder usar el flag aunque lo envien por POST.
- En create, el checkbox puede recordar el ultimo valor en `request.session` solo para jefe/instructor.
- En update, manda el valor propio del registro; la sesion no debe pisarlo.
- `signals.py` debe respetar el override y no volver a clasificar como INTRA.

## Revision horaria B2/B3

- B2 (`SolicitudRevisionHorarioAplicarView`) aplica economicamente una solicitud `APROBADA` una sola vez.
- B2 debe:
  - usar `transaction.atomic()`;
  - bloquear solicitud con `SolicitudRevisionHorarioRegistro.objects.select_for_update().get(pk=...)`;
  - bloquear registro con `RegistroEstudiosPorMedico.objects.select_for_update().get(pk=...)`;
  - cargar relaciones/sesion en consultas separadas sin `FOR UPDATE`;
  - revalidar dentro de la transaccion: estado `APROBADA`, `fecha_aplicacion is None`, sesion `ABIERTA` o `REVISION`;
  - recien despues modificar registro y solicitud;
  - guardar snapshots `horario_anterior`, `horario_aplicado`, `monto_anterior`, `monto_aplicado`, `aplicado_por`, `fecha_aplicacion`.
- B3 (`SolicitudRevisionHorarioRecalcularAplicacionView`) recalcula puntualmente una solicitud ya aplicada usando reglas vigentes.
- B3 debe:
  - operar solo sobre una solicitud aplicada, `APROBADA`, con `horario_aplicado`;
  - operar solo si la sesion esta `ABIERTA` o `REVISION`;
  - usar `horario_aplicado` para simular/recalcular;
  - no tocar `monto_anterior`, `horario_anterior`, `fecha_aplicacion` ni `aplicado_por`;
  - crear `HistorialRecalculoSolicitudRevisionHorario` solo si el monto cambia;
  - no crear historial ni actualizar registro si el monto no cambia.

## Concurrencia

- En escrituras compuestas usar `transaction.atomic()`.
- Regla critica PostgreSQL: no usar `select_for_update().select_related(...)` cuando haya relaciones nullable.
- Aplicar `select_for_update()` solo sobre el modelo base que se quiere bloquear.
- Cargar `sesion_contable`, medico, estudios y otras relaciones en consultas separadas sin `FOR UPDATE`.
- No hacer returns silenciosos despues de haber modificado un registro dentro de una transaccion.

## RRHH D1

- `PreparacionLiquidacionRRHH` es snapshot auditable para preparar liquidacion de residencia.
- D1 no envia email real.
- D1 esta disponible desde sesiones `CERRADA`, `FACTURADA` o `PAGADA`.
- D1 no cambia el estado de la sesion.
- D1 usa `monto_calculado` persistido; no recalcula.
- D1 incluye solo roles residencia: `medico_residente`, `jefe_residentes`, `instructor_residentes`.
- `PREPARADO` requiere destinatarios; `BORRADOR` puede guardarse sin destinatarios.
- Si una sesion no tiene practicas de residencia, RRHH queda como `No requerido` y no bloquea facturacion.
- Si una sesion `CERRADA` tiene practicas de residencia, no puede pasar a `FACTURADA` sin una `PreparacionLiquidacionRRHH` en estado `PREPARADO`.
- Una preparacion `BORRADOR` no habilita facturacion.
- No agregar envio real de email salvo fase especifica aprobada.

## Checklist de cierre E1

- `construir_checklist_cierre_sesion(sesion, user=None)` resume estado operativo de cierre.
- El checklist E1 es orientacion visual y operativa; no es fuente de verdad economica.
- No mover reglas economicas al checklist ni al template.
- Los detalles siguen viviendo en gate administrativo, auditoria ECO, solicitudes, RRHH e historial.
- El gate de registros puede mostrar acciones de navegacion para resolver bloqueantes, pero no debe ejecutar correcciones automaticas.
- La inspeccion administrativa de registros bloqueantes es read-only; no debe recalcular ni modificar registros.
- El gadget `Registros` debe dirigir y abrir el bloque de gate administrativo de esa sesion.

## Auditoria ECO/PACS E3/E4

- `RevisionAuditoriaEcoRegistro` registra revision administrativa de alertas ECO contra PACS.
- La revision ECO no modifica montos por si sola.
- Estados de revision ECO:
  - `VALIDADO`;
  - `REQUIERE_CORRECCION`;
  - `DESCARTADO`.
- `CorreccionPacsRegistro` registra un ajuste economico puntual originado en control PACS.
- Correccion PACS debe:
  - operar sobre un solo `RegistroEstudiosPorMedico`;
  - requerir ultima revision ECO en `REQUIERE_CORRECCION`;
  - bloquear sesiones `FACTURADA` y `PAGADA`;
  - usar `transaction.atomic()` y lock simple si hay escritura concurrente;
  - recalcular con `RegistroEstudiosPorMedico.calcular_monto()` cuando la correccion sea por horario corregido;
  - guardar `hora_pacs` cuando la correccion sea por horario corregido;
  - actualizar `monto_calculado`, `modificado_por`, `fecha_modificacion` y `motivo_modificacion`;
  - actualizar `horario` solo en correcciones PACS de tipo `HORARIO_RECALCULADO`;
  - crear historial `CorreccionPacsRegistro`;
  - mostrarse al profesional en su lista de registros.
- Correccion PACS no debe:
  - modificar `calcular_monto()`;
  - tocar `signals.py`;
  - recalcular masivamente;
  - cambiar estudios, paciente, clasificacion automatica o reglas residencia;
  - aplicarse si el monto nuevo coincide con el actual.
- En pantallas operativas, mostrar como dato principal la hora PACS asociada a la fecha del registro; la fecha administrativa de aplicacion queda como trazabilidad secundaria.

## Cruce EGES y validacion operativa

- El cruce EGES valida registros de residencia contra turnos importados desde EGES/PACS; no es fuente de calculo economico.
- `construir_preview_cruce_liquidacion_eges` cruza por paciente/DNI o HC, fecha, modalidad ECO y practicas candidatas.
- En esta etapa el cruce compara solo modalidad ECO. No mezclar con TC/RM/RX/MAM sin tarea explicita.
- Los turnos EGES pueden traer varias practicas para el mismo paciente, fecha, hora, centro y tipo de atencion; deben agruparse como un mismo turno candidato.
- La coincidencia de medico debe tolerar orden de nombre/apellido y apellidos adicionales.
- `ECO ABDOMINAL` y `ECOGRAFIA COMPLETA DE ABDOMEN` son equivalentes para el cruce.
- Horario esperado EGES:
  - dias habiles 08:00-17:00: `INTRA`;
  - fuera de ese rango: `EXTRA`;
  - sabado, domingo y feriado: `EXTRA`;
  - cruces ambiguos o turnos que atraviesan el limite deben quedar `MANUAL`.
- Guardias en EGES entre 08:00 y 17:00 se esperan `INTRA`, salvo sabados, domingos y feriados.
- `RevisionCruceEgesRegistro` registra la decision administrativa del cruce:
  - `VALIDADO`: coincidencia aceptada;
  - `REQUIERE_CORRECCION`: queda pendiente para resolver por otro flujo;
  - `DESCARTADO`: alerta descartada.
- Validar o descartar un cruce EGES no modifica `RegistroEstudiosPorMedico`, no recalcula montos y no crea correcciones economicas.
- `REQUIERE_CORRECCION` tampoco aplica correccion por si mismo; solo deja trazabilidad y mantiene el caso pendiente.
- La auditoria ECO de sesiones puede considerar resuelto un registro si existe revision EGES `VALIDADO` o `DESCARTADO` y no hay revision PACS pendiente. `REQUIERE_CORRECCION` debe seguir visible.
- La accion masiva `Validar OK visibles` solo debe persistir resultados `OK` del filtro actual y sin revision previa.
- El campo DNI de carga de practicas debe aceptar solo numeros. No permitir nombres, puntos, espacios ni letras.

## Permisos y trazabilidad

- Validar permisos en backend (`dispatch`, `test_func`, queryset restringido), no solo en template.
- En `UpdateView` y `DeleteView`, limitar queryset al usuario cuando corresponda.
- En ediciones/correcciones guardar `modificado_por`, `fecha_modificacion` y `motivo_modificacion` cuando aplique.
- Correcciones sensibles deben dejar trazabilidad explicita.
- No permitir cambios silenciosos en registros sensibles.

## No regresion

- No recalcular masivamente salvo comando/fase aprobada.
- No tocar `signals.py`, `calcular_monto()`, B2/B3, reglas residencia o templates fuera del alcance solicitado.
- No cambiar estados de sesion como efecto lateral de previews, snapshots o diagnosticos.
- No enviar emails reales desde previews.
- No modificar exportaciones existentes salvo tarea explicita.
- Mantener N+1 controlado en listados, previews y reportes.

## Tests minimos por tipo de cambio

- Cambio de reglas/modelo residencia: `python manage.py test liquidacion.tests_regla_descuento_residencia --verbosity=1`.
- Cambio de calculo residencia: `python manage.py test liquidacion.tests_regla_descuento_residencia_calculo --verbosity=1`.
- Cambio B2/B3 o sesiones: usar tests focales en `liquidacion.tests_auditoria_2026_05_11` antes de suites largas.
- Cambio RRHH D1: `python manage.py test liquidacion.tests_preparacion_rrhh --verbosity=1`.
- Cambio checklist E1: `python manage.py test liquidacion.tests_checklist_cierre --verbosity=1`.
- Cambio cruce/validacion EGES: `python manage.py test liquidacion.tests_cruce_eges --verbosity=1`.
- Cambio validacion DNI de practica: `python manage.py test liquidacion.tests.ClasificacionHorarioResidenciaProxyTest --verbosity=1`.
- Cambio de transicion `CERRADA -> FACTURADA`: agregar/ejecutar test focal en `liquidacion.tests_auditoria_2026_05_11.SesionContableWorkflowPermissionsTest`.
- Si se toca modelo: `python manage.py makemigrations --check --dry-run`.
- Correr suite completa `python manage.py test liquidacion --verbosity=1` solo cuando el alcance/riesgo lo justifique o el usuario lo pida.
