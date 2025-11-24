# Verificación de Lógica de Permisos por Grupos de Usuarios

## 🔐 Sistema de Permisos Implementado

### Grupos de Usuarios Definidos:
1. **"Técnicos de tomografía"** - Acceso restringido a eventos de tomografía
2. **"Técnicos de resonancia"** - Acceso restringido a eventos de resonancia
3. **Otros usuarios** (médicos, administrativos) - Acceso completo a todos los servicios

---

## 🎯 Lógica de Filtrado por Vista

### 1. **Dashboard de Eventos** (`EventosDashboardView`)
**Archivo**: `gestion_eventos/views.py`

```python
def get_queryset(self):
    user = self.request.user
    
    if user.groups.filter(name="Técnicos de tomografía").exists():
        return EventoServicio.objects.filter(
            servicio_origen_evento='tomografia'
        ).order_by('-fecha_creacion')[:5]
    elif user.groups.filter(name="Técnicos de resonancia").exists():
        return EventoServicio.objects.filter(
            servicio_origen_evento='resonancia'
        ).order_by('-fecha_creacion')[:5]
    else:
        return EventoServicio.objects.all().order_by('-fecha_creacion')[:5]
```

**Métricas filtradas por grupo:**
- `eventos_activos`: Solo del servicio correspondiente
- `eventos_resueltos_hoy`: Solo del servicio correspondiente  
- `eventos_pendientes`: Solo del servicio correspondiente

### 2. **Lista de Eventos Activos** (`EventoServicioListView`)
**Archivo**: `gestion_eventos/views.py`

```python
def get_queryset(self):
    user = self.request.user

    if user.groups.filter(name="Técnicos de tomografía").exists():
        # Solo eventos de tomografía
        return EventoServicio.objects.filter(
            estado__in=['abierto', 'en_revision'],
            servicio_origen_evento='tomografia'
        ).order_by('-fecha_creacion')

    elif user.groups.filter(name="Técnicos de resonancia").exists():
        # Solo eventos de resonancia
        return EventoServicio.objects.filter(
            estado__in=['abierto', 'en_revision'],
            servicio_origen_evento='resonancia'
        ).order_by('-fecha_creacion')

    else:
        # Médicos, administrativos, etc. ven todo
        return EventoServicio.objects.filter(
            estado__in=['abierto', 'en_revision']
        ).order_by('-fecha_creacion')
```

### 3. **Historial de Eventos** (`HistorialEventoListView`)
**Archivo**: `gestion_eventos/views.py`

```python
def get_queryset(self):
    user = self.request.user

    if user.groups.filter(name="Técnicos de tomografía").exists():
        queryset = EventoServicio.objects.filter(
            estado='resuelto',
            servicio_origen_evento='tomografia'
        ).order_by('-fecha_creacion')
    elif user.groups.filter(name="Técnicos de resonancia").exists():
        queryset = EventoServicio.objects.filter(
            estado='resuelto',
            servicio_origen_evento='resonancia'
        ).order_by('-fecha_creacion')
    else:
        queryset = EventoServicio.objects.filter(
            estado='resuelto'
        ).order_by('-fecha_creacion')
```

---

## 📝 Lógica de Formularios

### **Formulario de Creación de Eventos** (`EventoServicioForm`)
**Archivo**: `gestion_eventos/forms.py`

#### Restricción de Tipo de Evento:
```python
# Opciones base para todos los usuarios
base_choices = [
    ('cancelado', 'Estudio cancelado'),
    ('demorado', 'Estudio demorado'),
    ('pendiente', 'Estudio pendiente'),
    ('tecnico', 'Problema técnico'),
    ('conflicto', 'Conflicto o situación interpersonal'),
    ('otro', 'Otro'),
]

# Solo técnicos de resonancia pueden agregar estas opciones:
if user and user.groups.filter(name="Técnicos de resonancia").exists():
    base_choices += [
        ('guardia', 'Estudio de guardia realizado'),
        ('internado', 'Estudio de paciente internado realizado'),
    ]
```

#### Restricción de Servicio:
```python
if user:
    if user.groups.filter(name="Técnicos de tomografía").exists():
        # Solo puede seleccionar tomografía
        self.fields['servicio_origen_evento'].choices = [('tomografia', 'Tomografía')]
        self.fields['servicio_origen_evento'].widget.attrs['readonly'] = True
        self.initial['servicio_origen_evento'] = 'tomografia'
        
    elif user.groups.filter(name="Técnicos de resonancia").exists():
        # Solo puede seleccionar resonancia
        self.fields['servicio_origen_evento'].choices = [('resonancia', 'Resonancia')]
        self.fields['servicio_origen_evento'].widget.attrs['readonly'] = True
        self.initial['servicio_origen_evento'] = 'resonancia'
```

