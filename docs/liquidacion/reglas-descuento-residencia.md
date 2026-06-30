# Reglas de descuento residencia

Documento vigente del flujo de descuento INTRA residencia y cierre operativo de liquidacion de residencia.

Ultima actualizacion: junio 2026.

## Problema resuelto

La modalidad clinica del estudio no alcanza para decidir si corresponde descuento de residencia.

El caso principal es Doppler: algunos estudios Doppler hechos por `medico_residente` deben descontar 50% cuando el registro esta en horario `INTRA`, pero otros Doppler no deben descontar. Antes, el comportamiento legado solo descontaba ECO general real y dejaba DOP/ECOCAR al 100%.

## Componentes implementados

### Modelo

`ReglaDescuentoResidencia`

Campos principales:

- `estudio`
- `grupo_tarifario`
- `aplica_medico_residente`
- `aplica_jefe_residentes`
- `aplica_instructor_residentes`
- `vigencia_desde`
- `vigencia_hasta`
- `activo`
- `observacion`
- auditoria de creacion/actualizacion

Una regla debe apuntar a un estudio o a un grupo tarifario, pero no a ambos.

### Servicio

`estudio_aplica_descuento_residencia(estudio, rol, fecha)`

Devuelve:

- `aplica`
- `fuente`
- `regla_id`
- `motivo`

Precedencia:

1. Regla por estudio.
2. Regla por grupo tarifario.
3. Fallback legado.

Fallback legado:

- ECO general real aplica.
- DOP/ECOCAR no aplica.
- Roles no residencia no aplican.

Roles:

- `medico_residente` aplica si la regla lo permite.
- `jefe_residentes` aplica solo si la regla lo permite explicitamente.
- `instructor_residentes` aplica solo si la regla lo permite explicitamente.

## Integracion con calculo de monto

`RegistroEstudiosPorMedico.calcular_monto()` ya usa el servicio de reglas.

Condiciones para aplicar descuento:

- `registro.horario == "INTRA"`
- rol de residencia
- `estudio_aplica_descuento_residencia(...).aplica == True`

Fecha de vigencia usada:

```python
fecha_referencia = registro.fecha_del_informe or timezone.now().date()
```

Esto mantiene el calculo economico alineado con la fecha del informe y evita que la fecha actual cambie historicos por accidente.

## Doppler

Un Doppler solo descuenta si existe regla activa vigente por estudio o por grupo tarifario que lo permita para el rol.

Si no hay regla:

- `fuente = fallback_legado`
- `aplica = False`
- el Doppler queda al 100%

## Solicitudes de revision de horario

### B2 - Aplicacion economica

`SolicitudRevisionHorarioAplicarView`

Aplica una solicitud aprobada:

- bloquea la solicitud con `select_for_update()` sobre queryset simple;
- bloquea el registro asociado con `select_for_update()` sobre queryset simple;
- carga la sesion contable en consulta separada;
- revalida dentro de `transaction.atomic()`:
  - estado `APROBADA`;
  - `fecha_aplicacion is None`;
  - sesion `ABIERTA` o `REVISION`;
- cambia el horario del registro al `horario_solicitado`;
- recalcula monto con `calcular_monto()`;
- guarda snapshots:
  - `horario_anterior`
  - `horario_aplicado`
  - `monto_anterior`
  - `monto_aplicado`
  - `aplicado_por`
  - `fecha_aplicacion`

No debe usar `select_for_update().select_related(...)`, porque PostgreSQL rechaza `FOR UPDATE` sobre el lado nullable de un outer join.

### B3 - Recalculo puntual de solicitud aplicada

`SolicitudRevisionHorarioRecalcularAplicacionView`

Permite recalcular una solicitud ya aplicada usando las reglas vigentes actuales, sin recalculos masivos.

Condiciones:

- solicitud `APROBADA`;
- `fecha_aplicacion` existente;
- `horario_aplicado` existente;
- sesion `ABIERTA` o `REVISION`;
- solo permisos administrativos.

Funcionamiento:

- bloquea solicitud con queryset simple;
- bloquea registro con queryset simple;
- carga sesion contable aparte;
- usa `horario_aplicado` como horario vigente en memoria;
- ejecuta `registro.calcular_monto()`;
- si el monto no cambia, no actualiza registro ni crea historial;
- si cambia:
  - actualiza `RegistroEstudiosPorMedico.monto_calculado`;
  - confirma `horario = horario_aplicado`;
  - actualiza auditoria de modificacion;
  - actualiza `SolicitudRevisionHorarioRegistro.monto_aplicado`;
  - crea `HistorialRecalculoSolicitudRevisionHorario`.

No toca:

- `monto_anterior`;
- `horario_anterior`;
- `fecha_aplicacion`;
- `aplicado_por`.

## Diagnostico B3 en pantalla

En el detalle de una solicitud ya aplicada se muestra el bloque **Diagnostico de recalculo** antes del boton B3.

El bloque muestra:

- `horario_aplicado`;
- rol del medico;
- fecha usada para vigencia (`fecha_del_informe`);
- monto actual del registro;
- monto simulado con reglas vigentes;
- diferencia esperada;
- por cada estudio:
  - nombre;
  - tipo;
  - grupo tarifario;
  - aplica;
  - fuente;
  - regla_id;
  - motivo;
  - advertencia.

