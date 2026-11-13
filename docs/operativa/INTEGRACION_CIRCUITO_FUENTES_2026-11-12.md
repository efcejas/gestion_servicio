# Integración del circuito EGES y Netterm

## Revisión de lo recibido de Copilot

Base revisada: HEAD `27e2186e`, con persistencia de respaldos (`48a9df08`)
y confirmación por página. Había cambios locales previos en conciliación y
documentación; se conservaron. No se publicó ni se modificó una base habitual.

La producción combinada existía en una pantalla separada. Los respaldos
confirmados se guardaban por línea, pero el resumen del cierre no los consultaba.
El control EGES existente alcanza residentes ECO/DOP/ECOCAR y también evalúa
cantidad y horario: no es un control general de todas las modalidades.

## Cambios iniciales de Codex

- El tablero habitual incluye el formulario y resultado de producción EGES +
  Netterm, reutilizando una plantilla parcial con la pantalla independiente.
  Se eligen explícitamente lotes y fechas. No se suman todas las importaciones
  automáticamente. Los gráficos históricos siguientes conservan sus fuentes
  y filtros EGES y están identificados como tales.
- El resumen del control usado por panel y checklist reconoce las confirmaciones
  vigentes de respaldo cuando el único motivo original es ausencia completa de
  EGES. Deben estar confirmadas todas las líneas del registro en una misma
  selección de fuentes. El resultado histórico EGES no se sobrescribe.
- Se recalcula el preview y se comparan sus firmas con las confirmaciones
  guardadas. Una vista previa sin confirmar, una línea parcial o una firma que
  cambió no libera el pendiente. No se mezclan líneas de selecciones distintas.
- Diferencias de cantidad, horario, autoría, ambigüedad y solicitudes explícitas
  de corrección no se resuelven mediante esta sustitución. No se recalculan
  importes ni se cambian cantidades, horarios o estados de la sesión.

## Uso esperado

1. Importar las fuentes y consultar la producción desde Estadísticas.
2. En la sesión, ejecutar el control EGES habitual si hay residentes ECO y consultar
  respaldo de fuentes. Las sesiones solo TC no requieren un control ECO vacío.
3. Confirmar las coincidencias inequívocas de respaldo con los controles existentes.
4. Volver al panel/checklist: la ausencia EGES cubierta ya no requiere otra revisión
   manual equivalente. Los pendientes económicos reales siguen visibles.

## Límites que no deben confundirse con circuito terminado

- Si hay registros en el alcance ECO y no existe control EGES previo, el checklist
  conserva «Control no realizado», aunque las tomografías estén respaldadas.
- El motor EGES de cantidad y horario conserva su alcance ECO. Tomografía se
  integra al cierre como respaldo confirmado de práctica y profesional, no como
  certificación económica de cantidades u horarios. Otras modalidades no se amplían.
- No unifica todos los gráficos y exportaciones históricos con Netterm.
- No resuelve la equivalencia clínica de cantidades RX/subsiguientes, ni asigna
  cantidades Netterm desconocidas, ni cambia reglas de finalización.
- La aplicación de decisiones humanas de conciliación conserva las restricciones
  existentes de selección y snapshot; este cambio no las amplía.
- Revalidar selecciones históricas puede tener coste: requiere medir con el volumen
  real antes de publicar. No se agregan infraestructura ni nuevas migraciones.

## Verificación inicial de Codex

Pruebas sobre SQLite en memoria, con comprobación explícita de la configuración;
sin importar archivos clínicos ni conectar a producción. Se cubren consulta del
tablero, no duplicación entre fuentes, pendiente sin confirmar, aceptación tras
confirmar, preservación de diferencias económicas, invalidación por cambios de
cantidad y conservación del monto. Resultado: 270 pruebas OK de `eges_import`,
`liquidacion.tests_cruce_eges`, `liquidacion.tests_respaldo_fuentes` y
`liquidacion.tests_checklist_cierre`. `makemigrations --check --dry-run`: sin
cambios. Sin QA visual ni prueba de rendimiento en Heroku en esta intervención.

## Extensión de cierre TC por Copilot

- El resumen del panel y checklist incluye todos los registros activos con
  prácticas `TOM`, de cualquier rol, sin introducirlos en el motor horario ECO.
