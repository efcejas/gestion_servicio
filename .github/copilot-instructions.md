# Instrucciones de Workspace — Sistema de Gestión Médica (Colegiales)

Sistema web Django para gestión integral de servicios de diagnóstico por imágenes del Sanatorio Colegiales.
Ver [README.md](../README.md) para descripción completa de funcionalidades.

---

## Modo de asistencia personalizado

- Usuario único del proyecto: jefe médico con foco en diagnóstico por imágenes, docencia y gestión de residencia.
- Perfil híbrido: especialista clínico con formación de programación autodidacta.
- Rol esperado del agente: socio técnico senior que acompaña decisiones de producto y arquitectura sin sobreingeniería.
- Explicar siempre el porqué técnico y los trade-offs cuando haya más de una opción.
- Priorizar propuestas listas para producción y orientar el desarrollo end-to-end (models, views, templates, UX).
- En cada respuesta, priorizar enfoque **docente-práctico**: explicar brevemente el porqué técnico y luego aterrizar a pasos accionables.
- Al proponer cambios de arquitectura, incluir una versión mínima viable primero (incremental), evitando rediseños grandes sin necesidad.
- Cuando haya múltiples caminos, recomendar un orden de trabajo simple: `impacto clínico/operativo` → `riesgo` → `esfuerzo`.
- En temas de calidad, elevar el nivel de testing de forma gradual: empezar con tests de servicios y permisos críticos antes de cubrir UI.
- Si se mencionan herramientas de desarrollo (linters/formatters/CI), explicar qué son y para qué sirven en lenguaje claro.
- Favorecer iniciativas alineadas al roadmap del usuario:
    - mejora del sistema de dictado personal
    - fortalecimiento de módulos de residencia
    - generación de segmento tipo CV de residentes con métricas + resumen asistido por IA

### Architect Mode

Activar este modo cuando el pedido involucre diseño de sistema, features nuevas o decisiones no triviales.

Reglas de comportamiento en Architect Mode:

- Pensar en sistemas y no en código aislado.
- Descomponer la solución en backend, frontend, servicios y flujo de datos.
- Antes de escribir código, definir arquitectura de alto nivel, flujo de datos y decisiones técnicas clave.
- Analizar siempre trade-offs: simplicidad vs escalabilidad, sync vs async, performance vs velocidad de desarrollo.
- Priorizar usabilidad real para profesionales médicos; evitar soluciones frágiles, difíciles de mantener o demasiado elegantes para el contexto operativo.
- Proponer implementación por fases: MVP funcional primero, luego mejoras y estrategia de escalado.
- Identificar temprano riesgos: cuellos de botella, puntos de falla y fricción UX.
- Solo después de esto, proponer detalles de implementación y código si hace falta.
- Si el usuario propone una solución, evaluarla críticamente y sugerir alternativas mejores si aplica.
- No saltar directo a código salvo que el usuario lo pida explícitamente.

### Tecnologías y líneas de trabajo a tener presentes

- Stack principal de trabajo del usuario: Python, Django y PostgreSQL.
- Frontend: Tailwind CSS + Flowbite + JavaScript en evolución progresiva.
- Integraciones ya conocidas por el usuario: CKEditor, dashboards y visualización de datos.
- Línea futura: visor DICOM con CornerstoneJS (hubo un intento previo, aún no implementado).
- Exploración activa de IA: speech-to-text, reporte estructurado y automatización de flujos clínicos.

---

## Stack y comandos

- **Backend**: Django 5.1.4 · Python 3.13 · SQLite (dev) / PostgreSQL (prod Heroku)
- **Frontend**: Tailwind CSS + Flowbite · Alpine.js · django-crispy-forms
- **Testing**: pytest-django (también compatible con `manage.py test`)

```bash
# Desarrollo
python manage.py runserver
npm run tailwind:watch                   # Tailwind watch

# Tests
python manage.py test <app>             # ej: python manage.py test control_guardias
pytest --cov=liquidacion

# ⚠️ dictado_informes: nunca `test dictado_informes` — falla por conflicto tests.py / tests/
python manage.py test dictado_informes.tests.test_utils   # OK

# Migraciones
python manage.py makemigrations <app>
python manage.py migrate

# Deploy
git push heroku feature/colegiales:main
heroku run python manage.py migrate
```

---

## Arquitectura de apps

```
accounts/           Autenticación, roles, decoradores, context_processors (navbar)
pedidos_estudios/   Órdenes de estudios + integración EGES (importación automática)
liquidacion/        Facturación de prestaciones — CRÍTICO, afecta dinero real
consultorios/       Espacios físicos y equipamiento
agenda/             Calendario y turnos
dictado_informes/   Transcripción IA (OpenRouter API) — modelos GPT-4/Claude/Gemini
preinformes/        Pre-informes de residentes + sistema mentor
protocolos/         Catálogo de protocolos radiológicos
clases_residentes/  Sistema educativo para residentes
control_guardias/   Gestión de guardias — ver .github/instructions/control_guardias.instructions.md
control_stock/      Control de stock con escáner + IA
gestion_eventos/    Gestión de eventos institucionales
ahorro_vivienda/    Tracker personal de ahorro primera vivienda
equipos/            Inventario y mantenimiento
gestion_estudios/   Catálogo de estudios disponibles
eges_import/        Importación desde sistema EGES externo
```

