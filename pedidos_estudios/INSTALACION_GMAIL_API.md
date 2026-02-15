# Guía Completa de Instalación de Gmail API

## 🎯 Objetivo

Conectar tu aplicación Django con Gmail para leer automáticamente los emails de pedidos de estudios.

## ⏱️ Tiempo estimado: 15-20 minutos

---

## Parte 1: Instalar Librerías Python

### Paso 1.1: Activar entorno virtual

```powershell
# Ya deberías tenerlo activado, pero por las dudas:
cd C:\Dev\GitHub\gestion_servicio
.\gestion_env\Scripts\Activate.ps1
```

### Paso 1.2: Instalar dependencias de Google

```bash
pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client beautifulsoup4
```

**Qué hace cada librería:**
- `google-auth`: Autenticación con Google
- `google-auth-oauthlib`: OAuth 2.0 (login con Google)
- `google-auth-httplib2`: Transporte HTTP para las APIs
- `google-api-python-client`: Cliente de Gmail API
- `beautifulsoup4`: Parser de HTML para emails

### Paso 1.3: Actualizar requirements.txt

```bash
pip freeze | Select-String -Pattern "google|beautiful" >> requirements_gmail.txt
```

Copia las líneas que se generaron y agrégalas a tu `requirements.txt` principal:

```txt
google-auth==2.25.2
google-auth-httplib2==0.2.0
google-auth-oauthlib==1.2.0
google-api-python-client==2.110.0
beautifulsoup4==4.12.2
```

---

## Parte 2: Configurar Google Cloud Console

### Paso 2.1: Acceder a Google Cloud Console

1. Ve a: **https://console.cloud.google.com/**
2. Inicia sesión con tu cuenta de Gmail (la que administra `solicitudestudioscolegiales@gmail.com`)

### Paso 2.2: Crear un Proyecto Nuevo

1. En la parte superior, haz clic en el **selector de proyectos**
2. Clic en **"Proyecto nuevo"** (o "New Project")
3. Completa:
   - **Nombre del proyecto**: `Sanatorio Colegiales - Pedidos Estudios`
   - **ID del proyecto**: (se genera automático) `pedidos-estudios-xxxxx`
   - **Ubicación**: Sin organización (o tu organización si tienes)
4. Clic en **"Crear"**

⏱️ Espera 10-20 segundos mientras se crea el proyecto.

### Paso 2.3: Habilitar Gmail API

1. En el menú lateral, ve a: **APIs y servicios → Biblioteca**
   - O busca en el buscador superior: "Gmail API"
2. Encuentra **"Gmail API"**
3. Clic en la tarjeta de Gmail API
4. Clic en el botón **"HABILITAR"**

⏱️ Espera unos segundos. Verás un mensaje de confirmación.

### Paso 2.4: Configurar Pantalla de Consentimiento OAuth

Este paso es necesario para que Google sepa qué permisos necesitas.

1. Ve a: **APIs y servicios → Pantalla de consentimiento de OAuth**
2. Selecciona tipo de usuario: **"Externo"** (o "Interno" si tienes Google Workspace)
3. Clic en **"Crear"**

**Completar formulario:**

#### Paso 1 - Información de la aplicación:
- **Nombre de la aplicación**: `Sistema de Pedidos - Sanatorio Colegiales`
- **Correo de asistencia**: `tu-email@sanatoriocolegiales.com.ar`
- **Logo**: (opcional, déjalo en blanco por ahora)
- **Dominio de la app**: (déjalo en blanco)
- **Página principal**: (déjalo en blanco)

#### Paso 2 - Dominios autorizados:
- (Déjalo en blanco por ahora)

#### Paso 3 - Información de contacto del desarrollador:
- **Correo electrónico**: `ecejas@sanatoriocolegiales.com.ar`

Clic en **"Guardar y continuar"**

