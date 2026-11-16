# Análisis previo para completar EGES y Netterm

## Estado verificado el 14/11/2026

La rama `feature/liquidacion-copilot-specialization` local coincide con la rama
consultada mediante el conector GitHub, en `574f9470c34aeabf0002d01a2f8b8fbe6ccc8f3c`.
El árbol local estaba limpio al iniciar el análisis.

Los commits `010cc1ec` y `04045a10` incorporaron el cierre TC y las estadísticas
conciliadas, respectivamente. La descripción anterior que señalaba ambas
integraciones como pendientes quedó desactualizada.

La suite de `eges_import`, `liquidacion.tests_cruce_eges`,
`liquidacion.tests_respaldo_fuentes` y `liquidacion.tests_checklist_cierre`
pasó con 282 pruebas. `makemigrations --check --dry-run` informó que el esquema
está actualizado. La ejecución utilizó SQLite en memoria y comprobó su
configuración efectiva antes de iniciar Django.

## Hallazgos

### 1. Las decisiones humanas pierden efecto al consultar un período

Reproducción con datos sintéticos del mismo mes y los mismos lotes

| Consulta | Prácticas aceptadas | Vínculos humanos consumidos |
|---|---:|---:|
| Producción, selección completa | 1 | 1 |
| Producción, fechas del mes | 0 | 0 |
| Tablero, fechas del mes | 0 | 0 |

Se crearon dos filas EGES recepcionadas y una fila Netterm realizada con la
misma identidad candidata. Se guardó VINCULAR contra la segunda fila EGES.
La decisión confirmó una práctica al evaluar la selección completa. El filtro
por fechas del mismo mes volvió a presentar el caso como pendiente.

`services_produccion._decisiones_vigentes` depende de `permite_revision` y de
la firma de la consulta completa. `services_conciliacion` habilita esa bandera
para un lote EGES sin filtros temporales o de modalidad. El filtro cambia
también la firma. La escritura de auditoría y su aplicación posterior tienen
que contar con reglas independientes de presentación.

La corrección debe conservar la validez de la pareja y la evidencia de origen,
además de resolver conflictos uno a uno al combinar lotes. Requiere pruebas
de períodos, modalidades, múltiples lotes y reemplazos de decisiones.

### 2. El respaldo profesional evalúa nuevamente las candidatas automáticas

`construir_preview_respaldo_fuentes` construye sus índices desde la conciliación
automática. En su implementación actual las decisiones guardadas de
`ConciliacionRevision` carecen de un paso de aplicación en esa evaluación.
En el escenario sintético anterior, el registro profesional quedó REVISAR por
tener varias candidatas después de haber guardado una vinculación de origen.

La correspondencia entre fuentes debe alimentar el respaldo como evidencia
reutilizable. La atribución al profesional y la unicidad entre líneas siguen
requiriendo comprobación propia. Vincular EGES y Netterm puede aportar evidencia
para resolver una excepción profesional cuando las restantes condiciones se
cumplen.

### 3. Checklist y transición de sesión tienen comprobaciones distintas

`construir_checklist_cierre_sesion` consulta el resumen EGES y respaldo TC.
`sesion_contable_transicion` consulta la auditoría de consistencia y el requisito
RRHH para facturar. El resumen de respaldo carece de una consulta equivalente
en esa transición.

Esto es una diferencia de comportamiento verificada por lectura del código.
Su tratamiento requiere acordar el efecto operativo de los pendientes de origen
al cerrar o facturar, respetando el flujo de revisión y sus excepciones. La
modificación de esa política debe quedar explícita y probada en el endpoint
de transición.

### 4. Falta medir el recorrido con volumen representativo

El lector conserva límites de 10 MB y 20.000 filas y acumula las filas analizadas.
El cruce admite 50.000 observaciones. El resumen del cierre reconstruye previews
por cada combinación histórica de lotes que tenga confirmaciones guardadas.

La medición pendiente debe registrar tiempo, memoria y consultas para importación,
tablero con comparación temporal, respaldo, confirmación y reapertura del panel.
Los resultados permitirán decidir si alcanza con optimizar esas operaciones.
Las pruebas actuales acreditan comportamiento funcional con datos sintéticos.

## Secuencia para finalizar

1. Corregir el uso de decisiones por pareja a través de filtros y selecciones.
2. Reutilizar esa correspondencia en el respaldo profesional y cubrir sus excepciones.
3. Definir y alinear el efecto de los pendientes en panel y transición de sesión.
4. Calibrar con exportaciones representativas y registros profesionales autorizados,
   incluyendo internación, fechas diferentes y RX con subsiguientes.
5. Recorrer importación, revisión, estadísticas, PDF, respaldo y cierre en pantalla,
   verificando cantidades, horarios y montos históricos en cada paso.

Este análisis generó únicamente este documento. Las comprobaciones se ejecutaron
en bases efímeras. La revisión del entorno desplegado y la medición de volumen
productivo quedan pendientes.

## Decisiones y cambios posteriores durante la revisión por voz

El usuario indicó contar estudios realizados con informe definitivo, por mes
de realización. Autorizó aplicar el criterio al tablero y al respaldo de
Liquidación, manteniendo la correspondencia entre fuentes para evitar duplicados.
El trabajo se trasladó a `feature/eges-netterm` por indicación del usuario.

