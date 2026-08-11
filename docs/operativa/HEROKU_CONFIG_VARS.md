# ⚙️ Variables de Entorno para Heroku - Actualización 2026

## 🔴 CRÍTICAS (Ya deberían estar configuradas)

```bash
# Django Core
SECRET_KEY=<tu-secret-key-actual>
DEBUG=False  # ⚠️ DEBE ser False en producción
ALLOWED_HOSTS=<tu-app>.herokuapp.com

# Base de datos (auto-configurada por Heroku)
DATABASE_URL=postgres://...

# Gmail API
GMAIL_TOKEN_JSON=<contenido-de-token-for-heroku.txt>
GMAIL_EMAIL=solicitudestudioscolegiales@gmail.com
GMAIL_PEDIDOS_QUERY=is:unread

# Email SMTP
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=<tu-email>@gmail.com
EMAIL_HOST_PASSWORD=<app-password>

# Notificaciones
PEDIDOS_EMAIL_DEFAULT=ecejas@sanatoriocolegiales.com.ar
SITE_URL=https://<tu-app>.herokuapp.com

# Sanatorio
SANATORIO_NOMBRE=Sanatorio Colegiales
SANATORIO_MODO=Colegiales
```

---

## 🟢 NUEVAS (No requeridas, pero recomendadas)

### Para búsqueda inteligente de casos en preinformes

```bash
# Requiere la misma clave utilizada por los demás asistentes del sistema
OPENAI_API_KEY=<clave-openai>

# Opcional; default: True
PREINFORMES_BUSCADOR_IA_HABILITADO=True

# Opcionales; valores predeterminados mostrados
PREINFORMES_EMBEDDING_MODEL=text-embedding-3-small
PREINFORMES_EMBEDDING_UMBRAL=0.30
PREINFORMES_EMBEDDING_MAX_RESULTADOS=50
```

Para desactivarlo sin desplegar código:

```bash
heroku config:set PREINFORMES_BUSCADOR_IA_HABILITADO=False --app <tu-app>
```

Después del primer deploy, generar el índice histórico:

```bash
heroku run python manage.py indexar_busqueda_semantica --app <tu-app>
```

Programar el mismo comando en Heroku Scheduler mantiene indexados los informes nuevos y corregidos; el comando omite automáticamente los que ya están vigentes.

### Para Logging y Monitoreo

```bash
# Nivel de log (opcional, default: INFO)
LOG_LEVEL=INFO  # Opciones: DEBUG, INFO, WARNING, ERROR, CRITICAL

# Sentry para monitoreo de errores (opcional)
SENTRY_DSN=<tu-sentry-dsn>
```

### Para Seguridad Avanzada (Futuro)

```bash
# Rate Limiting (cuando se implemente django-ratelimit)
RATELIMIT_ENABLE=True
RATELIMIT_USE_CACHE=default

# Django Defender (cuando se active)
DEFENDER_ENABLE=True
DEFENDER_LOGIN_FAILURE_LIMIT=5
DEFENDER_BEHIND_REVERSE_PROXY=True  # Heroku usa proxies

# Content Security Policy (cuando se configure)
CSP_DEFAULT_SRC="'self'"
CSP_SCRIPT_SRC="'self' 'unsafe-inline'"
CSP_STYLE_SRC="'self' 'unsafe-inline'"
```

---

## 📊 Verificar Variables Actuales

```bash
# Listar todas las config vars
heroku config --app <tu-app>

# Ver una variable específica
heroku config:get DEBUG --app <tu-app>

# Establecer una variable
heroku config:set DEBUG=False --app <tu-app>

# Eliminar una variable
heroku config:unset VARIABLE_NAME --app <tu-app>
```

---

## 🔒 Variables que Activan Configuraciones de Seguridad

Las siguientes configuraciones en `settings.py` **se activan automáticamente** cuando `DEBUG=False`:

