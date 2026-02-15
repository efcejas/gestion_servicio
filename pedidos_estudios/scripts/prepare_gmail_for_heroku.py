"""
Script helper para preparar credenciales de Gmail para Heroku.

Uso:
    python pedidos_estudios/scripts/prepare_gmail_for_heroku.py

Genera el valor que debes copiar en GMAIL_TOKEN_JSON de Heroku Config Vars.
"""
import json
import sys
from pathlib import Path


def prepare_token_for_heroku():
    """
    Lee token.json y lo prepara para usarse como variable de entorno en Heroku.
    """
    token_file = Path('token.json')
    
    print("="*70)
    print("🔑 Preparación de Credenciales Gmail para Heroku")
    print("="*70)
    print()
    
    # Verificar que existe token.json
    if not token_file.exists():
        print("❌ ERROR: No se encontró 'token.json' en la raíz del proyecto")
        print()
        print("📝 Primero debes generar el token localmente:")
        print("   1. Asegúrate de tener credentials.json")
        print("   2. Ejecuta: python manage.py shell")
        print("   3. Ejecuta: from pedidos_estudios.services.gmail_service import GmailService")
        print("   4. Ejecuta: g = GmailService()")
        print("   5. Se abrirá el navegador para autorizar")
        print("   6. Se generará token.json")
        print()
        return False
    
    try:
        # Leer token
        with open(token_file, 'r') as f:
            token_data = json.load(f)
        
        print("✅ token.json encontrado y leído correctamente")
        print()
        
        # Verificar que tiene refresh_token
        if 'refresh_token' not in token_data:
            print("⚠️  ADVERTENCIA: El token no contiene 'refresh_token'")
            print("   Esto puede causar problemas cuando el token expire.")
            print()
        
        # Convertir a formato compacto (una línea)
        token_json_compact = json.dumps(token_data, separators=(',', ':'))
        
        print("📋 Configuración para Heroku")
        print("-"*70)
        print()
        print("1. Ve a tu app en Heroku Dashboard")
        print("2. Settings → Config Vars → Reveal Config Vars")
        print("3. Agrega una nueva variable:")
        print()
        print("   Variable name:")
        print("   GMAIL_TOKEN_JSON")
        print()
        print("   Value (copia todo lo siguiente, sin comillas):")
        print()
        print("-"*70)
        print(token_json_compact)
        print("-"*70)
        print()
        
        # Guardar en archivo temporal para copiar fácilmente
        output_file = Path('token_for_heroku.txt')
        with open(output_file, 'w') as f:
            f.write(token_json_compact)
        
        print(f"✅ También guardado en: {output_file.absolute()}")
        print("   (Puedes copiar desde ese archivo)")
        print()
        
        # Información adicional
        print("📝 Información del token:")
        print(f"   - Client ID: {token_data.get('client_id', 'N/A')[:50]}...")
        print(f"   - Scopes: {', '.join(token_data.get('scopes', []))}")
        if 'expiry' in token_data:
            print(f"   - Expira: {token_data['expiry']}")
        print()
        
        print("✅ ¡Listo! Ahora copia el valor y pégalo en Heroku Config Vars")
        print()
        print("⚠️  IMPORTANTE:")
        print("   - NO subas token.json ni token_for_heroku.txt a Git")
        print("   - Estos archivos ya están en .gitignore")
        print("   - El token se renovará automáticamente cuando expire")
        print()
        
        return True
        
    except json.JSONDecodeError:
        print("❌ ERROR: token.json no es un JSON válido")
        return False
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False


def check_gitignore():
    """Verifica que los archivos sensibles estén en .gitignore"""
    gitignore = Path('.gitignore')
    
    if not gitignore.exists():
        print("⚠️  ADVERTENCIA: No se encontró .gitignore")
        return
    
    with open(gitignore, 'r') as f:
        content = f.read()
    
    required_entries = [
        'token.json',
        'credentials.json',
        '.env'
    ]
    
    missing = [entry for entry in required_entries if entry not in content]
    
    if missing:
        print("⚠️  ADVERTENCIA: Los siguientes archivos NO están en .gitignore:")
        for entry in missing:
            print(f"   - {entry}")
        print()
        print("   Agrégalos para evitar subir credenciales a Git!")
        print()


if __name__ == '__main__':
    check_gitignore()
    success = prepare_token_for_heroku()
    sys.exit(0 if success else 1)
