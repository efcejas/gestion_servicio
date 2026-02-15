# Guía Visual: Google Cloud Console

Esta guía complementa [INSTALACION_GMAIL_API.md](INSTALACION_GMAIL_API.md) con descripciones visuales de cada pantalla.

---

## 🖼️ Pantalla 1: Crear Proyecto

**URL**: https://console.cloud.google.com/

```
┌─────────────────────────────────────────────────────┐
│ Google Cloud Platform                    [👤 User ▼]│
├─────────────────────────────────────────────────────┤
│                                                      │
│  ┌──────────────────────────────────────────┐      │
│  │ 📁 Seleccionar un proyecto          [▼] │      │
│  └──────────────────────────────────────────┘      │
│                                                      │
│  Al hacer clic se abre modal:                       │
│                                                      │
│  ┌──────────────────────────────────────────┐      │
│  │ Seleccionar proyecto              [✕]   │      │
│  ├──────────────────────────────────────────┤      │
│  │ 🔍 Buscar proyectos                     │      │
│  │                                          │      │
│  │ Mis proyectos               [NUEVO +]   │      │
│  │  • My First Project                     │      │
│  │  • Project ABC                          │      │
│  └──────────────────────────────────────────┘      │
│                                                      │
│  Hacer clic en: [NUEVO +] o [+ PROYECTO NUEVO]     │
└─────────────────────────────────────────────────────┘
```

### Formulario Nuevo Proyecto:

```
┌─────────────────────────────────────────────────────┐
│ Proyecto nuevo                              [✕]    │
├─────────────────────────────────────────────────────┤
│                                                      │
│  Nombre del proyecto *                              │
│  ┌────────────────────────────────────────────┐    │
│  │ Sanatorio Colegiales - Pedidos  │    │
│  └────────────────────────────────────────────┘    │
│                                                      │
│  ID del proyecto                                    │
│  ┌────────────────────────────────────────────┐    │
│  │ pedidos-estudios-123456  [✎ Editar]       │    │
│  └────────────────────────────────────────────┘    │
│  Tu ID de proyecto será: pedidos-estudios-123456   │
│                                                      │
│  Ubicación                                          │
│  ┌────────────────────────────────────────────┐    │
│  │ Sin organización                      [▼] │    │
│  └────────────────────────────────────────────┘    │
│                                                      │
│            [CANCELAR]  [CREAR]                      │
└─────────────────────────────────────────────────────┘
```

---

## 🖼️ Pantalla 2: Habilitar Gmail API

**Navegación**: Menú ☰ > APIs y servicios > Biblioteca

```
┌─────────────────────────────────────────────────────┐
│ ☰ APIs y servicios > Biblioteca             [🔍]   │
├─────────────────────────────────────────────────────┤
│                                                      │
│  🔍 Buscar APIs y servicios                         │
│  ┌────────────────────────────────────────────┐    │
│  │ gmail                                      │    │
│  └────────────────────────────────────────────┘    │
│                                                      │
│  ┌──────────────────────────────────────────────┐  │
│  │  📧 Gmail API                                │  │
│  │  Proporciona acceso a todos los datos de    │  │
│  │  Gmail                                       │  │
│  │                             Google           │  │
│  └──────────────────────────────────────────────┘  │
│                                                      │
│  ← Hacer clic aquí                                  │
└─────────────────────────────────────────────────────┘
```

### Página de Gmail API:

```
┌─────────────────────────────────────────────────────┐
│ Gmail API                                           │
├─────────────────────────────────────────────────────┤
│                                                      │
│  📧 Gmail API                                       │
│                                                      │
│  The Gmail API lets you view and manage Gmail      │
│  mailbox data like threads, messages, and labels.  │
│                                                      │
│              [HABILITAR]  [PRUÉBALA]               │
│                 ↑                                   │
│           Hacer clic aquí                           │
│                                                      │
│  Descripción general                                │
│  Documentación                                      │
│  Soporte                                            │
│  Términos                                           │
│                                                      │
└─────────────────────────────────────────────────────┘
```

