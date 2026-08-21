# Auditoría del Portafolio de residentes

Fecha: 18/08/2026

Actualización de rollout: 21/08/2026

Estado auditado: Corte A implementado, en validación exclusiva por superusuario

## 1. Resultado ejecutivo

La implementación actual es una base adecuada para validar la utilidad del
Portafolio. Funciona como agregador de solo lectura, mantiene las reglas en
selectores y servicios propios, y no modifica los módulos que originan la
actividad.

El alcance disponible incluye:

- acceso al portafolio propio para usuarios con rol `medico_residente`;
- seguimiento y detalle individual para perfiles docentes autorizados;
- integración con Guardias, Preinformes, Liquidación y Clases;
- ciclo lectivo calculado desde el primer día hábil de agosto;
- indicadores y desgloses sin datos identificatorios de pacientes ni montos;
- navegación integrada al grupo `Docencia`;
- presentación responsive coherente con el portal.

No forman parte de este corte la actividad académica manual, certificados,
validación docente, evaluaciones, selección de ciclos históricos ni el cierre
anual formal e inmutable.

No se detectaron bloqueantes críticos para continuar la validación del tablero.
Antes de ampliar el acceso o implementar cierres deben resolverse las brechas
prioritarias de la sección 8.

### Rollout actual en producción

El flag `PORTAFOLIO_SOLO_SUPERUSER` está activo por defecto. Mientras mantenga
el valor `True`:

- solo los superusuarios ven `Seguimiento de residentes` en el navbar;
- solo los superusuarios pueden abrir el listado y el detalle individual;
- residentes, docentes y administrativos reciben `403` aun con una URL directa;
- `Mi portafolio` permanece oculto y bloqueado para residentes.

El flag se evalúa en navegación y backend. Al establecerlo en `False` se
recupera la matriz funcional prevista, sin cambiar URLs ni permisos base.

## 2. Inventario implementado

### Rutas

| Ruta | Finalidad |
|---|---|
| `/portafolio/` | Portafolio propio del residente o egresado con cuenta activa. |
| `/portafolio/residentes/` | Listado docente de residentes. |
| `/portafolio/residentes/<id>/` | Resumen longitudinal individual. |

### Arquitectura

- `portafolio/selectors.py`: período académico y consultas agregadas.
- `portafolio/services.py`: composición del resumen de una persona.
- `portafolio/views.py`: autorización y renderizado.
- `templates/portafolio/`: resumen individual y seguimiento docente.
- `accounts/context_processors.py`: acceso desde el navbar según rol o grupo.

El módulo no tiene modelos ni migraciones propias en este corte. Toda la
información se obtiene en tiempo real desde las fuentes existentes.

## 3. Acceso funcional después del rollout

Durante el rollout rige la restricción exclusiva para superusuarios descrita en
la sección anterior. La siguiente matriz documenta la apertura prevista cuando
`PORTAFOLIO_SOLO_SUPERUSER=False`:

| Perfil | Propio | Listado | Detalle de otros |
|---|---:|---:|---:|
| Residente activo | Sí | No | No |
| Egresado con rol `medico_residente` y cuenta activa | Sí | No | No |
| Jefe de residentes | No | Sí | Sí |
| Instructor de residentes | No | Sí | Sí |
| Jefe de servicio | No | Sí | Sí |
| Superusuario | No | Sí | Sí |
| Grupo `Administrativo - Docencia` | No | Sí | Sí, actualmente |
| Otros perfiles | No | No | No |

Las vistas validan permisos en backend. El navbar refleja esos permisos, pero
no se utiliza como mecanismo de autorización.

El listado incluye únicamente cuentas `medico_residente` activas y con perfil
completo. La URL de detalle, si la solicita un perfil autorizado, admite también
residentes con perfil incompleto o cuenta inactiva. Esta diferencia debe
resolverse como decisión de producto antes de considerar definitivo el alcance
del seguimiento.

## 4. Criterio de cada fuente

| Fuente | Fecha utilizada | Inclusión actual | Información expuesta |
|---|---|---|---|
| Guardias | `AsignacionGuardia.fecha` | `PUBLICADA` o `CUMPLIDA`, dentro del ciclo y anterior a hoy. | Total y tipo de guardia. |
| Preinformes | `Preinforme.fecha_creacion` | Todos los estados, excluyendo registros demo; `finalizado` se informa como subtotal. | Total, estado agregado, tipo de estudio y región. |
| Estudios | `RegistroEstudiosPorMedico.fecha_del_informe` | Registros no anulados dentro del ciclo. | Cantidades, modalidad, regiones y nombre de práctica. |
| Clases | `ClaseResidente.fecha_clase` | Clases activas cuyo autor es el residente. | Total y categoría. |

### Guardias y excepciones

El selector computa `PUBLICADA` y `CUMPLIDA`; no cuenta `BORRADOR`, `AUSENTE` ni
`REASIGNADA`. Esto coincide con los flujos actuales del módulo:

- ante una ausencia con reemplazo, la asignación original queda `REASIGNADA` y
  se crea una nueva `PUBLICADA` para quien la cubre;
- ante una ausencia sin reemplazo, la asignación queda `AUSENTE`;
- un cambio bilateral aprobado intercambia el residente de las asignaciones
  publicadas;
- un cambio a un slot vacante deja la asignación anterior `REASIGNADA` y crea
  la nueva como `PUBLICADA`.

Por lo tanto, las modificaciones validadas cambian el conteo automáticamente y
el Portafolio no necesita reinterpretarlas.

### Privacidad y frontera económica

