# control_stock

Módulo de gestión de stock por área para el sistema de gestión del servicio médico.

---

## Arquitectura

### Modelos principales

```
AreaServicio
  └── StockPorArea (cache del total)
        └── LoteEnArea (fuente de verdad — FEFO)
              └── MovimientoStock (log inmutable de auditoría)
Producto (catálogo global)
```

| Modelo | Rol |
|---|---|
| `AreaServicio` | Área/servicio del hospital. Tiene responsable y flag activa. |
| `Producto` | Catálogo global. `codigo_barras` único. |
| `StockPorArea` | **Cache** del total por producto+área. No editar directo: siempre usar `recalcular()`. |
| `LoteEnArea` | Unidad FEFO: lote + fecha vencimiento + cantidad. Fuente de verdad. |
| `MovimientoStock` | Log inmutable de todas las operaciones. Soporta anulación con audit trail. |

### Flujo de una entrada

```
scanner.html  →  api_registrar_movimiento
                  ├── get_or_create(Producto)
                  ├── get_or_create(StockPorArea)
                  ├── get_or_create(LoteEnArea)  ← agrupa por codigo+lote+fecha_venc
                  ├── lote.cantidad += n
                  └── stock.recalcular()
```

### Flujo de una salida / uso (FEFO)

Las salidas consumen lotes ordenados por `fecha_vencimiento ASC, creado_en ASC`.
Pueden distribuirse en varios lotes si uno no tiene suficiente cantidad.
El `MovimientoStock` referencia solo el primer lote afectado (**limitación conocida**, ver pendientes).

---

## Tipos de movimiento

| Tipo | Descripción | Requiere motivo | Requiere autorización |
|---|---|---|---|
| `entrada` | Reposición de stock | No | Sí (ROLES_STOCK) |
| `salida` | Salida genérica (legacy) | No | Sí (ROLES_STOCK) |
| `uso` | Consumo en procedimiento (reversible 15 min) | No | Sí (ROLES_STOCK) |
| `descarte` | Retiro por vencimiento/daño | **Sí** | Sí (ROLES_PUEDEN_DESCARTAR) |
| `ajuste` | Corrección de inventario | **Sí** | Sí (ROLES_PUEDEN_DESCARTAR) |

---

## Control de acceso

| Constante | Roles incluidos | Dónde se aplica |
|---|---|---|
| `ROLES_STOCK` | medico_staff, medico_residente, jefe_residentes, instructor_residentes, jefe_servicio, cardiologo, tecnico, enfermeria | Acceso a todas las vistas y APIs |
| `ROLES_PUEDEN_DESCARTAR` | jefe_servicio, medico_staff, jefe_residentes, instructor_residentes | Descarte y ajuste de inventario |
| `ROLES_GESTION` | jefe_servicio, jefe_residentes, instructor_residentes, medico_staff | Crear/editar productos |

Los superusuarios siempre pasan todos los controles.

---

## Endpoints API

Todas las APIs requieren `@login_required` + `_check_rol()`.

| Endpoint | Método | Descripción |
|---|---|---|
| `api/buscar/` | GET | Busca producto por código de barras. Fallback a UPCItemDB. |
| `api/buscar-global/` | GET | Busca productos por nombre, agrupa por producto. |
| `api/buscar-nombre/` | GET | Devuelve ≤15 productos que coincidan con nombre. ⚠ N+1 si se pasa `area_id`. |
| `api/analizar-foto/` | POST | Envía imagen base64 a GPT-4o-mini Vision. Fallback por nombre si no hay barcode. |
| `api/movimiento/` | POST | Registra cualquier tipo de movimiento. Vec entrada con FEFO. |
| `api/anular/<id>/` | POST | Anula un movimiento (ventana 24 h para roles, ilimitada para superuser). |
| `api/salida-rapida/` | POST | Salida/entrada sin escanear. FEFO automático. |
| `api/lotes/` | GET | Lista lotes activos de producto+área con flags de vencimiento. |
| `api/reportar-lote/` | POST | Cualquier usuario puede reportar un lote para descarte. |
| `api/descarte-masivo/` | POST | Descarta lista de lotes (máx 50). Solo ROLES_PUEDEN_DESCARTAR. |

---

## Vistas HTML

