"""
SCRIPT DE VERIFICACIÓN VISUAL - Templates de Autenticación
===========================================================

Este script te ayuda a verificar visualmente todos los templates
de autenticación actualizados.

INSTRUCCIONES:
1. Asegúrate de que el servidor Django esté corriendo (python manage.py runserver)
2. Ejecuta este script: python scripts/verificar_templates_auth.py
3. Se abrirán automáticamente las URLs en tu navegador predeterminado
4. Verifica que todos los templates tengan diseño consistente

CHECKLIST VISUAL:
✓ Header con icono circular, título y subtítulo
✓ Card blanca con bordes grises y sombra
✓ Inputs con borde gray-300 y focus ring azul
✓ Botón primario azul (bg-blue-600)
✓ Mensajes de error/info con borde lateral de color
✓ Fondo gris claro (bg-gray-50)
"""

import webbrowser
import time

# URLs a verificar
AUTH_URLS = [
    {
        'name': '🔐 Login',
        'url': 'http://127.0.0.1:8000/accounts/login/',
        'checks': [
            'Header con icono fa-heartbeat',
            'Título "Bienvenido"',
            'Inputs de usuario y contraseña',
            'Botón "Iniciar Sesión" azul',
            'Links a "¿Olvidaste contraseña?" y "Regístrate"'
        ]
    },
    {
        'name': '📝 Registro',
        'url': 'http://127.0.0.1:8000/accounts/register/',
        'checks': [
            'Header con icono fa-user-plus',
            'Título "Crear Cuenta"',
            'Secciones con iconos de colores',
            'Grid de 2 columnas en pantallas grandes',
            'Botón "Crear Cuenta" azul'
        ]
    },
    {
        'name': '🔑 Recuperar Contraseña',
        'url': 'http://127.0.0.1:8000/accounts/password_reset/',
        'checks': [
            'Header con icono fa-key',
            'Alert azul con info sobre recuperación',
            'Input de email',
            'Botón "Enviar enlace de recuperación"',
            'Link para volver al login'
        ]
    },
    {
        'name': '🔒 Cambiar Contraseña',
        'url': 'http://127.0.0.1:8000/accounts/password_change/',
        'checks': [
            'Header con icono fa-lock',
            'Sección "Verificación de identidad"',
            'Sección "Nueva contraseña"',
            '3 inputs (actual, nueva, confirmar)',
            'Botones "Cambiar" y "Cancelar"'
        ]
    },
    {
        'name': '✏️ Completar Perfil',
        'url': 'http://127.0.0.1:8000/accounts/completar-perfil/',
        'checks': [
            'Header con icono fa-user-edit',
            'Progress bar (50%)',
            'Alert azul informativo',
            'Campo Rol con iconos',
            'Campo fecha_ingreso (visible solo para residentes)',
            'Card de info sobre roles al final'
        ],
        'note': 'REQUIERE LOGIN - Debes estar autenticado'
    },
    {
        'name': '👤 Editar Perfil',
        'url': 'http://127.0.0.1:8000/accounts/editar-perfil/',
        'checks': [
            'Avatar circular con inicial',
            'Badge de rol',
            '4 secciones: Personal, Profesional, Contacto, Preferencias',
            'Grid de 2 columnas',
            'Botones "Volver" y "Guardar Cambios"',
            'Alert sobre cambio de contraseña'
        ],
        'note': 'REQUIERE LOGIN - Debes estar autenticado'
    }
]

def print_header():
    print("\n" + "="*70)
    print("  VERIFICACIÓN VISUAL DE TEMPLATES DE AUTENTICACIÓN")
    print("="*70 + "\n")

def print_checklist(template):
    print(f"\n{template['name']}")
    print(f"URL: {template['url']}")
    if 'note' in template:
        print(f"⚠️  {template['note']}")
    print("\nCHECKLIST:")
    for check in template['checks']:
        print(f"  ☐ {check}")
    print()

def open_urls():
    print_header()
    
    print("📋 CHECKLIST GENERAL:")
    print("  ☐ Fondo gris claro (bg-gray-50)")
    print("  ☐ Cards blancas con bordes gray-200")
    print("  ☐ Sombras suaves (shadow-lg)")
    print("  ☐ Bordes redondeados (rounded-2xl)")
    print("  ☐ Inputs con focus ring azul")
    print("  ☐ Botones azules (bg-blue-600 hover:bg-blue-700)")
    print("  ☐ Iconos Font Awesome con colores temáticos")
    print("  ☐ Responsive (funciona en mobile)")
    print()
    
    response = input("¿Deseas abrir todas las URLs en el navegador? (s/n): ")
    
    if response.lower() != 's':
        print("\n❌ Verificación cancelada.")
        print("\nPuedes visitar manualmente las siguientes URLs:")
        for template in AUTH_URLS:
            print(f"  • {template['name']}: {template['url']}")
        return
    
    print("\n🚀 Abriendo templates en el navegador...")
    print("Espera 2 segundos entre cada URL para no saturar el navegador.\n")
    
    for i, template in enumerate(AUTH_URLS, 1):
        print(f"[{i}/{len(AUTH_URLS)}] Abriendo: {template['name']}")
        print_checklist(template)
        
        try:
            webbrowser.open(template['url'])
            if i < len(AUTH_URLS):
                time.sleep(2)
        except Exception as e:
            print(f"❌ Error al abrir URL: {e}")
    
    print("\n" + "="*70)
    print("✅ TODAS LAS URLs HAN SIDO ABIERTAS")
    print("="*70)
    print("\n📝 SIGUIENTE PASO:")
    print("  1. Revisa cada pestaña del navegador")
    print("  2. Verifica que el diseño sea consistente")
    print("  3. Prueba cambiar el tamaño de la ventana (responsive)")
    print("  4. Prueba enviar formularios con errores (ver mensajes de error)")
    print("\n💡 TIP: Usa Ctrl+Shift+I (Chrome) o F12 para inspeccionar elementos")
    print()

if __name__ == "__main__":
    try:
        open_urls()
    except KeyboardInterrupt:
        print("\n\n❌ Verificación interrumpida por el usuario.")
    except Exception as e:
        print(f"\n\n❌ Error inesperado: {e}")