### Implementación local

- Corrección del número de turno EGES mediante coincidencia explícita de encabezado.
- Producción V2 resuelve las correspondencias en los lotes completos antes de
  aplicar fechas. Esto permite trasladar un estudio compartido a noviembre cuando
  su pedido y turno EGES están en octubre y Netterm acredita realización en noviembre.
- La inclusión exige informe definitivo. EGES «Informado» acredita ese estado.
  Netterm requiere fecha de realización, estado definitivo y ausencia de anulación
  o pendiente de realización.
- Para una coincidencia válida se usa la fecha de realización Netterm. En estudios
  respaldados únicamente por EGES se conserva la fecha de turno como referencia
  disponible. Esa es una aproximación que debe considerarse al interpretar los datos.
- Una anulación contradictoria conserva el tratamiento anterior de excepción y
  prioridad de la evidencia EGES. Requiere revisión del caso.
- Estadísticas, agrupación temporal y PDF usan la fecha de producción resultante.
  El período inferido desde Netterm usa fechas de realización.
- El respaldo profesional V2 exige estado definitivo y fecha de realización en la
  sesión correspondiente. El contraste con la fecha declarada por el profesional
  sigue siendo exacto. Diferencias entre fecha de informe y realización pueden
  dejar un caso pendiente.
- Las firmas de respaldo incluyen la nueva versión. Las confirmaciones anteriores
  requieren revalidación con este criterio. Los importes, cantidades, horarios y
  estados de sesión permanecen conservados por el servicio de respaldo.
- Los pendientes diagnósticos abarcan los lotes completos. El total de producción
  se filtra por su fecha resultante. La tasa calculada sobre esta población de
  estudios finalizados será 100%; su eventual uso para medir finalización del
  circuito completo requiere definir otro denominador.

### Calibración con los tres archivos suministrados

Importación real del Excel EGES ECO y ambos Netterm, exclusivamente en SQLite
en memoria, comprobada antes de migrar e importar. Se comparó el conteo anterior
extraído del commit de la rama con el código local nuevo.

| Octubre | Anterior | Nuevo |
|---|---:|---:|
| Prácticas únicas conciliadas | 4.392 | 4.319 |
| Base EGES | 3.696 | 3.625 |
| Aporte Netterm | 696 | 694 |
| Pacientes únicos identificables | 2.664 | 2.627 |
| Informes confirmados | 4.347 | 4.319 |

Los mismos archivos aportan 28 prácticas a noviembre con el criterio nuevo.
Ese valor corresponde únicamente a estos archivos, cuyo pedido es de octubre.
El conteo del tablero coincidió con el servicio de producción.

Continúan 55 observaciones pendientes de modalidad y 161 de correspondencia,
además de estados incompletos. Estos totales son diagnósticos de los lotes
seleccionados. Las correspondencias ambiguas se conservan para revisión.

La base local habitual se consultó mediante SQLite en modo de solo lectura y
carece de sesión de octubre de 2026. El impacto sobre registros profesionales
reales de ese mes queda pendiente de una fuente autorizada disponible.

Validación del código funcional: 289 pruebas OK de EGES, cruce, respaldo y
checklist en memoria, incluyendo desplazamiento entre meses y exclusión de
respaldo sin informe definitivo. La última edición posterior agregó metadatos
descriptivos y una aclaración de alcance en la plantilla. `makemigrations
--check --dry-run` informó ausencia de cambios de esquema. La publicación y
verificación visual del ajuste quedan pendientes.

## Circuito de validación implementado posteriormente

El usuario solicitó coincidencias automáticas, revisión conjunta de excepciones
y consumo del resultado aprobado desde el dashboard. Se agregó la pantalla
«Validar producción EGES + Netterm». Las decisiones disponibles para cada excepción
son vincular una candidata EGES, aceptar como adicional independiente o excluir
del aporte Netterm. Las casillas permiten aplicar acciones a todas las filas
seleccionadas. La vinculación conjunta sólo elige cuando hay una candidata única;
las selecciones competidoras se rechazan en el servidor.

La confirmación requiere resolver todas las excepciones elegibles del período.
Los pendientes de realización y los estudios sin informe definitivo conservan
su exclusión. Las versiones divergentes requieren elegir fuentes consistentes
o excluir la observación. Confirmar una adicional significa declarar un estudio
distinto de las candidatas EGES presentadas.

La migración `0013_produccionvalidada` incorpora la selección, período, firma,
decisiones, resultado y actor de confirmación. El resultado guardado se usa para
dashboard y PDF. La consulta web de Netterm pendiente requiere confirmar antes
de generar gráficos. La entrada habitual al dashboard abre la última confirmación
cuando existe. Los enlaces con otra selección permiten iniciar otra validación.
La comparación temporal de una versión aprobada sólo dispone de las prácticas
incluidas en esa versión; consultar otros períodos requiere confirmar su selección.

La suite de EGES, respaldo, cruce y checklist pasó 299 pruebas en una base aislada,
incluyendo publicación HTTP, PDF, idempotencia, permisos y rechazos de confirmación
incompleta o de vínculos competidores. Falta QA visual de las acciones conjuntas.
La tabla se aplicó a la base local durante las pruebas del usuario y se verificó
que el plan global de migraciones estaba vacío. La publicación permanece pendiente.

