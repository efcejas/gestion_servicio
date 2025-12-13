#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import sys
import django

# Set UTF-8 encoding for output
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_estudios.settings')
django.setup()

from protocolos.models import Protocolo

print('\n' + '='*80)
print('VERIFICACIÓN DE PROTOCOLOS PARA PÁGINA DE DECISIÓN CLÍNICA')
print('='*80 + '\n')

# Protocolos que busca la vista elegir_protocolo
protocolos_esperados = [
    'TC Hígado trifásico (caracterización de lesión focal)',
    'TC Riñón multifásico (renal mass protocol)',
    'TC Páncreas bifásico (fase pancreática + portal)',
    'Uro-TC hematuria (urograma CT)',
    'TC sangrado activo abdomen (arterial + portal)',
    'TC de abdomen y pelvis con contraste para dolor agudo',
    'Angio-TC para descarte de TEP',
    'Angio-TC cerebral (stroke code)',
    'Angio-TC Aorta (síndrome aórtico agudo)',
    'TC TAP con contraste EV para estadificación oncológica',
]

print('Protocolos esperados por la vista elegir_protocolo:\n')

protocolos_existentes = 0
protocolos_faltantes = 0

for nombre in protocolos_esperados:
    try:
        p = Protocolo.objects.get(nombre=nombre, es_activo=True)
        print(f'✅ EXISTE: {nombre}')
        print(f'   - ID: {p.id}, Modalidad: {p.modalidad.codigo}, Región: {p.region.codigo}')
        protocolos_existentes += 1
    except Protocolo.DoesNotExist:
        print(f'❌ FALTA:  {nombre}')
        protocolos_faltantes += 1
    except Protocolo.MultipleObjectsReturned:
        print(f'⚠️  DUPLICADO: {nombre} (hay múltiples protocolos con este nombre)')
        protocolos_existentes += 1
    print()

print('='*80)
print(f'\n📊 RESUMEN:')
print(f'  • Protocolos existentes: {protocolos_existentes}/{len(protocolos_esperados)}')
print(f'  • Protocolos faltantes: {protocolos_faltantes}/{len(protocolos_esperados)}')

if protocolos_faltantes > 0:
    print(f'\n⚠️  Algunos protocolos no están cargados. Se mostrarán como "No cargado aún".')
else:
    print(f'\n✅ Todos los protocolos están disponibles.')

print('\n✅ La página /protocolos/elegir/ está lista para usar\n')
