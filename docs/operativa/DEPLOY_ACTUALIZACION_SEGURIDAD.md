# 🔒 Deploy de Actualización de Seguridad a Heroku
**Fecha:** 7 de marzo de 2026  
**Actualización:** 25 vulnerabilidades críticas corregidas

---

## 📋 RESUMEN DE CAMBIOS

### Paquetes Actualizados
| Paquete | Versión Anterior | Versión Nueva | Criticidad |
|---------|------------------|---------------|------------|
| Django | 5.1.4 | 5.2.12 | 🔴 CRÍTICA (SQL Injection) |
| pypdf | 5.1.0 | 6.7.5 | 🔴 CRÍTICA (DoS) |
| urllib3 | 2.6.0 | 2.6.3 | 🟡 Alta |
| requests | 2.32.3 | 2.32.5 | 🟡 Alta |
| sqlparse | 0.5.3 | 0.5.5 | 🟡 Media |
| cryptography | 44.0.0 | 46.0.5 | 🟡 Alta |
| fonttools | 4.55.4 | 4.61.1 | 🟡 Media |
| brotli | 1.1.0 | 1.2.0 | 🟡 Media |

### Configuraciones de Seguridad Añadidas
✅ HTTP Security Headers (X-Frame-Options, Content-Type-Nosniff, etc.)  
✅ Password validators mejorados (12 caracteres mínimo)  
✅ Cookie security (HttpOnly, SameSite)  
✅ Configuración HTTPS para producción (HSTS, SSL Redirect)

---

## ⚠️ ANTES DE DESPLEGAR

### 1. Ejecutar Tests Localmente (CRÍTICO)

```powershell
# Activar entorno virtual
.\gestion_env\Scripts\Activate.ps1

# Ejecutar suite de tests completa
python manage.py test

# Verificar compatibilidad Django 5.2
python manage.py check --deploy
```

**Importante:** Django pasó de 5.1 → 5.2 (major version). Aunque `manage.py check` no mostró problemas, **debes ejecutar los tests** antes de desplegar.

### 2. Probar Funcionalidades Críticas Manualmente

- [ ] **Login/Logout** → Django auth podría tener cambios
- [ ] **Crear Pedido** → Verificar formularios y validaciones
- [ ] **Generar PDF** → pypdf cambió de 5.1 → 6.7 (major version)
- [ ] **Subir archivos** → Verificar storage y validaciones
- [ ] **Gmail API** → Verificar que `procesar_pedidos_auto` funciona

### 3. Crear Backup de Base de Datos Heroku

```bash
# Crear backup manual antes del deploy
heroku pg:backups:capture --app <tu-app>

# Verificar backups disponibles
heroku pg:backups --app <tu-app>
```

### 4. Verificar runtime.txt

Se creó `runtime.txt` con Python 3.12.8 (compatible con Heroku-24):
```
python-3.12.8
```

**Nota:** Tu entorno local usa Python 3.13.2, pero Heroku aún no soporta 3.13. Python 3.12.8 es compatible con Django 5.2 y todos los paquetes actualizados.

---

## 🚀 DESPLIEGUE A HEROKU

### 1. Verificar Config Vars de Seguridad

Ve a **Heroku Dashboard → Settings → Config Vars** y verifica:

```bash
# Verificar variables actuales
heroku config --app <tu-app>
```

**Variables REQUERIDAS para seguridad:**

```env
# Debe estar en False para activar configuraciones de seguridad
DEBUG=False

# Debe incluir tu dominio Heroku
ALLOWED_HOSTS=<tu-app>.herokuapp.com,www.<tu-app>.herokuapp.com

# Debe ser una clave segura distinta a desarrollo
SECRET_KEY=<genera-una-nueva-clave-para-produccion>
```

**Generar nueva SECRET_KEY (recomendado):**
```python
# En terminal local
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

### 2. Commit y Push de Cambios

```bash
# Ver archivos modificados
git status