### Carga única de Netterm

El usuario pidió elegir el archivo una sola vez. La pantalla «Cargar Netterm» envía
la acción `cargar`, analiza el archivo, guarda sus filas mediante el archivo ya
recibido y muestra el resumen y el lote resultante. Ofrece «Cargar otro libro» e
«Ir a validar EGES + Netterm». El motivo de auditoría de esta acción se completa
como «Carga de origen desde la pantalla Netterm», asociado al usuario autenticado.

El contrato anterior de vista previa sin escritura sigue disponible para los
clientes que envían únicamente el archivo. El guardado firmado anterior conserva
su validación de usuario, vencimiento y coincidencia de archivo. La interfaz
habitual utiliza la carga única. El hash conserva la idempotencia de reenvíos.

### Revisión de Doppler MMII bilateral

El usuario autorizó detectar grupos por paciente, fecha de realización y modalidad
vascular, con revisión manual de los casos dudosos. `services_bilateralidad.py`
reutiliza el clasificador de la auditoría de Liquidación y adapta las variantes
Netterm «MM INF» y «miembro inferior» a sus denominaciones reconocidas.

Los documentos se agrupan dentro de su tipo. Venoso y arterial forman grupos
distintos. Las observaciones con fechas distintas conservan su independencia.
La detección requiere varias filas realizadas con informe definitivo. El revisor
elige «Representan un único estudio» o «Son estudios independientes»; también
puede aplicar una decisión al conjunto de grupos mostrados.

Al confirmar un único estudio, el resultado estadístico conserva una fila
representativa, prioriza respaldo EGES cuando existe y guarda referencias a todas
las observaciones Netterm del grupo. Los originales permanecen archivados. Las
decisiones por grupo forman parte de la firma y del resultado aprobado. Los
gráficos y el PDF usan la misma población resultante.

Cuando un grupo carece de candidata EGES y tiene modalidad conocida, elegir una
decisión de grupo completa sus excepciones de identidad vacías como aporte
Netterm. Las candidatas EGES ambiguas conservan su revisión específica.

La comprobación sobre una copia en memoria de la base local detectó 13 grupos
con 28 registros, incluido el caso señalado por el usuario con dos pedidos venosos.
La suite pasó 307 pruebas, cubriendo un bilateral, estudios independientes,
arterial y venoso, fechas distintas, libreta cívica y representación en la vista.
Sin nuevas migraciones para esta revisión. Falta completar la prueba visual local
del recorrido de confirmación.

### Procedimientos guiados y filas complementarias

El usuario indicó contar el acto de intervencionismo ecoguiado dentro de ECO,
con identificación adicional como procedimiento. Al revisar los datos se encontró
que 22 pedidos contienen conjuntamente los códigos 900079 (punción guiada),
150101 (biopsia) y 150111 (citología). Los tres códigos también aparecen en EGES,
por lo que excluir solamente el aporte Netterm deja componentes contados en la base.

La pantalla incorpora «Revisar procedimientos ecoguiados», con decisiones
«Un procedimiento guiado y sus componentes» o «Conservar decisiones por práctica».
La agrupación requiere mismo pedido, documento con tipo y fecha de realización,
además de una punción guiada presente. La decisión es explícita y se guarda en la
confirmación. La acción conjunta permite revisar los pedidos como grupo.

Al elegir un procedimiento se conservan sus originales y se retiran los componentes
del conjunto estadístico aceptado en EGES y Netterm. Las correspondencias EGES
ambiguas deben resolverse expresamente. La punción se identifica en el desglose
ECO como «Procedimientos guiados». La versión de validación cambia a revisión
clínica V4. Las versiones aprobadas anteriores conservan su resultado histórico.

El ensayo aislado con fuentes reales detectó 22 grupos, conservó 23 punciones
guiadas y retiró del conteo 44 componentes, manteniendo iguales las otras decisiones
del ensayo. Este resultado demuestra el efecto de la regla para ese conjunto,
sin constituir la aprobación clínica de cada pedido. La suite pasó 311 pruebas
antes del agregado final de una protección para exigir una punción principal
aceptada y precisar la selección de candidatas principales ambiguas.

El usuario confirmó después que las tres filas describen el acto de intervencionismo
ecoguiado y sus componentes. El desglose estadístico se rotula «Procedimientos
intervencionistas ecoguiados». Se mantiene una unidad por procedimiento confirmado.

### Ecoestrés como práctica de ecocardiografía

El usuario indicó conservar el ecoestrés como práctica propia dentro de ecocardio.
El lector Netterm V4 reconoce las variantes ECOESTRESS, ECOESTRES y ECO ESTRÉS.
La conciliación V9 compara la modalidad calculada actualmente, permitiendo usar
los lotes archivados con una clasificación anterior. Los originales conservan
su contenido. La población estadística conserva la submodalidad del aporte
exclusivo Netterm para ubicarlo correctamente en el gráfico de ecocardio.

