#!/usr/bin/env python
"""Script rápido para testear el parser de emails"""
import sys
import os

# Setup Django
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_estudios.settings')

import django
django.setup()

from pedidos_estudios.services.email_parser import EmailParser
from datetime import datetime

# Email de prueba (formato del usuario)
email_test = {
    'message_id': 'test-001',
    'asunto': 'Pedido de estudio',
    'remitente': 'test@sanatorio.com',
    'fecha': datetime.now(),
    'cuerpo_texto': """Paciente: Juan Pérez
DNI: 12345678
Historia Clínica: HC-98765
Habitación: 301
Cama: A
Piso: 3
Estudio solicitado: Ecodoppler de Miembros Inferiores
Urgente - favor realizar hoy
Médico solicitante: Dr. García
""",
    'cuerpo_html': '',
    'adjuntos': []
}

# Parsear
parser = EmailParser()
resultado = parser.parsear_email(email_test)

# Mostrar resultados
print("=" * 60)
print("RESULTADOS DEL PARSER")
print("=" * 60)

print("\n📋 PACIENTE:")
for key, value in resultado['paciente'].items():
    status = "✓" if value else "✗"
    print(f"  {status} {key}: {value}")

print("\n🔬 ESTUDIO:")
for key, value in resultado['estudio'].items():
    status = "✓" if value else "✗"
    print(f"  {status} {key}: {value}")

print(f"\n⚠️  PRIORIDAD: {resultado['prioridad']}")

if resultado['errores']:
    print("\n❌ ERRORES:")
    for error in resultado['errores']:
        print(f"  - {error}")
else:
    print("\n✅ Sin errores")

print("\n" + "=" * 60)