**Después de habilitar**:

```
┌─────────────────────────────────────────────────────┐
│ ✓ API habilitada                                    │
│                                                      │
│  Gmail API está habilitada para este proyecto      │
│                                                      │
│  [Ver métricas]  [Administrar]  [Inhabilitar]      │
└─────────────────────────────────────────────────────┘
```

---

## 🖼️ Pantalla 3: Pantalla de Consentimiento OAuth

**Navegación**: Menú ☰ > APIs y servicios > Pantalla de consentimiento de OAuth

```
┌─────────────────────────────────────────────────────┐
│ Pantalla de consentimiento de OAuth                 │
├─────────────────────────────────────────────────────┤
│                                                      │
│  Tipo de usuario                                    │
│                                                      │
│  ┌────────────────────────┐  ┌────────────────────┐│
│  │ ⭕ Interno              │  │ ⭕ Externo         ││
│  │                         │  │                    ││
│  │ Solo usuarios de tu     │  │ Cualquier usuario  ││
│  │ organización Google     │  │ con cuenta Google  ││
│  │ Workspace               │  │                    ││
│  └────────────────────────┘  └────────────────────┘│
│                                  ↑                   │
│                           Seleccionar este          │
│                                                      │
│              [CANCELAR]  [CREAR]                    │
└─────────────────────────────────────────────────────┘
```

### Formulario - Paso 1: Información de la app

```
┌─────────────────────────────────────────────────────┐
│ Editar registro de apps                             │
├─────────────────────────────────────────────────────┤
│                                                      │
│  ● 1. Información de la app                         │
│  ○ 2. Alcances                                      │
│  ○ 3. Usuarios de prueba                            │
│  ○ 4. Resumen                                       │
│                                                      │
│  Información de la aplicación                       │
│                                                      │
│  Nombre de la aplicación *                          │
│  ┌────────────────────────────────────────────┐    │
│  │ Sistema de Pedidos - Sanatorio Colegiales │    │
│  └────────────────────────────────────────────┘    │
│                                                      │
│  Correo electrónico de asistencia al usuario *     │
│  ┌────────────────────────────────────────────┐    │
│  │ ecejas@sanatoriocolegiales.com.ar    [▼]  │    │
│  └────────────────────────────────────────────┘    │
│                                                      │
│  Logo de la aplicación (opcional)                   │
│  [📁 Seleccionar archivo]                           │
│                                                      │
│  Dominios de aplicaciones                           │
│  Dominios autorizados (opcional)                    │
│  ┌────────────────────────────────────────────┐    │
│  │ (dejar vacío)                              │    │
│  └────────────────────────────────────────────┘    │
│                                                      │
│  Información de contacto del desarrollador          │
│  Direcciones de correo electrónico                  │
│  ┌────────────────────────────────────────────┐    │
│  │ ecejas@sanatoriocolegiales.com.ar          │    │
│  └────────────────────────────────────────────┘    │
│                                                      │
│    [CANCELAR]  [GUARDAR Y CONTINUAR]               │
└─────────────────────────────────────────────────────┘
```

### Formulario - Paso 2: Alcances

```
┌─────────────────────────────────────────────────────┐
│ Editar registro de apps                             │
├─────────────────────────────────────────────────────┤
│                                                      │
│  ○ 1. Información de la app                         │
│  ● 2. Alcances                                      │
│  ○ 3. Usuarios de prueba                            │
│  ○ 4. Resumen                                       │
│                                                      │
│  Alcances para las APIs de Google                   │
│                                                      │
│  [AGREGAR O QUITAR ALCANCES]                        │
│   ↑                                                  │
│  Hacer clic aquí                                    │
│                                                      │
│  Tu alcance no sensible                             │
│  No se agregó ningún alcance                        │
└─────────────────────────────────────────────────────┘
```

**Modal: Agregar alcances**

