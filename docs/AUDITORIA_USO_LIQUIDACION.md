# AUDITORÍA DE USO: ¿QUÉ SE USA REALMENTE?
## Sanatorio Colegiales - Febrero 2026

---

## CHECKLIST DE VALIDACIÓN

Antes de eliminar, necesitás verificar si eso que decimos "no sirve" realmente no se usa.

### PREGUNTAS A RESPONDER:

#### 🔍 **Procedimientos de Intervensionismo**
```
¿Se usa RegistroProcedimientosIntervensionismo?

[ ] ¿Ves procedimientos en dashboard/reportes regularmente?
[ ] ¿Los médicos cargaban procedimientos?
[ ] ¿Qué procedimientos eran? (cateterismo, angiografía, etc.)
[ ] ¿Se facturan diferente que un "estudio"?
[ ] ¿Necesitas histórico de P.I. para auditoría?

SI TODAS SON "NO/NO SÉ": ELIMINAR
SI ALGUNA ES "SÍ": Preguntar si absorber en Estudios es opción o necesita tabla separada
```

#### 🔍 **Portal sin Login**
```
¿Alguien accede a /portal/?

[ ] ¿Está linkado desde algún lado en navbar/menú?
[ ] ¿Aparece en Google Analytics (si tienes)?
[ ] ¿Qué mostraba esa página?
[ ] ¿Un administrativo sin login realmente la necesita?

SI TODAS SON "NO": ELIMINAR + agregar @login_required a reportes
```

#### 🔍 **Carga de Excel**
```
¿Se usa CargaMasivaView?

[ ] ¿Alguien subió archivos en último año?
[ ] ¿Cuál era el formato?
[ ] ¿Se procesaron correctamente o errores?
[ ] ¿Hay datos muertos por carga mal hecha?

SI TODAS SON "NO/NO SÉ": ELIMINAR (puede agregarsse después si se comprueba necesario)
```

#### 🔍 **Tres vistas de reportes** (Informados, Ecografías, Procedimientos)
```
¿Se usan las 3 vistas separadas o bastaría 1 vista con filtros?

[ ] ¿Alguien bookmarkeó las 3 URLs?
[ ] ¿Son "reportes diarios" o "reportes ocasionales"?
[ ] ¿Necesitan formato diferente (tabla vs gráfico)?
[ ] ¿El admin dice "necesito ver SOLO ecografías" regularmente?

SI SON "Reportes ocasionales, mismo formato": CONSOLIDAR
SI SON "Reports diarios, diferente formato": MANTENER SEPARADAS (pero mejorar código base)
```

---

## ANÁLISIS DE DATOS

### Opción 1: Ver en Django Admin

```bash
# Conectarte a la BD (local o Heroku)
python manage.py dbshell

# Ver cuántos registros hay en cada tabla
SELECT COUNT(*) FROM liquidacion_estudios;
SELECT COUNT(*) FROM liquidacion_registroestudiospormedico;  
SELECT COUNT(*) FROM liquidacion_registroprocedimientosintervensionismo;
SELECT COUNT(*) FROM liquidacion_diasinpacientes;

# Ver cuándo fue el último registro (está activa?)
SELECT MAX(fecha_registro) FROM liquidacion_registroestudiospormedico;
SELECT MAX(fecha_procedimiento) FROM liquidacion_registroprocedimientosintervensionismo;
```

### Opción 2: Ver en Settings / Django Admin

1. Entrar a `/admin/` como superuser
2. Ver cada tabla:
   - ¿Estudios: cuántos registros?
   - ¿RegistroEstudiosPorMedico: cuántos? ¿cuándo fue el último?
   - ¿RegistroProcedimientos: cuántos? ¿edad?
   - ¿DiaSinPacientes: cuántos?

### Opción 3: Ver Heroku Logs / Request Logs

```bash
heroku logs --app gestion-colegiales | grep "liquidacion"
# Ver qué URLs se accedieron en últimas 24h
```

---

## MATRIZ DE ELIMINACIÓN ASEGURADA

| Componente | ¿Datos históricos? | ¿En uso activo? | Acción |
|-----------|------------------|----------------|--------|
| **RegistroProcedimientosIntervensionismo** | VALIDAR | VALIDAR | Export a CSV + ELIMINAR si <100 registros en 1 año |
| **CargaMasivaView** | VALIDAR | VALIDAR | Ver logs, si no appears → DELETE sin miedo |
| **PortalLiquidacionInicioView** | NO | PROBABLEMENTE NO | DELETE + ADD @login_required a reportes |
| **3 vistas de reportes** | -- | VALIDAR PATRÓN | Si es "filtro" → CONSOLIDAR. Si "vista separada permanente" → MEJORAR Y MANTENER. |

