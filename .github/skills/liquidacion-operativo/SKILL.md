---
name: liquidacion-operativo
description: "Skill para cambios focales en liquidacion: calculo, reglas residencia, B2/B3, cierre mensual, RRHH, checklist, permisos y trazabilidad. Usar cuando el cambio pueda afectar dinero, estados de sesion o registros historicos."
---

# Skill: Liquidacion Operativa

> Ultima actualizacion: 28/06/2026

## Checklist rapida

- Confirmar alcance exacto: calculo, permisos, B2/B3, residencia, RRHH, checklist, UI o docs.
- Leer `.github/instructions/liquidacion.instructions.md` antes de tocar codigo del modulo.
- Identificar si el cambio toca dinero persistido, historial, snapshot o estado de sesion.
- Si el cambio toca facturacion, verificar requisito RRHH: con practicas de residencia requiere preparacion `PREPARADO`; sin residencia es `No requerido`.
- Si el cambio toca bloqueantes de cierre, distinguir navegacion/inspeccion de correccion real.
- Mantener la logica economica fuera de templates.
- Usar servicios existentes antes de crear nuevas reglas.
- Evitar recalculos masivos.
- No enviar emails reales salvo fase especifica aprobada.
- Si hay locks, usar `select_for_update()` sobre queryset simple, sin `select_related()` nullable.

## Fuentes de verdad

- Reglas duras del modulo: `.github/instructions/liquidacion.instructions.md`.
- Residencia, Doppler, C1/C2, B2/B3: `docs/liquidacion/reglas-descuento-residencia.md`.
- Modelos y calculo: `liquidacion/models.py`.
- Servicio de reglas residencia: `liquidacion/services.py`.
- Snapshot RRHH D1 y requisito para facturar: `liquidacion/services_rrhh.py`.
- Checklist E1 y acciones E2: `liquidacion/services_cierre.py`, `liquidacion/services_auditoria.py`, `liquidacion/views.py`.
- Vistas B2/B3/D1/sesiones: `liquidacion/views.py`.
- Clasificacion automatica y override: `liquidacion/signals.py`.

## Archivos criticos

- `liquidacion/models.py`: `calcular_monto`, sesiones, reglas, snapshots, historial.
- `liquidacion/views.py`: escrituras criticas, B2/B3, D1, sesiones.
- `liquidacion/services.py`: reglas de residencia y servicios compartidos.
- `liquidacion/services_rrhh.py`: snapshot auditable para RRHH, deteccion de practicas de residencia y requisito para facturar; no recalcula.
- `liquidacion/services_cierre.py`: checklist visual/operativo; no calcula montos.
- `liquidacion/services_auditoria.py`: gate administrativo y hallazgos accionables; no corrige datos.
- `liquidacion/signals.py`: clasificacion automatica; debe respetar override Extra Residencia.
- `templates/liquidacion/*`: UX; no fuente de verdad economica.
- `liquidacion/tests_auditoria_2026_05_11.py`: regresiones B2/B3/sesiones/gate.

## Comandos por tipo de cambio

### Reglas residencia C1

```bash
python manage.py test liquidacion.tests_regla_descuento_residencia --verbosity=1
python manage.py makemigrations --check --dry-run
```

### Calculo residencia C2

```bash
python manage.py test liquidacion.tests_regla_descuento_residencia_calculo --verbosity=1
python manage.py test liquidacion.tests_regla_descuento_residencia --verbosity=1
python manage.py makemigrations --check --dry-run
```

### Revision horaria B2/B3

```bash
python manage.py test liquidacion.tests_auditoria_2026_05_11 --verbosity=1 --failfast
python manage.py makemigrations --check --dry-run
```

Preferir tests focales de la clase/metodo afectado si el usuario pide no correr suite larga.

### RRHH D1

```bash
python manage.py test liquidacion.tests_preparacion_rrhh --verbosity=1
python manage.py makemigrations --check --dry-run
```

Si el cambio afecta `CERRADA -> FACTURADA`, agregar test focal en `liquidacion.tests_auditoria_2026_05_11.SesionContableWorkflowPermissionsTest`.

### Checklist E1

```bash
python manage.py test liquidacion.tests_checklist_cierre --verbosity=1
python manage.py makemigrations --check --dry-run
```

Incluye E2 si el cambio toca acciones de bloqueantes, inspeccion read-only de registros o apertura del gate desde el checklist.

### Override Extra Residencia

```bash
python manage.py test liquidacion.tests.ClasificacionHorarioResidenciaProxyTest --verbosity=1
python manage.py makemigrations --check --dry-run
```

### Cambio documental

```bash
git diff -- <archivos-documentales>
git status --short
```

No correr tests Django para cambios puramente documentales salvo pedido explicito.

## Senales de riesgo

- El cambio toca `calcular_monto()`.
- El cambio modifica `signals.py`.
- El cambio permite operar en `CERRADA`, `FACTURADA` o `PAGADA`.
- El cambio altera la transicion `CERRADA -> FACTURADA`.
- El cambio actualiza mas de un registro.
- El cambio combina `select_for_update()` con `select_related()`.
- El cambio crea o modifica snapshots/historial.
- El cambio mueve reglas a template.
- El cambio convierte una vista read-only de inspeccion en una vista de edicion.
- El cambio envia email real.

## Salida esperada

- Que se cambio o audito.
- Que reglas sensibles se preservaron.
- Que comandos se ejecutaron.
- Estado final de `git status --short` cuando corresponda.
- Riesgo residual y proximo paso si queda algo abierto.