| URL | Vista | Acceso |
|---|---|---|
| `/stock/` | `dashboard` | ROLES_STOCK |
| `/stock/area/<id>/` | `detalle_area` | ROLES_STOCK |
| `/stock/scanner/` | `scanner` | ROLES_STOCK |
| `/stock/historial/` | `historial` | ROLES_STOCK |
| `/stock/historial/exportar/` | `exportar_historial_csv` | ROLES_STOCK |
| `/stock/vencimientos/` | `vencimientos` | ROLES_STOCK |
| `/stock/buscar/` | `buscar_producto` | ROLES_STOCK |
| `/stock/producto/nuevo/` | `crear_producto` | ROLES_STOCK |
| `/stock/producto/<id>/editar/` | `editar_producto` | ROLES_GESTION |

---

## Features especiales

### IA en el scanner
- `api_analizar_foto` envía imagen a GPT-4o-mini Vision con prompt estructurado.
- Extrae: código de barras, nombre, fecha de vencimiento, número de lote, categoría sugerida.
- Si no hay barcode: busca el producto en la DB local por nombre (primero búsqueda exacta, luego por cada palabra ≥ 4 caracteres).
- Cuando el match es por nombre (no por barcode), el frontend muestra badge naranja "Coincidencia por nombre".

### Vencimientos
- Filtra por `LoteEnArea.fecha_vencimiento__lte=hoy+días` + `activo=True` + `cantidad__gt=0`.
- Superuser y ROLES_PUEDEN_DESCARTAR: ven checkboxes y pueden descartar individual o masivamente.
- Otros roles: pueden "Reportar" lotes (marca `reportado_para_descarte=True`) para que un autorizado tome acción.
- Tab "Reportados" solo visible para roles sin permiso de descarte directo.

### Alertas de stock bajo
- `signals.py` → `post_save` de `MovimientoStock` → `enviar_alerta_stock_bajo` si `stock.bajo_minimo`.
- Envía email al responsable del área de forma **síncrona** en el request.

---

## Tests

Correr con:
```bash
python manage.py test control_stock
```

Cobertura (28 tests):

| Suite | Qué cubre |
|---|---|
| `LoteEnAreaModelTests` | `vencido`, `vence_pronto`, `vence_en_dias`, sin fecha |
| `ApiRegistrarMovimientoTests` | Entrada, acumulación de lote, FEFO, descarte con lote_id, permisos |
| `VencimientosViewTests` | Filtros cantidad > 0, sin fecha, filtro días, puede_descartar por rol |
| `ApiReportarDescarteMasivoTests` | Reportar lote, descarte masivo, validaciones, permisos |

---

## Bugs conocidos / Pendientes

### 🔴 Alta prioridad

- **Anulación de salida FEFO multi-lote**: si una salida distribuyó cantidad en N lotes, `MovimientoStock.lote` apunta solo al primero. Al anular, toda la cantidad se restaura en ese único lote, corrompiendo los balances individuales (aunque `StockPorArea.cantidad` queda correcto). Solución: guardar todos los lotes afectados (tabla intermedia `MovimientoLote`).

### 🟠 Media prioridad

- **Dashboard y `detalle_area` usan `MovimientoStock` para vencimientos** en lugar de `LoteEnArea`. Pueden mostrar datos stale si un lote fue descartado o reaprovisado. Migrar ambas vistas a consultar `LoteEnArea` directamente.
- **`AreaServicio.tiene_vencimientos_proximos()`** también consulta `MovimientoStock` (stale). No se usa en las vistas actuales — candidato a eliminar o reescribir.
- **Alertas de stock bajo sin cooldown**: cada movimiento que deja el stock bajo mínimo dispara un email. Si se registran 10 salidas seguidas, el responsable recibe 10 emails. Implementar cooldown por área+producto (ej. 1 alerta cada 6 h usando Django cache).
- **`api_salida_rapida` duplica lógica FEFO** de `api_registrar_movimiento`. Candidato a extraer a un servicio `_descontar_fefo(stock, cantidad, usuario, observacion)`.

### 🟡 Baja prioridad

- **`api_buscar_por_nombre` N+1**: hace un `StockPorArea.objects.get()` por cada producto encontrado. Refactorizar con un `filter(producto__in=...).values(...)`.
- **`services.py` sentinel de caché frágil**: usa el string `'__not_found__'` como valor centinela en `cache.set`. Reemplazar con patrón `cache.get(key, _MISSING)` con objeto sentinel.
- **Docstring de `views_api.py`** menciona `api_uso_rapido` que no existe (el endpoint real es `api/salida-rapida/`).
