# ========================================
# 🔒 SEGURIDAD - CHEAT SHEET
# ========================================
# Referencia rápida de conceptos y comandos

## 📋 COMANDOS RÁPIDOS

```powershell
# Auditoría completa
.\audit_security.ps1

# Auditoría rápida (sin detect-secrets)
.\audit_security.ps1 -Quick

# Escanear solo vulnerabilidades de dependencias
safety check

# Escanear solo código
bandit -r . -ll --exclude ./*/tests.py,./*/migrations/*

# Verificar configuración Django
python manage.py check --deploy

# Ver dependencias desactualizadas
pip list --outdated

# Actualizar paquete específico
pip install --upgrade nombre-paquete

# Generar nueva SECRET_KEY
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

---

## 🎯 OWASP TOP 10 - RESUMEN EJECUTIVO

### 1. Broken Access Control
**Problema:** Usuario A puede ver datos de Usuario B
**Solución:** Validar permisos en CADA vista
```python
if not puede_acceder(request.user, objeto):
    raise PermissionDenied()
```

### 2. Cryptographic Failures
**Problema:** Datos sensibles sin cifrar
**Solución:** 
- Nunca guardar passwords en claro
- Usar HTTPS en producción
- Cifrar datos sensibles en BD

### 3. Injection
**Problema:** SQL Injection, Command Injection
**Solución:**
```python
# ✅ BUENO
User.objects.filter(username=user_input)

# ❌ MALO
cursor.execute(f"SELECT * FROM users WHERE username='{user_input}'")
```

### 4. Insecure Design
**Problema:** Arquitectura sin considerar seguridad
**Solución:**
- Rate limiting en endpoints sensibles
- Logging de eventos de seguridad
- Principio de menor privilegio

### 5. Security Misconfiguration
**Problema:** DEBUG=True, SECRET_KEY expuesta
**Solución:**
```python
DEBUG = config('DEBUG', default='False')
SECRET_KEY = config('SECRET_KEY')
```

### 6. Vulnerable Components
**Problema:** Dependencias desactualizadas con CVEs
**Solución:**
```powershell
safety check
pip list --outdated
```

### 7. Authentication Failures
**Problema:** Brute force, passwords débiles
**Solución:**
- Rate limiting en login
- Password validators robustos
- Django Defender

### 8. Software Integrity Failures
**Problema:** Deserialización insegura (pickle)
**Solución:**
```python
# ❌ MALO
import pickle
data = pickle.loads(untrusted_data)

# ✅ BUENO
import json
data = json.loads(trusted_data)
```

### 9. Logging Failures
**Problema:** No registrar eventos de seguridad
**Solución:**
```python
import logging
security_logger = logging.getLogger('security')
security_logger.warning(f'Login fallido: {username}')
```

### 10. SSRF
**Problema:** Servidor hace requests a URLs no confiables
**Solución:**
```python
# Validar y whitelist dominios
ALLOWED_DOMAINS = ['api.example.com']
if urlparse(url).netloc not in ALLOWED_DOMAINS:
    raise ValueError("Dominio no permitido")
```

---

## 🛡️ HEADERS DE SEGURIDAD

```python
# En settings.py
X_FRAME_OPTIONS = 'DENY'                    # Anti-clickjacking
SECURE_CONTENT_TYPE_NOSNIFF = True          # Anti MIME-sniffing
SECURE_BROWSER_XSS_FILTER = True            # XSS protection
SECURE_REFERRER_POLICY = 'same-origin'      # Privacidad

# Solo en PRODUCCIÓN (HTTPS)
SECURE_SSL_REDIRECT = True                   # Force HTTPS
SECURE_HSTS_SECONDS = 31536000               # HSTS 1 año
SESSION_COOKIE_SECURE = True                 # Cookies solo HTTPS
CSRF_COOKIE_SECURE = True                    # CSRF solo HTTPS
SESSION_COOKIE_HTTPONLY = True               # No acceso desde JS
SESSION_COOKIE_SAMESITE = 'Lax'              # Anti CSRF
```

---

## 🔐 PASSWORDS

### Validadores Fuertes
```python
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': '...UserAttributeSimilarityValidator'},
    {'NAME': '...MinimumLengthValidator', 'OPTIONS': {'min_length': 12}},
    {'NAME': '...CommonPasswordValidator'},
    {'NAME': '...NumericPasswordValidator'},
]
```

### Generar Hash
```python
from django.contrib.auth.hashers import make_password
hashed = make_password('mi_password')
```

### Verificar
```python
user.check_password('password_ingresado')
```

---

## 🚫 RATE LIMITING

### Decorador Simple
```python
from django_ratelimit.decorators import ratelimit

@ratelimit(key='ip', rate='5/m', method='POST')
def login_view(request):
    ...
```

### Keys disponibles:
- `ip`: Por dirección IP
- `user`: Por usuario autenticado
- `header:x-real-ip`: Por header custom
- `get:search`: Por parámetro GET

### Rates:
- `5/m`: 5 por minuto
- `100/h`: 100 por hora
- `1000/d`: 1000 por día

---

## 📝 VALIDACIÓN DE INPUTS

### En Forms
```python
class MiForm(forms.Form):
    email = forms.EmailField()  # Valida formato
    edad = forms.IntegerField(min_value=0, max_value=120)
    telefono = forms.CharField(
        validators=[RegexValidator(r'^\d{10}$')]
    )
    
    def clean_email(self):
        email = self.cleaned_data['email']
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('Ya existe')
        return email
