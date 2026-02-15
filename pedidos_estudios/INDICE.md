# 📚 Índice de Documentación - Sistema de Pedidos de Estudios

Este documento es un índice central de toda la documentación del sistema. Usa esta guía para navegar rápidamente a la información que necesitas.

---

## 🚀 Inicio Rápido

Para empezar con el sistema, sigue este orden:

### 1️⃣ **Primera vez (Instalación completa)**

1. **[QUICKSTART.md](QUICKSTART.md)** ⭐
   - Guía de inicio rápido para desarrolladores
   - Pasos esenciales de configuración
   - **Tiempo estimado**: 30-45 minutos

2. **[INSTALACION_GMAIL_API.md](INSTALACION_GMAIL_API.md)** ⭐⭐⭐ *IMPRESCINDIBLE*
   - Guía completa paso a paso de instalación de Gmail API
   - Configuración de Google Cloud Console
   - OAuth 2.0, credenciales, autenticación
   - **Tiempo estimado**: 1-2 horas (primera vez)

3. **[GUIA_VISUAL_GOOGLE_CLOUD.md](GUIA_VISUAL_GOOGLE_CLOUD.md)** 🖼️
   - Capturas visuales de cada pantalla de Google Cloud Console
   - Complementa INSTALACION_GMAIL_API.md
   - Ideal si es tu primera vez con Google Cloud
   - **Uso**: Consulta visual mientras sigues la instalación

4. **[CHECKLIST_INSTALACION.md](CHECKLIST_INSTALACION.md)** ✅
   - Lista de verificación completa de instalación
   - Imprimible o seguir en pantalla
   - Monitoreo y mantenimiento
   - **Uso**: Marcar cada paso completado

### 2️⃣ **Ya instalado (Uso diario)**

5. **[README.md](README.md)** 📖
   - Documentación técnica completa
   - Arquitectura del sistema
   - Modelos, servicios, vistas
   - Personalización y extensión
   - **Uso**: Referencia técnica general

6. **[CONFIGURACION_ECODOPPLER.md](CONFIGURACION_ECODOPPLER.md)** 🩺
   - Configuración especializada para ecodoppler/ecocardiogramas
   - 12 tipos de estudios predefinidos
   - Keywords y patrones específicos
   - Casos especiales (urgencias, preparación)
   - **Uso**: Entender la especialización del sistema

7. **[EJEMPLOS_EMAILS.md](EJEMPLOS_EMAILS.md)** ✉️
   - 8 ejemplos de formatos de email
   - Casos de uso comunes
   - Patrones identificados
   - **Uso**: Probar el parser, ajustar patrones

---

## 📂 Documentación por Categoría

### 🔧 Instalación y Configuración

| Documento | Descripción | Prioridad | Tiempo |
|-----------|-------------|-----------|--------|
| [INSTALACION_GMAIL_API.md](INSTALACION_GMAIL_API.md) | Instalación paso a paso de Gmail API | 🔴 Alta | 1-2 horas |
| [GUIA_VISUAL_GOOGLE_CLOUD.md](GUIA_VISUAL_GOOGLE_CLOUD.md) | Capturas visuales de Google Cloud Console | 🟡 Media | Consulta |
| [CHECKLIST_INSTALACION.md](CHECKLIST_INSTALACION.md) | Lista de verificación de instalación | 🟡 Media | Seguimiento |
| [QUICKSTART.md](QUICKSTART.md) | Inicio rápido para desarrolladores | 🔴 Alta | 30-45 min |

### 🩺 Configuración Especializada

| Documento | Descripción | Prioridad | Cuándo usar |
|-----------|-------------|-----------|-------------|
| [CONFIGURACION_ECODOPPLER.md](CONFIGURACION_ECODOPPLER.md) | Configuración para ecodoppler/ecocardiogramas | 🟡 Media | Después de instalar |
| [EJEMPLOS_EMAILS.md](EJEMPLOS_EMAILS.md) | Ejemplos de emails para testing | 🟢 Baja | Al ajustar parser |

### � Costos y Planificación

