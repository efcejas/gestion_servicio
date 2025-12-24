# 🎨 Plan de Migración a Tailwind CSS

## 📋 Estado Actual del Proyecto

### ✅ Ya Configurado
- **django-tailwind**: Instalado y configurado
- **App theme**: Creada para estilos personalizados
- **TAILWIND_APP_NAME**: Configurado como 'theme'
- **Algunos templates**: Ya usando clases Tailwind (dashboard_simple.html, admin_dashboard.html)

### 📊 Análisis de Templates por Migrar

#### 🔴 Prioridad Alta (Bootstrap → Tailwind)
1. **Autenticación** (`templates/registration/`)
   - `login.html` - ❌ Bootstrap
   - `register.html` - ❌ Bootstrap  
   - `password_reset_*.html` - ❌ Bootstrap

2. **Layout Base** (`templates/layouts/`)
   - `base.html` - ❌ Bootstrap
   - `base_with_sidebar.html` - ⚠️ Mixto (necesita limpieza)

#### 🟡 Prioridad Media (Apps específicas)
3. **Control de Guardias** (`templates/control_guardias/`)
   - Calendarios y formularios
   - Ya tiene `TailwindCalendarView` ✅

4. **Gestión de Eventos** (`templates/gestion_eventos/`)
   - Listados y formularios de eventos

5. **Liquidación** (`templates/liquidacion/`)
   - Reportes y dashboards

6. **Pedidos de Estudios** (`templates/pedidos_estudios/`)
   - Formularios y listados

#### 🟢 Prioridad Baja (Refinamiento)
7. **Componentes Específicos**
   - Modales y alertas
   - Tablas y paginación
   - Formularios avanzados

## 🎯 Plan de Ejecución por Fases

### **Fase 1: Fundamentos** (Estimado: 2-3 horas)
- [ ] Limpiar y optimizar `base.html` y `base_with_sidebar.html`
- [ ] Migrar templates de autenticación (`registration/`)
- [ ] Crear componentes Tailwind reutilizables
- [ ] Establecer paleta de colores y design system

### **Fase 2: Apps Principales** (Estimado: 4-5 horas)
- [ ] Migrar `control_guardias` templates
- [ ] Migrar `gestion_eventos` templates  
- [ ] Migrar `liquidacion` templates
- [ ] Migrar `pedidos_estudios` templates

### **Fase 3: Optimización** (Estimado: 1-2 horas)
- [ ] Eliminar dependencias de Bootstrap
- [ ] Optimizar CSS personalizado
- [ ] Testing responsivo completo
- [ ] Performance audit

## 🛠️ Herramientas y Recursos

### **Design System Propuesto**
```css
/* Colores principales */
Primary: blue-600 (#2563eb)
Secondary: gray-600 (#4b5563)  
Success: green-600 (#16a34a)
Warning: yellow-600 (#ca8a04)
Danger: red-600 (#dc2626)

/* Espaciado */
Contenedores: max-w-7xl mx-auto px-4
Secciones: py-8 lg:py-12
Cards: p-6 rounded-lg shadow-md

/* Responsive */
Breakpoints: sm: 640px, md: 768px, lg: 1024px, xl: 1280px
```

### **Componentes a Crear**
- [ ] Card base reutilizable
- [ ] Button variants (primary, secondary, danger)
- [ ] Form input base
- [ ] Modal base
- [ ] Alert/notification system
- [ ] Table responsive

## 📈 Beneficios Esperados

1. **Performance**: CSS más pequeño y optimizado
2. **Mantenibilidad**: Sistema de diseño consistente  
3. **Responsive**: Mobile-first approach nativo
4. **Productividad**: Utility-first CSS para cambios rápidos
5. **Moderno**: Stack tecnológico actualizado

## 🚀 Próximos Pasos

1. **Empezar Fase 1**: Migrar base templates
2. **Testing continuo**: Verificar en cada paso
3. **Commits granulares**: Un template/componente por commit
4. **Documentation**: Mantener registro de cambios

---

**Rama**: `feature/migrate-to-tailwind`
**Inicio**: 13 de octubre de 2025
**Meta**: Migración completa sin perder funcionalidad