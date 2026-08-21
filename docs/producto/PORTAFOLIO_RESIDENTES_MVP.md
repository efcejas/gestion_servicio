# Portafolio de residentes - alcance MVP

Estado: Corte A implementado, en rollout exclusivo para superusuarios

Fecha de definición inicial: 14/08/2026

Última auditoría: 18/08/2026

Desde el 21/08/2026, el flag `PORTAFOLIO_SOLO_SUPERUSER` está activo por
defecto. Durante esta validación solo los superusuarios ven y pueden abrir
`Seguimiento de residentes`; el acceso del resto de los perfiles queda oculto
en el navbar y bloqueado en backend.

La implementación efectiva, sus criterios de conteo, permisos actuales y
riesgos pendientes se registran en
[PORTAFOLIO_RESIDENTES_AUDITORIA_2026_08_18.md](PORTAFOLIO_RESIDENTES_AUDITORIA_2026_08_18.md).

## 1. Proposito

Crear una vista longitudinal de la actividad academica y asistencial de cada
residente, alimentada principalmente por informacion que ya existe en el
sistema, y permitir luego el registro y validacion de actividades academicas
que no nacen en otro modulo.

El MVP debe responder tres preguntas:

1. Al residente: `¿Que actividad tengo registrada y como vengo evolucionando?`
2. Al docente: `¿Que actividad y seguimiento tiene cada residente?`
3. Al cierre anual: `¿Cual fue la trayectoria formal del residente en este ciclo?`

No es objetivo inicial construir un sistema curricular completo ni definir
todavia las competencias del programa UBA.

## 2. Decisiones confirmadas

- El instructor puede ver a todos los residentes.
- Jefe de residentes, instructor de residentes y jefe de servicio tienen vista
  longitudinal de todos los residentes.
- La actividad originada en otros modulos se incorpora automaticamente y no se
  vuelve a cargar ni copiar de forma manual.
- Liquidacion aporta solamente cantidades, modalidad y regiones. El Portafolio
  no consulta, calcula, persiste ni muestra montos, tarifas, obras sociales o
  informacion contable.
- La comparacion del residente con su cohorte queda fuera del MVP. Se prioriza
  la evolucion personal y el cumplimiento de actividad.
- El ciclo lectivo comienza el primer dia habil de agosto. La fecha debe
  calcularse para cada año y persistirse en el cierre, no quedar hardcodeada.
- Las guardias se cuentan a partir de publicaciones efectivas del sistema de
  Guardias. Las cancelaciones y modificaciones validadas en ese modulo son la
  fuente de excepciones y deben cambiar el conteo automaticamente.
- Las actividades academicas pueden almacenar certificados y evidencias en S3.
  En esta etapa no se fija un limite institucional de peso, aunque el backend
  debe validar tipo, nombre y resultado de la carga.
- Cada cierre de año lectivo debe producir un documento formal unico e
  inmutable por residente y ciclo.
- Las competencias y requisitos por año se definiran en una etapa posterior,
  buscando coherencia con el programa de la UBA.

## 3. Ubicacion y arquitectura

Crear una aplicacion Django independiente `portafolio`, accesible en:

```text
/portafolio/
```

Navegacion propuesta:

- Residente o egresado: `Docencia > Mi portafolio`.
- Jefe, instructor o jefe de servicio: `Docencia > Seguimiento de residentes`.
- Administrativo del grupo `Administrativo - Docencia`: seguimiento operativo
  de solo lectura, sin contenido clinico sensible.

La aplicacion debe funcionar como capa de agregacion. Las consultas reutilizables
viven en `portafolio/selectors.py` y la construccion de resumenes y cierres en
`portafolio/services.py`. No se debe duplicar la logica de negocio de los modulos
de origen.

## 4. Fuentes automaticas

### 4.1 Perfil y ciclo

Fuente: `accounts.CustomUser`.

Datos utilizables:

- identidad y avatar;
- año de residencia R1-R4;
- fecha de ingreso;
- estado activo o egresado;
- fecha de egreso;
- ciclo academico.

### 4.2 Guardias

Fuente: `control_guardias.AsignacionGuardia`.

Resumen previsto:

- cantidad de guardias cuya fecha ya transcurrio dentro del periodo;
- distribucion por tipo de guardia;
- fechas computadas que correspondan al ciclo.

Una guardia se incorpora cuando:

- fue publicada efectivamente por el sistema de Guardias;
- su `fecha` es anterior a `timezone.localdate()`;
- no quedo cancelada por una excepcion validada;
- se toma el resultado final de cualquier modificacion validada en Guardias.

