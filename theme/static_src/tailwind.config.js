/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    // Templates de Django - rutas específicas
    '../../templates/**/*.html',
    '../../accounts/templates/**/*.html',
    '../../control_guardias/templates/**/*.html',
    '../../gestion_eventos/templates/**/*.html',
    '../../liquidacion/templates/**/*.html',
    '../../pedidos_estudios/templates/**/*.html',
    
    // Archivos JavaScript específicos (evitando node_modules)
    '../../static/**/*.js',
    '../../**/static/**/*.js',
    
    // Python files que pueden tener clases CSS en strings
    '../../**/*.py',
    '!../../gestion_env/**',
    '!../../**/migrations/**',
    '!../../node_modules/**',
    '!../../staticfiles/**',
    
    // FLOWBITE: Incluir archivos de Flowbite para detectar clases
    './node_modules/flowbite/**/*.js',
    
    // Archivos de configuración que pueden contener clases
    './src/**/*.css',
  ],
  safelist: [
    // Incluir TODOS los colores de Tailwind automáticamente
    {
      pattern: /bg-(red|green|blue|yellow|purple|pink|indigo|gray|orange|amber|lime|emerald|teal|cyan|sky|violet|fuchsia|rose)-(50|100|200|300|400|500|600|700|800|900)/,
      variants: ['hover', 'focus', 'active', 'dark', 'dark:hover']
    },
    {
      pattern: /text-(red|green|blue|yellow|purple|pink|indigo|gray|orange|amber|lime|emerald|teal|cyan|sky|violet|fuchsia|rose)-(50|100|200|300|400|500|600|700|800|900)/,
      variants: ['hover', 'focus', 'active', 'dark', 'dark:hover']
    },
    {
      pattern: /border-(red|green|blue|yellow|purple|pink|indigo|gray|orange|amber|lime|emerald|teal|cyan|sky|violet|fuchsia|rose)-(50|100|200|300|400|500|600|700|800|900)/,
      variants: ['hover', 'focus', 'active', 'dark', 'dark:hover']
    },
    {
      pattern: /ring-(red|green|blue|yellow|purple|pink|indigo|gray|orange|amber|lime|emerald|teal|cyan|sky|violet|fuchsia|rose)-(50|100|200|300|400|500|600|700|800|900)/,
      variants: ['focus', 'dark:focus']
    },
    // Gradientes
    {
      pattern: /from-(red|green|blue|yellow|purple|pink|indigo|gray|orange|amber|lime|emerald|teal|cyan|sky|violet|fuchsia|rose)-(50|100|200|300|400|500|600|700|800|900)/
    },
    {
      pattern: /via-(red|green|blue|yellow|purple|pink|indigo|gray|orange|amber|lime|emerald|teal|cyan|sky|violet|fuchsia|rose)-(50|100|200|300|400|500|600|700|800|900)/
    },
    {
      pattern: /to-(red|green|blue|yellow|purple|pink|indigo|gray|orange|amber|lime|emerald|teal|cyan|sky|violet|fuchsia|rose)-(50|100|200|300|400|500|600|700|800|900)/
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
    'font-bold', 'mb-4',
    
    // Clases específicas del proyecto
    'min-h-screen', 'max-w-7xl', 'mx-auto', 'flex-1', 'flex-shrink-0',
    'rounded-md', 'rounded-full', 'shadow-md', 'shadow-sm',
    'border-gray-200', 'border-gray-300', 'bg-gray-50', 'bg-gray-100', 'bg-gray-800', 'bg-gray-900',
    'text-gray-400', 'text-gray-500', 'text-gray-600', 'text-gray-700', 'text-gray-900',
    'hover:bg-gray-700', 'hover:bg-blue-700', 'hover:bg-green-700', 'hover:bg-red-700',
    'focus:ring-2', 'focus:ring-blue-500', 'focus:ring-offset-2',
    'transition-colors', 'transition-all', 'duration-200',
    'w-full', 'h-full', 'space-x-2', 'space-x-4', 'space-y-2', 'space-y-6', 'space-y-8',
    'grid', 'grid-cols-1', 'md:grid-cols-2', 'lg:grid-cols-3', 'gap-4', 'gap-6',
    'flex', 'items-center', 'justify-center', 'justify-between',
    'px-3', 'px-4', 'px-6', 'py-2', 'py-3', 'py-4', 'py-6', 'py-8', 'py-12',
    'mt-2', 'mt-4', 'mt-6', 'mt-8', 'mb-2', 'mb-4', 'mb-6', 'mb-8',
    'text-white', 'font-semibold', 'font-extrabold',
    'sr-only', 'hidden', 'block', 'inline-flex',
    'border', 'border-transparent'
  ],
  theme: {
    extend: {
      // Aquí puedes extender el tema por defecto
      colors: {
        // Colores personalizados para tu proyecto médico
        'medical': {
          'primary': '#164569',    // Color principal del proyecto
          'secondary': '#4b49c0',  // Color violeta secundario
          'blue': '#2563eb',
          'green': '#059669', 
          'red': '#dc2626',
        },
        // Colores extendidos con prefijo medical-
        'medical-primary': '#164569',
        'medical-secondary': '#4b49c0',
        'medical-success': '#10b981',
        'medical-warning': '#f59e0b',
        'medical-error': '#ef4444',
        'medical-info': '#3b82f6',
        'medical-light': '#f8fafc',
        'medical-dark': '#0f172a',
        // Mantener colores originales del proyecto
        'project-blue': '#164569',
        'project-purple': '#4b49c0',
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
  
  // IMPORTANTE: Configuración optimizada para Tailwind puro
  corePlugins: {
    // Habilitar preflight para estilos base de Tailwind
    preflight: true,
    // Habilitar container de Tailwind
    container: true,
  }
}
