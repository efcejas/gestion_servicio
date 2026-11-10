# RX: comparación de conjuntos EGES / Netterm

Fecha: 09/11/2026. Autor de esta revisión: Codex, a pedido del usuario.
Estado: diagnóstico ejecutado; **sin cambios del motor, conteos publicados o pagos**.
Este documento permite a Copilot retomar el trabajo sin repetir las hipótesis como hechos.

## Resultado y decisión

La mayor parte de los pedidos multifila que encuentran varias filas EGES tiene
una correspondencia estructural fuerte por códigos. No era correcto limitar el
análisis a los cuatro pedidos con una sola candidata EGES.

En **1040 pedidos** la firma de códigos coincide con una sola agrupación EGES y
no compite con otro pedido Netterm del mismo paciente y día con esa firma.
Esto es evidencia para comparar registros, **no prueba de que una fila, un código,
una cantidad o un pedido sean un estudio clínico o una proyección**.

La hipótesis concreta «una fila EGES cantidad 2 = dos filas Netterm» sigue sin
demostrarse. La representación frecuente observada es otra: **principal y
subsiguiente aparecen como dos códigos y dos filas en ambas fuentes**, y EGES
puede además registrar cantidad 2 en la fila subsiguiente. No sumar filas Netterm
como proyecciones ni sumar cantidades EGES como estudios por esta observación.

## Reproducción y aislamiento

Script nuevo: [analizar_rx_conjuntos.py](../../scripts/utils/analizar_rx_conjuntos.py).

```powershell
.\gestion_env\Scripts\python.exe scripts/utils/analizar_rx_conjuntos.py --directorio <directorio-de-exportaciones>
```

El script crea SQLite en `TemporaryDirectory`, fuerza `DATABASE_URL`, comprueba
motor y ruta efectiva antes de migrar/importar, cierra conexiones y elimina el
directorio al salir. Usa el importador EGES actual y el parser Netterm actual;
no guarda Netterm ni llama al motor de conteo o a servicios de Liquidación.
Solo imprime agregados y muestras de catálogo sin pacientes, DNI, fechas,
pedidos, protocolos, horas ni localizadores personales. La corrida confirmó
`sqlite_temporal_eliminada: true`. No se aplicaron migraciones a la base habitual
ni a producción. El costo de esta corrida incluye migraciones de todo el proyecto;
no es un benchmark del procesamiento ni de Heroku.

Fuentes y huellas de contenido de esta corrida:

| Archivo | Bytes | SHA-256 |
| --- | ---: | --- |
| Atendidos-RX-Octubre-26.xls | 3056128 | a0ce75a33c9301f1795cc1a3486ac371b5f5719a6bf02417686ec2e9eb64fb17 |
| LibroDescargadoNetterm-RX-oct-26.xlsx | 1348158 | f9b7ab03bbd77e36fed39fc95dc8136c5bcfadddf4ce0a7b73a3239800071011 |

Importación EGES aislada: 3570 filas creadas, 8 duplicadas omitidas por la regla
existente, 0 errores. De las creadas, **3505 son RX y 65 SERIE**. El análisis siguiente
usa solo RX: no confundir las 3570 filas del archivo con 3570 filas de modalidad RX.
Netterm: 6366 filas clasificadas RX. Estos datos incluyen diversos estados, no solo
informadas, y no son un nuevo total estadístico consolidado.

## Método

1. Identidad y código se normalizan con `_dni` y `_codigo` del motor actual.
   El tipo documental Netterm admite puntos/espacios al reconocer DNI.
2. Netterm se agrupa por DNI + fecha de pedido + pedido. No se fusionan pedidos.
3. EGES se busca por DNI + fecha de turno y se subdivide por hora + centro +
   protocolo + número de turno. Esta es una agrupación operativa candidata,
   no una identidad clínica certificada. Campos vacíos reducen su fuerza.
4. Se comparan **multiconjuntos** de códigos: además de qué códigos hay, se conserva
   cuántas veces aparece cada uno. No se usa un `set` que elimine repeticiones.
5. Se distingue igualdad con todo el día de igualdad con una agrupación. Una
   firma solo se llama unívoca si coincide con una agrupación EGES y ningún otro
   pedido Netterm del mismo DNI/día tiene la misma firma.
6. Las cantidades se observan, nunca se usan para inventar cantidad Netterm.
   Los estados se conservan separados de la correspondencia estructural.

No se interpreta `PATOLOG` de Netterm como región anatómica validada ni se requiere
igualdad literal entre ese campo y `region_informe` EGES. El catálogo de códigos
puede incluir descripciones con varias regiones; compartir ese código no certifica
la región concreta. Tampoco se deriva lateralidad o número de exposiciones.

## Hallazgos agregados

| Resultado | Pedidos Netterm |
| --- | ---: |
| Multifila con identidad y fecha utilizables | 2277 |
| Sin fila EGES RX del mismo DNI/fecha | 1163 |
| Con exactamente una fila EGES RX | 4 |
| Con varias filas EGES RX | 1110 |

Dentro de esos 1110 (las filas siguientes se solapan, salvo la partición indicada):

| Comparación | Pedidos |
| --- | ---: |
| Todos sus códigos, con multiplicidad, están contenidos en el día EGES | 1110 |
| Firma igual al conjunto EGES de todo el día | 1053 |
| Firma igual a exactamente una agrupación EGES | 1074 |
| Firma igual a varias agrupaciones EGES | 24 |
| Firma sin igualdad con una agrupación completa, aunque contenida en el día | 12 |

