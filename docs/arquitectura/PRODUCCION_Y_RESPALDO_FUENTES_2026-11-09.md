# Produccion combinada y respaldo profesional de origen

**Verificacion operativa posterior, 09/11/2026:** los archivos de esta entrega ya
coinciden con los publicados en Heroku y sus migraciones estan aplicadas. La rama
remota de GitHub todavia no contiene los dos commits y la etiqueta de release es inconsistente con
los archivos. Ver el [informe de publicacion](../operativa/REVISION_PRE_DESPLIEGUE_NETTERM_2026-11-09.md).
El estado local/sin despliegue indicado abajo corresponde a la entrega inicial;
esta comprobacion no realizo un despliegue nuevo.

Fecha: 09/11/2026. Implementado por Codex por indicacion explicita del usuario.
Entrega inicial: produccion y preview de respaldo sin decisiones persistidas ni
cambios de modelos/economia. Ampliacion local del 10/11/2026: consumo estadistico de
`VINCULAR` vigente y OK de respaldo persistido por linea en una tabla propia; incluye
migracion `liquidacion.0060`. No modifica precios, importes, cantidades economicas ni
reglas de cierre. Esta ampliacion no esta desplegada.

## Intencion del usuario

EGES conserva prioridad. Netterm complementa practicas ausentes (en particular
internacion) y puede reafirmar el respaldo existente. Las diferencias de estado
de informe no deben impedir por si solas reconocer la practica. Produccion e
informes se muestran por separado. Netterm nunca recalcula valores economicos.

## Donde usarlo

1. Estadisticas EGES -> **Produccion EGES + Netterm**:
   `/eges/estadisticas/produccion/` (superusuario). Elegir lotes y periodo.
2. Sesiones de Liquidacion o pantalla del cruce EGES -> **Respaldo EGES + Netterm**:
   `/liquidacion/sesiones/<pk>/respaldo-fuentes/` (superusuario, administrativo o
   jefe de servicio, como el panel actual). Elegir lotes de ambas fuentes; el
   periodo de fuentes corresponde al mes de la sesion. Consulta paginada por 50.

La consulta de produccion y el preview de respaldo son GET. La conciliacion mantiene
su POST separado para registrar decisiones humanas. El respaldo agrega un POST
explicito por linea inequívoca para persistir su OK de origen; no sustituye ni altera
los endpoints historicos de estadisticas, el portal del director, los controles
economicos o las revisiones EGES existentes.

## Produccion: reglas PRODUCCION_RESPALDADA_V1

Archivo: `eges_import/services_produccion.py`. Reutiliza el preview V8 para conservar
el manejo de insumos, candidatos, versiones divergentes y repeticiones.

V8 unifica la comparacion numerica de DNI con la clave anonima de paciente: puntos,
espacios y ceros iniciales no crean otra identidad, y un documento compuesto solo
por ceros no es una clave utilizable. Se conservan los originales. Se agregaron
regresiones para impedir duplicar una practica por padding de DNI y para que DNI
cero no habilite un exclusivo Netterm automatico. La version forma parte de la firma;
las revisiones anteriores se conservan en historial sin migrarlas a una vigencia V8.
No se cambio la busqueda del control economico EGES historico.

- EGES acredita realizacion con `INFORMADO`, `FIN PRACTICA` o `ENTREGADO SIN INFORME`.
  Otros estados quedan pendientes de evidencia, no se suman por mera presencia.
- Netterm acredita realizacion con fecha de realizacion presente o informe
  `DEFINITIVO`, `NO_DEFINITIVO` o `ESCRITO`. Una indicacion explicita de pendiente
  de realizar impide incluir, incluso si hay una fecha contradictoria.
- Insumos y anulados no aportan. Netterm con vigencia incierta, identidad ambigua,
  modalidad desconocida o anulacion contradictoria no agrega actividad.
- EGES aporta una vez por fila elegible. Netterm exclusivo e inequivoco agrega
  una practica; una correspondencia unica compartida no duplica.
- Si EGES no confirma realizacion pero la correspondencia Netterm unica si, se
  incluye una sola practica como aporte Netterm, conservando la referencia EGES.
- Una anulacion Netterm no elimina la base EGES respaldada; se conserva la evidencia
  por fuente y no se usa esa fila Netterm para enriquecer el total o el informe.
- La unidad es **registro de practica identificado**, no suma de `cantidad`, pedido
  completo, proyeccion RX ni persona. Se mantiene la advertencia provisional por la
  unidad RX y por evidencia sin resolver. No presentar el numero como total clinico
  certificado del servicio si hay cobertura pendiente.

