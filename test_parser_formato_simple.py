# -*- coding: utf-8 -*-
"""
Script para probar el parser con formato simple.
"""
from pedidos_estudios.services.email_parser import EmailParser

# Texto de ejemplo - formato simple
texto_email = """
Pac: Lopez Juan
DNI 25123456
Hab 310-2
Ecodoppler MMSS derecho
Indicación: fístula para HD
Dr Martinez
"""

print("\n=== TEST PARSER - FORMATO SIMPLE ===\n")
print("Texto original:")
print(texto_email)
print("\n" + "="*60 + "\n")

# Crear parser
parser = EmailParser()

# Datos simulados del email
email_data = {
    'message_id': 'test-12345',
    'asunto': 'Pedido de estudio',
    'remitente': 'test@example.com',
    'fecha': None,
    'adjuntos': [],
    'cuerpo_texto': texto_email,
    'cuerpo_html': None
}

# Parsear
resultado = parser.parsear_email(email_data)

print("📋 DATOS DEL PACIENTE:")
paciente = resultado['paciente']
for campo, valor in paciente.items():
    if valor:
        print(f"  • {campo}: {valor}")
    else:
        print(f"  ✗ {campo}: No detectado")

print("\n📊 DATOS DEL ESTUDIO:")
estudio = resultado['estudio']
for campo, valor in estudio.items():
    if valor:
        print(f"  • {campo}: {valor}")
    else:
        print(f"  ✗ {campo}: No detectado")

print(f"\n⚠️  PRIORIDAD: {resultado['prioridad']}")

if resultado['errores']:
    print(f"\n❌ ERRORES ({len(resultado['errores'])}):")
    for error in resultado['errores']:
        print(f"  • {error}")
else:
    print("\n✅ Sin errores detectados")

print("\n" + "="*60)

# Verificar detección de tipo de estudio
tipo_detectado = estudio.get('tipo_estudio_sugerido')
descripcion = estudio.get('descripcion_estudio')

print(f"\n🔍 ANÁLISIS:")
print(f"  Descripción extraída: '{descripcion}'")
print(f"  Tipo clasificado: '{tipo_detectado}'")

if tipo_detectado:
    print(f"\n✅ ÉXITO: Tipo de estudio detectado correctamente")
else:
    print(f"\n❌ FALLO: No se pudo clasificar el tipo de estudio")

print("\n")
