# ========================================
# 🔒 MEJORAS DE SEGURIDAD IMPLEMENTABLES
# ========================================
# Configuraciones que puedes agregar YA a tu proyecto

## 🚀 IMPLEMENTACIÓN RÁPIDA (15 minutos)

### 1. Headers de Seguridad en settings.py

Agrega al final de tu `gestion_estudios/settings.py`:

```python
# ========================================
# 🔒 SECURITY HEADERS
# ========================================

# Prevenir clickjacking
X_FRAME_OPTIONS = 'DENY'

# Prevenir MIME-type sniffing
SECURE_CONTENT_TYPE_NOSNIFF = True

# Activar XSS filter del navegador
SECURE_BROWSER_XSS_FILTER = True

# Referrer Policy
SECURE_REFERRER_POLICY = 'same-origin'

# Solo en PRODUCCIÓN (cuando uses HTTPS):
if not DEBUG:
    # Redirigir todo a HTTPS
    SECURE_SSL_REDIRECT = True
    
    # HTTP Strict Transport Security (HSTS)
    SECURE_HSTS_SECONDS = 31536000  # 1 año
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    
    # Cookies solo por HTTPS
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

# Cookies HTTPOnly (prevenir acceso desde JavaScript)
SESSION_COOKIE_HTTPONLY = True

# CSRF cookie: False para permitir AJAX/fetch
# Nota: La sesión permanece protegida con SESSION_COOKIE_HTTPONLY=True  
CSRF_COOKIE_HTTPONLY = False

# SameSite cookies (prevenir CSRF)
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'
```

**Explicación:**
- `X_FRAME_OPTIONS`: Impide que tu sitio sea embebido en iframes (previene clickjacking)
- `SECURE_CONTENT_TYPE_NOSNIFF`: El navegador respeta el Content-Type (no intenta "adivinar")
- `SECURE_BROWSER_XSS_FILTER`: Activa protección XSS del navegador
- `HSTS`: Le dice al navegador "siempre usa HTTPS con este dominio"
- `SESSION_COOKIE_HTTPONLY`: JavaScript no puede leer cookies de sesión (previene XSS)
- `CSRF_COOKIE_HTTPONLY`: False para aplicaciones con AJAX (necesitan `getCookie('csrftoken')`)
- `SAMESITE`: Solo envía cookies en requests del mismo dominio

---

### 2. Password Validators Robustos

En `settings.py`, busca `AUTH_PASSWORD_VALIDATORS` y mejóralo:

```python
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
        'OPTIONS': {
            'user_attributes': ('username', 'email', 'first_name', 'last_name'),
            'max_similarity': 0.7,  # Más estricto
        }
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {
            'min_length': 12,  # Aumentado de 8 a 12
        }
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]
```

**Por qué:**
- Passwords más largos = exponencialmente más seguros
- Previene passwords como "juan1234" si el usuario se llama Juan

---

### 3. Rate Limiting (Anti Brute Force)

**Instalar:**
```powershell
pip install django-ratelimit
```

**En `accounts/views.py` (o donde esté tu login):**

```python
from django_ratelimit.decorators import ratelimit
from django_ratelimit.exceptions import Ratelimited

# Agregar al login
@ratelimit(key='ip', rate='5/m', method='POST')
def login_view(request):
    # Si es rate-limited, Django levanta Ratelimited exception
    try:
        # Tu código de login existente
        pass
    except Ratelimited:
        messages.error(request, 'Demasiados intentos. Espera 1 minuto.')
        return redirect('login')
```

**Configuración global en settings.py:**
```python
# Configuración de rate limiting
RATELIMIT_ENABLE = True
RATELIMIT_VIEW = 'accounts.views.rate_limited_view'  # Vista personalizada
```

**Crear vista para rate limit:**
```python
# En accounts/views.py
def rate_limited_view(request, exception):
    return render(request, 'errors/rate_limited.html', status=429)
```

**Por qué:**
- Previene ataques de fuerza bruta al login
- 5 intentos por minuto por IP es razonable

---

### 4. Django Defender (Protección Automática)

**Instalar:**
```powershell
pip install django-defender
```

**En `settings.py`:**

```python
INSTALLED_APPS = [
    # ... apps existentes
    'defender',
]

MIDDLEWARE = [
    # ... middleware existente
    'defender.middleware.FailedLoginMiddleware',
]

# Configuración de Defender
DEFENDER_REDIS_URL = config('REDIS_URL', default=None)  # Opcional, mejora performance
DEFENDER_LOGIN_FAILURE_LIMIT = 5  # Bloquear después de 5 fallos
DEFENDER_COOLOFF_TIME = 300  # Bloquear por 5 minutos (en segundos)
DEFENDER_LOCKOUT_TEMPLATE = 'errors/lockout.html'  # Template personalizado
DEFENDER_BEHIND_REVERSE_PROXY = True  # Si usas Heroku/proxy
DEFENDER_DISABLE_IP_LOCKOUT = False
DEFENDER_DISABLE_USERNAME_LOCKOUT = False
```

