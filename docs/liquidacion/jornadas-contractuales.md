# Jornadas contractuales

> Actualizado: 05/09/2026

Primera etapa: configuracion y consulta, sin integracion automatica con EGES.

## Que cambia al desplegar esta etapa

- Se habilita la tabla y la interfaz para registrar versiones de jornada desde agosto de 2026.
- La configuracion queda disponible para consulta por fecha y conserva historial de versiones.
- Las advertencias EGES ya existentes no desaparecen al crear una jornada.
- Los cruces anteriores, validaciones, correcciones PACS y montos persistidos no se reinterpretan ni se modifican.

## Accesos

- Administracion: Sesiones contables > Jornadas contractuales.
- Jefes e instructores: Mis registros > Mi jornada contractual (solo lectura propia).
- Superusuario y jefe_servicio pueden crear versiones.
- Administrativo necesita el permiso `liquidacion.gestionar_jornadas_contractuales` para crear; sin el permiso puede consultar.
- Django Admin muestra el historial en solo lectura. La escritura usa el servicio transaccional.

## Carga

Seleccionar la cuenta real del profesional, confirmar los siete dias y la vigencia desde el 01/08/2026. Cada dia admite hasta dos tramos. Sin jornada es una declaracion explicita; no se infiere de campos vacios. Un profesional sin version configurada figura como Sin jornada configurada.

Agenda informada por el usuario, pendiente de cargar vinculada a las cuentas correctas:

| Profesional | Dias y horarios desde agosto 2026 |
| --- | --- |
| Arianne Gonzalez Carriel | Lunes y martes 08:00-13:00; miercoles 08:00-18:00 |
| Maria Alejandra Maldonado | Lunes, jueves y viernes 08:00-14:00 |
| Camilo Gavilanes Ibarra | Miercoles 08:00-18:00; jueves y viernes 08:00-13:00 |

No se crean asignaciones por similitud de nombre ni se modifican usuarios o registros existentes mediante la migracion.

## Versiones e historial

Nueva version conserva la agenda anterior y cierra su vigencia el dia anterior al nuevo inicio, registrando autor y fecha. Solo se permiten inicios posteriores a la ultima version, para no reemplazar periodos previos silenciosamente. Una agenda equivocada que requiera rectificar el mismo inicio necesita un flujo de rectificacion futuro: no editar directamente la base.

`crear_jornada_contractual` bloquea la cuenta del profesional dentro de `transaction.atomic()`, incluso para la primera version. `jornada_para_fecha` consulta la version aplicable. La semana se guarda como JSON validado de siete dias (0=lunes, 6=domingo), con intervalos HH:MM y lista vacia para dias sin jornada. No hay tramos nocturnos que crucen medianoche en esta etapa.

## Preservacion de liquidacion

Guardar una jornada no cambia horarios, montos, reglas de descuento, sesiones, snapshots EGES ni validaciones existentes. No reprocesa controles consolidados. La agenda aun no modifica el resultado del cruce EGES.

En la siguiente etapa, las ECO generales con Extra Residencia se verificaran contra la jornada vigente y el horario de cada practica EGES. Los Doppler de jefe_residentes e instructor_residentes estan autorizados al 100% incluso dentro de jornada: esa superposicion no debe generar por si sola una advertencia ni justificar otras practicas de un registro mixto. Los casos ya validados deben conservar su decision y snapshot; cualquier nueva evaluacion sera explicita.

## EGES-J: proximo desarrollo

La integracion se desarrollara en pasos controlados:

1. Obtener la jornada vigente para cada profesional y fecha del estudio.
2. Evaluar cada practica ECO contra el horario de EGES, sin mezclar modalidades ni usar una practica Doppler para justificar otra.
3. Agregar una accion administrativa explicita para reanalizar cruces de agosto en adelante.
4. Reanalizar inicialmente solo casos pendientes o sin revision.
5. Mostrar resultado anterior, resultado nuevo, jornada aplicada, horario EGES y motivo.
6. Permitir luego la validacion masiva de los casos justificados mediante el flujo EGES existente.

Ejemplo: si Camilo tiene jueves de 08:00 a 13:00, una ECO general EGES a las 15:00 marcada como Extra Residencia puede quedar justificada por jornada. La misma practica a las 10:00 debe continuar como advertencia para revision. Un Doppler de Camilo conserva liquidacion al 100% aunque sea dentro de 08:00-13:00.

El reanalisis no debe modificar automaticamente `monto_calculado`, `horario`, estudios, paciente ni decisiones ya `VALIDADO` o `DESCARTADO`. Debe guardar trazabilidad y permitir revisar el antes/despues antes de confirmar.

## Flujo operativo transitorio

Hasta que EGES-J este implementado:

1. Cargar la jornada contractual correcta para cada jefe/instructor.
2. No esperar cambios inmediatos en las alertas existentes.
3. Mantener las validaciones y correcciones ya realizadas.
4. Resolver manualmente las advertencias que requieran decision.
5. Aplicar el reanalisis solo cuando este disponible y despues validar los casos justificados.

## Verificacion

`python manage.py test liquidacion.tests_jornadas_contractuales --verbosity=1`

`python manage.py makemigrations --check --dry-run`

Aplicar la nueva migracion antes de abrir Jornadas contractuales. No contiene migracion de datos ni recalculos.
