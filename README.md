# 🏥 Sistema de Gestión - Servicio de Diagnóstico por Imágenes

Sistema integral de gestión para servicios de diagnóstico por imágenes, desarrollado con Django 5.1.4 y Tailwind CSS.

## 🚀 Características Principales

### 👥 Gestión de Usuarios y Perfiles
- Sistema de roles: médicos staff, residentes, jefes, instructores, técnicos, administrativos
- Cálculo automático de año de residencia (R1-R5)
- Perfiles personalizados con datos profesionales
- Control de acceso basado en roles

### 📋 Protocolos Radiológicos
- Base de datos completa de protocolos por modalidad
- Selección inteligente de protocolos según contexto clínico
- Búsqueda por región anatómica, modalidad y tags
- Fases de adquisición con parámetros técnicos

### 📅 Gestión de Guardias
- Calendario de guardias médicas
- Asignación y notificaciones automáticas
- Control de cobertura y disponibilidad

### 📊 Eventos y Novedades
- Sistema de notificaciones del servicio
- Comunicación interna entre equipos
- Registro de eventos importantes

### 📝 Dictado de Informes
- Integración con OpenAI para asistencia en dictado
- Plantillas de informes por estudio
- Sistema de aprendizaje de preferencias

### 💰 Liquidación de Estudios
- Registro de estudios por profesional
- Control de procedimientos de intervencionismo
- Reportes estadísticos

### 🔧 Gestión de Equipos
- Inventario de equipamiento médico
- Control de mantenimiento
- Estado operativo

## 🛠️ Stack Tecnológico

- **Backend:** Django 5.1.4, Python 3.13
- **Frontend:** Tailwind CSS, Flowbite
- **Base de datos:** PostgreSQL (producción), SQLite (desarrollo)
- **Deployment:** Heroku
- **Email:** SendGrid (producción), Gmail SMTP (desarrollo)
- **IA:** OpenAI API para asistencia en dictado

## 📦 Instalación

### Requisitos
- Python 3.13+
- Node.js 18+ (para Tailwind)
- PostgreSQL (producción)

### Setup Local

1. **Clonar repositorio**
```bash
git clone https://github.com/efcejas/gestion_servicio.git
cd gestion_servicio
```

2. **Crear entorno virtual**
```bash
python -m venv gestion_env
# Windows
gestion_env\Scripts\activate
# Linux/Mac
source gestion_env/bin/activate
```

3. **Instalar dependencias**
```bash
pip install -r requirements.txt
npm install
cd theme/static_src
npm install
cd ../..
```

4. **Configurar variables de entorno**
Crear archivo `.env` basado en `.env.test`:
```env
DEBUG=True
SECRET_KEY=tu-secret-key-aqui
DATABASE_URL=postgres://...
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
OPENAI_API_KEY=tu-api-key
```

5. **Ejecutar migraciones**
```bash
python manage.py migrate
```

6. **Crear superusuario**
```bash
python manage.py createsuperuser
```

7. **Iniciar servidor de desarrollo**
```bash
# Terminal 1 - Django
python manage.py runserver

# Terminal 2 - Tailwind (watch mode)
npm run tailwind:dev
```

### Frontend (Tailwind) - comando rapido

```bash
# Compilar Tailwind en watch desde la raiz
npm run tailwind:dev

# Build minificado de Tailwind
npm run tailwind:build
```

## 📁 Estructura del Proyecto

```
gestion_servicio/
├── accounts/              # Sistema de autenticación y perfiles
├── agenda/                # Agenda y notas personales
├── control_guardias/      # Gestión de guardias médicas
├── dictado_informes/      # Sistema de dictado con IA
├── equipos/              # Gestión de equipamiento
├── gestion_estudios/     # Configuración principal del proyecto
├── gestion_eventos/      # Sistema de eventos y novedades
├── liquidacion/          # Liquidación de estudios
├── protocolos/           # Protocolos radiológicos
├── docs/                 # 📚 Documentación del sistema
├── scripts/              # 🛠️ Scripts de mantenimiento y carga
├── static/               # Archivos estáticos
├── templates/            # Templates HTML
└── media/                # Archivos de usuario
```

## 📚 Documentación

La documentación completa está organizada en:

- **[docs/README.md](docs/README.md)** - Índice de documentación técnica
- **[scripts/README.md](scripts/README.md)** - Guía de scripts y herramientas
- **[docs/archive/](docs/archive/)** - Documentación histórica

### Documentos Importantes

- **[Configuración de APIs de IA](docs/arquitectura/CONFIGURACION_APIS_IA.md)** - Setup OpenAI Whisper y GPT para dictado
- [Sistema de Perfiles](docs/producto/SISTEMA_PERFILES_README.md) - Gestión de usuarios y roles
- [Sistema de Protocolos](docs/producto/README_PROTOCOLOS.md) - Protocolos radiológicos
- [Despliegue en Heroku](docs/operativa/README_colegiales_deploy.md) - Guía de deployment
- [Seguridad](docs/SECURITY_IMPROVEMENTS.md) - Mejoras de seguridad
- [Testing](docs/operativa/TESTS_README.md) - Suite de tests

## 🧪 Testing

```bash
# Ejecutar todos los tests
python manage.py test

# Tests específicos
python manage.py test accounts
python manage.py test protocolos

# Con cobertura
coverage run --source='.' manage.py test
coverage report
```

## 🚀 Deployment

El sistema está configurado para despliegue en Heroku:

```bash
# Deploy a Heroku
git push colegiales feature/colegiales:main

# Ver logs
heroku logs --tail --app gestion-colegiales

# Ejecutar migraciones en producción
heroku run python manage.py migrate --app gestion-colegiales
```

Ver guía completa en [docs/operativa/README_colegiales_deploy.md](docs/operativa/README_colegiales_deploy.md)

## 🔐 Seguridad

- Autenticación de usuario obligatoria
- Control de acceso basado en roles
- HTTPS en producción
- Variables de entorno para secretos
- App Passwords para email (no passwords de usuario)
- Validación de permisos en todas las vistas

## 🤝 Contribuir

1. Crear branch desde `feature/colegiales`
2. Hacer cambios y commit
3. Push a repositorio
4. Crear Pull Request

## 📝 Licencia

Uso interno - Sanatorio Colegiales

## 👨‍💻 Autor

Dr. Eduardo Cejas
- Email: ecejas@sanatoriocolegiales.com.ar
- Teléfono: +54 11 6376 1360

---

*Sistema en producción: https://gestion-colegiales.herokuapp.com/*