```
┌─────────────────────────────────────────────────────┐
│ Actualizar alcances de APIs seleccionadas     [✕]  │
├─────────────────────────────────────────────────────┤
│                                                      │
│  🔍 Filtrar                                         │
│  ┌────────────────────────────────────────────┐    │
│  │ gmail                                      │    │
│  └────────────────────────────────────────────┘    │
│                                                      │
│  Gmail API                                          │
│                                                      │
│  ☑ .../auth/gmail.readonly                         │
│    Ver tus mensajes de correo electrónico y la     │
│    configuración                                    │
│                                                      │
│  ☑ .../auth/gmail.modify                           │
│    Ver, modificar, crear y eliminar solo los       │
│    metadatos específicos de Gmail                  │
│                                                      │
│  ☐ .../auth/gmail.compose                          │
│  ☐ .../auth/gmail.send                             │
│  ☐ .../auth/gmail.insert                           │
│                                                      │
│              [CANCELAR]  [ACTUALIZAR]              │
└─────────────────────────────────────────────────────┘
```

### Formulario - Paso 3: Usuarios de prueba

```
┌─────────────────────────────────────────────────────┐
│ Editar registro de apps                             │
├─────────────────────────────────────────────────────┤
│                                                      │
│  ○ 1. Información de la app                         │
│  ○ 2. Alcances                                      │
│  ● 3. Usuarios de prueba                            │
│  ○ 4. Resumen                                       │
│                                                      │
│  Usuarios de prueba                                 │
│                                                      │
│  [+ AGREGAR USUARIOS]                               │
│   ↑                                                  │
│  Hacer clic                                         │
│                                                      │
│  ┌────────────────────────────────────────────┐    │
│  │ Correo electrónico          Tipo            │    │
│  ├────────────────────────────────────────────┤    │
│  │ solicitudestudioscolegiales Usuario        │    │
│  │ @gmail.com                                  │    │
│  └────────────────────────────────────────────┘    │
│                                                      │
│    [CANCELAR]  [GUARDAR Y CONTINUAR]               │
└─────────────────────────────────────────────────────┘
```

---

## 🖼️ Pantalla 4: Crear Credenciales

**Navegación**: Menú ☰ > APIs y servicios > Credenciales

```
┌─────────────────────────────────────────────────────┐
│ Credenciales                                        │
├─────────────────────────────────────────────────────┤
│                                                      │
│  [+ CREAR CREDENCIALES ▼]                          │
│   ↓                                                  │
│  ┌──────────────────────────────────────────┐      │
│  │ ID de cliente de OAuth                   │ ←    │
│  │ Clave de API                             │      │
│  │ Cuenta de servicio                       │      │
│  └──────────────────────────────────────────┘      │
│                                              Seleccionar│
│  IDs de cliente de OAuth 2.0                       │
│  (vacío)                                            │
│                                                      │
│  Claves de API                                      │
│  (vacío)                                            │
└─────────────────────────────────────────────────────┘
```

### Formulario: Crear ID de cliente de OAuth

```
┌─────────────────────────────────────────────────────┐
│ Crear ID de cliente de OAuth                       │
├─────────────────────────────────────────────────────┤
│                                                      │
│  Tipo de aplicación                                 │
│  ┌────────────────────────────────────────────┐    │
│  │ Aplicación de escritorio            [▼]   │    │
│  └────────────────────────────────────────────┘    │
│   ↑                                                  │
│  Opciones:                                          │
│  • Aplicación web                                   │
│  • Aplicación de escritorio    ← Seleccionar      │
│  • Android                                          │
│  • iOS                                              │
│  • Chrome                                           │
│                                                      │
│  Nombre                                             │
│  ┌────────────────────────────────────────────┐    │
│  │ Cliente Desktop - Pedidos Estudios         │    │
│  └────────────────────────────────────────────┘    │
│                                                      │
│              [CANCELAR]  [CREAR]                    │
└─────────────────────────────────────────────────────┘
```

### Modal: Cliente de OAuth creado

