"""
Script simple para entender cómo funciona el sistema de emails en Django.
Ejecutar: python test_email_simple.py
"""

import os
import sys
import django

# Configurar Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_estudios.settings')
django.setup()

from django.core.mail import send_mail
from django.conf import settings

print("\n" + "="*70)
print("  🧪 PRUEBA SIMPLE DE EMAIL")
print("="*70 + "\n")

# Mostrar configuración actual
print("📋 Tu configuración actual:")
print(f"   Backend: {settings.EMAIL_BACKEND}")
print(f"   Host: {settings.EMAIL_HOST}")
print(f"   Port: {settings.EMAIL_PORT}")
print(f"   From: {settings.DEFAULT_FROM_EMAIL}")
print("\n")

# Explicar qué backend está usando
if 'console' in settings.EMAIL_BACKEND:
    print("✅ Estás usando Console Backend")
    print("   → El email se mostrará aquí en la terminal (no se envía realmente)")
elif 'filebased' in settings.EMAIL_BACKEND:
    print("✅ Estás usando File Backend")
    print("   → El email se guardará en un archivo (no se envía realmente)")
else:
    print("⚠️  Estás usando SMTP Backend")
    print("   → Esto intentará enviar un email REAL")
    respuesta = input("\n¿Continuar? (s/n): ")
    if respuesta.lower() != 's':
        print("Abortado.")
        sys.exit(0)

print("\n" + "-"*70)
print("📤 Enviando email de prueba...")
print("-"*70 + "\n")

# Intentar enviar email
try:
    resultado = send_mail(
        subject='🧪 Email de Prueba',
        message='Este es un mensaje de prueba.\n\n¡Si ves esto, funciona!',
        from_email='sistema@example.com',
        recipient_list=['destino@example.com'],
        fail_silently=False,
    )
    
    print("✅ ¡Email enviado exitosamente!")
    print(f"   Emails enviados: {resultado}")
    
    if 'console' in settings.EMAIL_BACKEND:
        print("\n💡 Busca el contenido del email ARRIBA en esta terminal")
    elif 'filebased' in settings.EMAIL_BACKEND:
        print(f"\n💡 El email se guardó en: {getattr(settings, 'EMAIL_FILE_PATH', 'carpeta configurada')}")
    
except Exception as e:
    print(f"❌ Error: {e}")
    print(f"   Tipo: {type(e).__name__}")

print("\n" + "="*70 + "\n")
