#!/usr/bin/env python
"""Script para regenerar token de Gmail"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_estudios.settings')
django.setup()

from pedidos_estudios.services.gmail_service import GmailService

print("🔐 Iniciando proceso de autorización OAuth...")
print("📌 Se abrirá tu navegador para autorizar el acceso")
print("")

try:
    gmail = GmailService()
    print("✅ Token generado exitosamente!")
    print("📁 Archivo token.json actualizado")
except Exception as e:
    print(f"❌ Error: {e}")
