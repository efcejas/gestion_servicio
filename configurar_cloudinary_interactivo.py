"""
Script interactivo para configurar Cloudinary
Ejecutar: python configurar_cloudinary_interactivo.py
"""
import os
import sys

def print_header(text):
    print("\n" + "="*70)
    print(f"  {text}")
    print("="*70 + "\n")

def print_step(num, text):
    print(f"\n📍 PASO {num}: {text}")
    print("-" * 70)

def print_success(text):
    print(f"✅ {text}")

def print_error(text):
    print(f"❌ {text}")

def print_info(text):
    print(f"ℹ️  {text}")

def verificar_env_existe():
    """Verificar si existe el archivo .env"""
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    return os.path.exists(env_path), env_path

def leer_env_actual(env_path):
    """Leer configuración actual de .env"""
    config = {}
    if os.path.exists(env_path):
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if '=' in line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    config[key.strip()] = value.strip()
    return config

def verificar_cloudinary_configurado(config):
    """Verificar si Cloudinary ya está configurado"""
    required = ['CLOUDINARY_CLOUD_NAME', 'CLOUDINARY_API_KEY', 'CLOUDINARY_API_SECRET']
    configurado = all(config.get(key) for key in required)
    return configurado

def obtener_credenciales():
    """Solicitar credenciales al usuario de forma interactiva"""
    print_info("Necesito las 3 credenciales de tu Dashboard de Cloudinary")
    print_info("Están en: Account Details → Product Environment Credentials")
    print()
    
    cloud_name = input("🔹 Cloud name (ej: dxxxxxxxxxxxxx): ").strip()
    api_key = input("🔹 API Key (ej: 123456789012345): ").strip()
    api_secret = input("🔹 API Secret (ej: abcdefg...): ").strip()
    
    return cloud_name, api_key, api_secret

def validar_credenciales(cloud_name, api_key, api_secret):
    """Validar que las credenciales tengan formato correcto"""
    errores = []
    
    if not cloud_name:
        errores.append("Cloud name está vacío")
    elif len(cloud_name) < 5:
        errores.append("Cloud name parece muy corto")
    
    if not api_key:
        errores.append("API Key está vacío")
    elif not api_key.isdigit() or len(api_key) < 10:
        errores.append("API Key debe ser numérico y largo (ej: 123456789012345)")
    
    if not api_secret:
        errores.append("API Secret está vacío")
    elif len(api_secret) < 10:
        errores.append("API Secret parece muy corto")
    
    return errores