# Agregar cambios
git add requirements.txt runtime.txt gestion_estudios/settings.py docs/

# Commit con mensaje descriptivo
git commit -m "🔒 Actualización seguridad: Django 5.2.12 + 7 paquetes críticos"

# Push al branch actual
git push origin feature/colegiales
```

### 3. Deploy a Heroku

```bash
# Opción A: Push desde tu branch
git push heroku feature/colegiales:main

# Opción B: Merge a main primero (recomendado)
git checkout main
git merge feature/colegiales
git push origin main
git push heroku main
```

### 4. Monitorear el Deploy

```bash
# Ver logs en tiempo real
heroku logs --tail --app <tu-app>
```

**Buscar estos mensajes:**
```
-----> Python app detected
-----> Using Python version specified in runtime.txt
-----> Installing dependencies using pip
-----> Running release phase command...
       Collecting static files...
       Running migrations...
```

---

## ✅ VERIFICACIÓN POST-DEPLOY

### 1. Verificar Aplicación

```bash
# Abrir la app en navegador
heroku open --app <tu-app>

# Verificar estado de dynos
heroku ps --app <tu-app>
```

### 2. Verificar Configuración Django

```bash
# Ejecutar check de producción
heroku run python manage.py check --deploy --app <tu-app>
```

**Output esperado:**
```
System check identified no issues (0 silenced).
```

### 3. Probar Funcionalidades Críticas

- [ ] Acceder al admin: `https://<tu-app>.herokuapp.com/admin/`
- [ ] Login exitoso
- [ ] Ver lista de pedidos
- [ ] Crear nuevo pedido (sin procesar)
- [ ] Generar un PDF de prueba
- [ ] Verificar que Gmail API funciona:

```bash
heroku run python manage.py shell --app <tu-app>
# En el shell:
from pedidos_estudios.services.gmail_service import verificar_configuracion_gmail
print(verificar_configuracion_gmail())
# Debe retornar: (True, 'Configuración de Gmail OK...')
```

### 4. Verificar Headers de Seguridad

Usa un navegador o curl para verificar headers HTTP:

```bash
# Opción 1: curl (Git Bash)
curl -I https://<tu-app>.herokuapp.com

# Opción 2: online (más fácil)
# Ve a: https://securityheaders.com/
# Ingresa: https://<tu-app>.herokuapp.com
```

**Headers esperados:**
```http
X-Frame-Options: DENY
X-Content-Type-Options: nosniff
Referrer-Policy: same-origin
Strict-Transport-Security: max-age=31536000; includeSubDomains
```

### 5. Verificar Scheduler (Procesamiento Automático)

```bash
# Ver configuración del scheduler
heroku addons:open scheduler --app <tu-app>
```

Asegurar que el job tiene:
- **Comando:** `python manage.py procesar_pedidos_auto --max-emails=20 --silent`
- **Frecuencia:** Every 10 minutes

---

## 🚨 ROLLBACK (Si algo falla)

### Opción 1: Rollback de Release

```bash
# Ver releases recientes
heroku releases --app <tu-app>

# Rollback a release anterior
heroku rollback v123 --app <tu-app>
```

### Opción 2: Rollback de Código

```bash
# Revertir commit
git revert HEAD
git push heroku main

# O forzar versión anterior
git push heroku <commit-anterior>:main --force
```

### Opción 3: Restaurar Base de Datos

```bash
# Listar backups
heroku pg:backups --app <tu-app>

# Restaurar backup específico
heroku pg:backups:restore b001 DATABASE_URL --app <tu-app>
```

---

## 📊 MONITOREO POST-DEPLOY

### Durante las Primeras 24 Horas

```bash
# Monitorear logs continuamente
heroku logs --tail --source app --app <tu-app>

# Verificar métricas
heroku dashboard --app <tu-app>
```

**Buscar errores comunes:**
- `500 Internal Server Error` → Revisar logs para stack trace
- `ImportError` → Algún paquete no se instaló correctamente
- `OperationalError` → Problema de base de datos/migraciones
- `TemplateDoesNotExist` → Problema con collectstatic

