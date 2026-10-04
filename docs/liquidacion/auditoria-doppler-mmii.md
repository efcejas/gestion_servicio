# Auditoria de Doppler MMII

> Estado: revision persistente, estimaciones, lotes y filtro de estado publicados en `feature/liquidacion-copilot-specialization`; migraciones pendientes de despliegue.
> Corte de datos de produccion: 2026-10-03.
> No aplica correcciones ni modifica cantidades o montos.

## Regla acordada

La unidad facturable es la practica, no cada pierna:

- Doppler arterial bilateral de miembros inferiores: 1 practica.
- Doppler venoso bilateral de miembros inferiores: 1 practica.
- Arterial y venoso bilateral: 2 practicas.
- La cantidad de regiones se conserva como dato declarado, pero no equivale por si sola a cantidad de practicas pagables.

La regla de cantidad aplica a todos los roles. Para `medico_residente`, el resultado economico de esta auditoria es informativo y no propone debito. Jefes de residentes, instructores y otros profesionales quedan sujetos a la regla general, siempre pendiente de revision humana y evidencia.

## Datos de produccion observados

Consulta de solo lectura a la app Heroku `gestion-colegiales`, release 494, deploy `5c859ec7`. Se consultaron registros de Angel Gavilanes Ibarra (`jefe_residentes`) entre junio y septiembre de 2026. No se incluyeron nombres ni DNI de pacientes en esta documentacion.

- Registros activos del profesional en todos los periodos: 1.188.
- Registros activos con fecha del informe entre 2026-06-01 y 2026-09-30: 1.167.
- Lineas `RegistroEstudio` Doppler de todos los tipos en ese periodo: 630.
- Lineas Doppler MMII arterial/venoso: 291; suma de las cantidades declaradas: 435.

| Mes 2026 | Lineas Doppler MMII | Cantidad declarada sumada |
| --- | ---: | ---: |
| Junio | 80 | 139 |
| Julio | 65 | 103 |
| Agosto | 50 | 80 |
| Septiembre | 96 | 113 |
| **Total** | **291** | **435** |

La diferencia aritmetica de 144 unidades respecto de una unidad por linea es un indicador bruto, no un debito ni una conclusion: antes hay que resolver lineas repetidas y verificar casos contra la orden/VisualMedical.

## Catalogo y aranceles observados

| Codigo | Denominacion | Tipo | Grupo | Regiones por defecto |
| --- | --- | --- | --- | ---: |
| 900046 | ECODOPPLER ARTERIAL MM INFERIORES | DOP | DOP_PERIFERICO | 1 |
| 900048 | ECODOPPLER VENOSO MM INFERIORES | DOP | DOP_PERIFERICO | 1 |

Tarifas encontradas para el grupo base `DOP_PERIFERICO`:

| Vigencia | COBER | Otras obras sociales |
| --- | ---: | ---: |
| 2026-04-01 a 2026-06-30 | $9.400 | $11.000 |
| Desde 2026-07-01 | $10.350 | $12.100 |

Para `DOP_PERIFERICO_LECHO` se encontraron $11.600/$13.200 hasta junio y $12.800/$14.550 desde julio. El importe aplicable depende tambien de la obra social y el contexto guardado en `RegistroEstudio`; los montos almacenados no prueban por si solos factura aceptada, debito ni pago final.

## Posibles duplicados encontrados

Criterio exploratorio: mismo profesional, DNI almacenado, fecha del informe y estudio. El DNI se uso como clave interna de consulta y no se conserva en este documento. Se encontraron tres grupos, aun sin confirmar contra VisualMedical:

| Fecha | Practica | Registros | Datos observados |
| --- | --- | --- | --- |
| 2026-09-08 | Arterial MMII, codigo 900046 | #5603 y #5604 | Cada registro tiene cantidad 1, contexto LECHO, 2 regiones y monto registrado $29.100. |
| 2026-09-08 | Venoso MMII, codigo 900048 | #5603 y #5604 | Los mismos dos registros incluyen cantidad 1, contexto LECHO, 2 regiones y monto registrado $29.100. |
| 2026-09-22 | Arterial MMII, codigo 900046 | #6397 y #6413 | Cada registro tiene cantidad 1, contexto SERVICIO, 1 region y monto registrado $12.100. |

El caso del 8/9 parece una repeticion de dos cabeceras que contienen ambas practicas; debe contrastarse con la orden y VisualMedical. No se fusionaron ni modificaron registros.

### Reenvio del formulario

El alta medica comprueba si el mismo profesional, DNI, fecha del informe y conjunto de estudios ya se registraron en los ultimos cinco minutos. Si encuentra coincidencia, bloquea el nuevo alta. Esta proteccion no es una restriccion unica de base de datos ni serializa dos solicitudes concurrentes; ademas, deja de aplicar pasados cinco minutos.

Los registros #5603 y #5604 se crearon a las 18:00:46 UTC y 18:11:25 UTC, respectivamente: hay 10 minutos y 39 segundos entre ellos. Por eso no encajan con un reenvio inmediato dentro de la ventana actual; el motivo de la repeticion no se puede determinar solo con estas marcas.