No se cuentan guardias futuras aunque esten programadas. La fecha actual
tampoco se considera cumplida, porque la guardia puede estar todavia en curso.
El Portafolio no edita ni reinterpreta estados: consume el resultado publicado
y validado por el modulo de origen.

El Portafolio es de solo lectura respecto de Guardias. No distribuye guardias,
no cambia estados y no interviene en ausencias, reemplazos ni cuotas.

El Corte A considera computables los estados `PUBLICADA` y `CUMPLIDA`, siempre
que la fecha ya haya transcurrido. No cuenta borradores, ausencias ni registros
reasignados. Los flujos validados de ausencia y cambio actualizan esas
asignaciones en el módulo de Guardias y, por lo tanto, modifican el conteo sin
intervención del Portafolio.

### 4.3 Preinformes

Fuente: `preinformes.Preinforme`, `RevisionPreinforme` y sus estadisticas.

Resumen previsto:

- cantidad total y finalizada;
- distribucion por tipo de estudio y region;
- evolucion mensual;
- puntuaciones y evaluaciones publicadas cuando correspondan;
- estado de actividad reciente.

No se muestran datos identificatorios del paciente ni texto clinico en tableros
agregados. Los registros demo quedan excluidos.

### 4.4 Estudios registrados

Fuente: `liquidacion.RegistroEstudiosPorMedico` y los estudios asociados.

Resumen permitido:

- cantidad de registros realizados;
- cantidad y nombre de las practicas asociadas;
- modalidad;
- cantidad o agrupacion por regiones;
- evolucion por periodo.

Frontera de seguridad obligatoria:

- no seleccionar ni serializar `monto_calculado`;
- no seleccionar, serializar ni mostrar nombre, DNI, historia clinica u otro
  dato identificatorio del paciente;
- no exponer precios, tarifas, descuentos o liquidaciones;
- no modificar registros ni recalcular montos;
- no usar informacion economica para ningun indicador academico;
- no vincular el Portafolio con estados contables.

La consulta debe implementarse con un selector especifico que proyecte solo
los campos permitidos, en vez de entregar instancias completas al template.

### 4.5 Clases

Fuente: `clases_residentes.ClaseResidente`.

Resumen previsto:

- clases creadas o presentadas;
- fecha y categoria;
- material asociado mediante enlace al modulo de origen;
- evolucion por periodo.

Visitas y favoritos no se consideran indicadores formativos en el MVP.

### 4.6 Nuevas fuentes

Otros modulos podran agregarse mediante nuevos selectores si representan
actividad academica o asistencial. Cada integracion debe definir:

- responsable del dato;
- criterio de inclusion;
- fecha academica;
- campos visibles;
- tratamiento al corregir o eliminar el registro de origen;
- restricciones de privacidad.

## 5. Actividad academica sin modulo de origen

Luego de validar el tablero agregado se incorpora `ActividadAcademica` para:

- cursos;
- congresos y jornadas;
- ateneos o presentaciones no registradas como clase;
- publicaciones, posters y trabajos cientificos;
- rotaciones externas no cubiertas por otro flujo;
- actividad docente;
- otra actividad academica.

Campos minimos:

- residente;
- tipo;
- titulo;
- fecha de realizacion;
- institucion o ambito opcional;
- descripcion breve opcional;
- evidencia o enlace opcional;
- estado: borrador, enviado, validado u observado;
- docente validador y comentario;
- timestamps de auditoria.

No se incluyen inicialmente horas curriculares, creditos, competencias,
rubricas complejas ni multiples aprobadores. Se agregaran solamente cuando el
programa formativo defina una necesidad concreta.

## 6. Permisos del MVP

| Capacidad | Residente activo | Egresado | Instructor/Jefe | Administrativo Docencia |
|---|---:|---:|---:|---:|
| Ver portafolio propio | Si | Si, lectura | Si | No |
| Registrar actividad propia | Si | No | No | No |
| Ver todos los residentes | No | No | Si | Si, resumen operativo |
| Ver evaluaciones formativas | Propias publicadas | Historicas | Si | Solo indicadores autorizados |
| Validar actividad academica | No | No | Si | No |
| Generar cierre anual | No | No | Si | No inicialmente |

Todo permiso se valida en backend. La navegacion solo refleja permisos; no es
un control de acceso.

## 7. Indicadores iniciales

### Residente

- actividad total del ciclo por fuente;
- preinformes finalizados y su evolucion mensual;
- estudios por modalidad y region;
- guardias computadas por tipo;
- clases presentadas;
- actividades academicas validadas y pendientes;
- ultima actividad registrada;
- evolucion de evaluaciones propias, si existen.

