# Copilot Instructions - Sistema de Gestión de Servicios Médicos

## 📋 Resumen del Proyecto
Sistema web Django para gestión integral de servicios médicos del Sanatorio Colegiales, incluyendo:
- Gestión de pedidos de estudios
- Liquidaciones por prestaciones
- Control de consultorios y equipos
- Agenda de profesionales y residentes
- Dictado e informes médicos con IA

## 🏗️ Arquitectura

### Stack Tecnológico
- **Backend**: Django 4.2+
- **Base de Datos**: SQLite (desarrollo), PostgreSQL (producción Heroku)
- **Frontend**: Templates Django + Tailwind CSS + Alpine.js
- **Testing**: pytest-django
- **Deployment**: Heroku

### Apps Principales
```
accounts/          - Autenticación y roles (médicos, residentes, admin)
pedidos_estudios/  - Gestión de órdenes de estudios médicos
liquidacion/       - Cálculo y facturación de prestaciones
consultorios/      - Gestión de consultorios y equipamiento
agenda/            - Calendario y turnos
dictado_informes/  - Transcripción y generación de informes con IA
preinformes/       - Pre-informes de estudios
protocolos/        - Protocolos médicos
clases_residentes/ - Sistema educativo para residentes
control_guardias/  - Gestión de guardias médicas
equipos/           - Inventario y mantenimiento
gestion_estudios/  - Catálogo de estudios disponibles
gestion_eventos/   - Eventos y actividades
```

## 🎯 Convenciones de Código

### Django Best Practices
- **Timezone**: Siempre usar `django.utils.timezone.now()` en lugar de `datetime.now()`
- **Queries**: Usar `select_related()` y `prefetch_related()` para optimizar N+1
- **Validaciones**: Implementar en modelos (clean()) Y formularios (clean_field())
- **Permisos**: Usar decoradores personalizados en `accounts/decorators.py`
- **Transacciones**: Usar `@transaction.atomic` para operaciones críticas

### Estructura de Código
```python
# Orden de importaciones
# 1. Python standard library
# 2. Django imports
# 3. Third party
# 4. Local imports

# Modelos
class MiModelo(models.Model):
    # Fields
    # Meta class
    # __str__()
    # save() y clean()
    # Custom methods
    # Properties

# Views
# - Usar Class-Based Views cuando sea posible
# - Función views para casos simples
# - Separar lógica de negocio en services.py o utils.py
```

### Testing
- **Framework**: pytest-django
- **Coverage**: Apuntar a >80% en lógica de negocio
- **Fixtures**: Usar factories o fixtures de pytest
- **Naming**: `test_<funcionalidad>_<escenario>_<resultado_esperado>`

```python
# Ejemplo
def test_calcular_liquidacion_prestacion_simple_devuelve_monto_correcto():
    pass
```

### Frontend
- **Templates**: Extender de `base.html` o templates específicos de app
- **CSS**: Usar clases de Tailwind, evitar CSS custom sin justificación
- **JS**: Alpine.js para interactividad, evitar jQuery
- **Forms**: Usar django-crispy-forms con Tailwind

### Nombres y Strings
- **Variables**: snake_case en Python
- **Clases**: PascalCase
- **Templates**: minúsculas con guiones `nombre-template.html`
- **URLs**: kebab-case `/pedidos-estudios/nuevo/`
- **i18n**: Strings siempre en español (es el idioma del negocio)

## 🔒 Seguridad y Permisos

### Decoradores Personalizados
```python
from accounts.decorators import (
    medico_required,
    residente_required,
    admin_required,
    tecnico_required
)

@medico_required
def mi_vista(request):
    pass
```

### Roles del Sistema
- **Médico**: Acceso completo a pedidos, informes, liquidaciones
- **Residente**: Acceso limitado, sistema de clases
- **Técnico**: Solo equipamiento y mantenimiento  
- **Admin**: Superusuario del sistema

## 📊 Modelos Clave

### Pedidos de Estudios
```python
# pedidos_estudios/models.py
- PedidoEstudio: Orden principal
- EstudioDetalle: Líneas del pedido
- Estado: pendiente, en_proceso, completado, cancelado
```

### Liquidación
```python
# liquidacion/models.py
- Prestacion: Servicios facturables
- Liquidacion: Período de facturación
- LiquidacionDetalle: Líneas de liquidación
```

### Consultorios
```python
# consultorios/models.py
- Consultorio: Espacios físicos
- Equipamiento: Inventario médico
- Mantenimiento: Historial de servicio
```

## 🚀 Flujos Importantes

### Procesamiento Automático de Pedidos
- Archivo: `pedidos_estudios/management/commands/procesar_pedidos_pendientes.py`
- Script: `procesar_pedidos_auto.bat` (Windows Task Scheduler)
- Lógica: Importar desde EGES, validar, notificar