La fecha eje sigue siendo turno EGES / pedido Netterm. No se presenta como volumen
por fecha efectiva de realizacion: los libros contienen pedidos de octubre con
realizacion/informe de noviembre. Una futura vista por fecha de realizacion requiere
su propio contrato; no se cambia silenciosamente el periodo al importar.

## Informes y tasa separada

Para cada practica incluida se cuenta una vez un informe confirmado cuando EGES
indica `INFORMADO` o una correspondencia Netterm unica/elegible indica `DEFINITIVO`.
No se exige igualdad entre estados; la discrepancia permanece en el preview V7.
La tasa documentada es `informes confirmados / produccion respaldada` y queda sin
valor si no hay poblacion. Ausencia de informe confirmado no afirma que no exista
un informe real; explicita la evidencia disponible.

No se interpreta `IMPRESO` como informe definitivo ni se equiparan automaticamente
`FIN PRACTICA`, `ESCRITO`, `ENTREGADO SIN INFORME` y `DEFINITIVO`. EGES conserva su
`estado_informe` original separado. La consulta muestra distribuciones de estados
para poder acordar reglas posteriores sin revisar cada practica.

La tasa EGES anterior (`tasa_conversion`, basada en Informado/candidatos) no cambio.
La nueva tasa tiene otra poblacion y no debe compararse como si fuera la misma serie.

## Respaldo: reglas RESPALDO_ORIGEN_V1

Archivo: `liquidacion/services_respaldo_fuentes.py`.

Se evalua cada linea de `RegistroEstudio` de registros activos de la sesion, incluidos
ECO y TOM (TC); tambien admite las otras modalidades reconocidas en el catalogo.
Se usa DNI normalizado y fecha exacta: `fecha_del_informe` del registro profesional
contra turno EGES / pedido Netterm, como el cruce actual. No se infieren tolerancias
de dias ni se sustituye por la fecha de informe Netterm.

La practica coincide por modalidad y codigo numerico normalizado (`/0` permitido).
Si el catalogo profesional no tiene codigo numerico, se admite nombre normalizado
exacto, con solo los aliases explicitados `ECO ABDOMINAL` y `ECOGRAFIA ABDOMINAL`
hacia `ECOGRAFIA COMPLETA DE ABDOMEN`. Un codigo numerico distinto no se ignora por
similitud textual. **No hay matching por una palabra generica**: codigo/catalogo
sin equivalencia comprobada queda sin respaldo automatico, para calibrar una regla.

La autoria exige nombre y apellido del usuario presentes en informante o actuante
EGES, o informante Netterm. Se omiten titulos habituales. No se atribuye al solicitante,
tecnico u operador. Nombres faltantes/truncados sin coincidencia suficiente quedan
para revisar; no se crean aliases de profesionales automaticamente.

Estados de linea:

- `OK_EGES`: respaldo unico de practica, realizacion y profesional en EGES.
  Netterm puede reafirmar la misma practica; otro informante Netterm no lo rebaja.
- `OK_NETTERM`: falta respaldo EGES compatible y hay evidencia unica de realizacion
  y profesional en Netterm; o Netterm confirma realizacion de una correspondencia
  EGES con autor conocido que aun no acredita realizacion.
- `REVISAR`: multiples candidatos, disputa de evidencia, autor no confirmado,
  anulacion, vigencia incierta o realizacion no acreditada.
- `SIN_RESPALDO`: no hay correspondencia por las claves/equivalencias admitidas.

EGES tiene prioridad: una contradiccion EGES de identidad/autoria o una anulacion no
se elude eligiendo Netterm. No se exige informe definitivo para el respaldo de origen.
Todas las lineas respaldadas producen `OK_RESPALDO`; algunas producen `PARCIAL`.

La evidencia es exclusiva en ambos sentidos: una fila no puede respaldar dos lineas
profesionales. Se evalua toda la sesion antes de aplicar filtro de profesional,
estado o paginacion, para no ocultar registros competidores. Pedidos o atenciones
repetidos no se resuelven por el primero ni se deduplican por paciente/dia.

**Alcance del OK:** acredita existencia y autoria de la practica. No certifica que
se hayan realizado todas las unidades de la cantidad declarada. Los resultados
expresan `cantidad_economica_validada=False` y `horario_economico_validado=False`.
La cantidad declarada se muestra tal como esta guardada, sin correccion.

El preview no llama `save`, `calcular_monto`, procesos de control ni acciones de
correccion economica. El POST explicito de confirmacion solo crea
`ValidacionRespaldoFuenteRegistro`; no crea `ResultadoControlEgesRegistro` ni
`RevisionCruceEgesRegistro`.
El **OK actual de Liquidacion y sus pendientes de cierre siguen con sus reglas**:
un OK de respaldo no los convierte silenciosamente en OK economico. Integrar este
respaldo en un checklist persistido exige distinguir esos alcances; no reutilizar
la validacion economica para simular un respaldo que no certifica cantidad/horario.