Sobre la copia en memoria de los lotes reales se reconocieron los cinco ecoestrés
realizados e informados en octubre. Los casos automáticos pasaron a 4.046 y las
excepciones a 205. No se agrupan con otras prácticas cardíacas por compartir paciente.
La suite con migraciones pasó 315 pruebas. Tras conservar la submodalidad de un
ecoestrés exclusivo Netterm, pasaron las 22 pruebas focales del circuito de
validación, usando esquema de test sincronizado en memoria.

### Revisión guiada por etapas y resumen previo

La validación presenta primero los grupos Doppler, después los procedimientos
ecoguiados y luego las dudas individuales restantes. Las etapas sin casos se
omiten. Se conserva la selección al avanzar y retroceder dentro de la página.
Reanalizar la selección inicia una nueva revisión y requiere volver a elegir
las decisiones que todavía no se confirmaron.

Al confirmar UNICO para un procedimiento, sus componentes con hasta una candidata
EGES quedan resueltos por el grupo y salen de la tabla individual. Su modalidad
individual deja de ser obligatoria. Las correspondencias ambiguas siguen requiriendo
seleccionar su candidata. Cambiar el grupo a INDEPENDIENTES restaura la revisión
individual. El servidor deriva esas mismas decisiones al calcular y confirmar.

El último paso calcula el resumen mediante una consulta POST protegida por CSRF,
valida la firma de fuentes y devuelve totales antes del guardado. La confirmación
se habilita cuando ese cálculo termina correctamente. Las respuestas de cálculos
anteriores se descartan si se modifican las decisiones.

Comprobación sobre copia en memoria de la base local, con el lote EGES de octubre
y los dos lotes Netterm ya cargados. Se obtuvieron 4.046 casos automáticos,
205 excepciones, 13 grupos Doppler y 22 grupos de procedimientos. Simular UNICO
para los procedimientos resuelve 44 componentes y deja 161 filas en la revisión
individual. Estas cifras describen la revisión y requieren las decisiones del
usuario para establecer el total aprobado.

Pasaron 28 pruebas focales del circuito, incluyendo el resumen sin escritura y
el rechazo de decisiones incompletas. La comprobación del JavaScript verificó
avance entre etapas, retiro y restauración de componentes, serialización y
habilitación de la confirmación después del resumen. La revisión visual final
corresponde a la prueba local del usuario.

La comprobación posterior de eges_import, liquidacion.tests_respaldo_fuentes y liquidacion.tests_cruce_eges pasó 273 pruebas con esquema sincronizado en memoria. Los cambios continúan locales en feature/eges-netterm, pendientes de commit y despliegue.

### Comparación con lotes históricos EGES

Se permite ampliar la selección aprobada con lotes EGES cuyas prácticas quedan
fuera del período confirmado. La población combina el resultado guardado del
período con la producción EGES histórica. Si los lotes añadidos aportan prácticas
dentro del período aprobado, se pide integrar y validar esa ampliación.
Los lotes Netterm deben seguir coincidiendo con la versión aprobada. Los filtros
de fechas se respetan. Para mostrar toda la curva histórica hay que ampliar o
vaciar las fechas. Al quitar Netterm, el tablero consulta EGES por su circuito
habitual. El estado identifica la combinación como período confirmado más histórico
EGES.

La tarjeta de prácticas por paciente muestra «No calculable» y la cantidad de
prácticas con identificación incompleta cuando no puede establecer un denominador
completo. Se conserva el conteo de pacientes identificables y el total de prácticas.

En copia en memoria de la base local, la selección de todos los lotes EGES junto
con los dos Netterm aprobados produjo 12.523 prácticas y una curva de mayo, junio y
octubre. La versión aprobada de octubre conserva 4.422 prácticas. Pasaron 54 pruebas
focales, incluidas dos regresiones para ampliar el histórico y detectar solapamiento
con el período aprobado. La plantilla compiló correctamente y git diff --check
no encontró errores de espacios. Falta la comprobación visual del usuario en local.

### Correcciones del tablero y ampliación de identificación estadística

Se recupera COBERTURA y PLAN del lector Netterm V5. Para los lotes ya archivados,
el tablero lee COBERTURA desde la columna original 13 y decodifica la celda tipada.
Se reutiliza la clasificación ECO existente para el aporte Netterm general que
carecía de subtipo y se ordena el gráfico por cantidad descendente.

«Resto fuera del top 10» suma las categorías conocidas que exceden los diez primeros.
Se incorporan detalles desplegables con el nombre y cantidad de cada médico y
cobertura que integra esa suma. Las sumas de todos los grupos conservan el total
de prácticas. La franja horaria incorpora hora_realizacion de Netterm, con turno
EGES como alternativa disponible. Se explica qué representa Sin dato.

Identificación estadística V3, independiente de la elegibilidad del cruce y de las
reglas económicas. Se reconocen documentos LC, LE, CI y pasaporte. Si su número
coincide con un DNI conocido, se exige además nombre normalizado coincidente.
Una historia clínica Netterm asociada a un único DNI permite reconocer al paciente.
Una HC con DNI contradictorios queda pendiente. Los documentos alternativos sin
correspondencia DNI reciben una clave privada por tipo y número. La HC sin documento
puede identificar dentro de Netterm mediante una clave propia. Se rechazan ceros
y valores sin especificar. No se cruza directamente la HC EGES con Netterm, porque
el importador EGES usa DNI como respaldo cuando falta columna de HC.

