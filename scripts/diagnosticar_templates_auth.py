"""
Script de diagnóstico de templates de autenticación
Analiza todas las vistas, templates, layouts y CSS del flujo de autenticación
"""
import os
import re
from pathlib import Path

# Colores para terminal
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

BASE_DIR = Path(__file__).resolve().parent.parent

def extract_template_info(template_path):
    """Extrae información clave del template"""
    info = {
        'exists': False,
        'extends': None,
        'extends_line': None,
        'blocks': [],
        'static_loads': [],
        'css_classes': set(),
        'size': 0
    }
    
    if not os.path.exists(template_path):
        return info
    
    info['exists'] = True
    info['size'] = os.path.getsize(template_path)
    
    with open(template_path, 'r', encoding='utf-8') as f:
        content = f.read()
        lines = content.split('\n')
        
        # Buscar {% extends %}
        for i, line in enumerate(lines, 1):
            extends_match = re.search(r'{%\s*extends\s+[\'"](.+?)[\'"]\s*%}', line)
            if extends_match:
                info['extends'] = extends_match.group(1)
                info['extends_line'] = i
                break
        
        # Buscar {% block %}
        blocks = re.findall(r'{%\s*block\s+(\w+)\s*%}', content)
        info['blocks'] = list(set(blocks))
        
        # Buscar {% load static %}
        static_loads = re.findall(r'{%\s*load\s+(.+?)\s*%}', content)
        info['static_loads'] = static_loads
        
        # Detectar frameworks CSS
        if 'tailwind' in content.lower() or 'bg-' in content or 'flex' in content:
            info['css_classes'].add('Tailwind')
        if 'flowbite' in content.lower():
            info['css_classes'].add('Flowbite')
        if 'daisyui' in content.lower():
            info['css_classes'].add('DaisyUI')
        if 'bootstrap' in content.lower() or 'btn btn-' in content:
            info['css_classes'].add('Bootstrap')
    
    return info

def analyze_views():
    """Analiza las vistas de autenticación configuradas"""
    print(f"\n{Colors.HEADER}{'='*80}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}1. ANÁLISIS DE VISTAS DE AUTENTICACIÓN{Colors.ENDC}")
    print(f"{Colors.HEADER}{'='*80}{Colors.ENDC}\n")
    
    views_info = []
    
    # Analizar gestion_estudios/views.py
    views_file = BASE_DIR / 'gestion_estudios' / 'views.py'
    if views_file.exists():
        with open(views_file, 'r', encoding='utf-8') as f:
            content = f.read()
            
            # CustomLoginView
            login_match = re.search(r"class CustomLoginView.*?template_name = ['\"](.+?)['\"]", content, re.DOTALL)
            if login_match:
                views_info.append({
                    'url': 'accounts/login/',
                    'name': 'login',
                    'view': 'CustomLoginView',
                    'file': 'gestion_estudios.views',
                    'template': login_match.group(1)
                })
    
    # Analizar accounts/views.py
    accounts_views = BASE_DIR / 'accounts' / 'views.py'
    if accounts_views.exists():
        with open(accounts_views, 'r', encoding='utf-8') as f:
            content = f.read()
            
            # UserRegisterView
            register_match = re.search(r"class UserRegisterView.*?template_name = ['\"](.+?)['\"]", content, re.DOTALL)
            if register_match:
                views_info.append({
                    'url': 'accounts/register/',
                    'name': 'register',
                    'view': 'UserRegisterView',
                    'file': 'accounts.views',
                    'template': register_match.group(1)
                })
            
            # completar_perfil
            if 'def completar_perfil' in content:
                render_match = re.search(r"render\(request,\s*['\"](.+?)['\"]", content)
                if render_match:
                    views_info.append({
                        'url': 'accounts/completar-perfil/',
                        'name': 'completar_perfil',
                        'view': 'completar_perfil (function)',
                        'file': 'accounts.views',
                        'template': render_match.group(1)
                    })
            
            # editar_perfil
            if 'def editar_perfil' in content:
                views_info.append({
                    'url': 'accounts/editar-perfil/',
                    'name': 'editar_perfil',
                    'view': 'editar_perfil (function)',
                    'file': 'accounts.views',
                    'template': 'accounts/editar_perfil.html'
                })
    
    # Django auth views (password reset, etc.)
    django_views = [
        {'url': 'password_reset/', 'name': 'password_reset', 'view': 'CustomPasswordResetView', 'template': 'registration/password_reset_form.html'},
        {'url': 'password_reset/done/', 'name': 'password_reset_done', 'view': 'PasswordResetDoneView', 'template': 'registration/password_reset_done.html'},
        {'url': 'reset/<uidb64>/<token>/', 'name': 'password_reset_confirm', 'view': 'PasswordResetConfirmView', 'template': 'registration/password_reset_confirm.html'},
        {'url': 'reset/done/', 'name': 'password_reset_complete', 'view': 'PasswordResetCompleteView', 'template': 'registration/password_reset_complete.html'},
        {'url': 'password_change/', 'name': 'password_change', 'view': 'PasswordChangeView', 'template': 'registration/password_change_form.html'},
        {'url': 'password_change/done/', 'name': 'password_change_done', 'view': 'PasswordChangeDoneView', 'template': 'registration/password_change_done.html'},
    ]
    
    for view in django_views:
        view['file'] = 'django.contrib.auth.views'
        views_info.append(view)
    
    # Imprimir tabla
    print(f"{Colors.OKBLUE}{'URL':<35} {'View':<30} {'Template':<40}{Colors.ENDC}")
    print(f"{'-'*105}")
    for view in views_info:
        print(f"{view['url']:<35} {view['view']:<30} {view['template']:<40}")
    
    return views_info

