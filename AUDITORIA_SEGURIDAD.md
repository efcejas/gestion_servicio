# ========================================
# 🔒 GUÍA DE AUDITORÍA DE SEGURIDAD
# ========================================
# Para aprender seguridad práctica en Django

## 📦 INSTALACIÓN

Primero instala las herramientas de seguridad:

```powershell
pip install -r requirements-security.txt
```

---

## 🛡️ HERRAMIENTAS Y QUÉ DETECTAN

### 1. SAFETY - Auditoría de Dependencias
**Qué detecta:** Vulnerabilidades conocidas (CVEs) en tus paquetes instalados
**Por qué es importante:** Bibliotecas con bugs de seguridad pueden ser explotadas

```powershell
# Escanear dependencias actuales
safety check --json > security_reports/safety_report.json

# Ver reporte legible
safety check
```

**Ejemplo de vulnerabilidad real:**
- Django 5.0.2 tiene CVE-2024-xxxxx que permite DoS
- Solución: Actualizar a Django 5.1.4 ✓

---

### 2. BANDIT - Análisis Estático de Código
**Qué detecta:** Patrones de código inseguro en Python
**Categorías:**
- SQL Injection
- Uso de `eval()`, `exec()`
- Hard-coded passwords
- Uso inseguro de `pickle`
- SSL sin verificación
- Permisos de archivo incorrectos

```powershell
# Escanear todo el proyecto
bandit -r . -f json -o security_reports/bandit_report.json

# Ver solo problemas de severidad ALTA y MEDIA
bandit -r . -ll

# Escanear solo una app específica
bandit -r accounts/ -ll

# Excluir tests y migraciones
bandit -r . -ll --exclude ./*/tests.py,./*/migrations/*
```

**Ejemplos de lo que encuentra:**
```python
# ❌ MALO - SQL Injection potencial
query = f"SELECT * FROM users WHERE username='{username}'"
cursor.execute(query)

# ✅ BUENO - Usa parámetros
cursor.execute("SELECT * FROM users WHERE username=%s", [username])

# ❌ MALO - Password hardcodeado
password = "mi_password_secreto"

# ✅ BUENO - Desde variable de entorno
password = config('DB_PASSWORD')
```

---

### 3. DJANGO-SECURITY-CHECK
**Qué detecta:** Configuraciones inseguras específicas de Django

```powershell
python manage.py check --deploy
```

**Ejemplos de warnings:**
- `DEBUG = True` en producción ⚠️
- `SECRET_KEY` hardcodeada
- `ALLOWED_HOSTS` vacío
- Falta configuración HTTPS (SECURE_SSL_REDIRECT, etc.)
- CSRF mal configurado

---

### 4. DETECT-SECRETS - Buscar Secretos Hardcodeados
**Qué detecta:** API keys, tokens, passwords en el código

```powershell
# Crear baseline (primera vez)
detect-secrets scan > .secrets.baseline

# Auditar cambios nuevos
detect-secrets scan --baseline .secrets.baseline

# Auditar un archivo específico
detect-secrets scan clases_residentes/bot_service.py
```

**Qué busca:**
- API keys de OpenAI, AWS, Google
- Tokens de autenticación
- Passwords en strings
- Claves privadas RSA/SSH

---

## 🚀 EJECUCIÓN COMPLETA

He creado un script que ejecuta todas las auditorías:

```powershell
# Ejecutar auditoría completa
.\audit_security.ps1

# O ejecutar cada herramienta manualmente:
safety check
bandit -r . -ll --exclude ./*/tests.py,./*/migrations/*
python manage.py check --deploy
detect-secrets scan
```

---

## 📊 INTERPRETANDO RESULTADOS

