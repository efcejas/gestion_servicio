# 📋 Templates de Mantenimiento - Sistema de Protocolos

> **Propósito**: Templates copiables para agregar/modificar escenarios en la página "¿Qué protocolo elegir?"

---

## 🆕 TEMPLATE: Agregar Nuevo Escenario

### Paso 1: Copiar este bloque en `protocolos/views.py`

**Ubicación**: Dentro de `escenarios = [...]`, al final antes del cierre `]`

```python
        {
            'key': 'NOMBRE-UNICO-MINUSCULAS',
            'titulo': 'Título descriptivo del escenario',
            'pregunta': '¿Pregunta clínica específica?',
            'cuando': [
                'Primera situación clínica donde aplicar',
                'Segunda situación clínica',
                'Tercera situación clínica',
            ],
            'phase_summary': 'Descripción corta',
            'quick_tags': ['Caracterización'],  # Opciones: Caracterización, Urgencia, Vascular, Oncológico
            'protocolos': ['Nombre EXACTO del protocolo en DB'],
            'recommendation': {
                'level': 'MONOFASE',  # Opciones: MONOFASE, BIFASICO, TRIFASICO, MULTIFASICO
                'phase_template': 'Timing con segundos (ej: Portal única 65-70s)',
                'rationale': [
                    'Primera razón clínica/física',
                    'Segunda razón',
                    'Tercera razón (opcional)',
                ],
                'must_have': [
                    'Prerequisito técnico 1',
                    'Prerequisito técnico 2',
                ],
                'avoid': [
                    'Cuándo NO usar (razón 1)',
                    'Cuándo NO usar (razón 2)',
                ],
                'red_flags': ['Flag urgente 1'],  # OPCIONAL - solo urgencias
            }
        },
```

### Paso 2: Verificar

```bash
cd c:\Dev\GitHub\gestion_servicio
gestion_env\Scripts\activate
python manage.py check
python manage.py runserver
```

Abrir: http://localhost:8000/protocolos/elegir/

---

## 📝 EJEMPLO COMPLETO: Trauma Hepático

```python
        {
            'key': 'trauma-hepatico',
            'titulo': 'Trauma hepático con sospecha de laceración',
            'pregunta': '¿Hay sangrado activo o laceración hepática?',
            'cuando': [
                'Trauma abdominal cerrado con hipotensión',
                'Elevación de transaminasas post-trauma',
                'Sospecha de lesión de órgano sólido en FAST+',
            ],
            'phase_summary': 'Bifásico arterial + portal',
            'quick_tags': ['Urgencia', 'Vascular'],
            'protocolos': ['TC abdomen bifásico trauma (arterial + portal)'],
            'recommendation': {
                'level': 'BIFASICO',
                'phase_template': 'Arterial (25-30s) + Portal (65-70s)',
                'rationale': [
                    'Arterial: detecta sangrado activo parenquimatoso (extravasación)',
                    'Portal: evalúa extensión de laceración y compromiso vascular',
                    'Permite decisión quirúrgica vs observación',
                ],
                'must_have': [
                    'Vía venosa 18G para flujo rápido (4-5 mL/s)',
                    'Contraste yodado 100-120 mL',
                    'Paciente estabilizado para evitar artefactos por movimiento',
                ],
                'avoid': [
                    'NO solicitar para trauma menor sin sospecha de lesión visceral',
                    'NO indicar si estabilidad permite observación clínica',
                    'NO usar para seguimiento de lesión conocida estable',
                ],
                'red_flags': ['Shock hipovolémico refractario', 'Hematocrito descendente', 'Distensión abdominal'],
            }
        },
```

---

## ✏️ TEMPLATE: Modificar Solo Recomendación

Si quieres cambiar únicamente el bloque `recommendation` de un escenario existente:

**Buscar en `protocolos/views.py`**:
```python
        {
            'key': 'nombre-del-escenario',  # Buscar por este key
```

**Reemplazar SOLO**:
```python
            'recommendation': {
                'level': 'NUEVO_NIVEL',
                'phase_template': 'Nuevo timing',
                'rationale': [
                    'Nueva razón 1',
                    'Nueva razón 2',
                ],
                'must_have': [
                    'Nuevo prerequisito 1',
                    'Nuevo prerequisito 2',
                ],
                'avoid': [
                    'Nueva advertencia 1',
                    'Nueva advertencia 2',
                ],
            }
```

---

## 🎨 TEMPLATE: Agregar Nuevo Tag

### Paso 1: Botón en `templates/protocolos/elegir_protocolo.html`

**Buscar sección "Quick tags (chips)" y agregar**:
```django
<button 
    onclick="toggleTagFilter('NuevoTag')" 
    data-tag="NuevoTag"
    class="tag-filter px-3 py-1 text-xs font-medium rounded-full bg-teal-100 text-teal-800 hover:bg-teal-200 transition-colors">
    NuevoTag
</button>
```