## Como se presenta la auditoria

La pantalla agrupa una fila por `RegistroEstudiosPorMedico` y lista dentro los estudios Doppler detectados, con cantidad declarada y cantidad esperada por practica. Totales de practicas y regiones aparecen separados para no confundirlos: por ejemplo, arterial x2 + venoso x2 se presenta como 4 declaradas -> 2 segun regla, con 4 -> 2 regiones como dato informativo.

Los registros candidatos a duplicado permanecen como filas independientes y muestran referencias a otros IDs. La coincidencia no se llama duplicado confirmado y requiere revision humana.

## Implementacion actual

- Clasificador en `liquidacion/services_auditoria.py`: reconoce `MMII`, `MM INFERIORES` y `MIEMBROS INFERIORES`, y distingue arterial, venoso y combinado.
- Servicio `auditar_cantidad_doppler_mmii`: lectura de registros activos por periodo; conserva cantidades, regiones y montos originales.
- Posible duplicado: mismo profesional, DNI normalizado, fecha y clase de practica. Arterial y venoso son clases distintas.
- Pantalla administrativa en `liquidacion/views.py`, ruta `/liquidacion/auditoria-doppler-mmii/`, accesible para administrativo, jefe de servicio y superusuario.
- Template `templates/liquidacion/auditoria_doppler_mmii.html`, enlazado desde Sesiones Contables.
- Regresiones en `liquidacion/tests_auditoria_doppler.py`.

No existe aun enlace automatico de cada prestacion con su orden de VisualMedical ni una fuente estructurada de facturas/debitos/pagos. La estimacion segun cantidades confirmadas no demuestra lo efectivamente facturado, debitado o pagado.

### Revision persistente P1

La accion administrativa `Generar casos de revision` conserva un snapshot por registro, linea original y version de regla. Generar nuevamente no sobrescribe el snapshot ni duplica el caso. Guarda cantidad, regiones, monto historico, contexto, obra social, horario y datos de origen.

Estados: `PENDIENTE`, `CONFIRMADO`, `DESCARTADO` y `REQUIERE_EVIDENCIA`. Confirmar exige orden medica o VisualMedical verificada. EGES y NetTerm son fuentes complementarias; por si solos no habilitan la confirmacion. Toda decision exige observacion y agrega un evento de historial con estado anterior/nuevo, fuentes, usuario y fecha. Los eventos previos no se reescriben desde este flujo.

En `Mis registros`, cada profesional ve solo los casos asociados a sus registros: cantidad original/esperada, estado, observacion, fuentes y revisor. No se muestran referencias a registros ajenos. Residentes reciben informacion sin propuesta de debito; para otros roles se indica impacto potencial no aplicado.

La persistencia de auditoria no cambia prestaciones, regiones, horario, montos ni estados contables. P2 agrega un parametro opcional a `calcular_monto()` para simular cantidades, reutilizando sus reglas sin escribir datos; los llamados existentes mantienen su comportamiento. No cambia signals o B2/B3. Las migraciones `0053`, `0054` y `0055` agregan revision, historial y autor nullable; `0056` agrega los JSON de estimacion a revision e historial. En este trabajo no se ejecutaron migraciones en produccion.

### Uso de lotes P2

1. Filtrar por periodo y profesional en la auditoria Doppler y generar los casos, si no estan persistidos.
2. Revisar las ordenes o VisualMedical del conjunto que se pretende confirmar.
3. Marcar casos individuales o `Elegibles de esta pagina`. No selecciona otras paginas ni todo el periodo.
4. Marcar la evidencia verificada para TODOS los seleccionados y escribir el fundamento comun.
5. Pulsar `Confirmar seleccionados` y aceptar la confirmacion. Se agrega una decision e historial por caso, sin tocar las prestaciones ni el monto oficial.

El lote admite hasta 200 casos pendientes o que requieren evidencia, con cantidad declarada 2 y esperada 1. Excluye posibles duplicados, decisiones confirmadas/descartadas y cantidades manuales. El backend revalida los filtros, los datos y la deteccion de duplicados. Si un caso no es elegible o cambio, se rechaza TODO el lote sin decisiones parciales. Un reenvio no sobreescribe decisiones ya guardadas.

### Comparacion economica P2

La columna `Comparacion Doppler` aparece en auditoria, `Mis registros` y liquidacion mensual. Muestra monto original al detectar, estimado segun decisiones confirmadas y diferencia estimada; el monto vigente oficial permanece en su columna habitual. La simulacion se hace sobre el registro completo (tambien en registros mixtos), sustituyendo solo las cantidades confirmadas. Arterial y venoso en el mismo registro no duplican el importe total.

### Filtro de estado

La pantalla de auditoria permite filtrar por `Sin revision iniciada`, `Pendiente`, `Requiere evidencia`, `Diferencia confirmada` o `Diferencia descartada`, ademas de fecha, profesional y diferencias/manuales. `Sin revision iniciada` identifica candidatos que requieren revision y aun no tienen snapshot persistido. Los otros estados corresponden al caso guardado de cada practica.