### Liquidación de Prestaciones
- Cálculo automático por período
- Validación de montos
- Generación de reportes PDF
- Export a JSON para auditoría

### Dictado con IA
- `dictado_informes/ai_services.py`
- OpenRouter API para transcripción
- Múltiples modelos (GPT-4, Claude, Gemini)
- Sistema de aprendizaje y mejora continua

## ⚠️ Áreas Críticas

### No Modificar Sin Cuidado
1. **Liquidación**: Afecta facturación real
2. **Pedidos automáticos**: Integración con sistema EGES
3. **Permisos**: Pueden exponer datos sensibles
4. **Migraciones**: Siempre hacer backup de DB antes

### Always Check
- Timezone en operaciones con fechas
- Permisos en nuevas vistas
- Transacciones en operaciones financieras
- N+1 queries en listados

## 🧪 Testing Guidelines

### Prioridad Alta (Siempre con tests)
- Cálculos de liquidación
- Lógica de permisos
- Procesamiento de pedidos
- Validaciones de formularios

### Prioridad Media
- Views complejas
- Utils y helpers
- Services personalizados

### Prioridad Baja (Opcional)
- Views simples CRUD
- Templates
- Admin config

## 📝 Documentación

### Docstrings
```python
def calcular_liquidacion(periodo, medico):
    """
    Calcula la liquidación de un médico para un período específico.
    
    Args:
        periodo (Periodo): Período de liquidación
        medico (Medico): Médico a liquidar
        
    Returns:
        Liquidacion: Objeto de liquidación creado
        
    Raises:
        ValidationError: Si el período ya está cerrado
    """
    pass
```

### README por App
- Propósito de la app
- Modelos principales
- Flujos importantes
- Dependencias con otras apps

## 🔧 Comandos Útiles

```bash
# Desarrollo
python manage.py runserver
python manage.py test
python manage.py makemigrations
python manage.py migrate

# Testing
pytest
pytest --cov=liquidacion
pytest -v -s

# Datos
python manage.py cargar_datos_ejemplo
python manage.py procesar_pedidos_pendientes

# Deployment
heroku local
git push heroku feature/colegiales:main
```

## 🎨 UI/UX Guidelines

### Diseño
- Responsive first (mobile compatible)
- Color scheme: Azul médico primario
- Icons: Heroicons o similar
- Feedback: Toast notifications para acciones

### Accesibilidad
- Labels en todos los inputs
- Alt text en imágenes
- Contraste suficiente
- Navegación por teclado

## 🐛 Debugging

### Logs
- `logs/` directorio con logs por fecha
- `revisar_logs_procesamiento.py` para análisis
- Usar `logging` module, no `print()`

### Common Issues
1. **Token expired**: Renovar en `token.json`
2. **Migraciones conflictivas**: Resolver manualmente
3. **N+1 queries**: Usar Django Debug Toolbar
4. **Permisos**: Verificar decoradores y groups

## 🚢 Deployment

### Pre-Deploy Checklist
- [ ] Tests passing
- [ ] Migraciones aplicadas
- [ ] Secrets en Heroku config vars
- [ ] Static files collected
- [ ] ALLOWED_HOSTS actualizado
- [ ] Backup de DB producción

### Post-Deploy
- [ ] Verificar health check
- [ ] Revisar logs de Heroku
- [ ] Probar flujos críticos
- [ ] Notificar a usuarios si hay downtime

## 🤝 Colaboración

### Branch Strategy
- `main`: Producción (Sanatorio Principal)
- `feature/colegiales`: Desarrollo Colegiales
- `feature/*`: Features nuevos
- `hotfix/*`: Fixes urgentes

### Commit Messages
```
feat: agregar búsqueda por paciente en pedidos
fix: corregir cálculo de liquidación con bonifcación
refactor: mover lógica de validación a services
test: agregar tests para liquidación de guardia
docs: actualizar README de liquidacion
```

---

## 💡 Tips para Copilot

Cuando trabajes en este proyecto:

1. **Siempre considera el contexto médico**: Los términos y flujos tienen implicaciones reales
2. **Prioriza la seguridad**: Datos sensibles de pacientes y financieros
3. **Optimiza queries**: El sistema maneja muchos registros históricos
4. **Mantén consistencia**: Sigue los patrones existentes en el código
5. **Si hiciste cambios importantes, pregúntame si quiero que documentes**: Especialmente en áreas críticas
6. **Tests first**: Para lógica de negocio compleja

## 📚 Referencias
- Django Docs: https://docs.djangoproject.com/
- Tailwind CSS: https://tailwindcss.com/
- Alpine.js: https://alpinejs.dev/
- pytest-django: https://pytest-django.readthedocs.io/
