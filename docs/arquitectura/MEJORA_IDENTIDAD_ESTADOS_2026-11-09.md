# Correspondencia de origen y estados separados

Fecha: 09/11/2026. Implementado por Codex a pedido del usuario.

## Problema y comportamiento

Una practica con una unica correspondencia por DNI, codigo, fecha y modalidad podia
quedar en la cola de decisiones individuales solo porque EGES dice `FIN PRACTICA`
o `ENTREGADO SIN INFORME` y Netterm dice `DEFINITIVO`. Decidir VINCULAR/NO_VINCULAR
para cada pareja no resuelve el significado de esos estados.

El preview ahora reconoce la correspondencia de identidad por separado y presenta
esas diferencias como **alertas de estado sin revision individual de vinculacion**.
No declara equivalentes esos estados, no confirma produccion realizada y no valida
ningun registro profesional o pago. La regla general de estados sigue pendiente.

Las anulaciones contradictorias siguen requiriendo revision. Tambien se mantienen
las excepciones por varias candidatas, varios pedidos para la misma fila, versiones
divergentes, modalidad incompatible o datos de identificacion insuficientes.

## Contrato del motor V7

`services_conciliacion.py` agrega campos a cada resultado:

| Campo | Significado |
| --- | --- |
| `identidad_coincidente` | Correspondencia unica, bidireccional en los candidatos del cruce, con modalidad coincidente y sin ambiguedad de origen |
| `comparacion_estados` | `NO_COMPARADOS`, `EQUIVALENTES`, `DIFERENTES`, `NO_COMPARABLES` o `ANULACION_CONTRADICTORIA` |
| `alerta_estado_no_bloqueante` | Identidad coincidente con diferencia/no comparabilidad de estado, sin anulacion contradictoria |
| `contradiccion_anulacion` | Un origen indica anulacion y el otro no, en una pareja candidata unica; si la identidad no coincide sigue siendo excepcion de identidad |
| `requiere_revision_identidad` | Ambiguedad o conflicto que impide establecer correspondencia unica |
| `requiere_revision_estado` | Identidad coincidente con anulacion contradictoria |
| `requiere_revision_produccion` | Union de las dos necesidades anteriores; ya no incluye la diferencia de estado no anulada por si sola |

No se agregan equivalencias: solo `INFORMADO` / `DEFINITIVO` y las anulaciones que
el motor ya reconocia se consideran equivalentes. Estados nuevos o no mapeados son
`NO_COMPARABLES`. `PENDIENTE` frente a `DEFINITIVO` es `DIFERENTES`. Ninguno se
convierte automaticamente en elegible para el indicador.

Los resultados solo EGES y solo Netterm no se consideran identidad compartida.
Un codigo coincidente con modalidad distinta tampoco se considera tal.

**Compatibilidad del conteo:** se conserva `estado` con las categorias y criterios
anteriores. Por eso una alerta de estado puede seguir siendo `CONFLICTO` para el
conteo provisional, aunque no exija una decision individual de vinculacion. No
consumir `identidad_coincidente` como autorizacion de sumar, pagar o remapear estados.
`construir_preview_conteo_consolidado` no se modifico: mantiene estados elegibles,
base EGES, aporte Netterm, pendientes, cantidades desconocidas y pacientes.

El resumen agrega correspondencias unicas, alertas, anulaciones contradictorias con
identidad coincidente y total de excepciones. Son indicadores que pueden solaparse;
no se suman como practicas.

Se incremento la version a `DNI_CODIGO_FECHA_PEDIDO_V7`. La firma de snapshot incluye
esa version: las decisiones historicas permanecen en el historial, pero no se
trasladan automaticamente como vigentes a un snapshot V7. No hay migracion de datos.

## Pantalla de conciliacion existente

- El filtro **Solo excepciones de produccion** usa los nuevos motivos de revision.
- Nuevo filtro **Correspondencia unica con alerta de estado** para revisar las
  reglas por conjuntos sin exigir aprobar cada pareja.
- Las filas muestran la correspondencia por claves y distinguen anulaciones
  contradictorias de diferencias de estado. La revision opcional sigue disponible.
- La seleccion y la paginacion preservan el filtro; tambien lo preserva el retorno
  de un guardado de auditoria. La auditoria no cambia el resultado automatico.

No se conecto el conteo provisional a dashboards ni se alteraron el OK actual,
servicios de cruce, cantidades o montos historicos de Liquidacion. Tampoco se amplio
la carga, infraestructura o permisos.

## Verificacion

Se agregaron pruebas de:

- Estados RX `FIN PRACTICA`, `ENTREGADO SIN INFORME`, `RECEPCIONADO`, vacio y no conocido:
  identidad conservada, alerta sin revision individual y conteo sin incremento.
- EGES informado con Netterm pendiente: conserva el aporte EGES, sin aporte duplicado.
- Anulacion contradictoria, identidad ambigua y modalidad distinta: siguen siendo excepciones.
- Coincidencia de estados y anulaciones equivalentes: sin excepcion innecesaria.
- Filtro de alertas y filtro de excepciones, mensajes y ausencia de escrituras de revision.

Resultado final: **186 pruebas OK** (`eges_import` y `liquidacion.tests_cruce_eges`).
Se ejecutaron en SQLite de pruebas en memoria, tras comprobar una configuracion de
base temporal aislada. La corrida final uso `MD5PasswordHasher` exclusivamente en
el proceso de pruebas para acelerar las contrasenas de fixtures; no se modifico
la configuracion de autenticacion de la aplicacion.

`makemigrations --check --dry-run`: `No changes detected`. Esto significa que no
hacen falta migraciones nuevas por el codigo actual, no que las migraciones de
auditoria existentes esten aplicadas en la base habitual o en produccion.
`git diff --check` sin errores de whitespace. Las carpetas temporales de esta
entrega se eliminaron. No se ejecuto calibracion nueva de los trece archivos ni
QA visual en navegador; la plantilla se verifico mediante pruebas de respuesta
Django, filtros y mensajes. Los totales publicados en documentos previos conservan
su condicion provisional y no se presentaron como una nueva medicion V7.

## Retoma para Copilot

Esta entrega cambia la necesidad de revision, **no el significado del indicador**.
No volver a exigir VINCULAR/NO_VINCULAR para las alertas de estado. El proximo paso
es acordar estados de produccion/informe por modalidad y despues integrar Netterm
como respaldo complementario del registro profesional, conservando la prioridad
del respaldo EGES existente. Ese paso requiere sus pruebas y preview propios.

Para la unidad RX, continuar con
[el analisis por conjuntos](ANALISIS_RX_CONJUNTOS_2026-11-09.md): no se implemento
fusion de filas, equivalencias de proyecciones ni cantidades Netterm.

Archivos de runtime tocados: `services_conciliacion.py`, `forms.py`, `views.py` y
`preview_conciliacion.html`; pruebas en `eges_import/tests.py`. No se modificaron
modelos, migraciones ni archivos de Liquidacion. Sin commit, push o despliegue.
