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

nombres = [
    'TC Hígado trifásico (caracterización de lesión focal)',
    'TC Páncreas bifásico (fase pancreática + portal)',
    'TC Riñón multifásico (renal mass protocol)',
    'Uro-TC hematuria (urograma CT)',
    'TC sangrado activo abdomen (arterial + portal)'
]

print('\n' + '='*80)
print('REPORTE DE PROTOCOLOS MULTIFÁSICOS DE TC')
print('='*80 + '\n')

for nombre in nombres:
    p = Protocolo.objects.filter(nombre=nombre).prefetch_related('tags').select_related('region').first()
    
    if not p:
        print(f'⚠️  PROTOCOLO NO ENCONTRADO: {nombre}\n')
        continue
    
    print(f'\n## {p.nombre}\n')
    print(f'**Región:** {p.region.codigo}')
    print(f'**Tags:** {", ".join([t.nombre for t in p.tags.all()])}')
    
    print(f'\n### Descripción')
    print(p.descripcion)
    
    print(f'\n### Preparación del Paciente')
    print(p.preparacion_paciente)
    
    print(f'\n### Cobertura Global')
    print(p.cobertura_global)
    
    print(f'\n### Notas Docentes')
    print(p.notas_docentes)
    
    print(f'\n### Fases de Adquisición\n')
    
    fases = p.fases.select_related('region').order_by('orden')
    
    for f in fases:
        print(f'\n#### Fase {f.orden}: {f.nombre}')
        print(f'- **Tipo:** {f.tipo_fase}')
        
        if f.delay_segundos is None:
            print(f'- **Delay:** N/A (sin contraste o bolus tracking, ver técnicos)')
        else:
            print(f'- **Delay:** {f.delay_segundos}s')
        
        print(f'- **Cobertura:** {f.cobertura_desde} → {f.cobertura_hasta}')
        print(f'- **Ventanas:** {f.ventanas_recomendadas}')
        print(f'- **Técnicos:** {f.detalles_tecnicos}')
        print(f'- **Notas residente:**')
        print(f'  {f.notas_para_residente}')
    
    print('\n' + '-'*80 + '\n')

print('\n✅ Reporte completado\n')