### Testeo de Carga (Opcional)

Si quieres verificar que no hay problemas de rendimiento:

```bash
# Ver métricas de memoria/CPU
heroku metrics:web --app <tu-app>

# Si tienes New Relic o Datadog configurado, revisa sus dashboards
```

---

## 📝 NOTAS IMPORTANTES

### Compatibilidad Python 3.12 vs 3.13

Tu entorno local usa **Python 3.13.2**, pero Heroku usará **Python 3.12.8**. Esto es normal y seguro porque:

✅ Django 5.2 es compatible con ambos  
✅ Todos los paquetes actualizados soportan 3.12  
✅ No usas características específicas de 3.13

**Si encuentras problemas:** Puedes probar localmente con 3.12 creando un nuevo venv:
```powershell
py -3.12 -m venv venv_test312
.\venv_test312\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py test
```

### Configuraciones que se Activan Automáticamente

En `settings.py` las siguientes configuraciones **se activan solo cuando DEBUG=False** (producción):

```python
# HTTPS/SSL
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# HSTS (HTTP Strict Transport Security)
SECURE_HSTS_SECONDS = 31536000  # 1 año
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
```

**No necesitas hacer nada extra** - se activan automáticamente en Heroku si `DEBUG=False`.

### Nuevos Paquetes de Seguridad Instalados pero No Configurados

Estos paquetes se instalaron en el sistema de auditoría, **NO se despliegan a Heroku** porque no están en `requirements.txt`:

- `safety` (solo para auditoría local)
- `bandit` (solo para auditoría local)
- `detect-secrets` (solo para auditoría local)

Los siguientes **SÍ están** en requirements.txt pero **NO están configurados aún**:
- `django-ratelimit` → Instalado pero no aplicado a views
- `django-defender` → Instalado pero no activado en settings
- `django-csp` → Instalado pero sin política configurada
- `bleach` → Instalado pero no usado en sanitización

Estos se pueden configurar después del deploy exitoso ([ver MEJORAS_SEGURIDAD_IMPLEMENTABLES.md](./MEJORAS_SEGURIDAD_IMPLEMENTABLES.md)).

---

## 🎯 CHECKLIST FINAL

**Antes de Desplegar:**
- [ ] Tests ejecutados localmente (`python manage.py test`)
- [ ] Funcionalidades críticas probadas manualmente
- [ ] Backup de base de datos Heroku creado
- [ ] Config Vars verificadas (DEBUG=False, SECRET_KEY, ALLOWED_HOSTS)
- [ ] Cambios commiteados y pusheados a GitHub

**Durante Deploy:**
- [ ] Push a Heroku ejecutado
- [ ] Logs monitoreados (sin errores críticos)
- [ ] Release phase completado (collectstatic + migrate)

**Post-Deploy:**
- [ ] Aplicación accesible en navegador
- [ ] Login/admin funcionando
- [ ] Headers de seguridad presentes (securityheaders.com)
- [ ] Gmail API operativo (verificar con shell)
- [ ] Scheduler configurado y activo
- [ ] Monitoreo de logs por 24h sin errores

---

## 📚 REFERENCIAS

- [security/ACTUALIZACION_SEGURIDAD_COMPLETADA.md](../security/ACTUALIZACION_SEGURIDAD_COMPLETADA.md) - Detalles de CVEs corregidos
- [CHECKLIST_DEPLOY_HEROKU.md](CHECKLIST_DEPLOY_HEROKU.md) - Checklist general de deploy
- [security/MEJORAS_SEGURIDAD_IMPLEMENTABLES.md](../security/MEJORAS_SEGURIDAD_IMPLEMENTABLES.md) - Próximas mejoras de seguridad

---

**¿Problemas en el deploy?** Revisa la sección [ROLLBACK](#-rollback-si-algo-falla) o consulta los logs con `heroku logs --tail`.