La misma identificación se aplica al resumen previo y al resultado de nuevas
confirmaciones, versión de revisión clínica V5. Las confirmaciones existentes
conservan su población aprobada. Los indicadores del tablero y PDF se calculan
con la identificación estadística actual. El promedio de prácticas por paciente
identificado divide las prácticas con identidad por los pacientes identificados.
Se indica cuántas prácticas quedaron pendientes de identificación. Esa población
parcial requiere leer la etiqueta del promedio.

Comprobación en memoria sobre las fuentes cargadas. Octubre conserva 4.422 prácticas,
identifica 2.636 pacientes y deja dos prácticas con diferencias de nombre pendientes
de identidad. Antes había 51 sin clave DNI. El subtipo y la cobertura de octubre
quedan completos. El total seleccionado de todos los lotes conserva 12.523 prácticas,
con 6.810 pacientes identificables, 798 prácticas pendientes de identidad y promedio
entre identificados de 1,72. La mayoría de esas identidades pendientes pertenece al
lote histórico EGES sin columna DNI y requiere análisis adicional. Con Netterm se
recuperan todas las horas de producción de la selección ensayada. Las barras del
resto reúnen 77 médicos (5.344 prácticas) y 141 coberturas (4.587 prácticas).

La comparación exige período explícito y usa otro intervalo previo de igual duración.
Se muestran ambos intervalos. Con todos los lotes, junio 1-30 arroja 3.770 prácticas
frente a 4.295 en mayo 2-31. Para octubre no hay fuentes de septiembre cargadas.
Con toda la historia sin fechas se pide definir el intervalo en pantalla.

Las 62 anuladas Netterm están excluidas. El detalle de lectura distingue observaciones
de origen de exclusiones y queda desplegable. Se combinan también los diagnósticos
de los lotes históricos añadidos. Se retira la advertencia basada únicamente en
1.000 filas. Los límites técnicos Netterm existentes de 10 MB, 20.000 filas y
50.000 observaciones de análisis siguen siendo los parámetros del código actual.

Pendiente separado, planteado por el usuario durante esta revisión. Netterm archiva
nuevas observaciones y conserva las previas. EGES evita duplicados pero una fila
existente puede conservar su estado anterior al reimportar un archivo actualizado.
Ese circuito de actualización y la medición de demoras pedido-realización-informe
requieren una implementación posterior específica. El trabajo presente se mantuvo
en los gráficos, identificación y explicaciones del tablero.

Validación final de este bloque. Pasaron 284 pruebas de eges_import, liquidacion.tests_respaldo_fuentes y liquidacion.tests_cruce_eges con esquema sincronizado en memoria. Compilaron la plantilla y el JavaScript del dashboard. git diff --check pasó. Rama feature/eges-netterm con cambios locales pendientes de commit y publicación. La comprobación visual queda a cargo de la prueba local acompañada con el usuario.

### Unificación del ranking médico, revisión del 15 de noviembre

Se confirmó que los nombres del mismo profesional podían quedar separados entre
el top diez y la barra del resto. El tablero normaliza puntuación, acentos,
mayúsculas y orden de palabras usando la normalización profesional existente.
Se incorporaron dos equivalencias explícitas en ALIAS_MEDICOS_ESTADISTICAS,
a partir de los casos señalados por el usuario y de las variantes presentes.
Arianne Carriel González, Denis y Denisse, se agrupa como ARIANNE CARRIEL DENISSE
GONZALEZ. Ana Belén Izurieta con y sin el apellido Penaherrera se agrupa como
ANA BELEN IZURIETA PENAHERRERA. Dayanne permanece como otra profesional.

Estas equivalencias pertenecen al indicador estadístico. La interpretación de
roles profesionales y las identidades económicas conservan sus propias reglas.
Las futuras variantes semánticas requieren una equivalencia comprobada. La
normalización de formato se aplica automáticamente a todos los nombres.

Comprobación con copia en memoria de la base local y todos los lotes seleccionados.
El ranking muestra una sola entrada de Arianne con 1.044 prácticas, Dayanne con 519
y Ana Belén con 279. La suma de las barras médicas coincide con las 12.523 prácticas
del conjunto. Ana Belén integra el resto según su cantidad y las demás producciones
de esa selección. La posición de cada profesional se vuelve a calcular después
de agrupar los nombres. Pasaron 64 pruebas focales de producción y validación.

Verificación posterior de la unificación médica. Pasaron las 286 pruebas de eges_import, liquidacion.tests_respaldo_fuentes y liquidacion.tests_cruce_eges en base de test en memoria con esquema sincronizado. Compilaron los módulos modificados y git diff --check pasó. Cambios locales en feature/eges-netterm, pendientes de commit y publicación. Sigue pendiente la comprobación visual del ranking con el usuario.

### Ampliación del agrupamiento médico tras revisar la captura

La primera corrección contemplaba dos equivalencias y diferencias de formato.
La captura del usuario mostró que persistían otras variantes, como Guillermo
Toledo y Guillermo Carlos Toledo. Se amplió la resolución con evidencia de los
estudios ya vinculados en la población aprobada.

