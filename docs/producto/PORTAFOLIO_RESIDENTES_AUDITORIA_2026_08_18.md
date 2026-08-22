# Auditoría del Portafolio de residentes

Fecha: 18/08/2026

Actualización de rollout: 21/08/2026

Actualización de ciclos históricos: 21/08/2026

Actualización de acceso por roles: 22/08/2026

Estado auditado: Corte A implementado, abierto a residentes y docentes de residencia

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
validación docente, evaluaciones ni el cierre anual formal e inmutable.

No se detectaron bloqueantes críticos para continuar la validación del tablero.
Antes de ampliar el acceso o implementar cierres deben resolverse las brechas
prioritarias de la sección 8.

### Rollout actual

El flag `PORTAFOLIO_SOLO_SUPERUSER` está inactivo por defecto. La apertura
vigente habilita:

- `Mi portafolio` para usuarios con rol `medico_residente`;
- `Seguimiento de residentes`, detalle y trayectoria para jefes de residentes
  e instructores;
- seguimiento completo para superusuarios.

Staff, jefe de servicio y administrativos permanecen ocultos y bloqueados por
backend. El flag se conserva como reversa operativa: con valor `True`, el
módulo vuelve a quedar disponible únicamente para superusuarios.

## 2. Inventario implementado

### Rutas

| Ruta | Finalidad |
|---|---|
| `/portafolio/` | Portafolio propio del residente o egresado con cuenta activa. |
| `/portafolio/residentes/` | Listado docente de residentes. |
| `/portafolio/residentes/<id>/` | Resumen longitudinal individual. |
| `/portafolio/residentes/<id>/?ciclo=<año>` | Detalle reconstruido de un ciclo específico. |
| `/portafolio/residentes/<id>/trayectoria/` | Acumulado y comparación entre ciclos. |

### Arquitectura

- `portafolio/selectors.py`: período académico y consultas agregadas.
- `portafolio/services.py`: composición del resumen de una persona.
- `portafolio/views.py`: autorización y renderizado.
- `templates/portafolio/`: resumen individual y seguimiento docente.
- `accounts/context_processors.py`: acceso desde el navbar según rol o grupo.

El módulo no tiene modelos ni migraciones propias en este corte. Toda la
información se obtiene en tiempo real desde las fuentes existentes.

## 3. Acceso funcional vigente

| Perfil | Propio | Listado | Detalle de otros |
|---|---:|---:|---:|
| Residente activo | Sí | No | No |
| Egresado con rol `medico_residente` y cuenta activa | Sí | No | No |
| Jefe de residentes | No | Sí | Sí |
| Instructor de residentes | No | Sí | Sí |
| Jefe de servicio | No | No | No |
| Superusuario | No | Sí | Sí |
| Grupo `Administrativo - Docencia` | No | No | No |
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

El detalle permite seleccionar el ciclo mediante su año de inicio. La lista de
períodos comienza en `fecha_ingreso_residencia`; si ese dato falta, utiliza la
primera actividad encontrada en las cuatro fuentes y, si tampoco existe,
presenta solamente el ciclo vigente.

Para residentes activos, la trayectoria llega hasta el ciclo actual. Para
egresados con fecha de egreso, finaliza en el ciclo que contiene esa fecha. La
vista acumulada incluye el ciclo en curso y diferencia visualmente los períodos
cumplidos. Para 2026/27 el inicio calculado es el 03/08/2026 y el fin inclusivo
es el 01/08/2027, salvo que el calendario de feriados registrado modifique esas
fechas.

Los ciclos históricos se reconstruyen en tiempo real desde los módulos de
origen. No equivalen a un cierre formal ni garantizan inmutabilidad hasta que se
implemente el Corte C.

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

La suite `portafolio` contiene 25 pruebas y cubre:

- inicio del ciclo en el primer día hábil de agosto;
- consideración de feriados registrados;
- guardias publicadas pasadas y exclusión de futuras o reasignadas;
- proyección de Liquidación sin pacientes ni montos;
- ausencia de datos sensibles en el HTML;
- diferencia entre residente sin año informado y egresado;
- bloqueo del acceso entre residentes;
- acceso de jefe de residentes e instructor;
- denegación a staff, jefe de servicio y administrativos;
- acceso de superusuario durante el rollout restringido;
- bloqueo de residente e instructor mediante URL directa durante el rollout;
- ocultamiento del acceso en el navbar para perfiles no habilitados.
- selección validada de un ciclo anterior;
- acumulado de trayectoria entre ciclos sin pacientes ni montos;
- rechazo con `404` de períodos ajenos a la trayectoria disponible.
- límite hasta la fecha actual para estudios, clases y otras fuentes fechadas
  del ciclo en curso.

En la actualización de acceso del 22/08/2026 se ejecutaron exitosamente:

```text
python manage.py test portafolio
python manage.py check
```

## 8. Hallazgos y riesgos pendientes

### Prioridad alta antes de ampliar el alcance

1. **Contrato de staff y administrativos.** Permanecen bloqueados hasta definir
   qué perfiles necesitan acceso y si corresponde mostrarles el mismo detalle
   agregado que a un instructor o una vista más limitada.
2. **Los ciclos reconstruidos no son cierres.** La navegación histórica y el
   acumulado consultan los datos actuales de cada fuente. No deben presentarse
   como documentos inmutables ni reutilizarse como sustituto del snapshot,
   hash, PDF y fecha de corte previstos para el Corte C.

### Prioridad media para robustecer el Corte A

1. Confirmar si Preinformes debe pertenecer al ciclo por fecha de creación o
   por una fecha asistencial diferente.
2. Definir si el listado docente debe incluir residentes inactivos o con perfil
   incompleto, y mantener el mismo criterio en la URL de detalle.
3. Agregar pruebas para egresados y límites exactos de cada fuente.
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
| A - lectura y utilidad | Implementado, apertura inicial | Validar conteos y uso real con residentes y docentes. |
| B - gestión académica | No iniciado | Actividad manual, S3, envío, validación y observaciones. |
| C - cierre anual | No iniciado | Snapshot, PDF, hash, unicidad, inmutabilidad y corrección auditada. |

## 10. Próximo paso recomendado

Validar con residentes, jefes de residentes e instructores que los conteos, la
separación por ciclo y la navegación respondan a sus necesidades. Luego se
podrá definir el acceso de staff y administrativos antes de ampliar nuevamente
la matriz.