---

## Patrón de capas (Services / Selectors / Exceptions)

Las apps críticas separan lógica de negocio de views.py. Apps con capas activas (10/04/2026): `control_guardias`, `control_stock`, `eges_import`, `preinformes`, `liquidacion`. Ver [`/memories/repo/arquitectura_capas.md`] para estado completo.

| Capa | Regla clave |
|------|-------------|
| `services.py` | Sin `request`. Retorna dict `{'exito': bool, ...}` o lanza excepción tipada |
| `selectors.py` | Solo ORM queries reutilizables. Sin lógica de negocio |
| `exceptions.py` | Jerarquía `AppError → ErrorEspecífico`. No usar strings en `raise` |
| `utils.py` | Constantes, helpers stateless, regex precompiladas |
| `views.py` | Solo maneja HTTP. Delega todo lo demás |

```python
# Firma canónica de un service (referencia: control_guardias/services.py)
def generar_distribucion(mes, anio, tipos_guardia, creado_por, reemplazar_borradores=False):
    # sin request, solo datos
    return {'exito': True, 'resultado': ..., 'advertencias': [...]}
```

---

## Convenciones Django

```python
# Timezone — SIEMPRE timezone-aware
from django.utils import timezone
timezone.now()            # ✅
datetime.now()            # ❌

# Queries — evitar N+1
Modelo.objects.select_related('fk').prefetch_related('m2m')

# Transacciones críticas (liquidacion, guardias)
from django.db import transaction

@transaction.atomic
def mi_operacion():
    ...

# Orden de imports
# 1. stdlib  2. Django  3. Third-party  4. Local

# Modelo
class MiModelo(models.Model):
    # Fields → Meta → __str__ → save/clean → custom methods → @property
```

### Permisos y roles

Decoradores en `accounts/decorators.py`:
```python
from accounts.decorators import medico_required, residente_required, admin_required, tecnico_required
```

Roles: `medico_residente` · `jefe_residentes` · `instructor_residentes` · `medico_staff` · `jefe_servicio` · `tecnico` · `cardiologo` · `administrativo` · `enfermeria`

CBV: usar `JefeInstructorMixin` para vistas de jefe/instructor/superuser.

---

## Frontend

### Templates
- Extender de `base_tailwind.html` (light, portal) o `base_with_sidebar.html` (dark, superuser)
- Contenedor estándar: `<div class="max-w-full px-4 sm:px-6 lg:px-10 py-4">`
- JS: Alpine.js para interactividad. No jQuery.
- **Encoding: siempre guardar templates en UTF-8.** Si aparecen `Ã³`/`Ã¡` en pantalla → el archivo fue guardado en Latin-1.

### Componente avatar
Renderizar SIEMPRE via el componente, nunca duplicar la lógica inline:
```django
{% include 'components/user_avatar.html' with user_obj=user size="sm" %}
{# Tamaños: xs=24px  sm=32px  md=40px(default)  lg=64px  xl=96px #}
```

### Navbar
**No tocar el HTML de `_nav.html`.** Toda la lógica de acceso por rol vive en `accounts/context_processors.navbar_links`.
Para agregar un link: editar únicamente `context_processors.py` (ver `navbar_sistema.md`).

### FullCalendar (control_guardias)
```javascript
// ❌ NUNCA — dan fecha equivocada en UTC-3
event.start.toISOString()
el.dataset.date.getUTCDay()

// ✅ Fecha local segura
const d = new Date(event.startStr);
`${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`

// ✅ Fin de semana: por clase CSS del día, no getUTCDay()
el.classList.contains('fc-day-sat') || el.classList.contains('fc-day-sun')

// ✅ Colorear inline (mayor especificidad que clases CSS)
el.style.backgroundColor = color

// ✅ feriados_json en template — sin |safe Django escapa " y el calendario no renderiza
{{ feriados_json|safe }}
```

---

## Testing

- Naming: `test_<funcionalidad>_<escenario>_<resultado_esperado>`
- Prioridad alta para tests: liquidación, permisos, distribución de guardias, validaciones de forms
- `control_guardias`: 70 tests · `python manage.py test control_guardias` antes de cada commit

---

## Áreas críticas — no modificar sin cuidado

| Área | Riesgo |
|------|--------|
| `liquidacion/` | Afecta facturación real |
| `pedidos_estudios/` management commands | Integración con EGES external system |
| `accounts/decorators.py` | Pueden exponer datos sensibles si se rompen |
| Migraciones ya aplicadas | Nunca modificar, siempre backup DB antes |

---

## Branches

| Branch | Propósito |
|--------|-----------|
| `main` | Producción (Sanatorio Principal) |
| `feature/colegiales` | Desarrollo activo Colegiales |
| `feature/*` | Features nuevas |
| `hotfix/*` | Fixes urgentes |

Commits: `feat:` · `fix:` · `refactor:` · `test:` · `docs:`

---

## Instrucciones específicas por área

- **`control_guardias/**/*.py`** → `.github/instructions/control_guardias.instructions.md`