**Migrar:**
```powershell
python manage.py migrate defender
```

**Por qué:**
- Bloquea IPs y usuarios después de muchos intentos fallidos
- Es automático, no requiere modificar código existente

---

### 5. Content Security Policy (CSP)

**Instalar:**
```powershell
pip install django-csp
```

**En `settings.py`:**

```python
MIDDLEWARE = [
    # ... middleware existente
    'csp.middleware.CSPMiddleware',
]

# Configuración CSP (ajustar según tus necesidades)
CSP_DEFAULT_SRC = ("'self'",)
CSP_SCRIPT_SRC = (
    "'self'",
    "'unsafe-inline'",  # Solo si usas inline scripts (intenta evitarlo)
    'cdn.jsdelivr.net',  # CDNs que uses
)
CSP_STYLE_SRC = (
    "'self'",
    "'unsafe-inline'",  # Para Tailwind/estilos inline
)
CSP_IMG_SRC = (
    "'self'",
    'data:',  # Para imágenes base64
    'res.cloudinary.com',  # Tu CDN de imágenes
)
CSP_FONT_SRC = ("'self'", 'data:')
CSP_CONNECT_SRC = ("'self'",)
CSP_FRAME_ANCESTORS = ("'none'",)  # No permitir iframes
```

**Por qué:**
- Define qué recursos (scripts, estilos, imágenes) puede cargar tu sitio
- Previene ataques XSS y injection de código malicioso

---

### 6. Logging de Seguridad Mejorado

**En `settings.py` - LOGGING:**

```python
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{levelname}] {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'security_file': {
            'level': 'WARNING',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(BASE_DIR, 'logs', 'security.log'),
            'maxBytes': 1024 * 1024 * 10,  # 10MB
            'backupCount': 5,
            'formatter': 'verbose',
        },
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        # Logger específico de seguridad
        'security': {
            'handlers': ['security_file', 'console'],
            'level': 'INFO',
            'propagate': False,
        },
        # Loggear intentos de login fallidos
        'django.security': {
            'handlers': ['security_file'],
            'level': 'WARNING',
            'propagate': False,
        },
    },
}
```

**Crear directorio logs:**
```powershell
mkdir logs
# Agregar logs/ al .gitignore
```

**Usar en views:**
```python
import logging
security_logger = logging.getLogger('security')

def vista_sensible(request):
    security_logger.info(
        f'Acceso a recurso sensible',
        extra={
            'user': request.user.username,
            'ip': request.META.get('REMOTE_ADDR'),
            'path': request.path
        }
    )
```

---

### 7. Validación de Permisos por Objeto

**Patrón a seguir en TODAS las vistas:**

```python
from django.shortcuts import get_object_or_404
from django.core.exceptions import PermissionDenied

@login_required
def ver_pedido(request, pedido_id):
    pedido = get_object_or_404(Pedido, id=pedido_id)
    
    # ✅ VALIDAR permisos antes de mostrar datos
    if not puede_ver_pedido(request.user, pedido):
        raise PermissionDenied("No tienes permiso para ver este pedido")
    
    return render(request, 'pedido_detail.html', {'pedido': pedido})

def puede_ver_pedido(user, pedido):
    """Lógica de permisos centralizada"""
    if user.is_staff:
        return True
    if pedido.medico == user:
        return True
    if pedido.servicio in user.servicios_acceso.all():
        return True
    return False
```

**Por qué:**
- `@login_required` solo verifica que esté logueado
- NO verifica si DEBE ver ese recurso específico
- Esto previene Insecure Direct Object Reference (IDOR)

---

### 8. Sanitización de Outputs (Prevenir XSS)

**En templates, SIEMPRE escapa HTML:**

```django
{# ✅ BUENO - Escapado por defecto #}
{{ user.nombre }}

{# ❌ MALO - No escapa, abre XSS #}
{{ user.biografia|safe }}

{# ✅ BUENO si necesitas HTML - Usa bleach para sanitizar #}
{{ user.biografia|sanitize_html }}
```

**Instalar bleach:**
```powershell
pip install bleach
```

**Crear filtro personalizado:**
```python
# En templatetags/security_extras.py
from django import template
import bleach

register = template.Library()

ALLOWED_TAGS = ['p', 'br', 'strong', 'em', 'u', 'a']
ALLOWED_ATTRS = {'a': ['href', 'title']}

@register.filter(name='sanitize_html')
def sanitize_html(value):
    return bleach.clean(value, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS)
```

---

### 9. Validación Estricta de Inputs

**En forms.py:**