### SAFETY - Ejemplo de Output
```
+==============================================================================+
|                                                                              |
|                               /$$$$$$            /$$                         |
|                              /$$__  $$          | $$                         |
|           /$$$$$$$  /$$$$$$ | $$  \__//$$$$$$  /$$$$$$   /$$   /$$          |
|          /$$_____/ |____  $$| $$$$   /$$__  $$|_  $$_/  | $$  | $$          |
|         |  $$$$$$   /$$$$$$$| $$_/  | $$$$$$$$  | $$    | $$  | $$          |
|          \____  $$ /$$__  $$| $$    | $$_____/  | $$ /$$| $$  | $$          |
|          /$$$$$$$/|  $$$$$$$| $$    |  $$$$$$$  |  $$$$/|  $$$$$$$          |
|         |_______/  \_______/|__/     \_______/   \___/   \____  $$          |
|                                                            /$$  | $$          |
|                                                           |  $$$$$$/          |
|  by pyup.io                                                \______/           |
|                                                                              |
+==============================================================================+
| REPORT                                                                       |
+==============================================================================+
| package | installed | affected | source | vuln_id | CVE...
| Django  | 5.0.2     | <5.1.4   | pypi   | 12345   | CVE-2024-xxxx
+==============================================================================+
```

**Acción:** Actualizar paquetes con vulnerabilidades

---

### BANDIT - Ejemplo de Output
```
>> Issue: [B105:hardcoded_password_string] Possible hardcoded password: 'mi_password'
   Severity: Low   Confidence: Medium
   Location: accounts/views.py:42
   More Info: https://bandit.readthedocs.io/en/latest/plugins/b105_hardcoded_password_string.html
42         password = "mi_password"
```

**Cómo leer:**
- **Severity**: Baja/Media/Alta
- **Confidence**: Qué tan seguro está Bandit de que es un problema
- **Location**: Archivo y línea exacta
- **More Info**: Link a documentación

---

### DJANGO CHECK --DEPLOY - Ejemplo
```
System check identified some issues:

WARNINGS:
?: (security.W004) You have not set a value for the SECURE_HSTS_SECONDS setting.
?: (security.W008) Your SECURE_SSL_REDIRECT setting is not set to True.
?: (security.W012) SESSION_COOKIE_SECURE is not set to True.
```

**Acción:** Agregar esos settings en producción

---

## 🎯 OWASP TOP 10 APLICADO A TU PROYECTO

Te explico las vulnerabilidades más comunes y dónde buscarlas en TU código:

### 1. **Broken Access Control** ⭐⭐⭐
**Qué es:** Usuarios accediendo a recursos sin permiso

**En tu código:**
```python
# ❌ MALO - Cualquiera logueado puede ver cualquier pedido
@login_required
def ver_pedido(request, pedido_id):
    pedido = Pedido.objects.get(id=pedido_id)
    # ¡No valida si el usuario DEBE ver este pedido!

# ✅ BUENO - Validar permisos
@login_required
def ver_pedido(request, pedido_id):
    pedido = get_object_or_404(Pedido, id=pedido_id)
    if pedido.medico != request.user and not request.user.is_staff:
        return HttpResponseForbidden("No tienes permiso")
```

**Revisión en tu proyecto:**
```powershell
# Buscar views sin validación de permisos
grep -r "@login_required" --include="*.py" | grep "def "
```

---

### 2. **Cryptographic Failures**
**Qué es:** Datos sensibles sin cifrar o con cifrado débil

**En tu código:**
- ✅ Passwords: Django las hashea automáticamente (bcrypt/PBKDF2)
- ⚠️ Tokens de API (OpenAI, Google): En variables de entorno ✓
- ⚠️ Archivos subidos: ¿Están cifrados en S3/Cloudinary?

**Verificar:**
```python
# Ver qué usa Django para passwords
python manage.py shell
>>> from django.contrib.auth.hashers import identify_hasher
>>> identify_hasher('pbkdf2_sha256$...')
```

---

### 3. **Injection (SQL, Command, etc.)**
**Qué es:** Ejecutar código/queries maliciosas