La partición útil de los 1110 es **1040 firmas unívocas + 58 con competencia de
pedido/agrupación + 12 sin igualdad con una agrupación completa = 1110**.
Los 58 no deben resolverse eligiendo una fila o agrupación arbitrariamente.
Los 12 tampoco deben fusionar automáticamente varias atenciones del día.

Dentro de los 1040:

- 1006 contienen marca principal/subsiguiente en ambas fuentes.
- 304 tienen todas las cantidades EGES iguales a 1.
- 734 tienen al menos una cantidad EGES mayor que 1; los 2 restantes no cumplen
  ninguna de esas dos condiciones. No suponer que cantidad siempre es positiva.
- 342 tienen todas sus filas EGES en `INFORMADO`.
- 959 tienen todas sus filas Netterm en `DEFINITIVO`.

Los dos últimos conteos no son una intersección ni prueban equivalencia de estados.
No transformar `FIN PRACTICA` o `ENTREGADO SIN INFORME` en `INFORMADO`.
Los 1163 sin candidato del mismo día no son automáticamente faltantes confirmados:
puede haber diferencias de cobertura, fechas o criterios de exportación.

En los cuatro pedidos con una sola fila EGES, cero tienen cantidad EGES igual al
número de filas Netterm. Esto no refuta otros tipos de representación; limita esa
hipótesis concreta en esa muestra pequeña.

## Abreviaturas omitidas en el análisis anterior

Buscar solo `SUBSIGUIENTE` subestimaba fuertemente los registros relevantes.
La búsqueda diagnóstica `\bSUBSIG` incluye `SUBSIG.`, `SUBSIG` y `SUBSIGUIENTE`:

| Fuente RX | Palabra completa | Prefijo SUBSIG |
| --- | ---: | ---: |
| EGES | 736 | 1773 |
| Netterm | 864 | 3204 |

De los 2277 pedidos multifila Netterm, **2240** tienen esa marca amplia, frente a
184 con la búsqueda anterior de palabra completa. Es una señal de catálogo,
no una regla automática de cantidad o agrupación.

## Muestra pequeña sin identidad para acordar semántica

El script muestra un ejemplo de cantidades/estados por patrón, no su distribución
completa. Las frecuencias siguientes cuentan firmas de descripciones Netterm entre
los 1040 pedidos unívocos; **no significan que todos tengan el mismo estado o cantidad**.

| Patrón de catálogo | Códigos | Frecuencia | Ejemplo EGES observado |
| --- | --- | ---: | --- |
| Tórax + subsiguiente de tórax | 340301 + 340302 | 519 | Cantidades 1 + 2, ambas `FIN PRACTICA` |
| Hombro/húmero/pelvis/cadera/fémur + subsiguiente | 340211 + 340212 | 174 | Cantidades 1 + 2, ambas `ENTREGADO SIN INFORME` |
| Cráneo + subsiguiente | 340201 + 340202 | 64 | Cantidades 1 + 2, ambas `ENTREGADO SIN INFORME` |
| Columna + subsiguiente | 340209 + 340210 | 36 | Cantidades 1 + 2, ambas `INFORMADO` |
| Tobillo + subsiguiente y pie + subsiguiente | 340237 + 340247 | 33 | Dos descripciones compuestas, cantidades 1 + 1 |
| Abdomen + subsiguiente | 340421 + 340422 | 19 | Cantidades 1 + 2, ambas `RECEPCIONADO` |

No publicar estos patrones como equivalencias clínicas ni interpretar 1 + 2 como
tres proyecciones sin consultar el significado de cantidad en EGES.

## Retoma concreta para Copilot

1. **No volver a tratar los 1110 como una masa sin evidencia.** Hay una partición
   reproducible 1040/58/12 y debe conservarse al evaluar una futura regla por grupos.
   Muchos códigos ya pueden tener candidata individual en el motor; este diagnóstico
   no implica que haya 1040 casos nuevos para automatizar o 1040 prácticas adicionales.
2. Separar identidad de estado: una firma de códigos compatible puede respaldar la
   correspondencia de origen sin resolver si el indicador cuenta informes o realizados.
   Revisar por reglas los estados RX, manteniendo el circuito sin informe.
3. Si se incorpora matching por grupos, exigir evidencia suficiente, exclusividad en
   ambos sentidos y preservación de multiplicidades/atenciones; no implementar una
   unión many-to-many por DNI y fecha ni una resta de cantidades para cerrar diferencias.
4. Consultar al responsable del origen/nomenclador sobre estos patrones: ¿cantidad de
   subsiguiente significa exposiciones adicionales, unidades facturables u otra cosa?
   ¿una fila Netterm de subsiguiente agrega varias unidades sin mostrar su cantidad?
   ¿los códigos compuestos incluyen primera y subsiguientes en una unidad de catálogo?
   ¿qué identifica un estudio y sus repeticiones en cada exportación?
5. Hasta contar con esas respuestas, ofrecer conceptos separados: filas/códigos
   identificados, pacientes identificables y cantidades EGES; estudios/proyecciones
   Netterm quedan sin determinar. Los **10135 no están validados como estudios clínicos**.
6. La diferencia de 16 RX contra SERIE previamente documentada no se reanalizó aquí.
   Tampoco se recalculó el aporte RX ni se ejecutó la suite de aplicación: no se cambió
   código de runtime. La ejecución real del script y `git diff --check` verifican esta
   entrega diagnóstica. No se hizo commit, push o despliegue.

## Archivos de esta intervención

- Nuevo script diagnóstico independiente; usa servicios existentes sin modificarlos.
- Este informe, con agregados y muestras de catálogo sin información de pacientes.
- Enlace y precisiones en el contrato principal. No se modificaron modelos,
  migraciones, servicios de runtime, vistas, plantillas ni Liquidación.