| Documento | Descripción | Prioridad | Audiencia |
|-----------|-------------|-----------|-----------|
| [COSTOS_Y_LIMITES.md](COSTOS_Y_LIMITES.md) | Análisis de costos, límites y escalado | 🟡 Media | Admins/Managers |

### �📚 Documentación Técnica

| Documento | Descripción | Prioridad | Audiencia |
|-----------|-------------|-----------|-----------|
| [README.md](README.md) | Documentación técnica completa | 🔴 Alta | Desarrolladores |
| [COSTOS_Y_LIMITES.md](COSTOS_Y_LIMITES.md) | Análisis detallado de costos y límites | 🟡 Media | Administradores |
| Este archivo (INDICE.md) | Índice de toda la documentación | 🔴 Alta | Todos |

---

## 🎯 Flujo de Trabajo Recomendado

```
┌─────────────────────────────────────────────────────┐
│ 1. Leer QUICKSTART.md                               │
│    Entender conceptos básicos                       │
│                                                      │
│ 2. Seguir INSTALACION_GMAIL_API.md                  │
│    (con GUIA_VISUAL_GOOGLE_CLOUD.md abierta)       │
│    Completar instalación de Gmail API              │
│                                                      │
│ 3. Usar CHECKLIST_INSTALACION.md                    │
│    Verificar cada paso completado                   │
│                                                      │
│ 4. Leer CONFIGURACION_ECODOPPLER.md                 │
│    Entender especialización del sistema             │
│                                                      │
│ 5. Probar con EJEMPLOS_EMAILS.md                    │
│    Ajustar parser según sea necesario               │
│                                                      │
│ 6. Consultar README.md                              │
│    Para personalización y extensión                 │
└─────────────────────────────────────────────────────┘
```

---

## 📖 Guía de Lectura por Rol

### 👨‍💻 Desarrollador (Primera vez)

1. ⭐ [QUICKSTART.md](QUICKSTART.md)
2. ⭐⭐⭐ [INSTALACION_GMAIL_API.md](INSTALACION_GMAIL_API.md)
3. 🖼️ [GUIA_VISUAL_GOOGLE_CLOUD.md](GUIA_VISUAL_GOOGLE_CLOUD.md)
4. ✅ [CHECKLIST_INSTALACION.md](CHECKLIST_INSTALACION.md)
5. 📖 [README.md](README.md)

### 🩺 Administrador del Sistema (ya instalado)

1. 🩺 [CONFIGURACION_ECODOPPLER.md](CONFIGURACION_ECODOPPLER.md)
2. ✉️ [EJEMPLOS_EMAILS.md](EJEMPLOS_EMAILS.md)
3. 💰 [COSTOS_Y_LIMITES.md](COSTOS_Y_LIMITES.md)
4. ✅ [CHECKLIST_INSTALACION.md](CHECKLIST_INSTALACION.md) (sección monitoreo)
5. 📖 [README.md](README.md) (sección personalización)

### 🔧 DevOps / Despliegue

1. ⭐⭐⭐ [INSTALACION_GMAIL_API.md](INSTALACION_GMAIL_API.md) (Parte 8: Automatización)
2. 💰 [COSTOS_Y_LIMITES.md](COSTOS_Y_LIMITES.md) (Escenarios y hosting)
3. ✅ [CHECKLIST_INSTALACION.md](CHECKLIST_INSTALACION.md) (Opción B: Heroku)
4. 📖 [README.md](README.md) (sección Deployment)

---

## 🔍 Búsqueda Rápida de Información

### ❓ "¿Cómo hago X?"

