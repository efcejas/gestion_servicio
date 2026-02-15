# Sistema de Gestión de Pedidos de Estudios Médicos por Email

> � **¿Primera vez aquí?** Empieza por [INDICE.md](INDICE.md) - Índice completo de documentación
>
> 📖 **Guías de instalación**:
> - ⭐⭐⭐ [INSTALACION_GMAIL_API.md](INSTALACION_GMAIL_API.md) - Guía completa paso a paso (IMPRESCINDIBLE)
> - 🖼️ [GUIA_VISUAL_GOOGLE_CLOUD.md](GUIA_VISUAL_GOOGLE_CLOUD.md) - Capturas visuales de Google Cloud Console
> - ⭐ [QUICKSTART.md](QUICKSTART.md) - Inicio rápido
> - ✅ [CHECKLIST_INSTALACION.md](CHECKLIST_INSTALACION.md) - Lista de verificación imprimible>
> 💰 **¿Cuánto cuesta?** Ver [COSTOS_Y_LIMITES.md](COSTOS_Y_LIMITES.md) - **TL;DR**: Gmail API es 100% gratuito, hosting desde $0-7/mes
## 📋 Descripción

Sistema automatizado para procesar solicitudes de **Ecodoppler** (en todas sus modalidades) y **Ecocardiogramas** recibidas por email (Gmail), extraer información estructurada, crear pedidos en la base de datos y notificar a los médicos responsables.

**Estudios soportados inicialmente:**
- 🫀 Ecocardiograma Transtorácico
- 🫀 Ecocardiograma Transesofágico
- 🩺 Ecodoppler Vascular (arterial y venoso)
- 🩺 Ecodoppler de Miembros Superiores
- 🩺 Ecodoppler de Miembros Inferiores
- 🩺 Ecodoppler Carotídeo
- 🩺 Ecodoppler Renal

El sistema es extensible para agregar otros tipos de estudios en el futuro.

## 🏗️ Arquitectura

### Modelos de Datos

1. **PacienteEstudio**: Información del paciente y su ubicación en el sanatorio
2. **TipoEstudio**: Catálogo de tipos de estudios disponibles (US - Ecografía/Doppler)
3. **PedidoEstudio**: Pedido de estudio con estado, prioridad y tracking completo
4. **AdjuntoEmail**: Archivos adjuntos de los emails (órdenes, estudios previos)
5. **LogProcesamientoEmail**: Auditoría completa del procesamiento de cada email

### Servicios

#### 1. GmailService (`services/gmail_service.py`)
- Conexión con Gmail API usando OAuth 2.0
- Lectura de emails no leídos con filtros configurables
- Descarga de adjuntos
- Marcado de emails como leídos/procesados
- Funciones: `obtener_emails_nuevos()`, `descargar_adjunto()`, `marcar_como_leido()`

#### 2. EmailParser (`services/email_parser.py`)
- Parser flexible con patrones regex configurables
- Extracción de datos del paciente (nombre, DNI, HC, habitación, cama)
- Extracción de datos del estudio (tipo, descripción, médico solicitante)
- Detección automática de prioridad (urgente/normal)
- Validación de datos extraídos

#### 3. NotificadorPedidos (`services/notificador.py`)
- Notificaciones HTML por email a médicos responsables
- Asignación automática según tipo de estudio
- Templates de email con información completa del pedido
- Notificaciones de cambio de estado

#### 4. ProcesadorPedidos (`services/procesador.py`)
- Coordinador principal del flujo completo
- Procesamiento atómico (transacciones)
- Detección de duplicados
- Logging completo de errores
- Estadísticas de procesamiento

## 🚀 Instalación

### 1. Instalar dependencias

```bash
pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client beautifulsoup4
```

Agregar a `requirements.txt`:
```
google-auth>=2.16.0
google-auth-oauthlib>=1.0.0
google-auth-httplib2>=0.1.0
google-api-python-client>=2.80.0
beautifulsoup4>=4.11.0
```

### 2. Configurar Google Cloud Console