---

## PLAN EJECUTABLE AHORA

### Paso 0: BACKUP POR SI ACASO
```bash
# Export todas las tablas de liquidacion a CSV (safety net)
python manage.py dumpdata liquidacion --indent 2 > liquidacion_backup_2026-02-16.json

# O directamente desde DB:
pg_dump gestion_colegiales > liquidacion_backup_2026-02-16.sql (if Heroku)
```

### Paso 1: VALIDAR CÓN TU EQUIPO (30 min)
```
Email a coordinador/admin:

"Necesito validar: ¿De estos módulos, cuáles usás realmente?

1. Procedimientos de Intervensionismo (cateterismo, angiografía, etc)
   - ¿Se cargan? ¿Se facturan diferente?
   - Último que cargaste: ____?

2. Carga de archivos Excel
   - ¿Subiste alguna vez? ¿Cuándo?
   - Realmente necesario o entradas manual alcanza?

3. Portal sin login (la pantalla que entra sin usuario)
   - ¿La usan? ¿Para qué?
   - Dónde está linkeado?

Responde hoy porfa para limpiar sistema ✓
"
```

### Paso 2: EJECUTAR (en orden, bajo control)
```
A) SI confirmás que NADA de P.I. se usa:
   [ ] Backup de datos de RegistroProcedimientosIntervensionismo a CSV
   [ ] Eliminar modelo
   [ ] Eliminar sus 5 vistas
   [ ] Eliminar sus 4 formularios
   [ ] Eliminar sus 5 URLs
   [ ] Test: sistema sigue funcionando? OK → DEPLOY

B) SI confirmás que NO se usa Carga Excel:
   [ ] Eliminar CargaMasivaView
   [ ] Eliminar CargaExcelForm
   [ ] Eliminar URL /carga-excel/
   [ ] Test: OK → DEPLOY

C) SIEMPRE: Hacer públicos login todos los reportes:
   [ ] @login_required en PortalLiquidacionInicioView (o ELIMINAR)
   [ ] @login_required en todos los export_excel_*
   [ ] @rolle_required en los que sean admin-only
   [ ] Test en navegador privado: redirige a login? ✓ → DEPLOY

D) LUEGO (semana 2): Consolidar reportes
   [ ] Crear ReporteEstudiosListView única
   [ ] Move 3 vistas viejas al mismo endpoint con filtros
   [ ] Verificar cálculos sean iguales
   [ ] Test A/B: vista vieja vs nueva
   [ ] Deprecar viejos URLS (redirect a nuevas)
   [ ] DEPLOY
```

---

## CHECKLIST PRE-LIMPIEZA (Cópialo cuando empieces)

```markdown
## Before We Start Cleanup

- [ ] Backup completo: BD + code (git commit)
- [ ] Confirmación de stakeholder: "OK eliminar ________"
- [ ] Tests escritos: al menos las vistas core (create, list, update)
- [ ] Staging deployment: copiar DB real a local/staging
- [ ] Documentación de datos: ¿qué se mueve/se copia/se descarta?

## After Each Change

- [ ] Test básico: pantalla carga sin 500?
- [ ] Test de permisos: médico no puede ver otros? Admin sí?
- [ ] Heroku logs limpio: sin errores de imports?
- [ ] Admin interface: modelos deletreados bien?

## Pre-Deploy

- [ ] Backup final de BD en Heroku
- [ ] Feature flag activo (si implementas uno)
- [ ] Monitoreo post-deploy: Los primeros 30 min, eyes on logs
- [ ] Rollback plan: ¿qué haría si explota?
```

---

## CONCLUSIÓN

**No elimines nada sin:**
1. ✅ Confirmar con coordinador/admin: "¿lo usas?"
2. ✅ Backup de datos (export JSON o CSV)
3. ✅ Tests locales (antes de deploy)
4. ✅ Staging validation (copiar BD real)
5. ✅ Rollback plan por si necesitas volver atrás

**Orden recomendado:**
1. Primero: Eliminar muerto (procedimientos, carga excel) si confirms NO uso
2. Segundo: Mejorar auth en rutas públicas (agregar @login_required)
3. Tercero: Reorganizar código limpio (renombrar modelos, partir views)
4. Por último: Agregar nuevas piezas (SesionContable, auditoría)

**Riesgo:** BAJO si seguis este plan. ALTO si saltas pasos.