| Necesitas | Documento | Sección |
|-----------|-----------|---------|
| Instalar Gmail API | [INSTALACION_GMAIL_API.md](INSTALACION_GMAIL_API.md) | Completo |
| Ver pantallas de Google Cloud | [GUIA_VISUAL_GOOGLE_CLOUD.md](GUIA_VISUAL_GOOGLE_CLOUD.md) | Todas |
| Configurar automatización | [INSTALACION_GMAIL_API.md](INSTALACION_GMAIL_API.md) | Parte 8 |
| Ajustar el parser | [README.md](README.md) | Personalización |
| Ver ejemplos de emails | [EJEMPLOS_EMAILS.md](EJEMPLOS_EMAILS.md) | Completo |
| Entender tipos de estudios | [CONFIGURACION_ECODOPPLER.md](CONFIGURACION_ECODOPPLER.md) | Tipos Predefinidos |
| Verificar instalación | [CHECKLIST_INSTALACION.md](CHECKLIST_INSTALACION.md) | Verificación Final |
| Arquitectura del sistema | [README.md](README.md) | Arquitectura |
| Modelos de datos | [README.md](README.md) | Modelos de Datos |
| Servicios disponibles | [README.md](README.md) | Servicios |
| Costos del sistema | [COSTOS_Y_LIMITES.md](COSTOS_Y_LIMITES.md) | Completo |
| Límites de Gmail API | [COSTOS_Y_LIMITES.md](COSTOS_Y_LIMITES.md) | Gmail API |
| Opciones de hosting | [COSTOS_Y_LIMITES.md](COSTOS_Y_LIMITES.md) | Hosting y Ejecución |

### 🐛 Troubleshooting

| Problema | Solución en |
|----------|-------------|
| `ModuleNotFoundError: google` | [INSTALACION_GMAIL_API.md](INSTALACION_GMAIL_API.md) → Troubleshooting |
| `FileNotFoundError: credentials.json` | [INSTALACION_GMAIL_API.md](INSTALACION_GMAIL_API.md) → Troubleshooting |
| `invalid_grant` | [INSTALACION_GMAIL_API.md](INSTALACION_GMAIL_API.md) → Troubleshooting |
| Parser no extrae datos | [EJEMPLOS_EMAILS.md](EJEMPLOS_EMAILS.md) → Testing Parser |
| Email no detecta tipo de estudio | [CONFIGURACION_ECODOPPLER.md](CONFIGURACION_ECODOPPLER.md) → Keywords |
| Problemas de automatización | [CHECKLIST_INSTALACION.md](CHECKLIST_INSTALACION.md) → Parte 8 |

---

## 📋 Resumen de Cada Documento

### [INSTALACION_GMAIL_API.md](INSTALACION_GMAIL_API.md)
**572 líneas** | **8 partes** | **Tiempo: 1-2 horas**

Guía completa de instalación y configuración de Gmail API.

**Contenido:**
- Parte 1: Instalación de librerías Python
- Parte 2: Configuración de Google Cloud Console
- Parte 3: Configuración en Django
- Parte 4: Migraciones de base de datos
- Parte 5: Primera autenticación con OAuth
- Parte 6: Testing del sistema
- Parte 7: Ajuste del parser con emails reales
- Parte 8: Automatización (Windows/Heroku)
- Seguridad
- Troubleshooting
- Comandos útiles
- Checklist de verificación

### [GUIA_VISUAL_GOOGLE_CLOUD.md](GUIA_VISUAL_GOOGLE_CLOUD.md)
**ASCII Art de pantallas** | **Consulta visual**

Representaciones visuales de cada pantalla de Google Cloud Console.

**Contenido:**
- Pantalla 1: Crear proyecto
- Pantalla 2: Habilitar Gmail API
- Pantalla 3: Pantalla de consentimiento OAuth
- Pantalla 4: Crear credenciales
- Pantalla 5: Autorización del usuario (flujo completo)
- Archivos generados (credentials.json, token.json)
- Estructura de archivos final
- Verificación visual

### [CHECKLIST_INSTALACION.md](CHECKLIST_INSTALACION.md)
**10 Partes** | **Formato checklist imprimible**

Lista de verificación completa con todos los pasos del proceso de instalación.

**Contenido:**
- 10 partes de instalación con checkboxes
- Opciones A y B de automatización
- Sección de seguridad
- Monitoreo diario/semanal/mensual
- Verificación final (14 items)
- Troubleshooting rápido
- Notas para completar

### [QUICKSTART.md](QUICKSTART.md)
**213 líneas** | **Tiempo: 30-45 minutos**

