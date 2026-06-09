# RFC - Reglas explícitas de descuento residencia

## 1. Problema
- La modalidad ECO/DOP/ECOCAR no alcanza para decidir política de descuento.
- Algunos Doppler realizados por residentes pueden aplicar descuento intra residencia.
- El hotfix actual protege de descuentos indebidos pero deja casos legítimos para revisión manual.

## 2. Decisión
- Implementar modelo ReglaDescuentoResidencia.
- Resolver elegibilidad por estudio/grupo, rol y vigencia.
- Mantener fallback legado con ECO general real en V1.

## 3. Modelo propuesto
- estudio nullable
- grupo_tarifario nullable
- aplica_medico_residente
- aplica_jefe_residentes
- aplica_instructor_residentes
- vigencia_desde
- vigencia_hasta nullable
- activo
- observacion
- creado_por
- actualizado_por
- fecha_creacion
- fecha_actualizacion

## 4. Precedencia
- estudio > grupo > fallback legado.
- conflictos: vigencia_desde más reciente, id mayor, log warning.

## 5. Constraints y validaciones
- debe tener estudio o grupo.
- no puede tener ambos.
- vigencia_hasta >= vigencia_desde.
- evitar solapamientos por clean().
- UniqueConstraint base por entidad, vigencia_desde y activo.

## 6. Servicio
- estudio_aplica_descuento_residencia(estudio, rol, fecha)
- devuelve aplica, fuente, regla_id, motivo.

## 7. Plan incremental

### Fase 1
- modelo + migración + admin + servicio + tests.
- no tocar cálculo.
- no tocar clasificación.

### Fase 2
- integrar en clasificación INTRA/EXTRA/NA.

### Fase 3
- integrar en calcular_monto.

### Fase 4
- reportes/conflictos/hardening.

## 8. Criterios de aceptación Fase 1
- Se pueden crear reglas en admin.
- No se permiten reglas huérfanas.
- No se permiten reglas con estudio y grupo simultáneamente.
- No se permiten vigencias inválidas.
- El servicio respeta estudio > grupo > fallback.
- Roles no residencia devuelven False.
- Suite liquidacion sigue verde.
- No cambia ningún monto.

## 9. Qué NO hacer en Fase 1
- No tocar calcular_monto.
- No tocar services de clasificación.
- No tocar views de carga.
- No recalcular históricos.
- No tocar templates.
- No cambiar Fase A.

## 10. Checklist de tests
- regla por estudio.
- regla por grupo.
- precedencia estudio sobre grupo.
- fallback legado.
- roles residencia.
- rol no residencia.
- vigencia activa/inactiva/fuera de rango.
- constraints/clean.
