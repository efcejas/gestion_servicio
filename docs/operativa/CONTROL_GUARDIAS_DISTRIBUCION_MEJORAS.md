# Control de Guardias - Mejora de Lógica de Distribución

Fecha: 15/04/2026

## Objetivo

Corregir dos problemas operativos detectados en la distribución automática de guardias de residentes:

1. Evitar asignar guardias a residentes que ya reportaron ausencia en esas fechas.
2. Reducir distribuciones demasiado cercanas, aun cuando no sean técnicamente consecutivas.

Esta propuesta está pensada para implementarse sobre la estructura actual, sin rediseño grande inicial.

## Estado actual de la lógica

La función actual de distribución es:

- [control_guardias/services.py](control_guardias/services.py#L29)

### Qué hace hoy

1. Toma residentes activos con perfil completo.
2. Calcula cuotas mensuales por año de residencia.
3. Construye slots según tipos de guardia y feriados.
4. Filtra candidatos con estas restricciones duras:
- no superar cuota
- no tener guardia el mismo día
- no tener guardia el día anterior
- no tener guardia el día siguiente
5. Luego aplica, si corresponde:
- restricciones por año
- diversidad de año por día
6. Elige por menor carga mensual y, en empate, con componente aleatorio.

### Qué no hace hoy

1. No excluye residentes con ausencias reportadas para esa fecha.
2. No penaliza guardias cercanas con un día intermedio.
3. No distingue entre ausencia reportada y ausencia validada por autoridad.

## Problemas observados

### Problema 1 - Asignación durante ausencias reportadas

Ejemplo:

- Ana reportó ausencia del 11 al 20 de mayo.
- El algoritmo igualmente puede asignarle guardia el 12.

### Causa actual

La distribución no consulta `AusenciaResidente` al construir o filtrar candidatos.

Las ausencias hoy se usan de forma reactiva para reasignación posterior, no como restricción preventiva.

Referencia:

- [control_guardias/services.py](control_guardias/services.py#L567)

### Problema 2 - Guardias demasiado cercanas

Ejemplo:

- Agustín tiene guardia el martes y luego el jueves.

### Causa actual

La lógica solo bloquea diferencia de 1 día. Es decir:

- martes-miércoles: prohibido
- miércoles-jueves: prohibido
- martes-jueves: permitido

Referencia:

- [control_guardias/services.py](control_guardias/services.py#L213)

## Propuesta funcional

## Cambio 1 - Ausencias como restricción dura

### Regla propuesta

Al evaluar candidatos para una fecha determinada, excluir a todo residente que tenga una ausencia reportada cuyo rango incluya esa fecha.

### Regla operativa exacta

Para un slot con `fecha=X`, un residente queda excluido si existe una `AusenciaResidente` tal que:

- `residente = r`
- `fecha_inicio <= X <= fecha_fin`

### Alcance recomendado inicial

Aplicarlo a todas las ausencias registradas en el sistema.

### Riesgo conocido

Como la estructura actual no distingue estados administrativos más finos tipo `RECHAZADA` o `ANULADA`, cualquier ausencia cargada funcionará como bloqueo de distribución.

### Mitigación recomendada

Implementar primero la regla así por simplicidad y revisar después si hace falta refinar estados.

## Cambio 2 - Proximidad entre guardias como penalización blanda

### Regla propuesta

Mantener como regla dura solo la prohibición de días consecutivos.

Agregar además una penalización de prioridad si el candidato ya tiene otra guardia con separación de 2 días.

### Ejemplo

Si el residente tiene una guardia el martes:

- miércoles: prohibido
- jueves: permitido, pero penalizado fuerte
- viernes en adelante: normal

### Razón para hacerlo blando y no duro

Si se transforma de entrada en prohibición absoluta, aumenta mucho la probabilidad de dejar slots sin cubrir.

Con penalización blanda:

1. el algoritmo evita estos casos cuando tiene mejores opciones
2. pero conserva capacidad de cobertura cuando el pool es chico

## Nuevo orden de decisión sugerido

Para cada slot `(fecha, tipo_guardia, es_feriado)`:

### Filtro duro de elegibilidad

Un residente entra al pool solo si cumple todo esto:

1. Tiene cuota disponible.
2. No tiene guardia el mismo día.
3. No tiene guardia el día anterior.
4. No tiene guardia el día siguiente.
5. No tiene ausencia superpuesta a esa fecha.

### Filtros ya existentes que se mantienen

1. Restricción por año, si está activada.
2. Diversidad de año por día, según configuración actual.

### Orden sugerido de prioridad entre candidatos válidos

Para slots no feriados:

1. Menor cantidad de guardias generadas en el mes.
2. Menor penalización por cercanía.
3. Desempate aleatorio.

Para slots feriados:

1. Menor cantidad de guardias generadas en el mes.
2. Menor historial de feriados.
3. Menor penalización por cercanía.
4. Desempate aleatorio.

## Definición de penalización por cercanía

Versión mínima viable sugerida:

- diferencia de 2 días respecto de otra guardia del mismo residente: penalización alta
- diferencia de 3 días: penalización leve o nula
- diferencia mayor: sin penalización

### Implementación conceptual simple

Calcular para cada candidato la distancia mínima entre la fecha del slot y cualquier fecha ya ocupada del residente en ese mes.

Ejemplo de score:

- distancia 2 -> score 100
- distancia 3 -> score 10
- distancia >= 4 -> score 0

Después ordenar por:

- guardias_mes
- score_cercania

## Alternativas posibles

## Opción A - Solo arreglar ausencias

### Qué cambia

1. Se excluyen ausentes del sorteo.
2. No se toca cercanía martes-jueves.

### Ventaja

Muy bajo riesgo.

### Desventaja

No mejora la percepción de distribución “apretada”.

## Opción B - Ausencias duras + cercanía blanda

### Qué cambia

1. Se excluyen ausentes.
2. Se despriorizan guardias con separación de 2 días.

### Ventaja

Es el mejor balance entre mejora real y bajo riesgo de cobertura.

### Desventaja

No elimina 100% los casos cercanos; solo los vuelve excepcionales.

## Opción C - Ausencias duras + cercanía dura

### Qué cambia

1. Se excluyen ausentes.
2. Se prohíben también guardias con separación de 2 días.

### Ventaja

Muy alineada con criterio humano de descanso.

### Desventaja principal

Puede disparar mucho `slots_sin_cubrir`, especialmente si coinciden:

- pocos residentes
- muchas ausencias
- cuotas exigentes
- restricciones por año
- diversidad de año activada

## Recomendación

Implementar primero la Opción B.

## Posibles efectos no deseados

### 1. Aumento de slots sin cubrir

Especialmente si se combinan:

1. ausencias cargadas
2. restricciones por año
3. diversidad de año
4. poca cantidad de residentes

### 2. Resultados más sensibles al azar

Como el algoritmo usa mezcla aleatoria y desempates, al endurecer reglas pueden cambiar bastante los resultados entre corridas.

### 3. Falsos bloqueos por ausencias mal cargadas

Si una ausencia fue informada pero después no correspondía, con la lógica propuesta igual bloquearía la distribución mientras exista registrada.

## Mitigaciones recomendadas

1. Devolver advertencia específica cuando un slot no se cubre por restricciones de disponibilidad/ausencias.
2. Registrar métrica de cuántos candidatos quedaron excluidos por ausencia.
3. Mantener cercanía como criterio blando en primera etapa.
4. Probar con un mes real antes de endurecer más.

## Casos de test a agregar antes de implementar

1. `test_distribucion_excluye_residente_con_ausencia_en_fecha`
2. `test_distribucion_permite_residente_fuera_de_rango_de_ausencia`
3. `test_distribucion_prioriza_mejor_separacion_entre_guardias`
4. `test_distribucion_cercania_dos_dias_solo_como_penalizacion_no_como_bloqueo`
5. `test_distribucion_con_ausencias_y_restricciones_anio_no_rompe_ejecucion`
6. `test_distribucion_reporta_advertencias_si_no_cubre_slots_por_disponibilidad`

## Orden recomendado de implementación

1. Agregar tests de ausencia como exclusión.
2. Implementar exclusión por ausencias.
3. Agregar tests de cercanía blanda.
4. Implementar score de penalización por separación de 2 días.
5. Probar con datos reales de mayo.
6. Recién después evaluar si conviene una versión dura para martes-jueves.

## Decisión sugerida para avanzar

Versión recomendada para desarrollo:

1. Ausencias reportadas = restricción dura.
2. Guardias con separación de 2 días = penalización blanda.
3. Mantener consecutividad como única prohibición dura de descanso en esta primera etapa.
