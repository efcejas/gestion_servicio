# 🎨 SISTEMA DE DISEÑO UNIFICADO - Dictado con IA

**Objetivo:** Crear una UI homogénea, minimalista y que respete 100% el dark mode del sistema.

---

## 🎯 Principios de Diseño

### 1. Dark Mode Nativo
- Sistema completamente oscuro (bg-gray-900)
- Sin fondos claros que rompan la coherencia
- Textos claros sobre fondos oscuros

### 2. Minimalismo
- Reducir gradientes excesivos
- Menos sombras y efectos
- Más espacio en blanco (o gris oscuro)
- Jerarquía visual clara

### 3. Consistencia
- Mismo esquema de colores en todas las páginas
- Cards con mismo estilo
- Headers unificados
- Espaciados consistentes

---

## 🎨 Paleta de Colores Dark Mode

### Fondos
```css
/* Principal */
bg-gray-900    /* Body, fondo principal */
bg-gray-800    /* Cards, contenedores */
bg-gray-700    /* Bordes, divisores */

/* Destacados */
bg-blue-900    /* Elementos importantes */
bg-indigo-900/50  /* Sutiles, con transparencia */
```

### Textos
```css
text-white       /* Títulos principales */
text-gray-300    /* Textos secundarios */
text-gray-400    /* Textos terciarios */
text-gray-500    /* Placeholders, disabled */
```

### Acentos (Un solo gradiente principal)
```css
/* ÚNICO gradiente para elementos destacados */
from-indigo-600 via-purple-600 to-pink-600
```

### Estados
```css
/* Success */
bg-green-900/50  text-green-300  border-green-700

/* Warning */
bg-yellow-900/50  text-yellow-300  border-yellow-700

/* Error */
bg-red-900/50  text-red-300  border-red-700

/* Info */
bg-blue-900/50  text-blue-300  border-blue-700
```

---

## 🧩 Componentes Estandarizados

### Header de Página
```html
<!-- Sin gradiente de fondo, solo borde inferior -->
<div class="border-b border-gray-700 pb-6 mb-6">
    <div class="flex items-center justify-between">
        <div class="flex items-center space-x-4">
            <div class="p-3 bg-indigo-900/50 rounded-lg">
                <i class="fas fa-[icon] text-2xl text-indigo-400"></i>
            </div>
            <div>
                <h1 class="text-2xl font-bold text-white">[Título]</h1>
                <p class="text-gray-400">[Descripción]</p>
            </div>
        </div>
        <button class="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg">
            [Acción]
        </button>
    </div>
</div>
```

### Card Estándar
```html
<!-- Sin gradientes, borde sutil -->
<div class="bg-gray-800 border border-gray-700 rounded-lg p-6 hover:border-indigo-600 transition-colors">
    <div class="flex items-center justify-between mb-4">
        <h3 class="text-lg font-semibold text-white">[Título]</h3>
        <span class="text-gray-400">[Meta]</span>
    </div>
    <p class="text-gray-300">[Contenido]</p>
</div>
```

### Card de Estadística (Minimalista)
```html
<div class="bg-gray-800 border border-gray-700 rounded-lg p-6">
    <div class="flex items-center justify-between">
        <div>
            <p class="text-sm text-gray-400">[Label]</p>
            <p class="text-3xl font-bold text-white">[Valor]</p>
        </div>
        <div class="p-3 bg-indigo-900/30 rounded-lg">
            <i class="fas fa-[icon] text-2xl text-indigo-400"></i>
        </div>
    </div>
</div>
```

### Card de Acción (Para Dashboard)
```html
<!-- Solo gradiente en cards de ACCIONES PRINCIPALES -->
<a href="[url]" class="group block">
    <div class="bg-gradient-to-br from-indigo-600 to-purple-600 rounded-lg p-6 hover:from-indigo-500 hover:to-purple-500 transition-all">
        <div class="flex items-center mb-3">
            <i class="fas fa-[icon] text-3xl text-white mr-3"></i>
            <h3 class="text-xl font-bold text-white">[Título]</h3>
        </div>
        <p class="text-indigo-100">[Descripción]</p>
    </div>
</a>
```

### Tabla
```html
<div class="bg-gray-800 border border-gray-700 rounded-lg overflow-hidden">
    <table class="w-full">
        <thead class="bg-gray-700">
            <tr>
                <th class="px-6 py-3 text-left text-xs font-semibold text-gray-300 uppercase">[Header]</th>
            </tr>
        </thead>
        <tbody class="divide-y divide-gray-700">
            <tr class="hover:bg-gray-700/50">
                <td class="px-6 py-4 text-sm text-gray-300">[Data]</td>
            </tr>
        </tbody>
    </table>
</div>
```

### Badge
```html
<!-- Estados con background oscuro -->
<span class="px-2.5 py-1 rounded-full text-xs font-medium bg-[color]-900/50 text-[color]-300 border border-[color]-700">
    [Texto]
</span>
```

### Botón Primario
```html
<button class="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white font-medium rounded-lg transition-colors">
    [Texto]
</button>
```

### Botón Secundario
```html
<button class="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-gray-300 font-medium rounded-lg transition-colors">
    [Texto]
</button>
```

---

## 📏 Espaciados Estandarizados

```css
/* Padding de cards */
p-6         /* Estándar */
p-4         /* Compacto */

/* Gaps entre elementos */
gap-4       /* Estándar */
gap-6       /* Generoso */

/* Márgenes verticales */
mb-6        /* Entre secciones */
mb-4        /* Entre elementos */
```

---

## 🚫 Qué ELIMINAR

### ❌ Gradientes Excesivos
- ~~`bg-gradient-to-r from-purple-600 via-indigo-600 to-blue-600`~~
- ~~`bg-gradient-to-br from-slate-50 to-blue-50`~~
- **Solo usar gradientes en cards de ACCIONES principales**

### ❌ Fondos Claros
- ~~`bg-white`~~
- ~~`from-slate-50`~~
- **Todo debe ser bg-gray-800 o más oscuro**

### ❌ Sombras Excesivas
- ~~`shadow-2xl`~~
- ~~`shadow-xl`~~
- **Usar solo border-gray-700 para separación**

### ❌ Efectos Excesivos
- ~~`transform hover:-translate-y-2`~~
- ~~`hover:scale-105`~~
- **Solo cambios sutiles de color**

---

## ✅ Implementación

### Reglas de Aplicación

1. **Headers de Página:**
   - Sin gradiente de fondo
   - Borde inferior gris
   - Icono en círculo con bg-indigo-900/50

2. **Cards de Estadísticas:**
   - bg-gray-800
   - border-gray-700
   - Sin gradientes
   - Iconos con bg-indigo-900/30

3. **Cards de Acción (Dashboard):**
   - Solo 2-3 cards principales con gradiente
   - Resto: bg-gray-800 + border-gray-700

4. **Tablas:**
   - bg-gray-800
   - Header bg-gray-700
   - Divisores border-gray-700

5. **Breadcrumbs:**
   - text-gray-400
   - hover:text-indigo-400
   - Sin fondo

---

## 🎯 Resultado Esperado

### Antes
- ❌ Fondos blancos que rompen dark mode
- ❌ 10+ gradientes diferentes
- ❌ Sobrecarga visual
- ❌ Inconsistencia entre páginas

### Después
- ✅ Dark mode 100% consistente
- ✅ 1 gradiente (solo acciones principales)
- ✅ Diseño limpio y minimalista
- ✅ Homogeneidad total

---

**Próximo paso:** Aplicar este sistema a todos los templates de dictado_informes