```python
from django import forms
from django.core.validators import RegexValidator

class PedidoForm(forms.ModelForm):
    # Validador personalizado para número de afiliado
    numero_afiliado = forms.CharField(
        validators=[
            RegexValidator(
                regex=r'^\d{8,12}$',
                message='Debe ser un número de 8-12 dígitos'
            )
        ]
    )
    
    def clean_numero_afiliado(self):
        """Validación adicional"""
        numero = self.cleaned_data['numero_afiliado']
        
        # Sanitizar (remover espacios, guiones)
        numero = numero.replace(' ', '').replace('-', '')
        
        # Validar rango
        if not numero.isdigit():
            raise forms.ValidationError('Solo números permitidos')
        
        return numero
    
    def clean(self):
        """Validación a nivel de formulario completo"""
        cleaned_data = super().clean()
        
        # Validaciones cruzadas
        fecha_estudio = cleaned_data.get('fecha_estudio')
        if fecha_estudio and fecha_estudio > timezone.now().date():
            raise forms.ValidationError('La fecha no puede ser futura')
        
        return cleaned_data
```

**Por qué:**
- NUNCA confíes en datos del usuario
- Valida tipo, formato, rango, lógica de negocio

---

### 10. Variables de Entorno - Checklist

**Verificar tu `.env`:**

```env
# ✅ BUENAS PRÁCTICAS

# SECRET_KEY: 50+ caracteres, aleatorio
SECRET_KEY=django-insecure-q8h5h$%&ksdjfh3h4h5j43h5kjh345kj3h4k5jh34k5j

# DEBUG: False en producción
DEBUG=False

# ALLOWED_HOSTS: Dominios específicos
ALLOWED_HOSTS=midominio.com,www.midominio.com

# Database: No hardcodear passwords
DATABASE_URL=postgres://user:STRONG_PASS_HERE@host:5432/dbname

# API Keys: No compartir, rotar periódicamente
OPENAI_API_KEY=sk-proj-...
GROQ_API_KEY=gsk_...

# Email: Credenciales separadas
EMAIL_HOST_USER=notificaciones@midominio.com
EMAIL_HOST_PASSWORD=APP_SPECIFIC_PASSWORD  # No tu password real
```

**Generar SECRET_KEY segura:**
```python
# En shell de Python
from django.core.management.utils import get_random_secret_key
print(get_random_secret_key())
```

---

## ✅ CHECKLIST DE IMPLEMENTACIÓN

Marca lo que implementes:

```
□ Headers de seguridad agregados a settings.py
□ Password validators reforzados (min 12 caracteres)
□ Rate limiting instalado y configurado
□ Django Defender instalado
□ CSP configurado (opcional pero recomendado)
□ Logging de seguridad implementado
□ Validación de permisos por objeto en vistas críticas
□ Sanitización de HTML en templates
□ Validación estricta de inputs en forms
□ Variables de entorno auditadas
□ SECRET_KEY regenerada y segura
□ DEBUG=False en producción
□ HTTPS forzado en producción
□ Cookies secure en producción
```

---

## 🧪 TESTING DE SEGURIDAD

**Después de implementar, testea:**

### 1. Test Headers
```bash
# Desde terminal Unix/Mac/WSL
curl -I https://tu-dominio.com

# Deberías ver:
# X-Frame-Options: DENY
# X-Content-Type-Options: nosniff
# Strict-Transport-Security: max-age=31536000
```

### 2. Test Rate Limiting
```python
# En tests/test_security.py
from django.test import TestCase, Client

class SecurityTests(TestCase):
    def test_rate_limiting_login(self):
        client = Client()
        
        # Intentar login 10 veces
        for i in range(10):
            response = client.post('/accounts/login/', {
                'username': 'test',
                'password': 'wrong'
            })
        
        # El último debe ser bloqueado
        self.assertEqual(response.status_code, 429)
```

### 3. Test Permisos
```python
def test_no_puede_ver_pedido_de_otro(self):
    # Usuario A
    user_a = User.objects.create_user('user_a', password='test')
    pedido_a = Pedido.objects.create(medico=user_a, ...)
    
    # Usuario B intenta ver pedido de A
    client = Client()
    client.force_login(User.objects.create_user('user_b'))
    response = client.get(f'/pedidos/{pedido_a.id}/')
    
    self.assertEqual(response.status_code, 403)  # Forbidden
```

---

## 📊 PRIORIDAD DE IMPLEMENTACIÓN

### Alta (Hacer HOY):
1. ✅ Headers de seguridad
2. ✅ Rate limiting en login
3. ✅ Validación de permisos por objeto
4. ✅ Regenerar SECRET_KEY

### Media (Esta semana):
5. ✅ Django Defender
6. ✅ Password validators robustos
7. ✅ Logging de seguridad
8. ✅ Sanitización de HTML

### Baja (Próximo mes):
9. ⚡ CSP (requiere testing extensivo)
10. ⚡ Auditoría completa de inputs

---

¿Quieres que implemente alguna de estas mejoras directamente en tu código?