def analyze_templates(views_info):
    """Analiza cada template en detalle"""
    print(f"\n{Colors.HEADER}{'='*80}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}2. ANÁLISIS DETALLADO DE TEMPLATES{Colors.ENDC}")
    print(f"{Colors.HEADER}{'='*80}{Colors.ENDC}\n")
    
    templates_dir = BASE_DIR / 'templates'
    
    for view in views_info:
        template_path = templates_dir / view['template']
        info = extract_template_info(template_path)
        
        print(f"\n{Colors.OKCYAN}{Colors.BOLD}📄 {view['template']}{Colors.ENDC}")
        print(f"   URL: {view['url']}")
        print(f"   View: {view['view']}")
        
        if info['exists']:
            print(f"   {Colors.OKGREEN}✓ Existe{Colors.ENDC} ({info['size']} bytes)")
            
            if info['extends']:
                print(f"   {Colors.BOLD}Extends:{Colors.ENDC} {info['extends']} (línea {info['extends_line']})")
            else:
                print(f"   {Colors.WARNING}⚠ No extiende ningún layout{Colors.ENDC}")
            
            if info['blocks']:
                print(f"   Blocks: {', '.join(info['blocks'])}")
            
            if info['static_loads']:
                print(f"   Loads: {', '.join(info['static_loads'])}")
            
            if info['css_classes']:
                frameworks = ', '.join(info['css_classes'])
                print(f"   CSS Frameworks: {frameworks}")
        else:
            print(f"   {Colors.FAIL}✗ NO EXISTE{Colors.ENDC}")

def detect_duplicates():
    """Detecta templates duplicados"""
    print(f"\n{Colors.HEADER}{'='*80}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}3. DETECCIÓN DE DUPLICADOS{Colors.ENDC}")
    print(f"{Colors.HEADER}{'='*80}{Colors.ENDC}\n")
    
    templates_dir = BASE_DIR / 'templates'
    template_files = {}
    
    # Buscar todos los archivos HTML
    for root, dirs, files in os.walk(templates_dir):
        for file in files:
            if file.endswith('.html'):
                full_path = Path(root) / file
                rel_path = full_path.relative_to(templates_dir)
                
                # Agrupar por nombre de archivo
                if file not in template_files:
                    template_files[file] = []
                template_files[file].append(str(rel_path))
    
    # Reportar duplicados
    duplicates_found = False
    for filename, paths in template_files.items():
        if len(paths) > 1:
            duplicates_found = True
            print(f"{Colors.WARNING}⚠ Duplicado: {filename}{Colors.ENDC}")
            for path in paths:
                size = os.path.getsize(templates_dir / path)
                print(f"   - templates/{path} ({size} bytes)")
    
    if not duplicates_found:
        print(f"{Colors.OKGREEN}✓ No se encontraron templates duplicados{Colors.ENDC}")