1. Ve a [Google Cloud Console](https://console.cloud.google.com/)
2. Crea un nuevo proyecto o selecciona uno existente
3. Habilita la **Gmail API**
4. Ve a "Credenciales" → "Crear credenciales" → "ID de cliente de OAuth"
5. Tipo de aplicación: **Aplicación de escritorio**
6. Descarga el archivo JSON de credenciales

### 3. Configurar Django settings

En `settings.py` o `settings_local.py`:

```python
# Configuración de Gmail API
GMAIL_CONFIG = {
    'CREDENTIALS_FILE': 'path/to/credentials.json',  # Ruta al archivo de credenciales
    'TOKEN_FILE': 'path/to/token.json',  # Donde se guardará el token
    'EMAIL_ADDRESS': 'solicitudestudioscolegiales@gmail.com',
}

# Query de búsqueda de Gmail (opcional, default: 'is:unread')
GMAIL_PEDIDOS_QUERY = 'from:sanatorio@example.com is:unread'

# Email por defecto para notificaciones
PEDIDOS_EMAIL_DEFAULT = 'ecejas@sanatoriocolegiales.com.ar'
```

### 4. Agregar a INSTALLED_APPS

En `settings.py`:

```python
INSTALLED_APPS = [
    # ... otras apps
    'pedidos_estudios',
]
```

### 5. Configurar URLs

En `gestion_estudios/urls.py` principal:

```python
from django.urls import path, include

urlpatterns = [
    # ... otras urls
    path('pedidos-estudios/', include('pedidos_estudios.urls')),
]
```

### 6. Crear migraciones y migrar

```bash
python manage.py makemigrations pedidos_estudios
python manage.py migrate
```

### 7. Primera autenticación con Gmail

La primera vez que uses el servicio, necesitas autenticarte:

```bash
python manage.py shell
```

```python
from pedidos_estudios.services.gmail_service import verificar_configuracion_gmail

# Esto abrirá el navegador para autorizar el acceso
exito, mensaje = verificar_configuracion_gmail()
print(mensaje)
```

Se creará el archivo `token.json` que se usará en futuras conexiones.

### 8. Cargar tipos de estudio iniciales

El sistema incluye un comando para cargar automáticamente los tipos de ecodoppler y ecocardiograma:

```bash
python manage.py cargar_tipos_estudio_inicial
```

Este comando crea/actualiza:
- 3 tipos de ecocardiograma (TT, TE, Doppler color)
- 9 tipos de ecodoppler vascular (MMII, MMSS, carotídeo, renal, etc.)

Luego puedes asignar médicos responsables desde el admin.

## 📝 Uso

### Procesamiento Manual (Management Command)

```bash
# Procesar hasta 10 emails
python manage.py procesar_pedidos_email

# Procesar hasta 20 emails
python manage.py procesar_pedidos_email --max-emails 20

# Procesar sin enviar notificaciones (solo crear pedidos)
python manage.py procesar_pedidos_email --no-notificar

# Procesar sin marcar como leído (modo prueba)
python manage.py procesar_pedidos_email --no-marcar-leido
```

### Procesamiento desde la interfaz web

1. Navega a: `/pedidos-estudios/`
2. Clic en "Procesar Emails"
3. Se procesarán automáticamente los emails pendientes

### Procesamiento programado (Cron/Celery)

#### Opción 1: Cron job

Agregar a crontab (Linux/Mac):

```bash
# Procesar emails cada 15 minutos
*/15 * * * * cd /path/to/project && source venv/bin/activate && python manage.py procesar_pedidos_email >> /var/log/pedidos_email.log 2>&1
```

#### Opción 2: Celery Task (recomendado)

Crear `pedidos_estudios/tasks.py`:

```python
from celery import shared_task
from .services.procesador import procesar_emails_ahora

@shared_task
def procesar_pedidos_periodico():
    """Task de Celery para procesar emails periódicamente."""
    return procesar_emails_ahora(max_emails=20)
```

Configurar en Celery Beat:

```python
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    'procesar-pedidos-cada-15min': {
        'task': 'pedidos_estudios.tasks.procesar_pedidos_periodico',
        'schedule': crontab(minute='*/15'),
    },
}
```

## 🔧 Personalización

### Ajustar patrones de extracción

Cuando recibas el primer email real, ajusta los patrones en `services/email_parser.py`:

```python
PATRONES = {
    'nombre': [
        r'paciente:\s*([A-ZÁÉÍÓÚÑa-záéíóúñ\s]+)',
        r'nombre:\s*([A-ZÁÉÍÓÚÑa-záéíóúñ\s]+)',
        # Agregar más patrones según el formato real
    ],
    # ... otros patrones
}
```

### Configurar tipos de estudio

Desde el admin Django (`/admin/`):

1. Ve a "Tipos de Estudios"
2. Crea los tipos de ecodoppler y ecocardio:
   - **Ecocardiograma Transtorácico** (modalidad: US, tiempo: 45 min)
   - **Ecocardiograma Transesofágico** (modalidad: US, tiempo: 60 min, requiere preparación)
   - **Ecodoppler Carotídeo** (modalidad: US, tiempo: 30 min)
   - **Ecodoppler Miembros Inferiores** (modalidad: US, tiempo: 40 min)
   - **Ecodoppler Miembros Superiores** (modalidad: US, tiempo: 30 min)
   - **Ecodoppler Arterial** (modalidad: US, tiempo: 30 min)
   - **Ecodoppler Venoso** (modalidad: US, tiempo: 30 min)
   - **Ecodoppler Renal** (modalidad: US, tiempo: 30 min)
3. Asigna médico responsable y email de notificación a cada tipo
4. Configura si requiere preparación especial (ej: ayuno para TEE)

### Personalizar notificaciones

Edita `services/notificador.py` función `_generar_contenido_html()` o crea templates Django para emails más sofisticados.

## 📊 Panel Administrativo

Accede a `/admin/` y tendrás:

- **Pedidos de Estudios**: Lista completa con filtros por estado, prioridad, fecha
- **Pacientes**: Gestión de pacientes
- **Tipos de Estudio**: Catálogo de estudios y responsables
- **Logs de Procesamiento**: Auditoría completa de cada email procesado

Badges de color indican:
- 🔴 Urgente
- 🟠 Alta prioridad
- 🟢 Normal
- ⚪ Baja prioridad

## 🐛 Debugging

### Ver logs de procesamiento

```bash
# En desarrollo
python manage.py shell
```

```python
from pedidos_estudios.models import LogProcesamientoEmail

# Ver últimos logs
logs = LogProcesamientoEmail.objects.order_by('-fecha_procesamiento')[:10]
for log in logs:
    print(f"{log.email_asunto} - {log.resultado} - {log.mensaje}")
    if log.errores:
        print(f"  Errores: {log.errores}")
```

### Verificar configuración Gmail

```bash
python manage.py shell
```

```python
from pedidos_estudios.services.gmail_service import verificar_configuracion_gmail

exito, mensaje = verificar_configuracion_gmail()
print(f"Estado: {'✓' if exito else '✗'}")
print(f"Mensaje: {mensaje}")
```

### Probar parser con texto de ejemplo

```python
from pedidos_estudios.services.email_parser import extraer_informacion_basica

texto_prueba = """
Paciente: Juan Pérez
DNI: 12345678
Habitación: 302A
Cama: 1
Estudio solicitado: Radiografía de tórax
Médico: Dr. García
URGENTE
"""

datos = extraer_informacion_basica(texto_prueba)
print(datos)
```

## 🔐 Seguridad

- ✅ El archivo `credentials.json` y `token.json` **NO deben** commitearse a Git
- ✅ Agregar a `.gitignore`:
  ```
  credentials.json
  token.json
  ```
- ✅ Usar variables de entorno para datos sensibles en producción
- ✅ Limitar scopes de OAuth a solo lo necesario (readonly + modify)

## 📈 Próximas Mejoras

- [ ] Integración con IA para mejorar extracción de datos (GPT-4, Claude)
- [ ] Parser visual para emails HTML complejos
- [ ] Integración con sistema de turnos
- [ ] Webhooks de Gmail para notificación en tiempo real (Gmail Push API)
- [ ] Dashboard analytics con gráficos de estadísticas
- [ ] Exportación de reportes Excel/PDF

## 🛠️ Testing

### Crear datos de prueba

```bash
python manage.py shell
```

```python
from pedidos_estudios.models import TipoEstudio, PacienteEstudio, PedidoEstudio

# Crear tipos de estudio
rx = TipoEstudio.objects.create(
    nombre='Radiografía de Tórax',
    modalidad='RX',
    activo=True
)

tc = TipoEstudio.objects.create(
    nombre='Tomografía de Abdomen',
    modalidad='TC',
    activo=True
)

# Crear paciente de prueba
paciente = PacienteEstudio.objects.create(
    nombre_completo='Juan Pérez',
    dni='12345678',
    historia_clinica='HC001',
    habitacion='302A',
    cama='1'
)

# Crear pedido de prueba
pedido = PedidoEstudio.objects.create(
    paciente=paciente,
    tipo_estudio=rx,
    descripcion_estudio='Radiografía de tórax frente y perfil',
    medico_solicitante='Dr. García',
    prioridad='URGENTE'
)
```

## 📞 Soporte

Para problemas o preguntas:
1. Revisar logs: `LogProcesamientoEmail` en admin
2. Verificar configuración Gmail
3. Revisar permisos OAuth
4. Consultar documentación de Gmail API: https://developers.google.com/gmail/api

## 📄 Licencia

Este sistema es parte del proyecto `gestion_servicio` del Sanatorio Colegiales.
