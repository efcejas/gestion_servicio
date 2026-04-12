# 📚 Documentación del Sistema de Protocolos Radiológicos

> **Propósito**: Índice de toda la documentación del sistema de protocolos con acceso rápido a templates y guías.

---

## 🗂️ Estructura de Documentación

### 📖 Documentos Principales

| Documento | Propósito | Cuándo Usar |
|-----------|-----------|-------------|
| [archive/TEMPLATES_MANTENIMIENTO_PROTOCOLOS.md](archive/TEMPLATES_MANTENIMIENTO_PROTOCOLOS.md) | **Templates copiables** | ⭐ Cuando necesites agregar/modificar escenarios |
| [archive/MEJORAS_ELEGIR_PROTOCOLO_v3.md](archive/MEJORAS_ELEGIR_PROTOCOLO_v3.md) | Documentación completa v3 | Entender arquitectura y cambios implementados |
| [archive/REPORTE_AUDITORIA_PROTOCOLOS.md](archive/REPORTE_AUDITORIA_PROTOCOLOS.md) | Estado del sistema completo | Auditoría y diagnóstico de problemas |
| Este archivo (README) | Índice de navegación | Punto de entrada a la documentación |

---

## ⚡ Acceso Rápido por Tarea

### 🆕 Quiero agregar un nuevo escenario clínico

1. **Ir a**: [archive/TEMPLATES_MANTENIMIENTO_PROTOCOLOS.md](archive/TEMPLATES_MANTENIMIENTO_PROTOCOLOS.md)
2. **Sección**: "TEMPLATE: Agregar Nuevo Escenario"
3. **Copiar**: Template base o ejemplo completo
4. **Editar**: `protocolos/views.py` → lista `escenarios`
5. **Verificar**: 
   ```bash
   python manage.py check
   python manage.py runserver
   ```

### ✏️ Quiero modificar una recomendación existente

1. **Ir a**: [archive/TEMPLATES_MANTENIMIENTO_PROTOCOLOS.md](archive/TEMPLATES_MANTENIMIENTO_PROTOCOLOS.md)
2. **Sección**: "TEMPLATE: Modificar Solo Recomendación"
3. **Buscar en**: `protocolos/views.py` → `'key': 'nombre-escenario'`
4. **Reemplazar**: Solo bloque `'recommendation': {...}`

### 🎨 Quiero agregar un nuevo tag (ej: "Pediátrico")

1. **Ir a**: [archive/TEMPLATES_MANTENIMIENTO_PROTOCOLOS.md](archive/TEMPLATES_MANTENIMIENTO_PROTOCOLOS.md)
2. **Sección**: "TEMPLATE: Agregar Nuevo Tag"
3. **Editar**: 
   - `templates/protocolos/elegir_protocolo.html` (botón + JavaScript)
   - `protocolos/views.py` (usar en escenarios)

### 🔍 Quiero ver qué protocolos existen en la DB

1. **Ir a**: [archive/TEMPLATES_MANTENIMIENTO_PROTOCOLOS.md](archive/TEMPLATES_MANTENIMIENTO_PROTOCOLOS.md)
2. **Sección**: "COMANDOS ÚTILES"
3. **Copiar y ejecutar**:
   ```bash
   python manage.py shell
   ```
   ```python
   from protocolos.models import Protocolo
   for p in Protocolo.objects.filter(es_activo=True):
       print(f"'{p.nombre}' - {p.fases.count()} fases")
   ```

### 🏗️ Quiero crear un protocolo nuevo en la DB

1. **Ir a**: [archive/REPORTE_AUDITORIA_PROTOCOLOS.md](archive/REPORTE_AUDITORIA_PROTOCOLOS.md)
2. **Sección**: "ANEXO: Comandos de Gestión Django"
3. **Subsección**: "Crear nuevo protocolo"
4. **Copiar template** y modificar valores

### 🐛 Tengo un problema / Error

1. **Ir a**: [archive/TEMPLATES_MANTENIMIENTO_PROTOCOLOS.md](archive/TEMPLATES_MANTENIMIENTO_PROTOCOLOS.md)
2. **Sección**: "Solución Rápida de Problemas"
3. **Buscar**: Síntoma (ej: "Botón gris", "Escenario no aparece")

