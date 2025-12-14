# ✅ Protocolos Cargados en Colegiales

## 🎉 Resumen de Carga Exitosa

Se ejecutaron exitosamente los siguientes comandos:

### 1. Protocolos Base
```bash
python manage.py cargar_protocolos_base
```
**Resultado:**
- ✅ 4 modalidades creadas
- ✅ 9 regiones creadas
- ✅ 12 tags creados

### 2. Protocolos TC Core
```bash
python manage.py seed_protocolos_tc_core
```
**Resultado:**
- ✅ 5 protocolos actualizados
- ✅ 4 fases actualizadas
- Total: 17 protocolos en sistema

**Protocolos incluidos:**
1. Angio-TC Aorta (síndrome aórtico agudo)
2. Uro-TC litiasis (KUB sin contraste)
3. Angio-TC cerebral (stroke code)
4. TC columna cervical trauma (sin contraste)
5. TC tórax con contraste EV (no TEP)

### 3. Protocolos TC Multifásicos
```bash
python manage.py seed_protocolos_tc_multifasicos
```
**Resultado:**
- ✅ 5 protocolos actualizados
- ✅ 13 fases actualizadas

**Protocolos multifásicos:**
- TC Hígado trifásico (3 fases)
- TC Páncreas bifásico (2 fases)
- TC Riñón multifásico (4 fases)
- Uro-TC hematuria (3 fases)
- TC sangrado activo abdomen (2 fases)

---

## 📊 Estado Final

- **Total protocolos**: 17
- **Total fases**: 27
- **Modalidades**: 4 (TC, RM, RX, US)
- **Regiones**: 9
- **Tags**: 12

---

## 🚀 Para Heroku

### Opción A: Desde Heroku Dashboard (Recomendado)

1. Ir a: https://dashboard.heroku.com/apps/TU_APP_NAME
2. Pestaña "More" → "Run console"
3. Ejecutar cada comando uno por uno:

```bash
python manage.py cargar_protocolos_base
python manage.py seed_protocolos_tc_core
python manage.py seed_protocolos_tc_multifasicos
```

### Opción B: Desde Heroku CLI

```bash
# Si tienes Heroku CLI instalado
heroku run python manage.py cargar_protocolos_base --app gestion-servicio-colegiales
heroku run python manage.py seed_protocolos_tc_core --app gestion-servicio-colegiales
heroku run python manage.py seed_protocolos_tc_multifasicos --app gestion-servicio-colegiales
```

### Opción C: Script automático para Heroku

Crear archivo `Procfile.release` en la raíz del proyecto:

```
release: python manage.py migrate && python manage.py cargar_protocolos_base && python manage.py seed_protocolos_tc_core && python manage.py seed_protocolos_tc_multifasicos
```

Esto ejecutará los comandos automáticamente en cada deploy.

---

## ✅ Verificación

### Local (ya funcionando ✓)
```bash
python manage.py check
# System check identified no issues (0 silenced).
```

Probar en: http://localhost:8000/protocolos/elegir/

### En Heroku (después de ejecutar comandos)

1. Abrir: https://TU_APP.herokuapp.com/protocolos/elegir/
2. Verificar que los 10 escenarios tienen botones **verdes**
3. Probar filtros:
   - Buscar "sangrado"
   - Filtro "Urgencia"
   - Filtro "Bifásico"

---

## 🔧 Comandos de Verificación en Heroku

```bash
# Ver protocolos cargados
heroku run python manage.py shell --app TU_APP_NAME
```

Luego en el shell:
```python
from protocolos.models import Protocolo
print(f"Protocolos: {Protocolo.objects.count()}")
for p in Protocolo.objects.all()[:5]:
    print(f"- {p.nombre}")
exit()
```

---

## 📝 Notas Importantes

1. **Idempotencia**: Los comandos son seguros para ejecutar múltiples veces. No crean duplicados.

2. **Orden de ejecución**: Ejecutar en este orden:
   - `cargar_protocolos_base` (primero)
   - `seed_protocolos_tc_core` (segundo)
   - `seed_protocolos_tc_multifasicos` (tercero)

3. **Base de datos**: Los comandos funcionan tanto en SQLite (local) como en PostgreSQL (Heroku).

4. **Migraciones**: Asegurarse de que las migraciones estén aplicadas antes:
   ```bash
   python manage.py migrate protocolos
   ```

---

## 🎯 Próximos Pasos

### En Local (completado ✓)
- [x] Protocolos cargados
- [x] Sistema verificado
- [x] Página funcionando

### En Heroku (pendiente)
- [ ] Ejecutar los 3 comandos en Heroku
- [ ] Verificar página /protocolos/elegir/
- [ ] Confirmar botones verdes en todos los escenarios

---

**Fecha**: 2025-12-13  
**Branch**: feature/colegiales  
**Estado Local**: ✅ OPERATIVO  
**Estado Heroku**: ⏳ PENDIENTE (ejecutar comandos)