### HTTPS/SSL (Auto-activadas)
```python
SECURE_SSL_REDIRECT = True  # Redirige HTTP → HTTPS
SESSION_COOKIE_SECURE = True  # Cookies solo por HTTPS
CSRF_COOKIE_SECURE = True  # CSRF token solo por HTTPS
```

### HSTS (Auto-activadas)
```python
SECURE_HSTS_SECONDS = 31536000  # 1 año
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
```

### Headers de Seguridad (Siempre activas)
```python
X_FRAME_OPTIONS = 'DENY'
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_REFERRER_POLICY = 'same-origin'
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'
```

**Conclusión:** Solo necesitas asegurar que `DEBUG=False` para que todas las configuraciones de seguridad se activen.

---

## ⚠️ IMPORTANTE: SECRET_KEY

### Generar Nueva SECRET_KEY para Producción

**No uses la misma SECRET_KEY de desarrollo en producción.** Genera una nueva:

```bash
# Desde tu terminal local
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Copia el output y establécela en Heroku:

```bash
heroku config:set SECRET_KEY="<la-nueva-key-generada>" --app <tu-app>
```

### ¿Por qué es importante?

La `SECRET_KEY` se usa para:
- Firmar cookies de sesión
- Generar tokens CSRF
- Firmar datos en formularios
- Generar password reset tokens

**Si alguien obtiene tu SECRET_KEY, puede:**
- Falsificar sesiones de usuarios
- Generar tokens CSRF válidos
- Descifrar datos protegidos

---

## 🧪 Verificar Configuración

### Verificar DEBUG

```bash
heroku run python manage.py shell --app <tu-app>
```

En el shell:
```python
from django.conf import settings
print(f"DEBUG: {settings.DEBUG}")  # Debe mostrar: DEBUG: False
print(f"ALLOWED_HOSTS: {settings.ALLOWED_HOSTS}")
print(f"SECURE_SSL_REDIRECT: {settings.SECURE_SSL_REDIRECT}")  # Debe ser True
```

### Verificar Headers HTTP

```bash
# Desde Git Bash o Linux
curl -I https://<tu-app>.herokuapp.com

# Desde PowerShell
Invoke-WebRequest -Uri "https://<tu-app>.herokuapp.com" -Method Head | Select-Object -ExpandProperty Headers
```

Buscar:
```
X-Frame-Options: DENY
X-Content-Type-Options: nosniff
Strict-Transport-Security: max-age=31536000; includeSubDomains
```

---

## 📝 Checklist de Verificación

Antes de desplegar, verifica que estas variables estén configuradas:

- [ ] `DEBUG=False` (no "false", debe ser False con F mayúscula o 0)
- [ ] `SECRET_KEY=<nueva-key-para-produccion>`
- [ ] `ALLOWED_HOSTS=<tu-app>.herokuapp.com`
- [ ] `GMAIL_TOKEN_JSON=<token-json>`
- [ ] `GMAIL_EMAIL=solicitudestudioscolegiales@gmail.com`
- [ ] `EMAIL_HOST_USER=<email>`
- [ ] `EMAIL_HOST_PASSWORD=<app-password>`
- [ ] `PEDIDOS_EMAIL_DEFAULT=ecejas@sanatoriocolegiales.com.ar`
- [ ] `SITE_URL=https://<tu-app>.herokuapp.com`

**Verifica todas:**
```bash
heroku config --app <tu-app> | grep -E "DEBUG|SECRET_KEY|ALLOWED_HOSTS|GMAIL"
```

---

## 🚀 Aplicar Cambios

Después de modificar config vars, **reinicia los dynos**:

```bash
heroku restart --app <tu-app>
```

**Nota:** Heroku reinicia automáticamente cuando cambias config vars, pero es buena práctica confirmarlo explícitamente.

---

## 📚 Referencias

- Documentación Heroku Config Vars: https://devcenter.heroku.com/articles/config-vars
- Django Security Settings: https://docs.djangoproject.com/en/5.2/topics/security/
- Django Deployment Checklist: https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/
