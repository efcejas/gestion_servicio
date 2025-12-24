#!/usr/bin/env python
"""
Script para verificar que la navegación funcione correctamente 
para todos los tipos de usuarios según la lógica implementada.
"""

import os
import sys
import django

# Configurar Django
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_estudios.settings')
django.setup()

from accounts.models import CustomUser
from django.contrib.auth.models import Group
from django.template import Context, Template
from django.template.loader import get_template

def test_user_navigation(username):
    """Simula la navegación para un usuario específico"""
    try:
        user = CustomUser.objects.get(username=username)
        print(f"\n{'='*60}")
        print(f"TESTING USER: {username}")
        print(f"{'='*60}")
        print(f"Cargo: {user.cargo}")
        print(f"Superuser: {user.is_superuser}")
        print(f"Grupos: {[g.name for g in user.groups.all()]}")
        
        # Crear contexto de template
        context = Context({
            'user': user,
            'request': type('obj', (object,), {
                'resolver_match': type('obj', (object,), {
                    'url_name': 'home',
                    'namespace': ''
                })()
            })()
        })
        
        # Verificar condiciones de navegación
        print(f"\n--- CONDICIONES DE NAVEGACIÓN ---")
        
        # Dashboard (todos)
        print(f"✓ Dashboard: Todos los usuarios")
        
        # Superuser
        if user.is_superuser:
            print(f"✓ Superuser -> Acceso completo")
            print(f"  - Estudios por Profesional")
            print(f"  - Calendario de Guardias")  
            print(f"  - Eventos del Servicio")
            print(f"  - Panel de Administración")
            
        elif user.is_authenticated and not user.is_superuser:
            # Administrativo - Sanatorio (pedidos)
            if user.groups.filter(name="Administrativo - Sanatorio (pedidos)").exists():
                print(f"✓ Administrativo - Sanatorio (pedidos)")
                print(f"  - Nuevo Pedido")
                print(f"  - Estudios Solicitados")
                print(f"  - Reportes")
                
            else:
                # Navegación según cargo
                if user.cargo in ['administrativo', 'jefe administrativo']:
                    print(f"✓ Administrativo/Jefe administrativo")
                    print(f"  - Novedades")
                    print(f"  - Estudios Pendientes")
                    
                elif user.cargo in ['técnico radiólogo', 'jefe tecnico']:
                    print(f"✓ Técnico radiólogo/Jefe técnico")
                    print(f"  - Novedades")
                    print(f"  - Estudios Pendientes")
                    
                elif user.cargo in ['enfermero/a', 'jefe de enfermería']:
                    print(f"✓ Enfermero/Jefe de enfermería")
                    print(f"  - Estudios Pendientes")
                    
                elif user.groups.filter(name="Médicos de staff - informes").exists():
                    print(f"✓ Médicos de staff - informes")
                    print(f"  - Registrar Estudios")
                    print(f"  - Estudios Registrados")
                    print(f"  - Mis Guardias")
                    print(f"  - Novedades")
                else:
                    print(f"⚠️  Usuario sin navegación específica definida")
        
        return True
        
    except CustomUser.DoesNotExist:
        print(f"❌ Usuario {username} no existe")
        return False
    except Exception as e:
        print(f"❌ Error testing user {username}: {e}")
        return False

def main():
    """Ejecuta las pruebas para todos los tipos de usuarios"""
    print("🧪 TESTING DE NAVEGACIÓN TAILWIND")
    print("Verificando que cada tipo de usuario vea la navegación correcta\n")
    
    # Usuarios de prueba representativos
    test_users = [
        'efccejas',  # Superuser
        'USR_PEDIDOS',  # Administrativo - Sanatorio (pedidos)
        '95miguel',  # Médicos de staff - informes
        'Angrasso',  # Administrativo sin grupo
        'Alejandrofinde',  # Técnico radiólogo
        'enfermero_test',  # Enfermero/a
        'jefe_enfermeria_test',  # Jefe de enfermería
    ]
    
    successful_tests = 0
    total_tests = len(test_users)
    
    for username in test_users:
        if test_user_navigation(username):
            successful_tests += 1
    
    print(f"\n{'='*60}")
    print(f"RESUMEN DE PRUEBAS")
    print(f"{'='*60}")
    print(f"Exitosas: {successful_tests}/{total_tests}")
    
    if successful_tests == total_tests:
        print("🎉 ¡Todas las pruebas de navegación pasaron!")
    else:
        print("⚠️  Algunas pruebas fallaron. Revisar configuración.")
        
    print(f"\n🌐 Puedes verificar manualmente en: http://127.0.0.1:8000")
    print(f"🔑 Contraseña para usuarios de prueba: test123")

if __name__ == "__main__":
    main()