def actualizar_env(env_path, cloud_name, api_key, api_secret):
    """Actualizar archivo .env con las credenciales"""
    # Leer contenido actual
    lines = []
    if os.path.exists(env_path):
        with open(env_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    
    # Buscar si ya existen las variables
    has_cloudinary = any('CLOUDINARY' in line for line in lines)
    
    # Si no existe sección Cloudinary, agregarla
    if not has_cloudinary:
        lines.append("\n")
        lines.append("# ==============================================================================\n")
        lines.append("# CLOUDINARY CONFIGURATION\n")
        lines.append("# ==============================================================================\n")
        lines.append(f"CLOUDINARY_CLOUD_NAME={cloud_name}\n")
        lines.append(f"CLOUDINARY_API_KEY={api_key}\n")
        lines.append(f"CLOUDINARY_API_SECRET={api_secret}\n")
    else:
        # Actualizar valores existentes
        new_lines = []
        for line in lines:
            if 'CLOUDINARY_CLOUD_NAME=' in line:
                new_lines.append(f"CLOUDINARY_CLOUD_NAME={cloud_name}\n")
            elif 'CLOUDINARY_API_KEY=' in line:
                new_lines.append(f"CLOUDINARY_API_KEY={api_key}\n")
            elif 'CLOUDINARY_API_SECRET=' in line:
                new_lines.append(f"CLOUDINARY_API_SECRET={api_secret}\n")
            else:
                new_lines.append(line)
        lines = new_lines
    
    # Escribir archivo actualizado
    with open(env_path, 'w', encoding='utf-8') as f:
        f.writelines(lines)

def main():
    print_header("🌩️  CONFIGURADOR INTERACTIVO DE CLOUDINARY")
    
    print("Este script te ayudará a configurar Cloudinary paso a paso.\n")
    
    # PASO 1: Verificar archivo .env
    print_step(1, "Verificando archivo .env")
    env_existe, env_path = verificar_env_existe()
    
    if not env_existe:
        print_error(f"No se encontró el archivo .env en: {env_path}")
        print_info("Necesitas crear un archivo .env en la raíz del proyecto")
        print_info("Puedes copiarlo de .env.example si existe")
        return False
    
    print_success(f"Archivo .env encontrado: {env_path}")
    
    # PASO 2: Verificar configuración actual
    print_step(2, "Verificando configuración actual")
    config_actual = leer_env_actual(env_path)
    ya_configurado = verificar_cloudinary_configurado(config_actual)
    
    if ya_configurado:
        print_info("Cloudinary YA está configurado:")
        print(f"  • Cloud name: {config_actual['CLOUDINARY_CLOUD_NAME']}")
        print(f"  • API Key: {config_actual['CLOUDINARY_API_KEY'][:5]}***")
        print(f"  • API Secret: ***{config_actual['CLOUDINARY_API_SECRET'][-5:]}")
        print()
        respuesta = input("¿Deseas reconfigurar? (s/n): ").lower()
        if respuesta != 's':
            print_info("Configuración mantenida. Saliendo...")
            return True
    else:
        print_info("Cloudinary NO está configurado aún")
    
    # PASO 3: Instrucciones para obtener credenciales
    print_step(3, "Obtener credenciales de Cloudinary")
    print()
    print("Para obtener tus credenciales:")
    print("  1. Ve a: https://cloudinary.com/")
    print("  2. Si no tienes cuenta, crea una gratis: https://cloudinary.com/users/register_free")
    print("  3. Inicia sesión y ve al Dashboard")
    print("  4. En 'Account Details' verás:")
    print("     - Cloud name")
    print("     - API Key")
    print("     - API Secret")
    print()
    
    input("Presiona ENTER cuando tengas las credenciales listas...")
    
    # PASO 4: Solicitar credenciales
    print_step(4, "Ingresar credenciales")
    cloud_name, api_key, api_secret = obtener_credenciales()
    
    # PASO 5: Validar credenciales
    print_step(5, "Validando credenciales")
    errores = validar_credenciales(cloud_name, api_key, api_secret)
    
    if errores:
        print_error("Se encontraron problemas:")
        for error in errores:
            print(f"  • {error}")
        print()
        respuesta = input("¿Continuar de todos modos? (s/n): ").lower()
        if respuesta != 's':
            print_info("Configuración cancelada")
            return False
    else:
        print_success("Credenciales válidas")
    
    # PASO 6: Guardar en .env
    print_step(6, "Guardando en .env")
    
    try:
        actualizar_env(env_path, cloud_name, api_key, api_secret)
        print_success("Archivo .env actualizado correctamente")
    except Exception as e:
        print_error(f"Error al actualizar .env: {e}")
        return False
    
    # PASO 7: Instrucciones finales
    print_step(7, "Próximos pasos")
    print()
    print_success("¡Cloudinary configurado exitosamente!")
    print()
    print("Ahora necesitas:")
    print("  1. REINICIAR el servidor Django:")
    print("     • Si está corriendo, presiona Ctrl+C")
    print("     • Luego ejecuta: python manage.py runserver")
    print()
    print("  2. Verificar que aparezca:")
    print("     ✓ Cloudinary configurado correctamente")
    print()
    print("  3. Probar subir una clase con archivo:")
    print("     http://localhost:8000/clases/")
    print()
    print_info("Si algo falla, revisa TESTING_CLOUDINARY_QUICKSTART.md")
    
    return True

if __name__ == '__main__':
    try:
        print("\n" + "🌟" * 35)
        success = main()
        print("\n" + "🌟" * 35 + "\n")
        
        if success:
            print("✅ Configuración completada con éxito")
        else:
            print("⚠️  Configuración incompleta o cancelada")
        
        input("\nPresiona ENTER para salir...")
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Configuración interrumpida por el usuario")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Error inesperado: {e}")
        import traceback
        traceback.print_exc()
        input("\nPresiona ENTER para salir...")
        sys.exit(1)
