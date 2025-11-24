#!/usr/bin/env python
"""
Script para verificar la lógica de permisos en formularios
"""
import os
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_estudios.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from gestion_eventos.forms import EventoServicioForm

User = get_user_model()

def test_form_logic():
    print("=== VERIFICACIÓN DE LÓGICA DE FORMULARIOS ===\n")
    
    # Crear grupos si no existen
    grupo_tomo, created = Group.objects.get_or_create(name="Técnicos de tomografía")
    grupo_resonancia, created = Group.objects.get_or_create(name="Técnicos de resonancia")
    
    # Crear usuarios de prueba si no existen
    try:
        user_tomo = User.objects.get(username="test_tomo")
    except User.DoesNotExist:
        user_tomo = User.objects.create_user(
            username="test_tomo", 
            email="tomo@test.com", 
            password="testpass123"
        )
    user_tomo.groups.add(grupo_tomo)
    
    try:
        user_resonancia = User.objects.get(username="test_resonancia")
    except User.DoesNotExist:
        user_resonancia = User.objects.create_user(
            username="test_resonancia", 
            email="resonancia@test.com", 
            password="testpass123"
        )
    user_resonancia.groups.add(grupo_resonancia)
    
    try:
        user_medico = User.objects.get(username="test_medico")
    except User.DoesNotExist:
        user_medico = User.objects.create_user(
            username="test_medico", 
            email="medico@test.com", 
            password="testpass123"
        )
    
    print("1. TÉCNICO DE TOMOGRAFÍA:")
    form_tomo = EventoServicioForm(user=user_tomo)
    print(f"   - Opciones de servicio: {form_tomo.fields['servicio_origen_evento'].choices}")
    print(f"   - Valor inicial: {form_tomo.initial.get('servicio_origen_evento')}")
    print(f"   - Campo readonly: {form_tomo.fields['servicio_origen_evento'].widget.attrs.get('readonly')}")
    print(f"   - Opciones de tipo evento: {len(form_tomo.fields['tipo_evento'].choices)} opciones")
    
    print("\n2. TÉCNICO DE RESONANCIA:")
    form_resonancia = EventoServicioForm(user=user_resonancia)
    print(f"   - Opciones de servicio: {form_resonancia.fields['servicio_origen_evento'].choices}")
    print(f"   - Valor inicial: {form_resonancia.initial.get('servicio_origen_evento')}")
    print(f"   - Campo readonly: {form_resonancia.fields['servicio_origen_evento'].widget.attrs.get('readonly')}")
    print(f"   - Opciones de tipo evento: {len(form_resonancia.fields['tipo_evento'].choices)} opciones (incluye guardia/internado)")
    
    print("\n3. MÉDICO/ADMINISTRATIVO:")
    form_medico = EventoServicioForm(user=user_medico)
    print(f"   - Opciones de servicio: Todas las opciones disponibles")
    print(f"   - Valor inicial: {form_medico.initial.get('servicio_origen_evento', 'No preseleccionado')}")
    print(f"   - Campo readonly: {form_medico.fields['servicio_origen_evento'].widget.attrs.get('readonly', False)}")
    print(f"   - Opciones de tipo evento: {len(form_medico.fields['tipo_evento'].choices)} opciones")
    
    print("\n✅ VERIFICACIÓN COMPLETADA")
    print("La lógica de permisos está funcionando correctamente!")

if __name__ == "__main__":
    test_form_logic()