**Colores Tailwind disponibles**: 
- `bg-teal-100 text-teal-800` (verde azulado)
- `bg-orange-100 text-orange-800` (naranja)
- `bg-cyan-100 text-cyan-800` (cian)
- `bg-lime-100 text-lime-800` (lima)
- `bg-amber-100 text-amber-800` (ámbar)

### Paso 2: JavaScript en `<script>` del mismo archivo

**Buscar función `toggleTagFilter` y agregar en el primer bloque de `if/else`**:
```javascript
} else if (tag === 'NuevoTag') {
    btn.classList.remove('bg-teal-100', 'text-teal-800');
    btn.classList.add('bg-teal-600', 'text-white');
```

**Y en el segundo bloque de "Restore original colors"**:
```javascript
} else if (originalTag === 'NuevoTag') {
    btn.classList.remove('bg-teal-600', 'text-white');
    btn.classList.add('bg-teal-100', 'text-teal-800');
```

### Paso 3: Usar en escenarios

```python
'quick_tags': ['Urgencia', 'NuevoTag'],
```

---

## 🔍 COMANDOS ÚTILES

### Ver protocolos disponibles en DB

```bash
cd c:\Dev\GitHub\gestion_servicio
gestion_env\Scripts\activate
python manage.py shell
```

```python
from protocolos.models import Protocolo
for p in Protocolo.objects.filter(es_activo=True):
    print(f"- '{p.nombre}' ({p.fases.count()} fases)")
```

### Crear protocolo nuevo

```python
from protocolos.models import Protocolo, Modalidad, RegionAnatomica, FaseAdquisicion

protocolo = Protocolo.objects.create(
    nombre='TC abdomen bifásico trauma (arterial + portal)',
    descripcion='Protocolo para trauma abdominal con dos fases',
    modalidad=Modalidad.objects.get(codigo='TC'),
    region=RegionAnatomica.objects.get(nombre='Abdomen y pelvis'),
    requiere_contraste_ev=True,
    es_activo=True
)

FaseAdquisicion.objects.create(
    protocolo=protocolo,
    nombre='Arterial',
    orden=1,
    delay_segundos=25,
    region=RegionAnatomica.objects.get(nombre='Abdomen y pelvis')
)

FaseAdquisicion.objects.create(
    protocolo=protocolo,
    nombre='Portal',
    orden=2,
    delay_segundos=65,
    region=RegionAnatomica.objects.get(nombre='Abdomen y pelvis')
)

print(f"✅ Creado: {protocolo.nombre} (ID: {protocolo.id})")
```

### Verificar sistema

```bash
python manage.py check
python manage.py runserver
```

---

## ✅ CHECKLIST Nuevo Escenario

```
[ ] Copié template base
[ ] Cambié 'key' a nombre-unico-minusculas
[ ] Completé titulo, pregunta, cuando (3 bullets)
[ ] Elegí phase_summary descriptivo
[ ] Asigné 1-2 tags válidos
[ ] Verifiqué nombre exacto de protocolo en DB
[ ] Completé recommendation:
    [ ] level (MONOFASE/BIFASICO/TRIFASICO/MULTIFASICO)
    [ ] phase_template con timing
    [ ] rationale (2-4 razones)
    [ ] must_have (2-3 prerequisitos)
    [ ] avoid (2-4 advertencias)
    [ ] red_flags si es urgencia (opcional)
[ ] Agregué coma al final del dict
[ ] Ejecuté: python manage.py check ✅
[ ] Ejecuté: python manage.py runserver
[ ] Probé filtros en navegador
[ ] Protocolo muestra botón verde
```

---

## 🐛 Solución Rápida de Problemas

### Botón gris "No cargado aún"

**Causa**: Nombre de protocolo no coincide con DB

**Solución**:
```python
python manage.py shell
>>> from protocolos.models import Protocolo
>>> Protocolo.objects.filter(es_activo=True).values_list('nombre', flat=True)
# Copiar nombre EXACTO
```

### Escenario no aparece

**Causa**: Falta coma al final del dict

**Solución**: Agregar `,` después de `}`

### Filtro de fase no funciona

**Causa**: `level` no coincide con botón

**Verificar**:
1. views.py: `'level': 'BIFASICO'` (mayúsculas)
2. template: `data-phase-level="{{ escenario.recommendation.level }}"`
3. botón: `data-phase="BIFASICO"` (exacto)

### Error de sintaxis

```bash
python manage.py check
# Leer mensaje de error y corregir línea indicada
```

---

## 📚 Referencias Rápidas

### Tags válidos
- `Caracterización`
- `Urgencia`
- `Vascular`
- `Oncológico`

### Niveles válidos
- `MONOFASE`
- `BIFASICO`
- `TRIFASICO`
- `MULTIFASICO`

### Archivos a editar
- **Escenarios**: `protocolos/views.py` función `elegir_protocolo`
- **UI/Filtros**: `templates/protocolos/elegir_protocolo.html`
- **NO tocar**: `models.py`, `migrations/`

---

**Última actualización**: 2025-12-13  
**Versión**: 3.0  
**Branch**: feature/colegiales