---

## 🎨 Interfaz Visual Personalizada

### **Títulos Específicos por Servicio**

#### Dashboard:
```html
{% if group.name == "Técnicos de tomografía" %}
    Gestión de eventos - Tomografía
{% elif group.name == "Técnicos de resonancia" %}
    Gestión de eventos - Resonancia Magnética  
{% else %}
    Gestión integral de eventos del servicio médico
{% endif %}
```

#### Lista de Eventos:
```html
{% if group.name == "Técnicos de tomografía" %}
    ⚡ Eventos Activos - Tomografía
{% elif group.name == "Técnicos de resonancia" %}
    ⚡ Eventos Activos - Resonancia
{% endif %}
```

---

## 🔄 Flujo de Creación con Lógica de Permisos

### **Vista de Creación** (`EventoServicioCreateView`)
**Archivo**: `gestion_eventos/views.py`

```python
def form_valid(self, form):
    user = self.request.user
    form.instance.creado_por = user

    # Si es técnico, asigna el área automáticamente
    if user.groups.filter(name="Técnicos de tomografía").exists():
        form.instance.servicio_origen_evento = 'tomografia'
    elif user.groups.filter(name="Técnicos de resonancia").exists():
        form.instance.servicio_origen_evento = 'resonancia'
    # Si es médico, administrativo, etc., deja lo que venga del formulario

    return super().form_valid(form)
```

---

## ✅ Casos de Uso Verificados

### **Técnico de Tomografía:**
1. ✅ Ve solo eventos de tomografía en dashboard
2. ✅ Ve solo eventos activos de tomografía en lista  
3. ✅ Ve solo historial de tomografía
4. ✅ Al crear eventos, servicio se asigna automáticamente a 'tomografia'
5. ✅ Campo servicio aparece bloqueado en formulario
6. ✅ No puede seleccionar 'guardia' o 'internado' como tipo de evento

### **Técnico de Resonancia:**
1. ✅ Ve solo eventos de resonancia en dashboard
2. ✅ Ve solo eventos activos de resonancia en lista
3. ✅ Ve solo historial de resonancia
4. ✅ Al crear eventos, servicio se asigna automáticamente a 'resonancia'
5. ✅ Campo servicio aparece bloqueado en formulario  
6. ✅ **PUEDE** seleccionar 'guardia' e 'internado' como tipo de evento

### **Médicos/Administrativos:**
1. ✅ Ven todos los eventos en dashboard
2. ✅ Ven todos los eventos activos
3. ✅ Ven todo el historial
4. ✅ Pueden seleccionar cualquier servicio al crear eventos
5. ✅ Pueden seleccionar cualquier tipo de evento
6. ✅ Acceso completo a todas las funcionalidades

---

## 🔧 Archivos Modificados/Creados

### **Vistas:**
- `gestion_eventos/views.py` - Todas las vistas con lógica de filtros
- Nueva vista: `EventosDashboardView`

### **Formularios:**
- `gestion_eventos/forms.py` - Lógica de restricción de campos

### **URLs:**
- `gestion_eventos/urls.py` - Nueva ruta para dashboard

### **Templates:**
- `templates/gestion_eventos/dashboard_eventos.html` - Información específica por grupo
- `templates/gestion_eventos/lista_eventos.html` - Títulos específicos por servicio
- `templates/gestion_eventos/crear_evento_tailwind.html` - Nueva versión Tailwind
- `templates/gestion_eventos/historial_eventos_tailwind.html` - Nueva versión Tailwind

---

## 🚀 Estado de Implementación

**✅ COMPLETADO**: Toda la lógica de permisos está implementada y funcionando correctamente.

**✅ VERIFICADO**: Cada grupo de usuario ve solo la información correspondiente a su servicio.

**✅ MANTENIDO**: Toda la funcionalidad original se mantiene intacta.

**✅ MEJORADO**: La experiencia visual ahora es más clara para cada tipo de usuario.

---

**Fecha de verificación**: 18 de octubre de 2025
**Estado**: ✅ Sistema con permisos por grupos completamente funcional