### 📊 Quiero entender la arquitectura completa

1. **Ir a**: [archive/MEJORAS_ELEGIR_PROTOCOLO_v3.md](archive/MEJORAS_ELEGIR_PROTOCOLO_v3.md)
2. **Leer secciones**:
   - "Cambios Técnicos"
   - "Distribución de protocolos por nivel"
   - "Beneficios Educativos"

### 🔍 Quiero auditar el estado del sistema

1. **Ir a**: [archive/REPORTE_AUDITORIA_PROTOCOLOS.md](archive/REPORTE_AUDITORIA_PROTOCOLOS.md)
2. **Revisar**:
   - Resumen ejecutivo
   - Problemas detectados/corregidos
   - Estado actual del sistema

---

## 📋 Cheat Sheet de Archivos

### Archivos a Editar (Desarrollo)

| Archivo | Qué Contiene | Cuándo Editar |
|---------|--------------|---------------|
| `protocolos/views.py` | Función `elegir_protocolo` con lista de escenarios | Agregar/modificar escenarios |
| `templates/protocolos/elegir_protocolo.html` | UI de la página de decisión + JS | Cambiar filtros, colores, layout |
| `protocolos/models.py` | Modelos: Protocolo, FaseAdquisicion, etc. | ⚠️ NO tocar sin migración |
| `protocolos/management/commands/` | Scripts de carga de datos | Crear comandos de seed |

### Archivos de Documentación

| Archivo | Actualizar Cuando |
|---------|-------------------|
| `archive/TEMPLATES_MANTENIMIENTO_PROTOCOLOS.md` | Cambies estructura de escenarios o agregues nuevos templates |
| `archive/MEJORAS_ELEGIR_PROTOCOLO_v3.md` | Hagas cambios significativos en arquitectura |
| `archive/REPORTE_AUDITORIA_PROTOCOLOS.md` | Agregues/elimines protocolos o detectes problemas |
| `README_PROTOCOLOS.md` (este archivo) | Cambies estructura de documentación |

---

## 🎯 Estado Actual (Snapshot)

**Versión**: 3.0  
**Última actualización**: 2025-12-13  
**Branch**: feature/colegiales

### Números del Sistema

- **Escenarios configurados**: 10
- **Protocolos activos en DB**: 17
- **Fases totales**: 27
- **Cobertura**: 100% (todos los escenarios tienen protocolo)

### Distribución por Nivel

- **Monofásico**: 5 escenarios (Dolor abdominal, TEP, Stroke, Aorta, Oncológico)
- **Bifásico**: 4 escenarios (Páncreas, Hematuria, Sangrado activo)
- **Trifásico**: 1 escenario (Hígado)
- **Multifásico**: 1 escenario (Riñón 4 fases)

---

## ⚙️ Comandos de Verificación Rápida

```bash
# Activar entorno
cd c:\Dev\GitHub\gestion_servicio
gestion_env\Scripts\activate

# Verificar sistema Django
python manage.py check

# Iniciar servidor de desarrollo
python manage.py runserver

# Abrir shell de Django
python manage.py shell
```

### URLs del Sistema

| URL | Descripción |
|-----|-------------|
| http://localhost:8000/protocolos/ | Lista de todos los protocolos |
| http://localhost:8000/protocolos/elegir/ | Página de decisión clínica (v3) |
| http://localhost:8000/protocolos/<id>/ | Detalle de protocolo individual |

---

## 🔧 Flujo de Trabajo Típico

### Caso de Uso: Agregar "Trauma Esplénico"

