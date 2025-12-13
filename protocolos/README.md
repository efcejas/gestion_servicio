# Módulo de Protocolos Radiológicos

Módulo minimalista para gestionar protocolos radiológicos en Sanatorio Colegiales.

## 📋 Instalación

### 1. Agregar la app a `INSTALLED_APPS`

Edita `gestion_estudios/settings.py` y agrega:

```python
INSTALLED_APPS = [
    # ... otras apps
    'protocolos.apps.ProtocolosConfig',
]
```

### 2. Crear las migraciones

```bash
python manage.py makemigrations protocolos
```

### 3. Aplicar las migraciones

```bash
python manage.py migrate protocolos
```

### 4. Cargar datos iniciales (opcional)

```bash
python manage.py cargar_protocolos_base
```

Este comando crea:
- 4 modalidades (TC, RM, RX, US)
- 9 regiones anatómicas
- 10 tags comunes
- 1 protocolo de ejemplo: "TC TAP con contraste EV (oncológico)" con 2 fases

## 🎯 Modelos

### Modalidad
- Modalidades de imagen (TC, RM, RX, US)

### RegionAnatomica
- Regiones del cuerpo (Tórax, Abdomen, TAP, Cráneo, etc.)

### Tag
- Etiquetas para clasificar protocolos (TEP, Trauma, Oncológico, etc.)

### Protocolo
Protocolo radiológico completo con:
- Modalidad y región
- Información sobre contraste (EV/oral)
- Preparación del paciente (ayuno, calibre vía, etc.)
- Cobertura anatómica
- Notas docentes para residentes

### FaseAdquisicion
Fases de adquisición dentro de un protocolo:
- Sin contraste, Arterial, Portal, Tardía, Otra
- Delay en segundos
- Cobertura específica
- Ventanas recomendadas
- Detalles técnicos

## 🔧 Uso

### Admin Django

Accede al admin en: `http://localhost:8000/admin/`

Bajo la sección **"Protocolos Radiológicos"** encontrarás:

1. **Modalidades**: Gestiona TC, RM, RX, US
2. **Regiones Anatómicas**: Gestiona regiones del cuerpo
3. **Etiquetas**: Tags para clasificación
4. **Protocolos**: Vista principal
   - Filtros por modalidad, región, estado
   - Buscador por nombre/descripción
   - Inline de fases de adquisición
5. **Fases de Adquisición**: Vista individual de fases

### Crear un protocolo nuevo

1. Admin → Protocolos Radiológicos → Protocolos → Agregar protocolo
2. Selecciona modalidad y región
3. Completa nombre y descripción
4. Marca checkboxes de contraste/ayuno
5. Completa preparación del paciente
6. Agrega tags relevantes
7. En la sección "Fases de adquisición" agrega las fases necesarias:
   - Orden (1, 2, 3...)
   - Nombre de la fase
   - Tipo (Sin contraste, Arterial, Portal, Tardía)
   - Región específica
   - Delay en segundos (si aplica)
8. Guarda el protocolo

## 🚀 Próximas extensiones posibles

- [ ] Vistas frontend para residentes (búsqueda y visualización)
- [ ] PDF exportable de protocolos
- [ ] Versionado de protocolos
- [ ] Sistema de aprobación (borrador → revisión → aprobado)
- [ ] Estadísticas de uso
- [ ] Integración con sistema de órdenes/pedidos
- [ ] Contraste detallado (modelo separado con volumen, flujo, tipo)
- [ ] Parámetros técnicos avanzados (kVp, mAs, pitch, reconstrucciones)

## 📝 Estructura minimalista

Este módulo fue diseñado intencionalmente con una arquitectura simple:

✅ Sin versionado automático  
✅ Sin auditoría compleja  
✅ Sin flujos de aprobación  
✅ Sin componentes reutilizables complejos  

La idea es tener una **base sólida y funcional** que se pueda extender gradualmente según las necesidades reales del servicio.