#### Paso 4 - Alcances (Scopes):
1. Clic en **"Agregar o quitar alcances"**
2. En el buscador, busca: `gmail`
3. **Selecciona estos alcances:**
   - ✅ `https://www.googleapis.com/auth/gmail.readonly` - Ver tus mensajes
   - ✅ `https://www.googleapis.com/auth/gmail.modify` - Modificar etiquetas (marcar como leído)

4. Clic en **"Actualizar"**
5. Clic en **"Guardar y continuar"**

#### Paso 5 - Usuarios de prueba:
1. Clic en **"Agregar usuarios"**
2. Agrega el email: `solicitudestudioscolegiales@gmail.com`
3. Clic en **"Agregar"**
4. Clic en **"Guardar y continuar"**

#### Paso 6 - Resumen:
- Revisa que todo esté correcto
- Clic en **"Volver al panel"**

### Paso 2.5: Crear Credenciales OAuth 2.0

1. Ve a: **APIs y servicios → Credenciales**
2. Clic en **"+ CREAR CREDENCIALES"** (arriba)
3. Selecciona: **"ID de cliente de OAuth"**

**Configuración:**
- **Tipo de aplicación**: **"Aplicación de escritorio"**
- **Nombre**: `Cliente Desktop - Pedidos Estudios`

4. Clic en **"Crear"**

### Paso 2.6: Descargar Credenciales

1. Verás un modal: **"Cliente de OAuth creado"**
2. Clic en **"DESCARGAR JSON"**
3. Se descarga un archivo con nombre como: `client_secret_xxxxx.apps.googleusercontent.com.json`

**IMPORTANTE**: 
- Renombra este archivo a: **`credentials.json`**
- Guárdalo en la raíz de tu proyecto: `C:\Dev\GitHub\gestion_servicio\credentials.json`

---

## Parte 3: Configurar Django

### Paso 3.1: Crear archivo de configuración local

Crea `gestion_estudios/settings_local.py` (si no existe):

```python
# settings_local.py - NO commitear a Git (agregar a .gitignore)

import os
from pathlib import Path

# Base directory
BASE_DIR = Path(__file__).resolve().parent.parent

# Configuración de Gmail API
GMAIL_CONFIG = {
    'CREDENTIALS_FILE': os.path.join(BASE_DIR, 'credentials.json'),
    'TOKEN_FILE': os.path.join(BASE_DIR, 'token.json'),
    'EMAIL_ADDRESS': 'solicitudestudioscolegiales@gmail.com',
}

# Query de búsqueda personalizada (opcional)
# Puedes filtrar por remitente específico, por ejemplo:
# GMAIL_PEDIDOS_QUERY = 'from:sanatorio@ejemplo.com is:unread'
GMAIL_PEDIDOS_QUERY = 'is:unread'

# Email por defecto para notificaciones
PEDIDOS_EMAIL_DEFAULT = 'ecejas@sanatoriocolegiales.com.ar'
```

### Paso 3.2: Importar settings_local en settings.py

En tu archivo principal `gestion_estudios/settings.py`, al final:

```python
# Al final del archivo settings.py

# Importar configuración local si existe
try:
    from .settings_local import *
except ImportError:
    pass
```

### Paso 3.3: Actualizar .gitignore

**CRÍTICO**: No commitees las credenciales a Git

Abre `.gitignore` y agrega:

```gitignore
# Credenciales de Gmail API
credentials.json
token.json

# Settings locales
gestion_estudios/settings_local.py

# Archivos temporales
*.log
```

### Paso 3.4: Agregar app a INSTALLED_APPS

En `gestion_estudios/settings.py`:

```python
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # ... otras apps
    'pedidos_estudios',  # ← Agregar esta línea
]
```

### Paso 3.5: Agregar URLs

En `gestion_estudios/urls.py` (el archivo principal de URLs):

```python
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # ... otras URLs existentes
    
    # Pedidos de estudios
    path('pedidos-estudios/', include('pedidos_estudios.urls')),  # ← Agregar
]
```

---

## Parte 4: Migrar Base de Datos

### Paso 4.1: Crear migraciones

```bash
python manage.py makemigrations pedidos_estudios
```