Las evaluaciones no condicionan el primer tablero. Hasta definir periodicidad,
modalidad y reglas de publicacion, se muestran solamente las devoluciones ya
existentes cuya visibilidad para el residente este resuelta en el modulo de
origen; no forman parte obligatoria del cierre formal.

### Docente

- total de residentes activos por año;
- ultima actividad por residente;
- volumen del ciclo desglosado por fuente;
- actividades pendientes de validar;
- residentes sin actividad reciente;
- acceso al detalle longitudinal individual.

No se implementan ranking, percentiles, semaforos de rendimiento ni comparacion
con la cohorte hasta definir su finalidad pedagogica y evitar interpretaciones
incorrectas.

## 8. Cierre anual formal e inmutable

Cada residente tendra como maximo un cierre formal por ciclo academico. El
cierre debe capturar una fotografia de los datos visibles en ese momento, sin
depender de consultas futuras a registros que puedan cambiar.

Contenido minimo del snapshot:

- identidad y año del residente;
- periodo cubierto y fecha de emision;
- resumen numerico por cada fuente;
- desglose academico permitido;
- actividades academicas validadas;
- evaluaciones que se hayan definido como publicables;
- responsables de emision;
- version del formato del documento.

Persistencia prevista:

- datos estructurados del snapshot;
- PDF formal generado;
- hash criptografico del archivo;
- usuario y fecha de generacion;
- restriccion unica por residente y ciclo;
- bloqueo de edicion y eliminacion desde los flujos normales.

La correccion excepcional de un documento emitido requiere un procedimiento
administrativo auditado que se definira antes de implementar cierres. No debe
resolverse permitiendo editar el snapshot original.

El cierre anual se diseña desde el inicio, pero se implementa despues de validar
los indicadores y las fuentes del tablero. Asi se evita congelar formalmente un
resumen aun inmaduro.

El periodo comienza el primer dia habil de agosto y finaliza inmediatamente
antes del primer dia habil de agosto siguiente. El calculo debe contemplar fines
de semana y el calendario de feriados aplicable. La fecha exacta de inicio y fin
queda guardada dentro del snapshot para preservar el criterio usado en ese
cierre, aunque el calendario se modifique posteriormente.

## 9. Wireframes funcionales

### 9.1 Mi portafolio

```text
┌──────────────────────────────────────────────────────────────────────┐
│ Mi portafolio                 R2 · Ciclo 2026/27                     │
│ Nombre del residente          En curso                              │
├──────────────────────────────────────────────────────────────────────┤
│ Preinformes │ Estudios │ Guardias │ Clases │ Actividades academicas │
│     124     │   286    │    18    │   4    │       3 validadas      │
├──────────────────────────────────────────────────────────────────────┤
│ Evolucion del ciclo                    │ Pendientes                  │
│ [grafico mensual por fuente]           │ 1 actividad en revision    │
│                                        │ 2 devoluciones nuevas      │
├──────────────────────────────────────────────────────────────────────┤
│ Actividad reciente                     │ [Registrar actividad]      │
│ • Preinforme finalizado                                           │
│ • Guardia realizada                                               │
│ • Clase presentada                                                │
└──────────────────────────────────────────────────────────────────────┘
```

Los indicadores abren su desglose. La actividad enlaza al modulo de origen y
no replica pantallas operativas.

### 9.2 Registrar actividad academica

```text
┌─────────────────────────────────────────────────────┐
│ Registrar actividad academica                       │
├─────────────────────────────────────────────────────┤
│ Tipo *                 [Curso                 ▼]     │
│ Titulo *               [_______________________]     │
│ Fecha *                [__/__/____]                  │
│ Institucion            [_______________________]     │
│ Descripcion breve      [_______________________]     │
│ Evidencia o enlace     [Adjuntar] [URL_________]     │
├─────────────────────────────────────────────────────┤
│ [Guardar borrador]                 [Enviar a validar]│
└─────────────────────────────────────────────────────┘
```

No solicita datos que ya existan en otro modulo. Si la actividad es una clase
registrada, se muestra desde Clases y no se vuelve a cargar.

### 9.3 Seguimiento de residentes

```text
┌──────────────────────────────────────────────────────────────────────┐
│ Seguimiento de residentes                                           │
│ Buscar [____________]  Año [Todos ▼]  Actividad [Todos ▼]           │
├──────────────────────────────────────────────────────────────────────┤
│ Residente    Año  Preinf. Estudios Guardias Clases Pend. Ult. act.  │
│ A. Perez     R1      82      140      12      2     1   hace 2 dias │
│ B. Gomez     R2     124      286      18      4     0   hoy         │
├──────────────────────────────────────────────────────────────────────┤
│ Alertas operativas: 3 sin actividad reciente · 5 validaciones       │
└──────────────────────────────────────────────────────────────────────┘
```

