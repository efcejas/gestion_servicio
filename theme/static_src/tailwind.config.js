/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    // Templates de Django - rutas corregidas
    '../../templates/**/*.html',
    '../../**/templates/**/*.html',
    
    // Archivos JavaScript
    '../../static/**/*.js',
    
    // FLOWBITE: Incluir archivos de Flowbite para detectar clases
    './node_modules/flowbite/**/*.js',
    
    // Para asegurar que detecte nuestras clases de prueba
    '../templates/simple_tailwind_test.html',
    '../templates/flowbite_test.html',
  ],
  theme: {
    extend: {
      // Aquí puedes extender el tema por defecto
      colors: {
        // Colores personalizados para tu proyecto médico
        'medical-blue': '#2563eb',
        'medical-green': '#059669',
        'medical-red': '#dc2626',
      },
      fontFamily: {
        // Usar las fuentes que ya tienes configuradas
        'sans': ['proxima-nova', 'ui-sans-serif', 'system-ui'],
      }
    },
  },
  plugins: [
    require('@tailwindcss/forms'),
    require('@tailwindcss/typography'),
    // FLOWBITE: Plugin para componentes interactivos
    require('flowbite/plugin')
  ],
  
  // IMPORTANTE: Configuración para coexistir con Bootstrap
  corePlugins: {
    // Deshabilitar preflight para evitar conflictos con Bootstrap
    preflight: false,
    // Opcional: deshabilitar container si usas el de Bootstrap
    container: false,
  }
}