Mensajes esperados:

- Si la diferencia es cero: `El recalculo no cambiaria el monto actual.`
- Si el horario aplicado no es `INTRA`: `No aplica descuento porque el horario aplicado no es INTRA.`
- Si el estudio es Doppler y no hay regla activa aplicable: `No existe regla activa aplicable para este estudio en la fecha del informe.`

La simulacion es solo lectura:

- setea `registro.horario = horario_aplicado` solo en memoria;
- llama `registro.calcular_monto()`;
- restaura el horario original;
- no guarda nada;
- no dispara signals;
- no recalcula historicos.

## Cierre operativo de liquidacion residencia

La primera etapa de cierre administrativo liquida solo practicas registradas en `RegistroEstudiosPorMedico` para roles de residencia:

- `medico_residente`
- `jefe_residentes`
- `instructor_residentes`

No incluye guardias en esta fase. Si el snapshot RRHH conserva campos de guardias, deben quedar explicitamente en `0`.

### D1 - Preparacion RRHH sin email real

`PreparacionLiquidacionRRHH`

Es un snapshot auditable para preparar la liquidacion de residencia a RRHH.

Reglas:

- disponible desde sesiones `CERRADA`, `FACTURADA` o `PAGADA`;
- no cambia el estado de la sesion;
- no envia email real;
- usa `monto_calculado` persistido;
- no llama a `calcular_monto()`;
- incluye solo roles de residencia;
- permite multiples versiones por sesion;
- `BORRADOR` puede guardarse sin destinatarios;
- `PREPARADO` requiere destinatarios y no debe tener bloqueantes.

Validaciones bloqueantes principales para `PREPARADO`:

- solicitudes de revision horaria `PENDIENTE`;
- solicitudes `APROBADA` sin `fecha_aplicacion`;
- registros con estudios asociados y `monto_calculado <= 0`;
- destinatarios faltantes;
- intento de preparar `PREPARADO` cuando no hay practicas de residencia.

Si la sesion no tiene practicas de residencia:

- RRHH se marca como **No requerido**;
- no bloquea la facturacion;
- el snapshot muestra profesionales `0`, guardias `0` y total general de residencia `0`.

### E1 - Checklist de cierre

`construir_checklist_cierre_sesion(sesion, user=None)`

Resume el avance operativo de una sesion:

- registros validos;
- solicitudes pendientes;
- aprobadas sin aplicar;
- auditoria residentes ECO;
- preparacion RRHH;
- lista para facturar;
- sesion pagada.

El checklist es orientacion visual/operativa. No es fuente de verdad economica y no recalcula montos.

### E2 - Resolucion guiada de bloqueantes

La pantalla de sesiones transforma algunos hallazgos del gate administrativo y RRHH en acciones de navegacion:

- solicitudes pendientes o aprobadas sin aplicar -> bandeja de solicitudes filtrada;
- registros con problemas -> inspeccion administrativa read-only del registro;
- estudios sin configuracion suficiente -> edicion administrativa del estudio;
- grupos sin tarifa vigente -> carga de nueva tarifa;
- guardias con monto invalido -> edicion de guardia, si la sesion lo permite.

Estas acciones no corrigen automaticamente. Solo llevan al administrativo al punto de revision o configuracion correspondiente.

El gadget **Registros** abre el bloque **Registros: bloqueantes y advertencias** de la misma sesion. Ese bloque debe:

- desplegarse al navegar desde el checklist;
- explicar que los hallazgos deben revisarse antes de avanzar;
- mostrar acciones sugeridas cuando existan;
- mantener el retorno contextual a la sesion contable.

La inspeccion administrativa de registros es solo lectura: no recalcula, no guarda cambios y no reemplaza las solicitudes horarias B2/B3.

### E3 - Auditoria residentes ECO y control PACS

La **Auditoria residentes ECO** es una advertencia operativa para revisar registros ECO sospechosos contra PACS. No recalcula automaticamente y no reemplaza el gate administrativo ni las solicitudes horarias.

La vista completa de auditoria permite:

- ver todos los registros sospechosos de la sesion;
- filtrar por profesional y motivo;
- inspeccionar el registro en modo administrativo;
- ver la liquidacion del profesional;
- registrar una revision administrativa:
  - `VALIDADO`: el registro coincide con PACS o se acepta tal como esta;
  - `REQUIERE_CORRECCION`: el control PACS detecto diferencia que requiere ajuste;
  - `DESCARTADO`: la alerta no corresponde o no debe tratarse.

`RevisionAuditoriaEcoRegistro` deja trazabilidad de:

- sesion;
- registro;
- estado;
- motivos detectados;
- observacion obligatoria;
- usuario revisor;
- fecha de revision.

La revision por si sola no modifica montos.

### E4 - Correccion puntual por control PACS

Cuando la ultima revision de un registro queda en `REQUIERE_CORRECCION`, administracion puede aplicar un ajuste puntual por control PACS.

Modelo:

