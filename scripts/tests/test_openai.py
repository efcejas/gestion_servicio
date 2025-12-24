"""
Script de prueba para verificar la conexión con OpenAI
"""
import os
import sys
import django

# Configurar Django
sys.path.append(r'C:\Dev\GitHub\gestion_servicio')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_estudios.settings')
django.setup()

from dictado_informes.ai_services import ai_service

print("=" * 60)
print("PRUEBA DE CONEXIÓN CON OPENAI")
print("=" * 60)

# 1. Verificar si la API key está configurada
print("\n1. Verificando API Key...")
if ai_service.enabled:
    print("   ✅ API Key configurada correctamente")
else:
    print("   ❌ API Key NO configurada")
    print("   Por favor configura OPENAI_API_KEY en tu archivo .env")
    sys.exit(1)

# 2. Probar mejora de texto (más rápido que transcripción)
print("\n2. Probando mejora de texto con GPT-4...")
texto_prueba = """
paciente masculino 45 años resonancia cerebro sin contraste
no lesiones focales ventrículos normales todo normal
"""

print(f"   Texto original: {texto_prueba.strip()}")
print("   Procesando con IA...")

try:
    resultado = ai_service.improve_medical_text(
        texto_prueba,
        tipo_estudio='RES'
    )
    
    if 'error' in resultado:
        print(f"   ❌ Error: {resultado['error']}")
    else:
        print("   ✅ Texto mejorado exitosamente!")
        print("\n" + "=" * 60)
        print("TEXTO MEJORADO:")
        print("=" * 60)
        print(resultado['texto_mejorado'])
        print("=" * 60)
        print(f"\nConfianza: {resultado['confianza']:.2f}")
        print(f"Sugerencias: {', '.join(resultado.get('sugerencias', []))}")
        
except Exception as e:
    print(f"   ❌ Error inesperado: {str(e)}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("FIN DE LA PRUEBA")
print("=" * 60)