```bash
# 1. Copiar template desde TEMPLATES_MANTENIMIENTO_PROTOCOLOS.md

# 2. Editar protocolos/views.py
# Agregar al final de lista escenarios:
{
    'key': 'trauma-esplenico',
    'titulo': 'Trauma esplénico con sospecha de laceración',
    'pregunta': '¿Hay sangrado activo esplénico?',
    'cuando': [
        'Trauma abdominal contuso con dolor en cuadrante superior izquierdo',
        'Hematoma subcapsular en FAST',
        'Caída del hematocrito post-trauma',
    ],
    'phase_summary': 'Bifásico arterial + portal',
    'quick_tags': ['Urgencia', 'Vascular'],
    'protocolos': ['TC abdomen bifásico trauma (arterial + portal)'],
    'recommendation': {
        'level': 'BIFASICO',
        'phase_template': 'Arterial (25-30s) + Portal (65-70s)',
        'rationale': [
            'Arterial: detecta sangrado activo parenquimatoso',
            'Portal: evalúa grado de laceración (I-V)',
            'Permite decisión de embolización vs observación',
        ],
        'must_have': [
            'Vía venosa 18G para flujo rápido',
            'Contraste 100-120 mL a 4-5 mL/s',
            'Paciente estabilizado para evitar artefactos',
        ],
        'avoid': [
            'NO solicitar para trauma menor sin sospecha visceral',
            'NO indicar si paciente inestable (directo a quirófano)',
            'NO usar para seguimiento de lesión estable',
        ],
        'red_flags': ['Shock hipovolémico', 'Hemoperitoneo masivo', 'Inestabilidad hemodinámica'],
    }
},

# 3. Verificar
python manage.py check

# 4. Iniciar servidor
python manage.py runserver

# 5. Probar en navegador
# http://localhost:8000/protocolos/elegir/
# - Buscar "trauma"
# - Filtrar por "Urgencia"
# - Filtrar por "Bifásico"
# - Verificar que aparece la card
```

---

## 📞 Soporte y Troubleshooting

### Errores Comunes

| Error | Solución Rápida |
|-------|----------------|
| "No cargado aún" (botón gris) | Verificar nombre exacto de protocolo en DB |
| Escenario no aparece | Verificar coma al final del dict |
| Filtro de fase no funciona | Verificar `level` en mayúsculas |
| Error de sintaxis Python | `python manage.py check` para ver línea |

### Dónde Buscar Ayuda

1. **Templates copiables**: [archive/TEMPLATES_MANTENIMIENTO_PROTOCOLOS.md](archive/TEMPLATES_MANTENIMIENTO_PROTOCOLOS.md)
2. **Troubleshooting extendido**: [archive/MEJORAS_ELEGIR_PROTOCOLO_v3.md](archive/MEJORAS_ELEGIR_PROTOCOLO_v3.md) → Sección "Troubleshooting"
3. **Comandos Django**: [archive/REPORTE_AUDITORIA_PROTOCOLOS.md](archive/REPORTE_AUDITORIA_PROTOCOLOS.md) → ANEXO

---

## 📝 Notas para IA/Copilot

> **Para GitHub Copilot / Claude / GPT**: 
> 
> Cuando el usuario quiera modificar el sistema de protocolos:
> 
> 1. **SIEMPRE dirigir primero a**: `TEMPLATES_MANTENIMIENTO_PROTOCOLOS.md`
> 2. **Copiar el template exacto** de ese documento (no improvisar)
> 3. **Verificar con**: `python manage.py check` antes de confirmar
> 4. **NO tocar**: `models.py` ni crear migraciones sin explícita autorización
> 5. **Mantener consistencia**: usar solo tags permitidos (Caracterización, Urgencia, Vascular, Oncológico)
> 6. **Respetar niveles**: MONOFASE, BIFASICO, TRIFASICO, MULTIFASICO (mayúsculas exactas)

---

## 🚀 Roadmap de Mejoras Futuras

### Propuestas pendientes (opcional)

- [ ] Analytics: Trackear qué protocolos se consultan más
- [ ] Feedback loop: Botón "¿Fue útil?" en cada recomendación
- [ ] Comparador visual: Diagrama de timeline para cada protocolo
- [ ] Quiz mode: Modo de aprendizaje con casos clínicos aleatorios
- [ ] Export PDF: Descargar guía completa de escenario
- [ ] Integración Cloudinary: Imágenes de ejemplo de cada fase

---

**Última actualización**: 2025-12-13  
**Versión de documentación**: 1.0  
**Mantenedor**: Sistema de mejoras UX protocolos