Los resultados se calculan con los lotes seleccionados y no constituyen un snapshot
persistido del registro profesional. La firma mostrada identifica las fuentes del
preview, no certifica que un registro no haya cambiado despues de consultar.

## Limites y cobertura

Se conserva el limite de 50000 observaciones del preview (Netterm seleccionado antes
de filtrar por periodo) y se limita el respaldo a 10000 registros de sesion. No se
agrego almacenamiento de archivos, cola ni worker. El circuito es sincrono.

Las coincidencias de registros profesionales se probaron con datos sinteticos,
incluida internacion representada solo en Netterm y TC. No se consulto ni modifico
la base habitual para medir cobertura contra profesionales reales. Faltan calibrar
los codigos/nombres de catalogo que no tengan equivalencia y los nombres truncados.

## Verificacion de esta entrega

- **211 pruebas OK** en la verificacion final: `eges_import.tests`,
  `eges_import.tests_produccion`, `liquidacion.tests_respaldo_fuentes` y
  `liquidacion.tests_cruce_eges`, ejecutados juntos. Django encontro y aprobo las
  211 pruebas.
- Pruebas de lectura sin INSERT/UPDATE/DELETE, preservacion de montos historicos
  fijados, cantidades y horarios, permisos, POST rechazado, prioridad EGES, TC,
  respaldo mixto/parcial y no reutilizacion de evidencia aunque se filtre.
- `makemigrations --check --dry-run`: no se requieren migraciones nuevas. No significa
  que las migraciones de auditoria anteriores esten aplicadas en produccion.
- Se conserva el conteo anterior de informadas; la nueva consulta tiene otra regla
  y otra version, y no altera la serie historica ni sus endpoints.
- Calibracion de las trece exportaciones de octubre en SQLite descartable completada;
  resultados siguientes. No constituye un benchmark de Heroku.
- La implementacion inicial se verifico por respuestas Django, sin QA visual de
  navegador; ver el seguimiento de UI mas abajo. No se toco la base habitual ni
  produccion.

## Calibracion real de octubre, corrida final V8

Fuentes: las seis exportaciones `Atendidos` de octubre TC, RM, RX, Mamo, Densito y
ECO, y los siete `LibroDescargadoNetterm` de octubre TC, Doppler, eco, Seriada,
Densito, RX y RM provistos por el usuario. No se usan los archivos EGES de mayo.
Se importaron exclusivamente en una SQLite descartable, se seleccionaron juntos y
se consulto del 01/10/2026 al 31/10/2026 por turno/pedido.

| Modalidad | Base EGES | Aporte Netterm | Produccion respaldada | Informes confirmados |
| --- | ---: | ---: | ---: | ---: |
| DX | 187 | 0 | 187 | 187 |
| ECO | 3696 | 696 | 4392 | 4347 |
| MAM | 638 | 1 | 639 | 627 |
| RM | 619 | 346 | 965 | 917 |
| RX | 3394 | 2615 | 6009 | 3527 |
| SERIE | 65 | 3 | 68 | 68 |
| TC | 1152 | 1087 | 2239 | 2212 |
| Total | 9751 | 4748 | **14499** | **11885** |

Pacientes identificables incluidos: **5814**. Practicas incluidas sin identidad: 0.
Sin informe confirmado: 2614. Tasa documentada: **82,0%**. Es una poblacion
provisional de registros de practica; no certifica proyecciones, unidades economicas
ni estudios clinicos RX. No es el volumen por fecha efectiva de realizacion.

El indicador anterior de informadas conserva **10135** en esta seleccion. La
diferencia no es una correccion de montos ni de filas historicas: la nueva poblacion
incluye actividad sin informe y puede usar Netterm para confirmar realizacion o
informe de un registro EGES. Los criterios de elegibilidad del indicador anterior
no cambiaron; V8 corrige comparacion de formato DNI sin cambiar su cifra en la muestra.

Pendientes de la nueva poblacion: 167 filas EGES sin realizacion confirmada, 517
grupos Netterm con correspondencia sin resolver, 473 sin realizacion confirmada y
55 sin modalidad. No se suman como practicas extras ni como cota superior.
Excluidos Netterm: 303 anulados y 102 insumos.

