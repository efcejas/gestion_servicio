# Auditoria de Doppler MMII

> Estado: primera etapa de lectura y deteccion de candidatos.
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

No existe aun enlace automatico de cada prestacion con su orden de VisualMedical ni una fuente estructurada de facturas/debitos/pagos. La pantalla no simula importes corregidos ni escribe historial de decision.

## Pendientes para la siguiente etapa

1. Contrastar los tres grupos de septiembre y una muestra de registros con cantidad 2 contra orden y VisualMedical.
2. Revisar si existen otras variantes de nombre/codigo para arterial y venoso MMII en el catalogo.
3. Definir un estado y captura de evidencia de revision (quien, cuando, fuente y conclusion), sin corregir el origen.
4. Separar una futura diferencia monetaria estimada del monto facturado/debitado real, que no esta disponible como dato estructurado.
5. Revisar la proteccion contra doble envio del formulario; no asumir que todos los candidatos detectados son errores del usuario.
