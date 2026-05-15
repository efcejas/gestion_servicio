---
applyTo: "liquidacion/**/*.py"
---

# Instrucciones para liquidacion

> Ultima actualizacion: 13/05/2026

## Prioridad del modulo

- `liquidacion/` afecta facturacion real. Cualquier cambio debe minimizar riesgo operativo.
- Priorizar exactitud de calculo, permisos por rol y trazabilidad sobre cambios cosmeticos.
- Evitar redisenos grandes sin necesidad. Primero MVP funcional y seguro.

## Reglas de negocio clave

- Estados de sesion contable: `ABIERTA -> REVISION -> CERRADA -> FACTURADA -> PAGADA`.
- Medicos (staff, residentes, jefe/instructor, cardiologo) registran en `ABIERTA` o `REVISION`.
- `administrativo` y `superuser` pueden operar en `CERRADA` y `FACTURADA`.
- En `PAGADA` no se debe permitir nuevas practicas ni correcciones.
- Cardiologo se comporta como staff para calculo (sin INTRA/EXTRA).

## Decisiones funcionales vigentes (Mayo 2026)

- Jefe de residentes e instructor de residentes deben ver solo sus propios registros (igual que staff).
- La vista global operativa se reserva para `administrativo`, `jefe_servicio` y `superuser`.
- Etapa `REVISION` se usa como revision/disconformidad y control operativo.
- Correcciones sensibles deben dejar trazabilidad explicita.

## Modelos y calculo

- Mantener `monto_calculado` inmutable por registro historico (no recalcular por cambios de lista de precios).
- Para calculo usar siempre metodo del modelo (`calcular_monto`) y no duplicar logica en templates.
- Bonus urgencia RM: respetar regla de remoto + paciente internado + ventana temporal definida.

## Permisos y vistas

- En CBV, validar acceso por rol en `dispatch()` y no solo en template.
- En `UpdateView` y `DeleteView`, limitar queryset al usuario cuando corresponda.
- Para vistas globales, usar `UserPassesTestMixin` con matriz de roles explicita.

## Trazabilidad obligatoria

- En ediciones/correcciones guardar `modificado_por` y `fecha_modificacion`.
- Si la correccion impacta sesiones cerradas/facturadas, exigir `motivo_modificacion`.
- No permitir cambios silenciosos en registros sensibles.

## Calidad y performance

- Evitar N+1: usar `select_related` y `prefetch_related` en listados mensuales/globales.
- En operaciones criticas de guardado, usar `transaction.atomic`.
- No modificar migraciones ya aplicadas; crear nuevas migraciones de correccion.

## Testing minimo antes de merge

- Correr: `python manage.py test liquidacion`.
- Si se tocan permisos: agregar/actualizar tests de acceso por rol.
- Si se toca calculo: agregar/actualizar tests de monto (OS, horario, bonus).
- Si se toca cierre de sesion: tests por estado (`ABIERTA/REVISION/CERRADA/FACTURADA/PAGADA`).