Deberías ver:

```
Migrations for 'pedidos_estudios':
  pedidos_estudios\migrations\0001_initial.py
    - Create model PacienteEstudio
    - Create model TipoEstudio
    - Create model PedidoEstudio
    - Create model AdjuntoEmail
    - Create model LogProcesamientoEmail
```

### Paso 4.2: Aplicar migraciones

```bash
python manage.py migrate
```

Deberías ver algo como:

```
Running migrations:
  Applying pedidos_estudios.0001_initial... OK
```

### Paso 4.3: Cargar tipos de estudio iniciales

```bash
python manage.py cargar_tipos_estudio_inicial
```

Verás:

```
Cargando tipos de estudio iniciales...
  ✓ Creado: Ecocardiograma Transtorácico
  ✓ Creado: Ecocardiograma Transesofágico
  ✓ Creado: Ecodoppler Carotídeo y Vertebral
  ... (12 tipos en total)

Resumen:
  • Tipos de estudio creados: 12
  • Total: 12
```

---

## Parte 5: Primera Autenticación con Gmail

### Paso 5.1: Verificar que credentials.json está en su lugar

```bash
# Verifica que el archivo existe
Test-Path .\credentials.json
```

Debería devolver: `True`

### Paso 5.2: Ejecutar primera autenticación

```bash
python manage.py shell
```

Dentro del shell de Django:

```python
from pedidos_estudios.services.gmail_service import verificar_configuracion_gmail

# Esto abrirá tu navegador
exito, mensaje = verificar_configuracion_gmail()
print(f"Éxito: {exito}")
print(f"Mensaje: {mensaje}")
```

### Paso 5.3: Autorizar en el navegador

**Se abrirá automáticamente tu navegador** con la pantalla de Google:

1. **Selecciona la cuenta**: `solicitudestudioscolegiales@gmail.com`

2. **Verás advertencia**: "Google no ha verificado esta aplicación"
   - Es normal para apps en desarrollo
   - Clic en **"Avanzado"** o **"Advanced"**
   - Clic en **"Ir a Sistema de Pedidos (no seguro)"**

3. **Permisos solicitados**:
   - Ver tus mensajes de correo electrónico
   - Administrar tus mensajes (marcar como leído)
   - Clic en **"Permitir"**

4. **Confirmación**: Verás un mensaje "The authentication flow has completed"
   - Puedes cerrar esta pestaña

### Paso 5.4: Verificar token creado

El archivo `token.json` se habrá creado automáticamente:

```bash
Test-Path .\token.json
```

Debería devolver: `True`

### Paso 5.5: Ver resultado en shell

De vuelta en el shell de Django, deberías ver:

```python
Éxito: True
Mensaje: Conectado a solicitudestudioscolegiales@gmail.com - 1234 mensajes
```

¡Perfecto! La conexión está funcionando.

Sal del shell:

```python
exit()
```

---

## Parte 6: Probar el Sistema

### Paso 6.1: Crear un superusuario (si no tienes)

```bash
python manage.py createsuperuser
```

### Paso 6.2: Ejecutar servidor de desarrollo

```bash
python manage.py runserver
```

### Paso 6.3: Acceder al admin

Abre: http://127.0.0.1:8000/admin/

1. Inicia sesión con tu superusuario
2. Ve a **Pedidos estudios** → **Tipos de Estudios**
3. Deberías ver los 12 tipos cargados
4. **Edita cada tipo** y asigna un médico responsable

### Paso 6.4: Probar procesamiento de emails (modo prueba)

```bash
# Procesa emails SIN marcar como leído (modo prueba)
python manage.py procesar_pedidos_email --no-marcar-leido --no-notificar
```

Si hay emails no leídos en la casilla, los procesará y verás:

```
Iniciando procesamiento de hasta 10 emails...
Procesando 3 emails

=== Resumen del Procesamiento ===
Emails procesados: 3
✓ Exitosos: 2
⚠ Duplicados: 0
✗ Errores: 1

Procesamiento completado.
```

