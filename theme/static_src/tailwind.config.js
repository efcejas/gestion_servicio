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
  ],
  safelist: [
    // Incluir TODOS los colores de Tailwind automáticamente
    {
      pattern: /bg-(red|green|blue|yellow|purple|pink|indigo|gray|orange|lime|emerald|teal|cyan|sky|violet|fuchsia|rose)-(50|100|200|300|400|500|600|700|800|900)/,
      variants: ['hover', 'focus', 'active', 'dark', 'dark:hover']
    },
    {
      pattern: /text-(red|green|blue|yellow|purple|pink|indigo|gray|orange|lime|emerald|teal|cyan|sky|violet|fuchsia|rose)-(50|100|200|300|400|500|600|700|800|900)/,
      variants: ['hover', 'focus', 'active', 'dark', 'dark:hover']
    },
    {
      pattern: /border-(red|green|blue|yellow|purple|pink|indigo|gray|orange|lime|emerald|teal|cyan|sky|violet|fuchsia|rose)-(50|100|200|300|400|500|600|700|800|900)/,
      variants: ['hover', 'focus', 'active', 'dark', 'dark:hover']
    },
    {
      pattern: /ring-(red|green|blue|yellow|purple|pink|indigo|gray|orange|lime|emerald|teal|cyan|sky|violet|fuchsia|rose)-(50|100|200|300|400|500|600|700|800|900)/,
      variants: ['focus', 'dark:focus']
    },
    // Gradientes
    {
      pattern: /from-(red|green|blue|yellow|purple|pink|indigo|gray|orange|lime|emerald|teal|cyan|sky|violet|fuchsia|rose)-(50|100|200|300|400|500|600|700|800|900)/
    },
    {
      pattern: /via-(red|green|blue|yellow|purple|pink|indigo|gray|orange|lime|emerald|teal|cyan|sky|violet|fuchsia|rose)-(50|100|200|300|400|500|600|700|800|900)/
    },
    {
      pattern: /to-(red|green|blue|yellow|purple|pink|indigo|gray|orange|lime|emerald|teal|cyan|sky|violet|fuchsia|rose)-(50|100|200|300|400|500|600|700|800|900)/
    },
    // Clases de utilidad comunes
    'bg-gradient-to-r',
    'bg-gradient-to-br', 
    'hover:bg-gradient-to-br',
    'focus:outline-none',
    'focus:ring-4',
    'shadow-lg',
    'dark:shadow-lg',
    'font-medium',
    'rounded-lg',
    'text-center',
    'space-y-4',
    'p-4', 'p-8', 'm-4', 'px-5', 'py-2.5', 'mb-2', 'me-2',
    'text-sm', 'text-lg', 'text-4xl',
    'font-bold', 'mb-4'
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
