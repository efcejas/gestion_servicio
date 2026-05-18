# Matriz de Cierre - Liquidacion por Rol (17/05/2026)

## 1. Estado tecnico base del modulo
- Migraciones `liquidacion`: aplicadas hasta `0032`.
- Tests `liquidacion`: 54 OK, 1 skipped.
- Riesgo transversal: pruebas `accounts` con fallos de consistencia (`cargo/rol`, `register`, `__str__`), que puede impactar UX de acceso por rol.

## 2. Matriz rol x ingreso x acciones

Leyenda:
- `SI`: permitido y visible.
- `PARCIAL`: permitido pero con condicion de grupo/estado o con UX inconsistente.
- `NO`: no permitido.

| Rol | Al ingresar | Home (bloque principal) | Navbar | Registrar estudios | Ver mis registros | Portal liquidacion | Guardia pasiva | Liquidacion mensual | Estado de cierre |
|---|---|---|---|---|---|---|---|---|---|
| superuser | Redirige a `admin_dashboard` | N/A (usa admin dashboard) | Gestion completa | SI | SI | SI | SI | SI | PARCIAL |
| jefe_servicio | Home regular | Bloque staff/jefatura | Gestion completa | SI | SI | SI | SI | SI | PARCIAL |
| medico_staff | Home regular | Bloque staff (segun grupo) | Recursos + Docencia | PARCIAL | PARCIAL | NO | NO | NO | PARCIAL |
| cardiologo | Home cardiologo especifica | Registrar + Mis registros + metricas | Recursos (protocolos/novedades) | SI | SI | NO | NO | NO | PARCIAL |
| medico_residente | Home residentes | Clases/protocolos/guardias/preinformes | Recursos + Docencia + Guardias | SI (si sesion abierta/revision) | SI | NO | SI (monto backend) | NO | AVANZADO |
| jefe_residentes | Home residentes | Recursos/docencia/guardias/preinformes | Recursos + Docencia + Guardias | SI (si sesion abierta/revision) | SI | NO | SI (monto backend) | NO | AVANZADO |
| instructor_residentes | Home residentes | Recursos/docencia/guardias/preinformes | Recursos + Docencia + Guardias | SI (si sesion abierta/revision) | SI | NO | SI (monto backend) | NO | AVANZADO |
| administrativo | Home administrativa (o bloque pedidos) | Novedades + docencia (segun grupo) | Recursos + Docencia opcional + Gestion consultorios | NO (como medico) | NO (como medico) | PARCIAL (segun links y vistas) | SI (edicion de monto en config) | PARCIAL | PARCIAL |
| tecnico | Home tecnico | Protocolos + Novedades | Recursos | NO | NO | NO | NO | NO | AVANZADO |
| enfermeria/otro | Home fallback | Mensaje de dashboard en configuracion | Recursos minimos (novedades) | NO | NO | NO | NO | NO | AVANZADO |

## 3. Que pasa hoy al entrar (resumen operativo)
- `superuser`: salta al dashboard administrativo.
- `piloto_dictado`: salta a dictado rapido.
- `cardiologo`: home especifica con flujo corto (registrar/ver) y metricas.
- `residentes/jefes/instructores`: home academica-operativa (guardias + preinformes + recursos).
- `staff/jefe_servicio`: home staff con variaciones por grupos y rol.
- `administrativo`: bifurca entre bloque de pedidos y bloque administrativo/docencia.

## 4. Errores o puntos de falla probables hoy

### Criticos
1. **Inconsistencia `cargo` vs `rol` en templates y tests de cuentas**
- Riesgo: rutas o bloques de UI no esperados para ciertos usuarios.
- Evidencia: tests `accounts` fallando.

2. **Duplicacion de politica de acceso entre home y navbar**
- Riesgo: el usuario ve opciones en un lugar y no en otro.
- Impacto: confusion operativa y tickets de soporte.

### Medios
3. **Dependencia de grupo Django para algunos bloques staff/admin**
- Riesgo: alta de usuario incompleta deja UI vacia o parcial.

4. **Riesgo de integridad en datos historicos al migrar**
- Ya aparecio con huérfanos previos (resuelto localmente, falta protocolo formal).

## 5. Puntos aun por definir (decision final)
1. Matriz unica de permisos finales por rol para:
- Home.
- Navbar.
- Vistas directas (URL).

2. Politica definitiva de cardiologo:
- Si mantiene o no acceso a `protocolos`/`novedades` en navbar.
- Si se habilita luego guardia pasiva o se mantiene fuera.

3. Politica de administrativo sobre liquidacion:
- Solo configuracion/mantenimiento.
- O tambien acceso de lectura a resumen mensual global.

4. Convencion definitiva de identidad funcional:
- Estandarizar a `rol` (deprecando chequeos legacy por `cargo`).

## 6. Circuitos a cerrar para 100% operativo

1. **Circuito permisos y navegacion (prioridad alta)**
- Consolidar una sola matriz rol x accion.
- Aplicar igual criterio en home, navbar y vistas.
- Resultado esperado: cero contradicciones visuales o funcionales.

2. **Circuito operativo guardia pasiva (prioridad alta)**
- Confirmar responsable de actualizar monto vigente.
- Definir protocolo de cambio con motivo y fecha efectiva.
- Validar vista administrativa de configuracion + historial.

3. **Circuito calidad de cuentas/roles (prioridad alta)**
- Corregir tests `accounts` fallidos.
- Unificar `rol/cargo` en templates y modelo.

4. **Circuito predeploy de datos (prioridad media)**
- Agregar checklist de integridad para detectar huérfanos antes de migrar.

5. **Circuito UAT por rol (prioridad alta)**
- Smoke test de 30-45 min por rol operativo principal:
  - cardiologo
  - medico_staff
  - jefe_servicio
  - administrativo

## 7. Estimacion de cierre
- Cierre tecnico minimo: 8-12 horas efectivas.
- Cierre robusto con UAT + hardening: 16-24 horas efectivas.
- Calendario recomendado: 2-4 dias de trabajo + 48-72h de observacion post despliegue.

## 8. Definicion de terminado (Done)
Se considera modulo `100% operativo` cuando:
1. Matriz de permisos cerrada y aplicada en home/navbar/vistas.
2. Tests `liquidacion` OK y `accounts` sin fallos por roles/accesos.
3. Guardia pasiva operando con monto backend + trazabilidad activa.
4. Checklist predeploy ejecutado sin hallazgos.
5. UAT por rol completado y firmado sin bloqueantes.
