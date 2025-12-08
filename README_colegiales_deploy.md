# 🏥 DEPLOY COLEGIALES - DOCUMENTACIÓN COMPLETA

## 📊 INFORMACIÓN DEL DESPLIEGUE

- **App Name:** gestion-colegiales
- **URL:** https://gestion-colegiales-a1dfc873c2b8.herokuapp.com/
- **Remote Git:** colegiales
- **Rama:** feature/colegiales
- **Sanatorio:** COLEGIALES
- **Base de datos:** PostgreSQL (essential-0)
- **Fecha de deploy:** 8 de diciembre de 2025

---

## 🔐 CREDENCIALES

**Superusuario:**
- Username: `efccejas`
- Email: `ensofermincejas@gmail.com`
- Password: `[guardado en 1Password/LastPass]`

**Heroku Dashboard:** https://dashboard.heroku.com/apps/gestion-colegiales

---

## 🎯 CHULETA RÁPIDA - COMANDOS COMPLETOS

### 1️⃣ PREPARACIÓN (solo verificación)
```bash
git checkout feature/colegiales
git status
git push origin feature/colegiales
```

### 2️⃣ CREAR APP (YA ESTÁ CREADO - NO REPETIR)
```bash
# Ya ejecutado el 8/12/2025
heroku create gestion-colegiales
heroku git:remote -a gestion-colegiales -r colegiales
heroku addons:create heroku-postgresql:essential-0 -a gestion-colegiales
```

### 3️⃣ VARIABLES DE ENTORNO ACTUALES
```bash
# Ver todas las variables configuradas
heroku config -a gestion-colegiales

# Variables ya configuradas:
# - SECRET_KEY
# - DEBUG=False
# - ALLOWED_HOSTS=gestion-colegiales-a1dfc873c2b8.herokuapp.com
# - SANATORIO_ACTIVO=colegiales
# - DISABLE_COLLECTSTATIC=1
# - GMAIL_USER=noreply@colegiales.com
# - GMAIL_PASSWORD=changeme123
# - DATABASE_URL (automático)
```

### 4️⃣ DEPLOY (ACTUALIZACIONES FUTURAS)
```bash
# 1. Asegurate de estar en la rama correcta
git checkout feature/colegiales

# 2. Hacer tus cambios y commitear
git add .
git commit -m "Descripción del cambio"

# 3. Subir a GitHub
git push origin feature/colegiales

# 4. Deploy a Heroku
git push colegiales feature/colegiales:main
```

### 5️⃣ COMANDOS POST-DEPLOY

#### Ver logs en tiempo real
```bash
heroku logs --tail -a gestion-colegiales
```

#### Ejecutar migraciones (si agregaste nuevos modelos)
```bash
heroku run python manage.py migrate -a gestion-colegiales
```

#### Recolectar archivos estáticos
```bash
heroku run python manage.py collectstatic --noinput -a gestion-colegiales
```

#### Crear nuevo superusuario
```bash
heroku run python manage.py createsuperuser -a gestion-colegiales
```

#### Abrir la aplicación
```bash
heroku open -a gestion-colegiales
```

#### Ver estado de los procesos
```bash
heroku ps -a gestion-colegiales
```

#### Reiniciar la aplicación
```bash
heroku restart -a gestion-colegiales
```

#### Abrir consola Python en producción
```bash
heroku run python manage.py shell -a gestion-colegiales
```

---

## 🗄️ COMANDOS DE BASE DE DATOS

### Ver información de la base de datos
```bash
heroku pg:info -a gestion-colegiales
```

### Conectar a la base de datos con psql
```bash
heroku pg:psql -a gestion-colegiales
```

### Backup de la base de datos
```bash
heroku pg:backups:capture -a gestion-colegiales
heroku pg:backups:download -a gestion-colegiales
```

### Ver backups disponibles
```bash
heroku pg:backups -a gestion-colegiales
```

### ⚠️ RESETEAR BASE DE DATOS (CUIDADO: BORRA TODO)
```bash
# Confirma con el nombre exacto del app
heroku pg:reset DATABASE -a gestion-colegiales --confirm gestion-colegiales

# Luego ejecutar migraciones y crear superusuario nuevamente
heroku run python manage.py migrate -a gestion-colegiales
heroku run python manage.py createsuperuser -a gestion-colegiales
```

---

## 🔧 MODIFICAR VARIABLES DE ENTORNO

### Cambiar/Agregar una variable
```bash
heroku config:set NOMBRE_VARIABLE="valor" -a gestion-colegiales
```

### Ejemplos útiles:

#### Cambiar a modo debug (SOLO PARA DEBUGGING TEMPORAL)
```bash
heroku config:set DEBUG=True -a gestion-colegiales
# RECORDAR volver a False después
heroku config:set DEBUG=False -a gestion-colegiales
```

#### Configurar email real (si vas a usar notificaciones)
```bash
heroku config:set GMAIL_USER="tu-email@gmail.com" -a gestion-colegiales
heroku config:set GMAIL_PASSWORD="tu-app-password" -a gestion-colegiales
```

#### Agregar dominio personalizado a ALLOWED_HOSTS
```bash
heroku config:set ALLOWED_HOSTS="gestion-colegiales-a1dfc873c2b8.herokuapp.com,tudominio.com" -a gestion-colegiales
```

---

## 🚨 TROUBLESHOOTING