def analyze_layouts():
    """Analiza los layouts base"""
    print(f"\n{Colors.HEADER}{'='*80}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}4. ANÁLISIS DE LAYOUTS BASE{Colors.ENDC}")
    print(f"{Colors.HEADER}{'='*80}{Colors.ENDC}\n")
    
    layouts_dir = BASE_DIR / 'templates' / 'layouts'
    
    if not layouts_dir.exists():
        print(f"{Colors.FAIL}✗ Directorio layouts/ no existe{Colors.ENDC}")
        return
    
    for layout_file in layouts_dir.glob('*.html'):
        print(f"\n{Colors.OKCYAN}{Colors.BOLD}📐 {layout_file.name}{Colors.ENDC}")
        
        with open(layout_file, 'r', encoding='utf-8') as f:
            content = f.read()
            
            # Buscar bloques definidos
            blocks = re.findall(r'{%\s*block\s+(\w+)\s*%}', content)
            print(f"   Blocks definidos: {', '.join(set(blocks))}")
            
            # Buscar CSS/JS includes
            css_links = re.findall(r'<link[^>]*href=["\']([^"\']+)["\'][^>]*>', content)
            js_scripts = re.findall(r'<script[^>]*src=["\']([^"\']+)["\'][^>]*>', content)
            
            if css_links:
                print(f"   CSS: {len(css_links)} archivos")
                for css in css_links[:3]:  # Mostrar solo primeros 3
                    print(f"      - {css}")
            
            if js_scripts:
                print(f"   JS: {len(js_scripts)} archivos")
                for js in js_scripts[:3]:
                    print(f"      - {js}")

def generate_report():
    """Genera el reporte completo y plan de acción"""
    print(f"\n{Colors.HEADER}{'='*80}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}5. PLAN DE ACCIÓN (RECOMENDACIONES){Colors.ENDC}")
    print(f"{Colors.HEADER}{'='*80}{Colors.ENDC}\n")
    
    recommendations = [
        {
            'title': 'Unificar layout base',
            'description': 'Usar layouts/base_tailwind.html como único layout para autenticación',
            'actions': [
                'Verificar que base_tailwind.html incluye Tailwind CSS completo',
                'Asegurar que tiene blocks: title, extra_css, content, extra_js',
                'Incluir Font Awesome y assets comunes en el base'
            ]
        },
        {
            'title': 'Migrar templates a estructura consistente',
            'description': 'Todos los templates deben extender el mismo layout',
            'actions': [
                'Cambiar todos {% extends "..." %} a "layouts/base_tailwind.html"',
                'Asegurar estructura: {% block title %}, {% block content %}',
                'Usar clases Tailwind consistentes (same padding, shadows, borders)'
            ]
        },
        {
            'title': 'Eliminar duplicados',
            'description': 'Mantener solo una versión de cada template',
            'actions': [
                'Si hay login.html Y login_tailwind.html, eliminar login.html',
                'Si hay register.html Y register_tailwind.html, eliminar register.html',
                'Verificar que las vistas apuntan a la versión correcta'
            ]
        },
        {
            'title': 'Estandarizar CSS/componentes',
            'description': 'Usar mismo estilo en todos los formularios',
            'actions': [
                'Botones: bg-blue-600 hover:bg-blue-700 rounded-lg shadow',
                'Inputs: border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
                'Cards: bg-white rounded-lg shadow-md p-6',
                'Alerts: border-l-4 p-4 rounded (blue=info, red=error, yellow=warning)'
            ]
        }
    ]
    
    for i, rec in enumerate(recommendations, 1):
        print(f"{Colors.OKGREEN}{Colors.BOLD}{i}. {rec['title']}{Colors.ENDC}")
        print(f"   {rec['description']}\n")
        for action in rec['actions']:
            print(f"   • {action}")
        print()

if __name__ == '__main__':
    print(f"\n{Colors.BOLD}{'='*80}{Colors.ENDC}")
    print(f"{Colors.BOLD}DIAGNÓSTICO DE TEMPLATES DE AUTENTICACIÓN{Colors.ENDC}")
    print(f"{Colors.BOLD}{'='*80}{Colors.ENDC}")
    
    views_info = analyze_views()
    analyze_templates(views_info)
    detect_duplicates()
    analyze_layouts()
    generate_report()
    
    print(f"\n{Colors.BOLD}{'='*80}{Colors.ENDC}")
    print(f"{Colors.OKGREEN}{Colors.BOLD}✓ Diagnóstico completado{Colors.ENDC}")
    print(f"{Colors.BOLD}{'='*80}{Colors.ENDC}\n")