El filtro se conserva al paginar, generar snapshots o guardar una decision. El listado sigue mostrando todas las practicas Doppler del registro como contexto si al menos una coincide con el estado elegido; el texto auxiliar de la pantalla lo aclara.

Una decision guarda la estimacion y sus datos de calculo tanto en el caso como en su evento de historial. Las pantallas y Excel leen esa estimacion guardada, sin recalcular a partir de cambios posteriores de aranceles. Una nueva decision puede generar otra estimacion, conservando el evento anterior.

Se usa la fecha, obra social, contexto y reglas del calculo canonico. Antes de estimar, el monto original debe poder reproducirse con las tarifas historicas disponibles y todas las practicas deben tener precio positivo. Si los datos cambiaron, faltan tarifas, hay un duplicado confirmado o la cantidad es manual, se muestra `Pendiente` y su motivo, nunca cero como sustituto de un importe desconocido. Si quedan casos sin confirmar, la estimacion disponible se identifica como parcial. Los casos de P1 sin fuente completa conservan sus snapshots y se validan contra los campos originales disponibles al decidir.

Los resumenes separan diferencia estimada potencial para roles generales e informacion de residentes. La diferencia de residentes NO se suma como debito propuesto. No existe aplicacion de debitos Doppler en P2; por eso se muestra `No aplicado`, no un supuesto debito real.

### Excel P2

Ambos Excel conservan columnas y totales oficiales, y agregan al final las mismas columnas de comparacion Doppler. Incluyen una hoja `Auditoria Doppler` con cantidades, decisiones, evidencia, fundamento, revisor y fecha. Los importes de un registro se muestran una sola vez en esa hoja aunque tenga varios casos. Los textos del auditor se exportan como texto, no como formulas.

El Excel personal mantiene solo datos propios. Descarga todos los registros vigentes del mes/anio elegido, de todas las modalidades, y las guardias; ignora los filtros de modalidad, busqueda y hoy de la pantalla para evitar planillas incompletas. Los anulados siguen excluidos, como antes.

El archivo personal abre en un `Resumen` compacto, preparado para imprimir en una pagina y sin totales repetidos ni filas tecnicas de persistencia. Identifica profesional, rol y periodo; muestra practicas (todas las modalidades), guardias y TOTAL ACTUAL.

El contenido se adapta al rol autenticado, no a un parametro de descarga. Para `medico_residente` muestra solo la liquidacion vigente y la revision informativa de cantidades; no incluye columnas de debito, credito, diferencias monetarias o total proyectado en ninguna hoja. Para otros roles (incluidos jefe/instructor) agrega POSIBLE DEBITO y TOTAL ESTIMADO SI SE CORRIGE. Solo muestra credito cuando hay alguno. Los importes son estimaciones no aplicadas. Si faltan estimaciones o decisiones, advierte que la estimacion es parcial.

En `Practicas` se conservan los registros de todas las modalidades, cantidades y montos registrados. Metadatos de carga/sesion quedan ocultos por defecto, no eliminados. Se agrega estado de revision y, solo para roles no residentes, posible debito y monto estimado por registro (credito solo cuando existe). Los importes no calculables muestran `Pendiente`, no cero. `Guardias` conserva el detalle; `Revision Doppler` muestra cantidades, observacion, fuentes verificadas y revisor, con importes de registro una sola vez y solo para no residentes. La proyeccion no afirma facturacion o debito real ni modifica montos. El Excel administrativo mantiene su formato operativo separado.

El administrativo preliminar y el definitivo comparten la comparacion, pero sus totales oficiales siguen usando `monto_calculado`. El definitivo no descuenta estimaciones. Los resumenes muestran cuantos registros tienen estimacion y cuantos siguen pendientes.

NetTerm no tiene importador ni cruce implementado en P1. La casilla solo registra que el auditor consulto esa fuente manualmente. Para integrarlo al cruce EGES se necesita primero una muestra anonimizada del formato exportado o del texto copiado, y definir identificadores, fechas, practicas y criterios de ambiguedad sin ajustes economicos automaticos.

## Pendientes para la siguiente etapa

1. Contrastar los tres grupos de septiembre y una muestra de registros con cantidad 2 contra orden y VisualMedical.
2. Revisar si existen otras variantes de nombre/codigo para arterial y venoso MMII en el catalogo.
3. Validar operativamente los snapshots y decisiones P1 antes del despliegue.
4. Definir una fase separada para aplicar ajustes autorizados y registrar facturas/debitos reales; P2 solo estima.
5. Revisar la proteccion contra doble envio del formulario; no asumir que todos los candidatos detectados son errores del usuario.
6. Disenar la entrada NetTerm y su integracion con los cruces existentes a partir de una muestra anonimizada.

## Verificacion visual registrada

En QA local con SQLite en memoria y registros ficticios se comprobo el filtro de los cinco estados en navegador: `Todos` presento cinco casos; cada estado individual presento el caso esperado. En movil el selector fue visible y la pagina no tuvo desbordamiento horizontal. Pruebas automatizadas Doppler: 31 aprobadas en la integracion del filtro. No se usaron datos productivos ni se ejecutaron migraciones en produccion.