- Una TC permanece pendiente hasta confirmar todas las líneas del registro en
  una misma selección vigente de fuentes. Se acepta respaldo EGES o Netterm.
- Una sesión solo TC puede completar este control sin crear un snapshot ECO
  vacío. En una sesión mixta se conservan el control y los pendientes ECO.
- Un registro mixto se cuenta una sola vez. Una revisión explícita
  `REQUIERE_CORRECCION` de TC no se resuelve mediante respaldo.
- Cambiar cantidad o fuentes invalida la confirmación para el resumen actual.
  Los registros anulados no se incluyen; montos, cantidades, horarios y estados
  de sesión no se modifican desde este control.
- El panel muestra confirmados y pendientes TC, sin una versión EGES vacía;
  el formulario de respaldo permite volver al panel de sesiones.

Validación: 134 pruebas de respaldo/cruce/checklist antes de ampliar las
regresiones; 73 pruebas de respaldo/checklist después, incluyendo seis casos
de TC (staff, EGES, confirmación parcial, ECO sin control, sesión mixta con
corrección y anulación). Pruebas Django sobre base de test aislada.
La pasada final de respaldo tuvo 27 pruebas OK, agregando el conteo único de
un registro que contiene ECO y TC y la resolución de su item del checklist.

QA en navegador con SQLite temporal verificada antes de migrar: sesión TC
ficticia pendiente -> consulta y confirmación Netterm por página -> regreso al
panel con un confirmado y cero pendientes TC; checklist en OK para este control.
Monto persistido 1000.00, cantidad 1, horario EXTRA y estado REVISION intactos.
Al agregar una ECO sin respaldo y consolidar el control, permaneció un pendiente
ECO junto a la TC confirmada. Vistas de 390 y 1280 px sin desbordamiento horizontal,
con capturas del panel sin superposiciones.
No se accedió a Heroku ni se evaluó rendimiento con volumen productivo.

## Estadísticas conciliadas, 13/11/2026

La primera integración visual incrustó una página completa de producción dentro
del tablero, duplicando encabezados y filtros. Se retiró y se completó el cambio
mediante una sola población estadística compartida, sin duplicar esa pantalla.

- El tablero conserva una sola selección de fuentes/lotes, fechas y modalidades.
  KPI, gráficos, comparación y PDF se derivan de `construir_estadisticas_fuentes`,
  que parte de las prácticas aceptadas por el conteo conciliado.
- Las selecciones de fuente única (EGES o Netterm) son válidas para estadísticas;
  las reglas de la vista de conciliación no se relajan.
- El PDF conciliado usa la misma selección y agrupación del tablero. Los
  exportadores históricos del portal del director y del PDF EGES mantienen su
  contrato previo.
- Pacientes sin identidad hacen que promedio por paciente sea «Sin dato»;
  prácticas sin médico/cobertura permanecen en «Sin dato» y los restantes
  rankings se agrupan en «Otros», conservando los totales.
- Fechas comparadas: Turno EGES o Pedido Netterm. La distribución por día usa
  esas fechas; la franja horaria usa Hora Turno EGES. Netterm queda como «Sin
  dato» de hora, no se sustituye por Hora Pedido.
- La finalización documentada usa los estados respaldados de cada fuente, no se
  etiqueta como conversión de turnos. Los pendientes/exclusiones se muestran;
  cobertura de exportación permanece explícitamente no confirmada.
- Liquidación y sus reglas económicas no se modificaron en esta integración.

Validación final: las 142 pruebas de `eges_import` pasan; no hay migraciones.
En navegador con SQLite temporal sintética, una coincidencia EGES/Netterm más
un aporte Netterm exclusivo dieron dos prácticas sin duplicar, un informe
confirmado, un pendiente y una finalización documentada del 50%. La franja
horaria mostró la práctica EGES en 10-12 y la Netterm exclusiva en «Sin dato».
El PDF devolvió HTTP 200 y `%PDF-`, con la misma selección y agrupación. Se
revisó escritorio y móvil sin desbordamiento de página. No se accedió a Heroku
ni se midió rendimiento sobre volumen productivo; estos cambios siguen locales.
