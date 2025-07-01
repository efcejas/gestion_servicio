# 🚀 Guía Rápida: Tailwind CSS + Flowbite

## ⚡ Comandos Rápidos

### Iniciar desarrollo con Tailwind
```bash
# 1. Activar entorno virtual
cd gestion_servicio
gestion_env\Scripts\activate

# 2. Iniciar servidor Django
python manage.py runserver

# 3. En otra terminal: Compilar CSS con watch
cd theme/static_src
npm run build
```

### URLs de Prueba
- **Tailwind básico:** http://127.0.0.1:8000/simple-tailwind-test/
- **Componentes Flowbite:** http://127.0.0.1:8000/flowbite-test/
- **Debug CSS:** http://127.0.0.1:8000/debug-tailwind/

## 📋 Checklist de Uso

### Para crear un nuevo template con Tailwind:
- [ ] Agregar `{% load static %}` al inicio
- [ ] Incluir `<link rel="stylesheet" href="{% static 'css/tailwind.css' %}">`
- [ ] Usar clases de Tailwind normalmente
- [ ] Para componentes Flowbite, agregar el JavaScript:
  ```html
  <script src="https://cdn.jsdelivr.net/npm/flowbite@2.5.2/dist/flowbite.min.js"></script>
  ```

### Clases de Tailwind más útiles para el proyecto médico:
```css
/* Colores médicos */
bg-blue-500, bg-green-500, bg-red-500
text-blue-700, text-green-700, text-red-700

/* Espaciado */
p-4, m-4, px-8, py-2
space-x-4, space-y-2

/* Layout */
flex, grid, container, mx-auto
justify-center, items-center

/* Tipografía */
text-xl, text-2xl, font-bold, font-medium
```

## 🔧 Resolución de Problemas

### ❌ Los estilos no se aplican
1. Verificar que el template incluye `{% load static %}`
2. Verificar que se carga `{% static 'css/tailwind.css' %}`
3. Recompilar CSS: `cd theme/static_src && npm run build-prod`
4. Ejecutar: `python manage.py collectstatic --noinput`

### ❌ Error "Invalid block tag: static"
- Agregar `{% load static %}` al inicio del template

### ❌ Componentes Flowbite no funcionan
- Verificar que se incluye el JavaScript de Flowbite
- Verificar que las clases están en el CSS compilado

## 📁 Archivos Importantes
- `theme/static_src/tailwind.config.js` - Configuración principal
- `theme/static_src/src/styles.css` - Estilos fuente
- `static/css/tailwind.css` - CSS compilado final
- `templates/*_test.html` - Ejemplos de uso