### Paso 6.5: Ver pedidos creados

1. En el admin, ve a: **Pedidos estudios** → **Pedidos de Estudios**
2. Deberías ver los pedidos creados
3. Revisa datos extraídos, estado, prioridad

### Paso 6.6: Ver logs de procesamiento

1. En el admin: **Pedidos estudios** → **Logs de Procesamiento**
2. Verás cada email procesado con:
   - Resultado (Éxito/Error/Duplicado)
   - Tiempo de procesamiento
   - Errores encontrados
   - Datos extraídos

---

## Parte 7: Ajustar Parser (cuando tengas emails reales)

### Paso 7.1: Ver email crudo

En el admin, ve a un pedido y expande **"Datos del Email"** → verás el JSON completo.

### Paso 7.2: Probar extracción

```bash
python manage.py shell
```

```python
from pedidos_estudios.services.email_parser import extraer_informacion_basica

# Copia el texto de un email real aquí
texto = """
Paciente: Juan Pérez
DNI: 12345678
Habitación: 302A
Estudio: Ecodoppler carotídeo bilateral
"""

datos = extraer_informacion_basica(texto)
print(datos)
```

### Paso 7.3: Ajustar patrones

Edita `pedidos_estudios/services/email_parser.py`:

```python
PATRONES = {
    'nombre': [
        r'paciente:\s*([A-ZÁÉÍÓÚÑa-záéíóúñ\s]+)',
        r'nombre:\s*([A-ZÁÉÍÓÚÑa-záéíóúñ\s]+)',
        # Agregar nuevo patrón según tu formato
        r'pac:\s*([A-ZÁÉÍÓÚÑa-záéíóúñ\s]+)',  # ← Ejemplo
    ],
}
```

---

## Parte 8: Automatización (Opcional)

### Opción A: Windows Task Scheduler

1. Abre **Programador de tareas** (Task Scheduler)
2. Crear tarea básica:
   - **Nombre**: `Procesar Pedidos Estudios`
   - **Desencadenador**: Diariamente, cada 15 minutos
   - **Acción**: Iniciar programa
   - **Programa**: `C:\Dev\GitHub\gestion_servicio\gestion_env\Scripts\python.exe`
   - **Argumentos**: `manage.py procesar_pedidos_email`
   - **Iniciar en**: `C:\Dev\GitHub\gestion_servicio`

### Opción B: Heroku Scheduler (para producción)

Si despliegas en Heroku:

```bash
# Agregar Heroku Scheduler
heroku addons:create scheduler:standard --app gestion-colegiales

# Configurar job
heroku addons:open scheduler --app gestion-colegiales
```

En la interfaz web, agrega:
- **Comando**: `python manage.py procesar_pedidos_email`
- **Frecuencia**: Every 10 minutes

---

## 🔒 Seguridad

### ¡MUY IMPORTANTE!

**NUNCA subas a Git:**
- ❌ `credentials.json` - Credenciales OAuth
- ❌ `token.json` - Token de acceso
- ❌ `settings_local.py` - Configuración local

Verifica tu `.gitignore`:

```bash
git status
```

Si ves `credentials.json` o `token.json` listados:

```bash
git rm --cached credentials.json
git rm --cached token.json
```

### Para producción (Heroku):

No uses archivos JSON. En su lugar:

```python
# settings.py (producción)
import json
import os

if os.environ.get('HEROKU'):
    # Leer de variables de entorno
    GMAIL_CONFIG = {
        'CREDENTIALS': json.loads(os.environ.get('GOOGLE_CREDENTIALS')),
        'TOKEN': json.loads(os.environ.get('GOOGLE_TOKEN')),
    }
```

Configura en Heroku:

```bash
heroku config:set GOOGLE_CREDENTIALS="$(cat credentials.json)" --app gestion-colegiales
heroku config:set GOOGLE_TOKEN="$(cat token.json)" --app gestion-colegiales
```

---

## 🐛 Troubleshooting

### Error: "ModuleNotFoundError: No module named 'google'"

