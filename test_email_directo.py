"""
Test directo: enviar email a tu cuenta de Gmail
"""
import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_estudios.settings')
django.setup()

from django.core.mail import send_mail
from django.conf import settings

print("\n" + "="*70)
print("  📧 TEST: Enviar email a tu cuenta")
print("="*70 + "\n")

print(f"Configuración:")
print(f"  Backend: {settings.EMAIL_BACKEND}")
print(f"  Host: {settings.EMAIL_HOST}")
print(f"  User: {settings.EMAIL_HOST_USER}")
print(f"  From: {settings.DEFAULT_FROM_EMAIL}")
print(f"  Password configurado: {'✓' if settings.EMAIL_HOST_PASSWORD else '✗'}")
print()

destinatario = "ensofermincejas@gmail.com"
print(f"📤 Enviando email de prueba a: {destinatario}")
print("-"*70)

try:
    resultado = send_mail(
        subject='🧪 TEST - Sistema de Recuperación de Contraseñas',
        message='''¡Hola!

Este es un email de prueba del sistema de gestión.

Si recibiste este email, significa que la configuración está funcionando correctamente.

✅ Gmail SMTP está configurado
✅ La App Password es correcta
✅ El sistema puede enviar emails

Saludos,
Sistema de Gestión
''',
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[destinatario],
        fail_silently=False,
    )
    
    print("\n✅ EMAIL ENVIADO EXITOSAMENTE!")
    print(f"   Resultado: {resultado} email(s) enviado(s)")
    print("\n📋 Ahora verifica:")
    print("   1. Bandeja de entrada de Gmail")
    print("   2. Carpeta de SPAM/Correo no deseado")
    print("   3. Puede tardar 1-2 minutos en llegar")
    print()
    
except Exception as e:
    print("\n❌ ERROR al enviar email:")
    print(f"   Tipo: {type(e).__name__}")
    print(f"   Mensaje: {str(e)}")
    print()
    
    if 'authentication' in str(e).lower():
        print("🔧 SOLUCIÓN:")
        print("   La App Password parece incorrecta.")
        print("   1. Ve a: https://myaccount.google.com/apppasswords")
        print("   2. Elimina la App Password anterior")
        print("   3. Crea una nueva")
        print("   4. Actualiza el .env con la nueva contraseña (sin espacios)")
    elif 'connection' in str(e).lower():
        print("🔧 SOLUCIÓN:")
        print("   Problema de conexión.")
        print("   1. Verifica tu internet")
        print("   2. Intenta con otra red WiFi")
        print("   3. Algunos ISP bloquean puerto 587")

print("="*70 + "\n")
