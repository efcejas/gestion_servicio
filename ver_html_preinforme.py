#!/usr/bin/env python
"""Verificar HTML del preinforme en revisión"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_estudios.settings')
django.setup()

from preinformes.models import RevisionPreinforme

numero = sys.argv[1] if len(sys.argv) > 1 else '2025-002345'

r = RevisionPreinforme.objects.filter(preinforme__numero_estudio=numero).first()

if not r:
    print(f'❌ No se encontró revisión para {numero}')
    sys.exit(1)

html = r.informe_final_html

print('='*80)
print(f'📄 Preinforme: {numero}')
print('='*80)
print('\n📊 Análisis:')
print(f'   Total caracteres: {len(html)}')
print(f'   Párrafos <p>: {html.count("<p>")}')
print(f'   Tags <br>: {html.count("<br")}')

print('\n📝 Primeros 800 caracteres:')
print('-'*80)
print(html[:800])
print('-'*80)

# Ver si hay saltos de línea
if '\n' in html:
    print(f'\n⚠️  Contiene {html.count(chr(10))} saltos de línea')
else:
    print('\n✅ No contiene saltos de línea')