```

### En Views
```python
# NUNCA confiar en request.GET/POST directamente
dato = request.GET.get('dato')

# Siempre validar
if not dato or not dato.isdigit():
    return HttpResponseBadRequest('Dato inválido')
```

---

## 🧹 SANITIZACIÓN HTML

```python
import bleach

ALLOWED_TAGS = ['p', 'br', 'strong', 'em']
ALLOWED_ATTRS = {}

html_limpio = bleach.clean(
    html_sucio,
    tags=ALLOWED_TAGS,
    attributes=ALLOWED_ATTRS,
    strip=True
)
```

---

## 🔍 LOGGING DE SEGURIDAD

```python
import logging
security_logger = logging.getLogger('security')

# Niveles
security_logger.debug('Info de debug')
security_logger.info('Evento normal')
security_logger.warning('Evento sospechoso')
security_logger.error('Error de seguridad')
security_logger.critical('Brecha de seguridad!')

# Con metadata
security_logger.warning(
    'Login fallido',
    extra={
        'username': username,
        'ip': request.META['REMOTE_ADDR'],
        'user_agent': request.META['HTTP_USER_AGENT']
    }
)
```

---

## 📊 INTERPRETANDO SEVERITY

### Bandit
- **High**: Arreglar AHORA
- **Medium**: Arreglar antes de deploy
- **Low**: Revisar cuando puedas

### Safety (CVEs)
- **Critical**: Drop everything, patch NOW
- **High**: Patch within 24-48h
- **Medium**: Patch within 1 week
- **Low**: Patch in next maintenance window

### Django Check
- **ERROR**: Bloquea deploy
- **WARNING**: Revisar y justificar si no se arregla

---

## 🎯 CHECKLIST PRE-DEPLOY

```
□ safety check pasa
□ bandit sin issues críticos
□ python manage.py check --deploy sin errores
□ DEBUG=False
□ SECRET_KEY única y secreta
□ ALLOWED_HOSTS configurado
□ HTTPS forzado
□ Headers de seguridad activos
□ Rate limiting en login
□ Logging configurado
□ Backups automáticos activos
□ .env no en git
□ credentials.json no en git
```

---

## 🚨 QUÉ HACER EN CASO DE BRECHA

1. **Contener**
   - Desconectar servidor si es crítico
   - Cambiar todas las passwords/tokens/keys
   - Revisar logs para ver alcance

2. **Evaluar**
   - ¿Qué datos se comprometieron?
   - ¿Cuántos usuarios afectados?
   - ¿Cómo entró el atacante?

3. **Remediar**
   - Patchear vulnerabilidad
   - Notificar a usuarios afectados
   - Cambiar credenciales comprometidas

4. **Aprender**
   - Documentar incidente
   - Implementar prevención
   - Agregar tests

---

## 📚 RECURSOS ÚTILES

- OWASP Top 10: https://owasp.org/Top10/
- Django Security: https://docs.djangoproject.com/en/stable/topics/security/
- Common Vulnerabilities (CVE): https://cve.mitre.org/
- Bandit Docs: https://bandit.readthedocs.io/
- Safety DB: https://pyup.io/safety/

---

## 🎓 CONCEPTOS CLAVE

**XSS (Cross-Site Scripting)**: Inyectar JavaScript malicioso
- Prevención: Escapar outputs, CSP

**CSRF (Cross-Site Request Forgery)**: Hacer requests no autorizados
- Prevención: CSRF tokens (Django lo hace por defecto)

**SQL Injection**: Inyectar SQL malicioso
- Prevención: ORM, queries parametrizadas

**Clickjacking**: Iframe invisible que captura clicks
- Prevención: X-Frame-Options, CSP

**SSRF**: Servidor hace requests a recursos internos
- Prevención: Validar y whitelist URLs

**IDOR**: Acceso a objetos sin validar permisos
- Prevención: Validar permisos por objeto

**Brute Force**: Intentar todas las combinaciones
- Prevención: Rate limiting, CAPTCHA

---

## 💡 TIPS FINALES

1. **Defense in Depth**: Múltiples capas de seguridad
2. **Least Privilege**: Dar solo permisos necesarios
3. **Fail Securely**: En caso de error, negar acceso
4. **Don't Trust Input**: Validar TODO del usuario
5. **Keep Simple**: Código complejo = más bugs
6. **Audit Regularly**: Seguridad es proceso continuo
7. **Update Dependencies**: Parchear vulnerabilidades conocidas
8. **Encrypt Sensitive Data**: En tránsito y en reposo
9. **Log Security Events**: Para auditoría y forensics
10. **Test Security**: Incluir en test suite

---

**¿Preguntas? Revisa:**
- [AUDITORIA_SEGURIDAD.md](AUDITORIA_SEGURIDAD.md) - Guía completa
- [MEJORAS_SEGURIDAD_IMPLEMENTABLES.md](MEJORAS_SEGURIDAD_IMPLEMENTABLES.md) - Implementación paso a paso