**Solución**:
```bash
pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client
```

### Error: "FileNotFoundError: credentials.json"

**Solución**:
- Verifica que `credentials.json` está en la raíz del proyecto
- Verifica la ruta en `settings_local.py`

### Error: "invalid_grant" o token expirado

**Solución**:
```bash
# Eliminar token viejo
Remove-Item token.json

# Volver a autenticar
python manage.py shell
>>> from pedidos_estudios.services.gmail_service import verificar_configuracion_gmail
>>> verificar_configuracion_gmail()
```

### Error: "Access blocked: This app's request is invalid"

**Solución**:
- Verifica los alcances en Google Cloud Console
- Asegúrate de tener Gmail API habilitada
- Revisa que el email esté en "Usuarios de prueba"

### Los emails no se leen

**Solución**:
```bash
python manage.py shell
```

```python
from pedidos_estudios.services.gmail_service import GmailService

gmail = GmailService()
info = gmail.obtener_info_cuenta()
print(info)

# Probar lectura
emails = gmail.obtener_emails_nuevos(max_results=1)
print(f"Emails encontrados: {len(emails)}")
if emails:
    print(emails[0])
```

---

## 📊 Comandos Útiles

### Ver información de la cuenta conectada

```bash
python manage.py shell
```

```python
from pedidos_estudios.services.gmail_service import GmailService
gmail = GmailService()
info = gmail.obtener_info_cuenta()
print(f"Email: {info['email']}")
print(f"Total mensajes: {info['total_mensajes']}")
```

### Procesar emails en diferentes modos

```bash
# Modo prueba (no modifica Gmail)
python manage.py procesar_pedidos_email --no-marcar-leido --no-notificar

# Procesar 20 emails
python manage.py procesar_pedidos_email --max-emails 20

# Producción (marca leídos y notifica)
python manage.py procesar_pedidos_email
```

### Ver estadísticas

```bash
python manage.py shell
```

```python
from pedidos_estudios.models import PedidoEstudio, LogProcesamientoEmail

# Total pedidos
print(f"Total pedidos: {PedidoEstudio.objects.count()}")

# Pendientes
print(f"Pendientes: {PedidoEstudio.objects.filter(estado='PENDIENTE').count()}")

# Urgentes
print(f"Urgentes: {PedidoEstudio.objects.filter(prioridad='URGENTE').count()}")

# Últimos logs
logs = LogProcesamientoEmail.objects.order_by('-fecha_procesamiento')[:5]
for log in logs:
    print(f"{log.email_asunto} - {log.resultado}")
```

---

## ✅ Checklist Final

Antes de considerar la instalación completa:

- [ ] Librerías de Google instaladas
- [ ] Proyecto creado en Google Cloud Console
- [ ] Gmail API habilitada
- [ ] Pantalla de consentimiento configurada
- [ ] Credenciales OAuth descargadas como `credentials.json`
- [ ] `credentials.json` en raíz del proyecto
- [ ] `settings_local.py` creado con configuración
- [ ] `.gitignore` actualizado
- [ ] App agregada a `INSTALLED_APPS`
- [ ] URLs configuradas
- [ ] Migraciones aplicadas
- [ ] Tipos de estudio cargados
- [ ] Primera autenticación exitosa (token.json creado)
- [ ] Médicos responsables asignados a tipos de estudio
- [ ] Prueba de procesamiento ejecutada
- [ ] Parser ajustado con email real

---

## 🎉 ¡Listo!

Si llegaste hasta aquí y todos los checks están ✅, tu sistema está **100% funcional**.

**Próximos pasos:**
1. Envía un email de prueba a `solicitudestudioscolegiales@gmail.com`
2. Ejecuta: `python manage.py procesar_pedidos_email --no-marcar-leido`
3. Revisa el pedido creado en el admin
4. Ajusta el parser si es necesario
5. Configura la automatización (Task Scheduler o Heroku)

¿Algún problema? Revisa la sección de **Troubleshooting** o los logs en el admin.