La tabla no muestra montos, datos de pacientes ni contenido de informes. Cada
fila abre el perfil longitudinal.

### 9.4 Perfil docente del residente

```text
┌──────────────────────────────────────────────────────────────────────┐
│ ← Residentes   A. Perez · R1 · Ciclo 2026/27                        │
├──────────────────────────────────────────────────────────────────────┤
│ Resumen │ Asistencial │ Academico │ Evaluaciones │ Cierres          │
├──────────────────────────────────────────────────────────────────────┤
│ Indicadores del ciclo              │ Evolucion mensual              │
│ Preinformes 82 · Estudios 140      │ [grafico]                      │
│ Guardias 12 · Clases 2             │                                │
├──────────────────────────────────────────────────────────────────────┤
│ Actividades por validar                                             │
│ Curso de...       12/08/2026       [Revisar]                        │
├──────────────────────────────────────────────────────────────────────┤
│ Historial de actividad y evaluaciones                               │
└──────────────────────────────────────────────────────────────────────┘
```

La pantalla existente `perfil_residente_docente` de Preinformes debe integrarse
gradualmente como fuente o seccion de este perfil, no mantenerse como un perfil
docente paralelo.

## 10. Entregas recomendadas

### Corte A - lectura y validacion de utilidad

- crear aplicacion y permisos;
- agregar navegacion;
- implementar `Mi portafolio`;
- implementar `Seguimiento de residentes` y perfil individual;
- integrar Accounts, Guardias, Preinformes, Liquidacion y Clases;
- probar privacidad, conteos, desktop y mobile.

No incluye modelos academicos nuevos ni cierre PDF.

### Corte B - gestion academica minima

- actividad academica manual;
- certificado o evidencia opcional almacenado en S3;
- envio, validacion y observacion;
- bandeja docente de pendientes;
- integrar la actividad validada al resumen.

### Corte C - cierre anual

- definir contenido formal definitivo;
- crear snapshot estructurado;
- generar y almacenar PDF;
- hash y bloqueo de mutaciones;
- permisos y pruebas de unicidad e inmutabilidad.

### Evolucion posterior

- competencias y requisitos alineados con UBA;
- objetivos formativos;
- modulo de evaluaciones creado por instructores, con examenes choice y de
  desarrollo, soporte para imagenes, programacion, correccion y resultados;
- rotaciones con flujo propio si resulta necesario;
- comparaciones de cohorte solo con criterio pedagogico acordado.

## 11. Criterios de exito del MVP

- El residente encuentra en un solo lugar su actividad existente.
- El docente puede revisar a cualquier residente sin entrar manualmente a cada
  modulo.
- Los conteos coinciden con las fuentes y explican su criterio.
- Ninguna pantalla ni payload del Portafolio expone montos o datos de pacientes.
- No se modifica el comportamiento de los modulos de origen.
- La interfaz es util en mobile y desktop.
- El alcance permite incorporar el cierre anual sin rehacer las fuentes de datos.

## 12. Decisiones pendientes para los siguientes cortes

1. Definir el alcance definitivo de `Administrativo - Docencia` sobre el
   detalle individual agregado.
2. Definir navegación de ciclos históricos y el ciclo inicial para egresados.
3. Definir que evaluaciones se consideran publicadas y cuales pueden entrar al
   documento formal.
4. Definir mas adelante si ciertos certificados requieren validacion docente o
   una categoria documental especifica. Para el Corte B se prevé utilizar S3;
   el modelo y el flujo de carga todavía no están implementados.

## 13. Definiciones futuras que no bloquean el MVP

### Evaluaciones y examenes

La periodicidad y modalidad de las evaluaciones queda pendiente. Como evolucion
posible se contempla un modulo independiente para que instructores creen y
programen examenes:

- preguntas de opcion multiple;
- preguntas de desarrollo;
- casos con imagenes;
- reglas de disponibilidad e intentos;
- correccion manual o automatica segun el tipo de pregunta;
- publicacion controlada de resultados;
- incorporacion de resultados publicados al Portafolio y al cierre anual.

Este modulo no debe formar parte del primer desarrollo de Portafolio. Portafolio
solo necesitara una interfaz de integracion futura para consumir resultados ya
publicados, del mismo modo que consume actividad de los modulos actuales.

### Evidencias adjuntas

Las actividades academicas aceptaran desde el MVP un certificado o evidencia
opcional almacenado en S3, ademas de un enlace y una descripcion. No se fija un
limite institucional de peso en esta etapa. El formulario y el backend deben
validar que el archivo sea realmente recibido, conservar el nombre seguro y
restringir su descarga a los permisos del Portafolio.