La proyección de Liquidación entrega únicamente campos académicos y
asistenciales permitidos. No selecciona ni devuelve:

- nombre, apellido, DNI o historia clínica del paciente;
- monto calculado, precios, tarifas o descuentos;
- estado contable o información de facturación.

Preinformes tampoco entrega identidad del paciente, contenido clínico ni texto
del informe. Las pruebas automatizadas verifican que estos valores no aparezcan
en el resumen ni en el HTML.

## 5. Ciclo lectivo

El período comienza el primer día de agosto que no sea sábado, domingo ni un
feriado registrado en `control_guardias.Feriado`. Termina inmediatamente antes
del primer día hábil de agosto siguiente.

La pantalla muestra únicamente el ciclo que contiene la fecha local actual. No
existe todavía selector de ciclo ni navegación histórica. Para 2026/27 el
inicio calculado es el 03/08/2026 y el fin inclusivo es el 01/08/2027, salvo que
el calendario de feriados registrado modifique esas fechas.

## 6. Contrato visual consolidado

Las dos vistas usan `base_tailwind.html` y heredan su contenedor centrado
`max-w-7xl`, igual al header y al navbar. No agregan un segundo contenedor con
padding horizontal.

Patrones aplicados:

- cabecera mediante `page_header`, con gradiente institucional
  `medical-primary` a `medical-secondary`;
- título principal único, texto blanco e icono circular translúcido;
- estado o contexto en badge semántico;
- indicadores con la misma estructura, jerarquía numérica e iconografía;
- secciones de detalle blancas, con borde gris, `rounded-xl` y encabezado suave;
- tablas con scroll horizontal en mobile, números alineados y acción visible;
- estados vacíos explícitos;
- iconos decorativos marcados con `aria-hidden` cuando se revisaron.

Si este patrón se utiliza en una tercera pantalla, conviene extraer la cabecera
y las tarjetas repetidas a componentes compartidos, evitando mantener copias
independientes de las clases Tailwind.

## 7. Validación automatizada actual

La suite `portafolio` contiene 13 pruebas y cubre:

- inicio del ciclo en el primer día hábil de agosto;
- consideración de feriados registrados;
- guardias publicadas pasadas y exclusión de futuras o reasignadas;
- proyección de Liquidación sin pacientes ni montos;
- ausencia de datos sensibles en el HTML;
- diferencia entre residente sin año informado y egresado;
- bloqueo del acceso entre residentes;
- acceso de instructor y administrativo de Docencia;
- denegación a staff sin rol docente.
- acceso de superusuario durante el rollout restringido;
- bloqueo de residente e instructor mediante URL directa durante el rollout;
- ocultamiento del acceso en el navbar para perfiles no habilitados.

En la actualización de rollout del 21/08/2026 se ejecutaron exitosamente:

```text
python manage.py test portafolio
python manage.py check
```

## 8. Hallazgos y riesgos pendientes

### Prioridad alta antes de ampliar el alcance

1. **Contrato del administrativo de Docencia.** La especificación original lo
   limitaba a un resumen operativo, pero el código actual permite abrir el
   mismo detalle agregado que un instructor. No expone pacientes ni montos,
   aunque el alcance debe confirmarse y luego reflejarse en permiso y pruebas.
2. **Ciclos históricos y egresados.** El portafolio siempre abre el ciclo
   actual. Un egresado puede obtener un tablero vacío si su actividad pertenece
   a un ciclo anterior. Se necesita definir el ciclo inicial y la navegación
   histórica antes de declarar completo el acceso de egresados.
3. **Servicio no apto todavía para snapshots históricos.** El parámetro
   `fecha_referencia` limita Guardias hasta esa fecha, pero Preinformes,
   Estudios y Clases consultan el ciclo completo. No debe reutilizarse sin
   cambios para generar un cierre inmutable con fecha de corte.

### Prioridad media para robustecer el Corte A

1. Confirmar si Preinformes debe pertenecer al ciclo por fecha de creación o
   por una fecha asistencial diferente.
2. Definir si el listado docente debe incluir residentes inactivos o con perfil
   incompleto, y mantener el mismo criterio en la URL de detalle.
3. Agregar pruebas para jefe de residentes, jefe de servicio, superusuario,
   egresado, acceso administrativo al detalle y límites exactos de cada fuente.
4. Incorporar búsqueda o filtro por año cuando el volumen del listado lo
   justifique. El wireframe original los contemplaba, pero el listado actual es
   deliberadamente mínimo.
5. Establecer un presupuesto de consultas para el detalle antes de agregar más
   fuentes, gráficos o actividad reciente.

### Mejoras menores de UX y accesibilidad

- completar `aria-hidden` en los iconos puramente decorativos restantes;
- revisar estados de foco visibles en los enlaces de acción;
- validar visualmente desktop y mobile con datos largos y estados vacíos.

## 9. Estado por corte

| Corte | Estado | Alcance pendiente |
|---|---|---|
| A - lectura y utilidad | Implementado, en validación | Resolver hallazgos de acceso e historial; validar conteos con datos reales. |
| B - gestión académica | No iniciado | Actividad manual, S3, envío, validación y observaciones. |
| C - cierre anual | No iniciado | Snapshot, PDF, hash, unicidad, inmutabilidad y corrección auditada. |

## 10. Próximo paso recomendado

Validar con instructor y uno o dos residentes que los cuatro conteos coincidan
con los módulos fuente. En paralelo, cerrar las decisiones de acceso
administrativo y ciclo histórico. Recién después conviene iniciar el modelo de
actividad académica del Corte B.