### Error: "Application error"
```bash
# Ver los logs detallados
heroku logs --tail -a gestion-colegiales

# Reiniciar la app
heroku restart -a gestion-colegiales
```

### Error: "No web processes running"
```bash
heroku ps:scale web=1 -a gestion-colegiales
```

### Error: "relation does not exist" (tabla no existe)
```bash
# Ejecutar migraciones
heroku run python manage.py migrate -a gestion-colegiales
```

### Error: "collectstatic"
```bash
# Ejecutar collectstatic manualmente
heroku run python manage.py collectstatic --noinput -a gestion-colegiales
```

### La app no refleja los cambios después del deploy
```bash
# 1. Verificar que el push se hizo correctamente
git push colegiales feature/colegiales:main

# 2. Ver el último release
heroku releases -a gestion-colegiales

# 3. Ver output del release
heroku releases:output -a gestion-colegiales

# 4. Reiniciar
heroku restart -a gestion-colegiales
```

### Ver qué archivos están en Heroku
```bash
heroku run bash -a gestion-colegiales
# Luego dentro del bash:
ls -la
cd gestion_estudios
cat settings.py | grep SANATORIO_ACTIVO
```

---

## 📦 ESTRUCTURA DE REMOTES GIT

Verificá tus remotes con:
```bash
git remote -v
```

Deberías ver:
```
colegiales    https://git.heroku.com/gestion-colegiales.git (fetch)
colegiales    https://git.heroku.com/gestion-colegiales.git (push)
heroku        https://git.heroku.com/mi-gestion-servicio.git (fetch)
heroku        https://git.heroku.com/mi-gestion-servicio.git (push)
origin        https://github.com/efcejas/gestion_servicio.git (fetch)
origin        https://github.com/efcejas/gestion_servicio.git (push)
```

**Explicación:**
- `origin` → Tu repositorio en GitHub
- `heroku` → App de Dupuytren (si existe)
- `colegiales` → App nuevo de Colegiales

---

## ✅ CHECKLIST DE VALIDACIÓN POST-DEPLOY

Después de cada deploy, verificá:

- [ ] La app carga sin errores: https://gestion-colegiales-a1dfc873c2b8.herokuapp.com
- [ ] Login funciona en `/admin`
- [ ] Dashboard muestra "COLEGIALES" como sanatorio activo
- [ ] Sidebar muestra solo módulos de Colegiales (Agenda, Notas)
- [ ] NO aparecen módulos de Dupuytren
- [ ] Los logs no muestran errores: `heroku logs --tail -a gestion-colegiales`

---

## 🔄 WORKFLOW DE DESARROLLO RECOMENDADO

### Para cambios pequeños (hotfix):
```bash
# 1. Hacer el cambio en feature/colegiales
git checkout feature/colegiales
# ... editar archivos ...
git add .
git commit -m "fix: descripción del fix"

# 2. Push a GitHub
git push origin feature/colegiales

# 3. Deploy inmediato
git push colegiales feature/colegiales:main

# 4. Verificar logs
heroku logs --tail -a gestion-colegiales
```

### Para cambios grandes (features):
```bash
# 1. Crear rama de feature
git checkout feature/colegiales
git checkout -b feature/colegiales-nueva-funcionalidad

# 2. Desarrollar y testear localmente
# ... hacer cambios ...
python manage.py runserver

# 3. Cuando esté listo, merge a feature/colegiales
git checkout feature/colegiales
git merge feature/colegiales-nueva-funcionalidad

# 4. Push a GitHub
git push origin feature/colegiales

# 5. Deploy a Heroku
git push colegiales feature/colegiales:main
```

---

## 📝 NOTAS IMPORTANTES

1. **NUNCA** hacer `git push heroku` si estás trabajando con Colegiales. Siempre usar `git push colegiales`

2. **SIEMPRE** especificar `-a gestion-colegiales` en comandos de Heroku para evitar errores

3. **La base de datos es independiente** de Dupuytren. No hay datos compartidos.

4. **Las variables de entorno son independientes**. Cambios en una app no afectan la otra.

5. **El Procfile tiene un release command** que ejecuta `collectstatic` y `migrate` automáticamente en cada deploy.

6. **Email configurado como placeholder**: Si vas a usar notificaciones por email, recordá cambiar `GMAIL_USER` y `GMAIL_PASSWORD`.

---

## 🎯 CONVENCIONES DEL PROYECTO

| Concepto | Dupuytren | Colegiales |
|----------|-----------|------------|
| Heroku App | `mi-gestion-servicio` | `gestion-colegiales` |
| URL | https://mi-gestion-servicio.herokuapp.com | https://gestion-colegiales-a1dfc873c2b8.herokuapp.com |
| Git Remote | `heroku` | `colegiales` |
| Rama Git | `main` | `feature/colegiales` |
| Config | CONFIG_DUPUYTREN | CONFIG_COLEGIALES |
| Variable | SANATORIO_ACTIVO=dupuytren | SANATORIO_ACTIVO=colegiales |

---

## 🆘 CONTACTO Y SOPORTE

- **Heroku Status:** https://status.heroku.com/
- **Heroku Docs:** https://devcenter.heroku.com/
- **Django Docs:** https://docs.djangoproject.com/

---

**Última actualización:** 8 de diciembre de 2025
**Actualizado por:** efccejas
**Versión de Django:** 5.1.4
**Versión de Python:** 3.13.11