Los nombres incompletos se agrupan cuando sus palabras están contenidas en un
nombre más completo, existen correspondencias de al menos dos pacientes distintos
en estudios compartidos entre EGES y Netterm y el grupo tiene un único nombre
completo compatible con todas sus variantes. Una discrepancia de informante con
nombres incompatibles conserva las entradas separadas. También se conserva un
nombre corto cuando puede corresponder a dos nombres completos diferentes.
Las equivalencias se calculan antes de aplicar fecha, modalidad y top diez sobre
la población aprobada, para que el filtrado mantenga el agrupamiento.

Se ampliaron las equivalencias explícitas de abreviaturas de Sarabia, Sánchez
Murillo y Maldonado Hernández. Sus variantes coincidían respectivamente en
estudios de 165, 196 y 10 pacientes distintos en los archivos analizados.
El usuario confirmó además los tres pares de Maira Alejandra Hernández Mojica,
Nicole Stephanie Balcázar Pineda y Yefferson David Salinas Herrera. Las formas
truncadas ALEJAND, STEPHAN y DAVI se resuelven a los nombres completos indicados.

El tablero incorpora «Ver nombres unificados» con los nombres originales que
contribuyeron a cada entrada. Se corrigió el color del texto de los detalles de
médicos y coberturas para el tema oscuro. El agrupamiento pertenece a las estadísticas.
Las 4.422 prácticas de octubre y las 12.523 del conjunto de lotes constituyen
los totales de control para verificar que agrupar profesionales conserva la población.

Verificación de la ampliación. Se identificaron 18 grupos de nombres unificados.
En octubre, las entradas de control son Guillermo Carlos Toledo con 141 prácticas,
Yefferson David Salinas Herrera con 153, Maira Alejandra Hernández Mojica con 99
y Nicole Stephanie Balcázar Pineda con 76. Con todos los lotes, Toledo reúne 257.
Las sumas del gráfico médico son 4.422 y 12.523 según la selección, coincidiendo
con los respectivos totales de prácticas. Pasaron 291 pruebas generales antes de
incorporar las tres equivalencias confirmadas por el usuario y 70 pruebas focales
posteriores con esas equivalencias. Compilaron plantilla y JavaScript, y
 git diff --check pasó. Cambios locales pendientes de commit y publicación.
La comprobación visual final del contraste y los nombres queda para el usuario.

### Top diez y normalización de coberturas

El usuario aprobó mostrar únicamente las diez categorías individuales en los
rankings de médicos y coberturas. El total y listado del resto aparecen debajo
del gráfico. Los registros sin informante o cobertura también se informan debajo.
La comprobación de conservación ahora suma top diez, resto y sin dato. El PDF
usa las mismas diez categorías e informa los otros totales por separado. El
apilado médico del PDF incorpora todas las modalidades.

Se añadió services_coberturas.py para resolver las descripciones mediante códigos
EGES, nombres equivalentes en formato y correspondencias de prácticas ya vinculadas.
Una misma descripción de un código EGES se presenta con un nombre canónico. Las
variantes sin código se resuelven por nombre inequívoco. Para Netterm se normalizan
puntuación, espacios, el sufijo contractual (C) y sufijos societarios terminales.
Las equivalencias de significado diferente se apoyan en correspondencias de dos
pacientes distintos y un único destino. Las coincidencias de nombre que contradicen
las correspondencias documentadas también se dejan para revisión.

El tablero muestra las coberturas unificadas y las correspondencias pendientes.
Ejemplos ambiguos encontrados. COBENSIL se asocia en EGES a COBER, COBER-OSMECON y
COBER-Círculo Médico Vicente López. GENESEN se asocia a la entrada actual y a OLD.
Al seleccionar toda la historia, OSMEDICA también encuentra dos denominaciones
EGES. El agrupamiento estadístico conserva esos destinos mientras se revisa qué
entidad o contrato debe representar cada grupo.

Prueba con copia en memoria de los lotes locales. Se obtuvieron 42 grupos de
variantes de cobertura unificados. En octubre, el gráfico médico muestra 2.742
prácticas entre los diez primeros, 1.671 en el resto y nueve sin informante,
sumando 4.422. Las diez coberturas principales suman 2.947 y el resto 1.475,
sin registros de cobertura vacíos. En toda la historia, los diez médicos suman
7.463, el resto 5.047 y faltan 13 informantes, sumando 12.523. Las diez coberturas
suman 8.288 y las restantes 4.235. Quedan seis correspondencias de cobertura para
revisar en octubre y siete con toda la historia, incluyendo equivalencias con
una sola observación y destinos múltiples. Estos pendientes afectan el nombre
agrupado de cobertura y se muestran en el desplegable correspondiente.

Pasaron 78 pruebas focales de coberturas, producción y validación. También pasó
la regresión específica del gráfico médico PDF con dos modalidades apiladas.
Compilaron el JavaScript del dashboard y la plantilla en las comprobaciones previas.