**En tu código:**
```python
# ✅ BUENO - Django ORM previene SQL injection
Pedido.objects.filter(medico=medico_nombre)  # Seguro

# ❌ MALO - Query raw sin sanitizar
cursor.execute(f"SELECT * FROM pedidos WHERE medico='{medico}'")

# ✅ BUENO con raw()
cursor.execute("SELECT * FROM pedidos WHERE medico=%s", [medico])
```

**Revisar:**
```powershell
# Buscar uso de .raw() o .execute()
grep -r "\.raw\(|\.execute\(" --include="*.py"
```

---

### 4. **Insecure Design**
**Qué es:** Arquitectura sin considerar seguridad

**En tu proyecto:**
- ⚠️ Rate limiting: ¿Limitas intentos de login?
- ⚠️ Logs sensibles: ¿Guardas passwords en logs?
- ✅ Separación de concerns: Apps bien modularizadas

---

### 5. **Security Misconfiguration** ⭐⭐⭐
**Qué es:** Configuraciones por defecto inseguras

**Verificar en settings.py:**
```python
# ❌ MALO en producción
DEBUG = True
SECRET_KEY = 'hardcoded-secret-123'
ALLOWED_HOSTS = ['*']

# ✅ BUENO (tu configuración actual)
DEBUG = config('DEBUG', default='False')
SECRET_KEY = config('SECRET_KEY')
ALLOWED_HOSTS = config('ALLOWED_HOSTS').split(',')
```

---

### 6. **Vulnerable Components**
**Qué es:** Usar bibliotecas con vulnerabilidades conocidas

**Auditar:**
```powershell
safety check
pip list --outdated
```

---

### 7. **Authentication Failures**
**Qué es:** Login débil, sesiones inseguras

**En tu código:**
```python
# ✅ Django maneja esto bien por defecto
# - Rate limiting manual o con django-ratelimit
# - 2FA con django-otp (opcional)

# Verificar sesiones:
SESSION_COOKIE_HTTPONLY = True  # ✓ (default Django)
SESSION_COOKIE_SECURE = True    # Solo HTTPS
SESSION_COOKIE_SAMESITE = 'Lax'
```

---

### 8. **Software and Data Integrity Failures**
**Qué es:** Actualizaciones sin verificar, deserialización insegura

**Verificar:**
```powershell
# Buscar uso de pickle (inseguro)
grep -r "pickle\|marshal" --include="*.py"

# ✅ Mejor: Usar JSON
import json
data = json.loads(request.body)
```

---

### 9. **Logging Failures**
**Qué es:** No registrar eventos de seguridad

**En tu código:**
```python
# Agregar logging de seguridad
import logging
security_logger = logging.getLogger('security')

@login_required
def vista_critica(request):
    security_logger.info(f"Acceso a vista_critica por {request.user.username}")
    # ...

# En caso de error de autenticación
def login_view(request):
    # ...
    if not user.check_password(password):
        security_logger.warning(f"Login fallido para {username} desde {request.META['REMOTE_ADDR']}")
```

---

### 10. **Server-Side Request Forgery (SSRF)**
**Qué es:** Hacer requests a URLs internas desde el servidor

**Verificar:**
```python
# ❌ MALO - Sin validar URL
import requests
url = request.GET.get('url')
response = requests.get(url)  # ¡Puede acceder a servicios internos!

# ✅ BUENO - Validar y whitelist
ALLOWED_DOMAINS = ['api.openai.com', 'api.groq.com']
from urllib.parse import urlparse
domain = urlparse(url).netloc
if domain not in ALLOWED_DOMAINS:
    raise ValueError("Dominio no permitido")
```

---

## 📝 CHECKLIST DE SEGURIDAD COMPLETO

Copia y pega en un archivo para ir marcando:

```markdown
## Pre-Deploy Security Checklist

### Configuración
- [ ] DEBUG = False en producción
- [ ] SECRET_KEY única y aleatoria (50+ caracteres)
- [ ] ALLOWED_HOSTS configurado correctamente
- [ ] Variables de entorno (.env no en git)
- [ ] HTTPS configurado (SECURE_SSL_REDIRECT=True)
- [ ] HSTS configurado (SECURE_HSTS_SECONDS=31536000)

### Cookies y Sesiones
- [ ] SESSION_COOKIE_SECURE = True
- [ ] SESSION_COOKIE_HTTPONLY = True
- [ ] CSRF_COOKIE_SECURE = True
- [ ] SESSION_EXPIRE_AT_BROWSER_CLOSE = True (opcional)

### Base de Datos
- [ ] No usar SQLite en producción
- [ ] Password de BD fuerte y en variable de entorno
- [ ] Backups automáticos configurados
- [ ] Sin queries raw sin sanitizar

### Autenticación
- [ ] Password validators fuertes
- [ ] @login_required en todas las vistas sensibles
- [ ] Validación de permisos por objeto
- [ ] Rate limiting en login/registro

### Dependencias
- [ ] safety check sin vulnerabilidades críticas
- [ ] Dependencias actualizadas
- [ ] requirements.txt sin versiones vulnerables

### Código
- [ ] bandit -r . sin issues críticos
- [ ] No hay secretos hardcodeados (detect-secrets)
- [ ] Validación de inputs de usuario
- [ ] Sanitización de outputs (XSS)

### Infraestructura
- [ ] Firewall configurado
- [ ] Acceso SSH con llaves (no passwords)
- [ ] Logs centralizados (Sentry, etc.)
- [ ] Monitoring activo

### Archivos
- [ ] Media files con permisos correctos
- [ ] No servir archivos sensibles públicamente
- [ ] Validar tipo de archivo en uploads

### Headers de Seguridad
- [ ] X-Content-Type-Options: nosniff
- [ ] X-Frame-Options: DENY
- [ ] Content-Security-Policy configurado
```

---

## 🔧 MEJORAS IMMEDIATAS PARA TU PROYECTO

**1. Agregar Headers de Seguridad**

```python
# En settings.py
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
```

**2. Rate Limiting para Login**

```powershell
pip install django-ratelimit
```

```python
# En accounts/views.py
from django_ratelimit.decorators import ratelimit

@ratelimit(key='ip', rate='5/m', method='POST')
def login_view(request):
    # Solo 5 intentos por minuto por IP
    ...
```

**3. Instalar django-defender (anti brute-force)**

```powershell
pip install django-defender
```

**4. Logging de Seguridad**

```python
# En settings.py - LOGGING
'security': {
    'handlers': ['file'],
    'level': 'WARNING',
    'propagate': False,
},
```

---

## 📚 RECURSOS PARA APRENDER MÁS

1. **OWASP Top 10**: https://owasp.org/Top10/
2. **Django Security Docs**: https://docs.djangoproject.com/en/5.1/topics/security/
3. **Bandit Docs**: https://bandit.readthedocs.io/
4. **Python Security Best Practices**: https://python.readthedocs.io/en/latest/library/security_warnings.html

---

## ❓ PREGUNTAS FRECUENTES

**P: ¿Debo fixear TODOS los warnings de bandit?**
R: No necesariamente. Evalúa el contexto. Algunos son false positives.

**P: ¿Qué hago si Safety encuentra vulnerabilidades?**
R: 1) Lee el CVE para entender el riesgo
   2) Actualiza el paquete si es posible
   3) Si no hay fix: usa alternativas o mitigaciones

**P: ¿Cuándo ejecutar estas auditorías?**
R: - Antes de cada deploy
   - Semanalmente en desarrollo
   - Después de agregar dependencias nuevas
   - Como parte de CI/CD

---

¡Ahora ejecuta el script y aprende de los resultados! 🚀