```
┌─────────────────────────────────────────────────────┐
│ Cliente de OAuth creado                        [✕] │
├─────────────────────────────────────────────────────┤
│                                                      │
│  ✓ Se creó el cliente de OAuth                     │
│                                                      │
│  Tu ID de cliente                                   │
│  ┌────────────────────────────────────────────┐    │
│  │ 123456789-abc.apps.googleusercontent.com  │ 📋 │
│  └────────────────────────────────────────────┘    │
│                                                      │
│  Tu clave privada de cliente                        │
│  ┌────────────────────────────────────────────┐    │
│  │ GOCSPX-abc123def456                       │ 📋 │
│  └────────────────────────────────────────────┘    │
│                                                      │
│  [DESCARGAR JSON]  [Aceptar]                       │
│   ↑                                                  │
│  Hacer clic aquí para descargar                     │
└─────────────────────────────────────────────────────┘
```

---

## 🖼️ Pantalla 5: Autorización del Usuario

**Se abre automáticamente en el navegador**

### Paso 1: Seleccionar cuenta

```
┌─────────────────────────────────────────────────────┐
│                🔷 Google                             │
├─────────────────────────────────────────────────────┤
│                                                      │
│  Elige una cuenta                                   │
│                                                      │
│  para continuar con Sistema de Pedidos -            │
│  Sanatorio Colegiales                               │
│                                                      │
│  ┌────────────────────────────────────────────┐    │
│  │ 👤 solicitudestudioscolegiales@gmail.com   │    │
│  └────────────────────────────────────────────┘    │
│   ↑                                                  │
│  Hacer clic en tu cuenta                            │
│                                                      │
│  [Usar otra cuenta]                                 │
│                                                      │
└─────────────────────────────────────────────────────┘
```

### Paso 2: Advertencia de seguridad

```
┌─────────────────────────────────────────────────────┐
│                🔷 Google                             │
├─────────────────────────────────────────────────────┤
│                                                      │
│  ⚠️ Google no ha verificado esta aplicación        │
│                                                      │
│  Esta aplicación no ha sido verificada por Google.  │
│  Continúa solo si conoces y confías en el          │
│  desarrollador (Sistema de Pedidos).                │
│                                                      │
│  [Avanzado ▼]                                       │
│   ↑                                                  │
│  Hacer clic aquí                                    │
│                                                      │
│  [Volver a la seguridad]                            │
│                                                      │
└─────────────────────────────────────────────────────┘
```

**Después de clic en "Avanzado":**

```
┌─────────────────────────────────────────────────────┐
│  ⚠️ Google no ha verificado esta aplicación        │
│                                                      │
│  [Avanzado ▲]                                       │
│                                                      │
│  Si continúas, la aplicación podrá acceder a los    │
│  datos solicitados. Obtén más información sobre     │
│  las aplicaciones no verificadas.                   │
│                                                      │
│  [Ir a Sistema de Pedidos (no seguro)]             │
│   ↑                                                  │
│  Hacer clic aquí                                    │
│                                                      │
│  [Volver a la seguridad]                            │
└─────────────────────────────────────────────────────┘
```

### Paso 3: Permisos

```
┌─────────────────────────────────────────────────────┐
│                🔷 Google                             │
├─────────────────────────────────────────────────────┤
│                                                      │
│  Sistema de Pedidos - Sanatorio Colegiales         │
│  quiere acceder a tu Cuenta de Google               │
│                                                      │
│  📧 solicitudestudioscolegiales@gmail.com           │
│                                                      │
│  Esto permitirá a la aplicación:                    │
│                                                      │
│  ✉️ Ver tus mensajes de correo electrónico         │
│     y la configuración                              │
│                                                      │
│  🔖 Ver, modificar, crear y eliminar solo los      │
│     metadatos específicos de Gmail                  │
│                                                      │
│  ℹ️ Asegúrate de que confías en Sistema de         │
│     Pedidos - Sanatorio Colegiales                  │
│                                                      │
│  Es posible que estés compartiendo información      │
│  sensible con este sitio o esta app.                │
│                                                      │
│        [Cancelar]    [Permitir]                     │
│                        ↑                             │
│                   Hacer clic                        │
└─────────────────────────────────────────────────────┘
```