Se conservaron los estados observados: EGES contiene, ademas de Informado, Fin
Practica y Entregado Sin Informe, 171 Recepcionado, 3 Inicio Practica y 18 Informe
Entregado. Estos ultimos no se equipararon automaticamente a Informado. Una
correspondencia Netterm puede acreditar realizacion de algunos de ellos; los
restantes quedan pendientes. La regla de Informe Entregado puede calibrarse como
una ampliacion explicita, sin alterar la serie EGES anterior.

Tiempo local de la consulta de produccion en la corrida final: 4,636 s (`DEBUG=False`).
Huella de todas las filas EGES antes/despues identica. No se crearon registros
profesionales ni resultados de control economico en esa base. La SQLite se elimino.
El respaldo profesional se valida con fixtures sinteticos, no con registros reales
de profesionales: los libros solos no contienen ese tercer origen.

## Retoma para Copilot

Mantener separados produccion, informe, respaldo de origen y validacion economica.
No cambiar montos ni cantidades a partir de Netterm, ni permitir que un filtro haga
desaparecer una disputa por la misma evidencia. No exigir confirmar manualmente los
OK de respaldo calculados de forma inequivoca. Ampliar equivalencias solo con casos
reales y pruebas; continuar la semantica RX en el informe de analisis por conjuntos.

## Seguimiento de UI y estado local (09/11/2026)

Correcciones posteriores a la entrega inicial:

- El enlace **Produccion EGES + Netterm** no aparecia en Estadisticas EGES porque
  estaba en `page_actions`, bloque que `layouts/base_with_sidebar.html` no define.
  Se movio al bloque `content`; ahora es visible y navegable.
- En Cruce EGES, las acciones masivas se inicializaban aunque no hubiera lote
  seleccionado y sus formularios no existieran. Los scripts ahora verifican los
  controles antes de conectar eventos.
- El aviso RX sin informe mezclaba las clases Tailwind `hidden` y `flex`. Se separo
  la activacion de ambas clases, se agrego `aria-live` y se permite que el texto
  envuelva en pantallas estrechas.

QA realizado con SQLite temporal aislada y datos sinteticos:

- Cruce EGES sin lote: carga correcta, sin controles masivos ni errores JavaScript.
- Aviso RX: oculto con cero casos, visible con tres y de nuevo oculto al recargar
  datos sin casos. A 390 px no produce desbordamiento horizontal; el texto se
  envuelve dentro del aviso.
- La consulta real de produccion y el respaldo se recorrieron antes en navegador:
  una practica sin duplicacion por Netterm, evidencia EGES/Netterm visible y filtro
  `OK_RESPALDO` correcto. El monto persistido no cambio y no se crearon revisiones.
- Tras los cambios de UI, una primera ejecucion de `liquidacion.tests_cruce_eges`
  se detuvo a mitad con 48 OK; luego fue reemplazada por la verificacion final
  completa de 211 pruebas indicada arriba.
- Diagnosticos de ambos templates, `makemigrations --check --dry-run` y
  `git diff --check`: OK. Servidor y SQLite temporales eliminados.

Estado: el objetivo funcional local de produccion/respaldo y la comprobacion de UI
estan logrados. Los cambios se preparan en la rama local, sin push, despliegue ni
validacion en datos de produccion. Siguen pendientes la calibracion de
equivalencias/nombres truncados con casos profesionales reales.

## Consumo de conciliacion y respaldo persistido (10/11/2026)

- Un `VINCULAR` vigente de `ConciliacionRevision`, para el mismo `firma_snapshot`,
  basta para que produccion use ese par. Netterm confirma la misma practica, no
  suma otra. Las reglas de realizacion, anulacion y exclusiones siguen vigentes;
  `NO_VINCULAR` bloquea la fusion y deja el aporte Netterm como pendiente. El
  resumen indica cuantas decisiones vigentes se consumieron.
- En Liquidacion, una linea con `OK_EGES` o `OK_NETTERM` ofrece una confirmacion
  explicita. El POST revalida el snapshot y persiste un
  `ValidacionRespaldoFuenteRegistro` inmutable con linea, firma, lotes, evidencia,
  actor y fecha. Cambios en la linea o las fuentes requieren una nueva validacion.
- Este OK es respaldo de origen, no `RevisionCruceEgesRegistro.ESTADO_VALIDADO`:
  no resuelve pendientes del cierre, no cambia montos/horarios/cantidades y no
  llama al calculo economico. La identidad paciente del snapshot se guarda como
  hash, no DNI en claro.
- Verificacion local del 10/11: 217 tests OK, `makemigrations --check --dry-run`
  sin cambios adicionales, `git diff --check` limpio y POST probado en SQLite
  sintetica. Se comprobo monto/cantidad preservados y cero resultados/revisiones
  EGES creados. La migracion `0060` y esta ampliacion siguen sin desplegar.