`CorreccionPacsRegistro`

Guarda:

- sesion contable;
- registro corregido;
- revision ECO que origino la correccion;
- tipo de correccion:
  - `HORARIO_RECALCULADO`;
  - `MONTO_MANUAL`;
- horario anterior y horario nuevo, si corresponde;
- monto anterior;
- monto nuevo;
- observacion;
- usuario que corrige;
- fecha de correccion.

Reglas:

- solo se corrige un registro puntual;
- requiere que la ultima revision ECO del registro sea `REQUIERE_CORRECCION`;
- bloquea sesiones `FACTURADA` y `PAGADA`;
- si la correccion es por horario, setea el horario corregido y recalcula con `RegistroEstudiosPorMedico.calcular_monto()`;
- si la correccion es manual, usa el monto ingresado por administracion;
- no modifica `calcular_monto()`;
- no toca `signals.py`;
- no recalcula registros historicos;
- no cambia estudios, paciente ni clasificacion automatica;
- actualiza `RegistroEstudiosPorMedico.monto_calculado`;
- actualiza `RegistroEstudiosPorMedico.horario` solo cuando el tipo de correccion es `HORARIO_RECALCULADO`;
- actualiza auditoria del registro:
  - `modificado_por`;
  - `fecha_modificacion`;
  - `motivo_modificacion`.

La correccion queda visible para el profesional en **Mis registros** como **Ajuste PACS aplicado**, con horario anterior/nuevo si existio recorreccion horaria, monto anterior, monto nuevo, fecha y observacion. Esto permite que el usuario sepa que el valor fue ajustado por control administrativo contra PACS.

### Regla de facturacion con RRHH

Para pasar una sesion de `CERRADA` a `FACTURADA`:

- si hay practicas de residencia, debe existir una `PreparacionLiquidacionRRHH` ultima o vigente en estado `PREPARADO`;
- si no hay practicas de residencia, RRHH queda como **No requerido** y no bloquea;
- una preparacion `BORRADOR` no habilita facturacion;
- esta regla se valida en backend en la transicion de sesion.

La pantalla administrativa de sesiones muestra:

- estado global de cierre;
- proximo paso recomendado;
- estado RRHH residencia;
- ultima version preparada o borrador;
- hash corto del snapshot;
- destinatarios si existen;
- acceso directo a **Preparar RRHH** desde sesiones `CERRADA`, `FACTURADA` o `PAGADA`.

## Operacion manual para corregir un caso real

1. Identificar la solicitud aplicada y el registro asociado.
2. Verificar que la sesion este `ABIERTA` o `REVISION`.
3. Crear o ajustar `ReglaDescuentoResidencia`.
4. Entrar al detalle de la solicitud.
5. Revisar **Diagnostico de recalculo**:
   - si falta regla;
   - si la vigencia no cubre `fecha_del_informe`;
   - si `horario_aplicado` no es `INTRA`;
   - si el estudio/grupo no es el esperado;
   - si el rol no esta habilitado.
6. Si la diferencia esperada es correcta, ejecutar **Recalcular monto con reglas vigentes**.
7. Validar:
   - `registro.monto_calculado`;
   - `solicitud.monto_aplicado`;
   - historial B3 creado;
   - auditoria de modificacion del registro.

## Como cargar una regla para Doppler especifico

Usar regla por estudio si el cambio debe afectar solo ese Doppler puntual.

Valores sugeridos:

- `estudio`: Doppler especifico.
- `grupo_tarifario`: vacio.
- `aplica_medico_residente`: `True`.
- `aplica_jefe_residentes`: `False`.
- `aplica_instructor_residentes`: `False`.
- `vigencia_desde`: fecha igual o anterior a `fecha_del_informe`.
- `vigencia_hasta`: vacio si sigue vigente.
- `activo`: `True`.

Usar regla por grupo tarifario solo si todos los estudios del grupo deben compartir la misma politica, recordando que una regla por estudio tiene prioridad sobre grupo.

## Tests focales

Tests principales:

- `liquidacion.tests_regla_descuento_residencia`
- `liquidacion.tests_regla_descuento_residencia_calculo`
- tests `test_b3_*` en `liquidacion.tests_auditoria_2026_05_11.PermisosYTrazabilidadViewTest`
- `liquidacion.tests_preparacion_rrhh`
- `liquidacion.tests_checklist_cierre`
- tests de transicion `CERRADA -> FACTURADA` en `liquidacion.tests_auditoria_2026_05_11.SesionContableWorkflowPermissionsTest`

Comandos utiles:

```bash
python manage.py test liquidacion.tests_regla_descuento_residencia --verbosity=1
python manage.py test liquidacion.tests_regla_descuento_residencia_calculo --verbosity=1
python manage.py test liquidacion.tests_auditoria_2026_05_11.PermisosYTrazabilidadViewTest.test_b3_recalcula_solicitud_aplicada_dop_residente_intra_con_regla_activa --verbosity=2
python manage.py test liquidacion.tests_preparacion_rrhh --verbosity=1
python manage.py test liquidacion.tests_checklist_cierre --verbosity=1
python manage.py makemigrations --check --dry-run
```