### Paso 4: Confirmación

```
┌─────────────────────────────────────────────────────┐
│  ✓ The authentication flow has completed           │
│                                                      │
│  You may close this window.                         │
│                                                      │
│  Puedes cerrar esta ventana y volver a tu          │
│  terminal/aplicación.                               │
└─────────────────────────────────────────────────────┘
```

---

## 🖼️ Archivos Generados

### credentials.json (ejemplo simplificado)

```json
{
  "installed": {
    "client_id": "123456789-abc.apps.googleusercontent.com",
    "project_id": "pedidos-estudios-123456",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "client_secret": "GOCSPX-abc123def456",
    "redirect_uris": ["http://localhost"]
  }
}
```

### token.json (generado después de autorizar)

```json
{
  "token": "ya29.a0AfH6SMB...",
  "refresh_token": "1//0gDp...",
  "token_uri": "https://oauth2.googleapis.com/token",
  "client_id": "123456789-abc.apps.googleusercontent.com",
  "client_secret": "GOCSPX-abc123def456",
  "scopes": [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify"
  ],
  "expiry": "2026-02-13T12:00:00Z"
}
```

---

## 📁 Estructura de Archivos Final

```
C:\Dev\GitHub\gestion_servicio\
│
├── credentials.json          ← Descargado de Google Cloud
├── token.json               ← Generado al autorizar (primera vez)
├── .gitignore              ← Debe incluir credentials.json y token.json
│
├── gestion_estudios/
│   ├── settings.py
│   ├── settings_local.py    ← Configuración Gmail API
│   └── urls.py              ← URLs principales
│
├── pedidos_estudios/
│   ├── models.py
│   ├── admin.py
│   ├── views.py
│   ├── urls.py
│   ├── forms.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── gmail_service.py      ← Conexión Gmail
│   │   ├── email_parser.py       ← Parser de emails
│   │   ├── notificador.py        ← Notificaciones
│   │   └── procesador.py         ← Coordinador
│   ├── management/
│   │   └── commands/
│   │       ├── procesar_pedidos_email.py
│   │       └── cargar_tipos_estudio_inicial.py
│   └── INSTALACION_GMAIL_API.md
│
└── manage.py
```

---

## 🎯 Verificación Visual Final

Cuando todo esté bien configurado, en tu terminal verás:

```
C:\Dev\GitHub\gestion_servicio> python manage.py shell

>>> from pedidos_estudios.services.gmail_service import verificar_configuracion_gmail
>>> exito, mensaje = verificar_configuracion_gmail()

INFO:pedidos_estudios.services.gmail_service:Servicio de Gmail autenticado correctamente

>>> print(f"Éxito: {exito}")
Éxito: True

>>> print(f"Mensaje: {mensaje}")
Mensaje: Conectado a solicitudestudioscolegiales@gmail.com - 1234 mensajes
```

Y en el admin:

```
┌─────────────────────────────────────────────────────┐
│ 🏥 Administración de Django                         │
├─────────────────────────────────────────────────────┤
│                                                      │
│  PEDIDOS_ESTUDIOS                                   │
│                                                      │
│  Adjuntos de Emails          [+ Agregar]           │
│  Logs de Procesamiento       [+ Agregar]           │
│  Pacientes de Estudios       [+ Agregar]           │
│  Pedidos de Estudios         [+ Agregar]           │
│  Tipos de Estudios (12)      [+ Agregar]           │
│    ↑                                                 │
│   Deberías ver 12 tipos cargados                    │
│                                                      │
└─────────────────────────────────────────────────────┘
```

---

**¿Alguna pantalla te confunde?** Consulta esta guía visual mientras sigues los pasos de [INSTALACION_GMAIL_API.md](INSTALACION_GMAIL_API.md).