Verificación final de top diez y coberturas. Pasaron 301 pruebas de eges_import, liquidacion.tests_respaldo_fuentes y liquidacion.tests_cruce_eges en memoria con esquema sincronizado. Las comprobaciones JavaScript verificaron el resumen del resto, el detalle de equivalencias y la limpieza al cambiar filtros. Compilaron plantilla y módulos modificados. git diff --check pasó. Cambios locales en feature/eges-netterm, pendientes de commit y publicación. Falta la comprobación visual con el usuario.

### Base EGES completa e interruptor de aporte Netterm

El usuario solicitó que el tablero tome siempre todos los lotes EGES y permita
activar o desactivar el aporte Netterm para ver su efecto en la producción.
La carga de un lote RM de octubre había provocado un error al combinarlo con
la conciliación de ecografía del mismo mes. La restricción previa trataba toda
la combinación de lotes y período como indivisible.

La pantalla usa todos los lotes EGES automáticamente, con un listado informativo
en vez de casillas de selección. El interruptor «Añadir aporte Netterm validado»
está desactivado al abrir el tablero sin parámetros. Al volver desde una confirmación
se activa. Se conservan los filtros explícitos de fecha y modalidad. El período
completo sin fechas ya no se reduce implícitamente al de la última validación.
La pantalla muestra el aporte disponible con el interruptor apagado y el aporte
aplicado al activarlo. Cada cambio recarga los indicadores y gráficos, además del PDF.

services_dashboard.py compone la base EGES por lote reutilizando los criterios
existentes. La parte EGES de las conciliaciones aprobadas aporta sus agrupamientos
y fechas. Así, el interruptor suma sólo las prácticas adicionales cuya fuente en
el resultado aprobado es Netterm. Una práctica unificada entre EGES y Netterm se
mantiene en la base. Las otras modalidades de EGES se incorporan en el mismo mes
sin bloquear el aporte aprobado de ecografía.

Se combinan las aprobaciones por su período y modalidades. La confirmación más
reciente prevalece en los ámbitos solapados. Los estudios trasladados entre meses
se identifican por clave de práctica Netterm y paciente, usando HC válida o documento,
para conservar una sola versión aprobada. La reutilización del mismo pedido por
otro paciente conserva los estudios independientes. Las observaciones divergentes
entre archivos mantienen las reglas de revisión de conciliación existentes.
La composición utiliza versiones aprobadas, y las nuevas importaciones requieren
su validación para incorporarse como aporte.

Cuando un lote EGES nuevo aporta prácticas al mismo período y modalidad ya
conciliados, el tablero muestra la base y un aviso para revalidar ese aporte.
Ese caso deja de producir el error global de gráficos. Las otras modalidades y
sus aportes aprobados continúan componiendo la población. Las observaciones Netterm
anuladas archivadas se informan como tales en el detalle de origen. Los indicadores
y el PDF se obtienen en lectura, con la comprobación de ausencia de escrituras.
Los endpoints antiguos de selección explícita conservan su contrato para otros
consumidores y pruebas.

Comprobación con copia en memoria de la base local, tras la carga de RM. Cinco
lotes EGES producen una base de 12.298 prácticas en ECO y RM. Activar Netterm suma
841 prácticas aprobadas y lleva el total a 13.139. No aparecen avisos de revalidación
por la nueva RM. Pasaron 80 pruebas focales, incluidas la nueva modalidad en el mismo
mes, el interruptor, aportes de dos modalidades, reemplazo de confirmaciones,
traslado de mes, repetición legítima de pedidos, filtros y PDF. Los cambios permanecen
locales en feature/eges-netterm. Falta la comprobación visual final con el usuario.

Cierre de base EGES completa. Pasaron las 309 pruebas de eges_import, liquidacion.tests_respaldo_fuentes y liquidacion.tests_cruce_eges en memoria con esquema sincronizado. Se verificó que el PDF global consulta sin INSERT, UPDATE ni DELETE. La prueba JavaScript confirmó base_eges=todos, el cambio de incluir_netterm al accionar el interruptor y la conservación de filtros de fecha. Compilaron plantilla y JavaScript y git diff --check pasó. La versión de indicadores es ESTADISTICAS_FUENTES_V6. Cambios locales pendientes de commit y publicación. La verificación visual queda para la prueba del usuario.

## Comparativa y rendimiento del tablero, 15 de noviembre

La captura del usuario con toda la historia seleccionada muestra que faltan las
fechas del intervalo a comparar. La tarjeta ahora muestra «Elegí un período» y
reutiliza el motivo del servidor. Cuando hay fechas pero falta evidencia anterior,
muestra «Sin período comparable».

El perfil del cálculo identificó normalizaciones repetidas en `_valor_valido`.
Los valores de ausencia se normalizan una vez y la validación de textos utiliza
una caché acotada a 4.096 entradas. La caché guarda únicamente el resultado de
esa función pura. El tablero sigue consultando las fuentes en cada cálculo.
Una comparación con copia en memoria de la base local produjo respuestas
completas idénticas. El cálculo pasó de 5,74 a 4,89 segundos en esa medición.
El tiempo percibido en el navegador todavía requiere comprobación del usuario.