Guía de inicio rápido para poner el sistema en funcionamiento.

**Contenido:**
- Requisitos previos
- Instalación rápida (5 pasos)
- Configuración de Gmail API (resumen)
- Cargar tipos de estudio
- Primer test
- Ajustar parser
- Próximos pasos
- Troubleshooting

### [README.md](README.md)
**407 líneas** | **Documentación técnica completa**

Documentación técnica exhaustiva del sistema.

**Contenido:**
- Descripción del sistema
- Arquitectura (modelos y servicios)
- Instalación completa
- Uso (manual, web, programado)
- Personalización y extensión
- Testing
- Debugging
- Seguridad
- Próximas mejoras

### [CONFIGURACION_ECODOPPLER.md](CONFIGURACION_ECODOPPLER.md)
**218 líneas** | **Configuración especializada**

Guía de configuración específica para estudios de ecodoppler y ecocardiogramas.

**Contenido:**
- Enfoque del sistema (US - Ecografía)
- Configuración del parser (keywords)
- 12 tipos de estudios predefinidos
- Formatos de email esperados
- Flujo de trabajo
- Casos especiales (urgencias, preparación)
- Personalización
- Consultas útiles
- Problemas comunes

### [EJEMPLOS_EMAILS.md](EJEMPLOS_EMAILS.md)
**293 líneas** | **8 ejemplos de emails**

Colección de ejemplos de emails para testing y ajuste del parser.

**Contenido:**
- 8 formatos diferentes de emails:
  1. Formato simple
  2. Email urgente
  3. Email estructurado con órdenes
  4. Email en HTML
  5. Email estilo WhatsApp
  6. Email con múltiples estudios
  7. ETE con preparación
  8. Abreviaciones médicas
- Patrones comunes identificados
- Instrucciones de testing

### [COSTOS_Y_LIMITES.md](COSTOS_Y_LIMITES.md)
**Análisis completo** | **Proyecciones de costo**

Análisis detallado de todos los costos y límites del sistema.

**Contenido:**
- Resumen ejecutivo de costos
- Gmail API: Cuotas y límites gratuitos
- Google Cloud Platform: Costos (ninguno)
- Opciones de hosting (local $0, Heroku $7/mes)
- SendGrid: Planes y límites
- Base de datos: SQLite vs PostgreSQL
- 3 escenarios reales para Sanatorio Colegiales
- Proyección de costos por volumen
- Recomendaciones por fase
- Monitoreo y alertas
- FAQ sobre costos

---

## 🔄 Actualizaciones y Mantenimiento

### Orden de actualización si cambia algo:

1. **Código fuente** (`models.py`, `services/`, etc.)
2. **[README.md](README.md)** (documentación técnica)
3. **[CONFIGURACION_ECODOPPLER.md](CONFIGURACION_ECODOPPLER.md)** (si afecta estudios)
4. **[EJEMPLOS_EMAILS.md](EJEMPLOS_EMAILS.md)** (si cambian formatos)
5. **[INSTALACION_GMAIL_API.md](INSTALACION_GMAIL_API.md)** (si cambia proceso)
6. **[CHECKLIST_INSTALACION.md](CHECKLIST_INSTALACION.md)** (si cambian pasos)
7. **Este índice** (si se agregan/eliminan documentos)

---

## 📧 Contacto y Soporte

Para preguntas sobre el sistema:
- **Desarrollador**: Eduardo Cejas
- **Email**: ecejas@sanatoriocolegiales.com.ar
- **Organización**: Sanatorio Colegiales

---

## 📝 Convenciones de esta Documentación

- ⭐ = Esencial
- ⭐⭐⭐ = Imprescindible
- 🔴 Alta = Leer primero
- 🟡 Media = Leer después
- 🟢 Baja = Consulta según necesidad
- 🖼️ = Contenido visual
- ✅ = Checklist o verificación
- 🩺 = Específico de medicina/estudios

---

**Última actualización**: 2026-02-13

**Versión del sistema**: 1.0

**Documentos totales**: 9
