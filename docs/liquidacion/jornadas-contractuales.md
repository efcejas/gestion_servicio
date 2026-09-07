# Jornadas contractuales

> Actualizado: 07/09/2026

Configuracion historica e integracion explicita con el control EGES desde agosto de 2026.

## Accesos

- Administracion: Sesiones contables > Jornadas contractuales.
- Jefes e instructores: Mis registros > Mi jornada contractual, en modo de consulta propia.
- Superusuario y jefe_servicio pueden crear versiones.
- Administrativo necesita `liquidacion.gestionar_jornadas_contractuales` para crear; sin ese permiso puede consultar.
- Django Admin conserva el historial en solo lectura. La escritura usa el servicio transaccional.

## Carga

Se debe seleccionar la cuenta real del profesional, declarar los siete dias y usar una vigencia desde el 01/08/2026. Cada dia admite hasta dos tramos. Una lista vacia declara expresamente que ese dia no existe jornada; no equivale a una jornada sin configurar.

Agenda informada, pendiente de vincular a las cuentas correctas en cada ambiente:

| Profesional | Dias y horarios desde agosto 2026 |
| --- | --- |
| Arianne Gonzalez Carriel | Lunes y martes 08:00-13:00; miercoles 08:00-18:00 |
| Maria Alejandra Maldonado | Lunes, jueves y viernes 08:00-14:00 |
| Camilo Gavilanes Ibarra | Miercoles 08:00-18:00; jueves y viernes 08:00-13:00 |

No se asignan cuentas por similitud de nombre ni se modifican usuarios o registros mediante la migracion.

## Versiones

Una nueva version conserva la anterior y cierra su vigencia el dia previo al nuevo inicio. Se registra autor, fecha y observacion. Solo se permiten inicios posteriores a la ultima version para impedir reemplazos historicos silenciosos.

`crear_jornada_contractual` bloquea la cuenta del profesional dentro de `transaction.atomic()`. `jornada_para_fecha` obtiene la version aplicable. La semana se almacena como JSON validado de siete dias, con intervalos `HH:MM`; no se admiten tramos que crucen medianoche.

## J1 - Evaluacion de jornada

`evaluar_horario_en_jornada` devuelve un diagnostico serializable y no realiza escrituras:

- `DENTRO`: el turno esta contenido completamente en un tramo contractual.
- `FUERA`: el turno esta completamente fuera o el dia fue declarado sin jornada.
- `MANUAL`: falta una hora confiable, el intervalo es invalido o atraviesa el limite de un tramo.
- `SIN_CONFIGURACION`: no existe una version vigente para la fecha.
- `NO_APLICA`: la jornada no corresponde al profesional o a la practica evaluada.

El resultado incluye profesional, fecha, dia, horario EGES, version aplicada, tramos y motivo.

## J2 - Integracion con ECO

La jornada se aplica solamente cuando el administrativo ejecuta el reanalisis:

- ECO general con override Extra Residencia y fuera de jornada: espera `EXTRA`.
- ECO general con override y dentro de jornada: espera `INTRA` y mantiene la advertencia.
- Sin jornada vigente o con un intervalo que cruza un limite: requiere revision manual.
- Doppler y ECOCAR de jefe/instructor no usan la jornada para definir descuento y conservan liquidacion al 100%, incluso sin marcar el override.
- En registros mixtos, una practica Doppler no justifica una ECO general sin coincidencia.

Ejemplo: Camilo tiene jueves 08:00-13:00. Una ECO general a las 15:00 marcada como Extra Residencia queda justificada; la misma ECO a las 10:00 permanece como advertencia. Un Doppler a las 10:00 conserva su regla propia.

## J3 - Reanalisis explicito

En sesiones `REVISION` o `CERRADA`, desde agosto de 2026, la accion **Reanalizar con jornadas** crea una nueva version de `ControlEgesSesion` para el batch seleccionado.

- No cambia `RegistroEstudiosPorMedico`.
- No modifica horarios, estudios, pacientes ni `monto_calculado`.
- No llama a `calcular_monto()`.
- No reemplaza controles anteriores.
- Las revisiones administrativas previas se conservan; si existia un resultado consolidado para ellas, se copia en la nueva version.
- Al volver a entrar al mismo batch, el preview reconoce que el ultimo control usa jornadas.

## J4 - Revision operativa

El preview muestra el estado de jornada, sus tramos y la comparacion entre el control anterior y el actual. El filtro **Jornada** permite aislar:

- Extra justificado.
- Dentro de jornada.
- Cruce manual.
- Sin configuracion.
- Doppler / no aplica.

Flujo recomendado para regularizar advertencias anteriores:

1. Cargar las jornadas correctas.
2. Abrir el cruce EGES de la sesion y seleccionar el batch correspondiente.
3. Ejecutar **Reanalizar con jornadas**.
4. Filtrar `Jornada = Extra justificado` y `Revision = Sin revisar`.
5. Revisar el antes/despues.
6. Ejecutar **Validar OK visibles**.
7. Resolver manualmente los casos dentro de jornada, sin configuracion o con intervalos ambiguos.

## Verificacion

```bash
python manage.py test liquidacion.tests_jornadas_contractuales --verbosity=1
python manage.py test liquidacion.tests_cruce_eges --verbosity=1
python manage.py makemigrations --check --dry-run
```