Reglas clínicas confirmadas para el trabajo pendiente de cantidades. RX tórax
frente y perfil suma dos prácticas y un paciente. Mamografía y proyección axilar
suman dos prácticas. Densitometría suma una práctica por estudio aunque tenga
varias posiciones. Falta implementar y verificar la equivalencia entre una fila
EGES con cantidad dos y dos filas Netterm. Las cantidades económicas originales
se conservan en sus fuentes.

## Implementación de unidades radiológicas

El conteo de RX utiliza cantidades EGES positivas enteras. Una cantidad cero,
ausente o inválida conserva una práctica clínica. Las otras modalidades mantienen
su unidad por registro clínico, incluidas mamografía y densitometría. La regla
confirmada para mamografía es una práctica para senografía y otra para axilar,
incluso cuando las cantidades originales reflejan bilateralidad.

El cruce absorbe un subsiguiente Netterm dentro de la capacidad de una fila EGES
cuando ya existe una vinculación del mismo pedido, paciente, fecha y familia de
códigos. Los pares reconocidos son 340301/340302, 340211/340212, 340209/340210 y
340201/340202. Se exige un único respaldo y se conservan los identificadores de
los componentes absorbidos. Un pedido diferente o un adicional confirmado como
independiente conserva su aporte. Las excepciones del cruce siguen sujetas a
revisión.

La cantidad integra la huella de las fuentes. Las versiones son
PRODUCCION_REVISION_CLINICA_V7 y ESTADISTICAS_FUENTES_V7. Los gráficos, indicadores
y PDF usan las mismas unidades. Las validaciones antiguas de RX requieren una
nueva revisión y el tablero muestra la base actual con el aviso correspondiente.
La implementación conserva cantidades originales y registros económicos.

Se importaron los archivos reales de RX y mamografía en una base de prueba en
memoria. Los resultados provisionales, antes de resolver todas las excepciones,
fueron 4.609 unidades de RX y 627 de mamografía. En esos archivos concretos no
hubo absorciones automáticas de subsiguientes con el criterio estricto. Los
totales definitivos requieren las decisiones de validación del usuario. La base
habitual se utilizó únicamente en lectura para las mediciones anteriores.

Verificación final de este ajuste. Pasaron 327 pruebas de eges_import,
liquidacion.tests_respaldo_fuentes y liquidacion.tests_cruce_eges con base en
memoria. Se cubren cantidades de RX, capacidad de absorción por pedido, estudios
independientes, cantidades cero, mamografía bilateral, densitometría y lectura de
validaciones antiguas de RX. `git diff --check` pasó. Los cambios permanecen
locales en feature/eges-netterm, pendientes de commit y publicación.

## Optimización del tablero, 16 de noviembre

Los logs de Heroku registraron timeouts H12 de 30 segundos en fuentes-data,
exceso de memoria R14/R15 e interrupciones de otras solicitudes. Ocurrió también
con el aporte Netterm desactivado.

El tablero lee las producciones aprobadas y recorre la base EGES mediante un
iterador. Los registros cubiertos por la confirmación se omiten antes de crear
sus objetos de producción. La base restante conserva los controles de estado,
modalidad y cantidades. La consulta de estadísticas reutiliza esa producción
para el período anterior. Se eliminó la segunda consulta de cada validación,
la retención del JSON en el objeto de metadatos y su copia completa en esa lectura.
Las unidades de un mismo registro comparten datos de lectura para los gráficos.

Se compararon las respuestas completas con el código del commit previo usando
una copia en memoria de la base local. Los gráficos e indicadores coinciden.
La diferencia de metadatos es la firma interna del nuevo recorrido. En una
medición con fechas y aporte Netterm, el tiempo pasó de 7,98 a 6,24 segundos.
El pico de asignaciones Python al construir producción pasó de 72,58 a 55,32 MiB
según tracemalloc. Esa medición corresponde al cálculo local y no representa
la memoria total del proceso en Heroku.

El navegador reconoce respuestas HTML de error y muestra un aviso para volver
a aplicar filtros. Conserva los gráficos anteriores con una aclaración visible.
Pasaron 327 pruebas y la comprobación JavaScript de respuesta HTML 503.
Los cambios están locales y requieren publicación y medición posterior en Heroku.
El control de consultas superpuestas y la reducción de versiones reemplazadas
siguen como optimizaciones posteriores.

Se incorporaron después controles de período y solicitudes. El inicio utiliza
tres meses calendario hasta el mes más reciente de EGES o del período aprobado.
Hay accesos al último mes cargado y a toda la historia. La selección de modalidades
mantiene el filtro global de tarjetas y gráficos y agrupa cambios durante 300 ms.
Las solicitudes de datos se serializan en el navegador y descartan selecciones
reemplazadas antes de enviarlas. Se conserva Chart.js y los controles existentes.
La leyenda de cada gráfico mantiene su función visual propia.
Pasaron 47 pruebas focales y la comprobación JavaScript de los rangos calendario
antes del ajuste final del contexto de fecha de referencia.

La comprobación posterior del contexto pasó las 9 pruebas del tablero. El usuario
aprobó visualmente el modal de espera con fondo translúcido y reloj de agujas
animadas. El indicador cubre espera y procesamiento y se cierra al resolver la
consulta. Respeta movimiento reducido. El usuario solicitó commit y push para
realizar personalmente el despliegue en Heroku y la comprobación en producción.
