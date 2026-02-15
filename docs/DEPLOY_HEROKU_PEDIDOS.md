# Guía de Despliegue en Heroku - Sistema de Pedidos de Estudios

## 📋 Tabla de Contenidos
- [Archivos Protegidos](#archivos-protegidos)
- [Credenciales de Gmail API](#credenciales-de-gmail-api)
- [Variables de Entorno](#variables-de-entorno)
- [Configuración de Heroku Scheduler](#configuración-de-heroku-scheduler)
- [Comandos de Despliegue](#comandos-de-despliegue)
- [Verificación Post-Despliegue](#verificación-post-despliegue)

---

## 🔒 Archivos Protegidos

Los siguientes archivos ya están protegidos en `.gitignore` y **NO se subirán** a GitHub:

```
.env                    # Variables de entorno locales
credentials.json        # Credenciales OAuth2 de Google
token.json             # Token de acceso generado
settings_local.py      # Configuraciones locales
*.sqlite3              # Base de datos local
```

✅ **Verificación:** Estos archivos ya están correctamente configurados en `.gitignore`.

---

## 🔑 Credenciales de Gmail API

### Paso 1: Generar Token Localmente

**IMPORTANTE:** El token de Gmail debe generarse en tu máquina local antes de desplegar:

1. **Asegúrate de tener `credentials.json`** en la raíz del proyecto (descargado de Google Cloud Console)

2. **Ejecuta el comando de prueba:**
   ```bash
   python manage.py shell -c "from pedidos_estudios.services.gmail_service import GmailService; g = GmailService()"
   ```

3. **Se abrirá el navegador** para autorizar el acceso. Acepta los permisos.

4. **Se generará `token.json`** en la raíz del proyecto. Este archivo contiene el refresh token.

### Paso 2: Preparar Credenciales para Heroku

Las credenciales deben configurarse como **variables de entorno en Heroku**. Hay dos opciones:

#### Opción A: Usar archivos JSON como variables (Recomendado)

```bash
# En tu máquina local, convierte los archivos a formato de una línea
cat credentials.json | jq -c . > credentials_oneline.json
cat token.json | jq -c . > token_oneline.json

# Luego copia el contenido para Config Vars de Heroku
```

#### Opción B: Usar service account (Más seguro para producción)

Si prefieres usar una service account en lugar de OAuth2:

1. En Google Cloud Console → Credenciales → Crear credenciales → Service Account
2. Descarga el JSON de la service account
3. Habilita domain-wide delegation si es necesario
4. Usa este JSON en `GMAIL_CREDENTIALS_JSON`

---

## 🌍 Variables de Entorno

### En Heroku Dashboard

Ve a: **Settings → Config Vars** y agrega:

```env
# Django
SECRET_KEY=tu_secret_key_produccion
DEBUG=False
ALLOWED_HOSTS=tu-app.herokuapp.com
DATABASE_URL=postgres://...  # (Heroku lo crea automáticamente)

# Gmail API - Opción 1: JSON completo
GMAIL_CREDENTIALS_JSON={"type":"service_account","project_id":"..."}
GMAIL_TOKEN_JSON={"token":"...","refresh_token":"..."}

# Gmail API - Opción 2: Ruta a archivos (si usas buildpack)
GMAIL_CREDENTIALS_FILE=/app/config/credentials.json
GMAIL_TOKEN_FILE=/app/config/token.json

# Configuración de Gmail
GMAIL_EMAIL=solicitudestudioscolegiales@gmail.com
GMAIL_PEDIDOS_QUERY=is:unread

# Notificaciones
PEDIDOS_EMAIL_DEFAULT=ecejas@sanatoriocolegiales.com.ar
SITE_URL=https://tu-app.herokuapp.com

# Email (si usas SMTP para notificaciones)
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=tu_email@gmail.com
EMAIL_HOST_PASSWORD=tu_app_password

# Cloudinary (si lo usas)
CLOUDINARY_URL=cloudinary://api_key:api_secret@cloud_name

# Sanatorio
SANATORIO_NOMBRE=Sanatorio Colegiales
SANATORIO_MODO=Colegiales
```

### Usando Heroku CLI

```bash
# Configurar variables una por una
heroku config:set SECRET_KEY="tu_secret_key" --app tu-app

# Configurar desde archivo .env
heroku config:set $(cat .env.production | sed '/^#/d' | sed '/^$/d')

# Verificar configuración
heroku config --app tu-app
```

---

## ⏰ Configuración de Heroku Scheduler

Para que los emails se procesen automáticamente cada X minutos:

### Paso 1: Instalar Heroku Scheduler

```bash
heroku addons:create scheduler:standard --app tu-app
```

### Paso 2: Configurar el Job

```bash
# Abrir dashboard de scheduler
heroku addons:open scheduler --app tu-app
```

En el dashboard de Scheduler, agrega un nuevo job:

**Frecuencia:** `Every 10 minutes` (o la que prefieras)

**Comando:**
```bash
python manage.py procesar_pedidos_auto --max-emails=20 --silent
```

**Opciones de frecuencia:**
- `Every 10 minutes` → Procesamiento muy frecuente (recomendado)
- `Every hour at :00` → Cada hora en punto
- `Daily at 8:00 AM` → Diario a las 8am

### Paso 3: Verificar Logs

```bash
# Ver logs en tiempo real
heroku logs --tail --app tu-app

# Filtrar solo logs de procesamiento
heroku logs --tail --app tu-app | grep "Procesamiento automático"
```

---

## 🚀 Comandos de Despliegue

### Primera vez

```bash
# 1. Login en Heroku
heroku login

# 2. Crear app (si no existe)
heroku create tu-app-pedidos

# 3. Agregar addon de PostgreSQL
heroku addons:create heroku-postgresql:mini --app tu-app

# 4. Configurar variables de entorno (ver sección anterior)
heroku config:set SECRET_KEY="..." DEBUG=False --app tu-app

# 5. Verificar Procfile
cat Procfile
# Debe contener:
# web: gunicorn gestion_estudios.wsgi:application --log-file - --timeout 120
# release: python manage.py collectstatic --noinput && python manage.py migrate

# 6. Push a Heroku
git push heroku feature/colegiales:main

# 7. Ejecutar migraciones (si no se ejecutaron automáticamente)
heroku run python manage.py migrate --app tu-app

# 8. Crear superusuario
heroku run python manage.py createsuperuser --app tu-app
```

### Actualizaciones posteriores

```bash
# 1. Commit de cambios
git add .
git commit -m "Descripción de cambios"

# 2. Push a Heroku
git push heroku feature/colegiales:main

# 3. Ver logs (opcional)
heroku logs --tail --app tu-app
```

---

## ✅ Verificación Post-Despliegue

### 1. Verificar que la app está corriendo

```bash
# Ver estado de la app
heroku ps --app tu-app

# Abrir en navegador
heroku open --app tu-app
```

### 2. Verificar Gmail API

```bash
# Ejecutar comando de verificación
heroku run python manage.py shell -c "from pedidos_estudios.services.gmail_service import verificar_configuracion_gmail; print(verificar_configuracion_gmail())" --app tu-app
```

**Resultado esperado:**
```
(True, 'Configuración de Gmail OK. Email: solicitudestudioscolegiales@gmail.com')
```

### 3. Probar procesamiento manual

```bash
# Ejecutar procesamiento manual una vez
heroku run python manage.py procesar_pedidos_auto --max-emails=5 --app tu-app
```

### 4. Verificar Scheduler está activo

```bash
# Ver jobs configurados
heroku addons:open scheduler --app tu-app
```

En el dashboard verifica:
- ✅ Job está habilitado (toggle verde)
- ✅ Muestra "Next Due" con la próxima ejecución
- ✅ "Last Run" muestra ejecución reciente (después de 10 minutos)

### 5. Monitorear logs

```bash
# Logs en tiempo real
heroku logs --tail --app tu-app

# Ver últimos 200 logs
heroku logs -n 200 --app tu-app

# Filtrar por procesamiento
heroku logs --tail --app tu-app | grep "procesamiento"
```

**Busca estas líneas cada 10 minutos:**
```
Procesamiento automático: procesados=3, exitosos=2, errores=0, duplicados=1
```

### 6. Acceder al dashboard

Ingresa con tu superusuario a:
```
https://tu-app.herokuapp.com/admin/
https://tu-app.herokuapp.com/pedidos/
```

---

## 🔧 Actualizar Código para Variables de Entorno

Si el servicio de Gmail aún no lee variables de entorno, necesitas actualizar `gmail_service.py`:

```python
import os
import json
from django.conf import settings

class GmailService:
    def _authenticate(self):
        """Autentica con Google usando variables de entorno en producción."""
        creds = None
        
        # Intentar cargar desde variables de entorno (PRODUCCIÓN)
        if os.getenv('GMAIL_TOKEN_JSON'):
            try:
                token_data = json.loads(os.getenv('GMAIL_TOKEN_JSON'))
                creds = Credentials.from_authorized_user_info(token_data, self.SCOPES)
            except Exception as e:
                logger.error(f"Error cargando token desde env: {e}")
        
        # Fallback: cargar desde archivos (DESARROLLO)
        elif Path(token_file).exists():
            creds = Credentials.from_authorized_user_file(token_file, self.SCOPES)
        
        # Refresh si es necesario
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            
            # Guardar token actualizado en variable de entorno (opcional)
            if os.getenv('GMAIL_TOKEN_JSON'):
                updated_token = json.loads(creds.to_json())
                logger.info("Token refreshed. Update GMAIL_TOKEN_JSON in Heroku config.")
```

---

## 🚨 Troubleshooting

### Problema: "Credenciales no encontradas"

**Solución:**
1. Verifica que `GMAIL_CREDENTIALS_JSON` o `GMAIL_CREDENTIALS_FILE` esté configurado
2. Ejecuta: `heroku config --app tu-app | grep GMAIL`

### Problema: "Token expirado"

**Solución:**
1. El refresh token debería renovarse automáticamente
2. Si falla, regenera token localmente y actualiza `GMAIL_TOKEN_JSON`

### Problema: "Scheduler no ejecuta"

**Solución:**
1. Verifica que el addon esté instalado: `heroku addons --app tu-app`
2. Verifica logs: `heroku logs --tail | grep scheduler`
3. El plan gratuito de Heroku puede tener límites

### Problema: "Emails no se procesan"

**Solución:**
1. Verifica logs: `heroku logs -n 500 --app tu-app | grep "procesamiento"`
2. Ejecuta manualmente: `heroku run python manage.py procesar_pedidos_auto --app tu-app`
3. Verifica permisos de Gmail API en Google Cloud Console

---

## 📝 Checklist Final

Antes de considerar el despliegue completo:

- [ ] `.gitignore` protege archivos sensibles
- [ ] Token de Gmail generado localmente
- [ ] Variables de entorno configuradas en Heroku
- [ ] Heroku Scheduler instalado y configurado
- [ ] Migraciones ejecutadas correctamente
- [ ] Superusuario creado
- [ ] Dashboard accesible con permisos por rol
- [ ] Procesamiento manual funciona
- [ ] Scheduler ejecuta cada 10 minutos
- [ ] Logs muestran procesamiento exitoso
- [ ] Notificaciones por email funcionan

---

## 📞 Soporte

Si encuentras problemas:

1. **Revisa logs:** `heroku logs --tail --app tu-app`
2. **Verifica config:** `heroku config --app tu-app`
3. **Ejecuta shell:** `heroku run python manage.py shell --app tu-app`
4. **Contacta soporte:** Si el problema persiste

---

**Fecha:** 15/02/2026  
**Versión:** 1.0 - Sistema de Pedidos de Estudios
