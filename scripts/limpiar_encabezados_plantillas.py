#!/usr/bin/env python3
"""
Script para eliminar encabezados duplicados de las plantillas
"""
import os
import sys
import django
import re

# Configurar Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_estudios.settings')
django.setup()

from preinformes.models import PlantillaPreinforme

def limpiar_encabezados():
    """Eliminar encabezados duplicados de las plantillas"""
    
    # Patrones para detectar encabezados
    patrones = [
        r'<p><strong>TÉCNICA:</strong></p>',
        r'<p><strong>HALLAZGOS:</strong></p>',
        r'<p><strong>CONCLUSIÓN:</strong></p>',
        r'<strong>TÉCNICA:</strong>',
        r'<strong>HALLAZGOS:</strong>',
        r'<strong>CONCLUSIÓN:</strong>',
        r'TÉCNICA:',
        r'HALLAZGOS:',
        r'CONCLUSIÓN:',
    ]
    
    plantillas_modificadas = 0
    
    for plantilla in PlantillaPreinforme.objects.all():
        modificado = False
        
        # Limpiar técnica
        if plantilla.tecnica_template:
            tecnica_original = plantilla.tecnica_template
            tecnica_limpia = tecnica_original
            
            for patron in patrones:
                tecnica_limpia = re.sub(patron, '', tecnica_limpia, flags=re.IGNORECASE)
            
            # Limpiar espacios y párrafos vacíos
            tecnica_limpia = re.sub(r'<p></p>', '', tecnica_limpia)
            tecnica_limpia = re.sub(r'<p>\s*</p>', '', tecnica_limpia)
            tecnica_limpia = tecnica_limpia.strip()
            
            if tecnica_limpia != tecnica_original:
                plantilla.tecnica_template = tecnica_limpia
                modificado = True
                print(f"✓ Limpiado técnica de '{plantilla.nombre}'")
        
        # Limpiar hallazgos
        if plantilla.hallazgos_template:
            hallazgos_original = plantilla.hallazgos_template
            hallazgos_limpio = hallazgos_original
            
            for patron in patrones:
                hallazgos_limpio = re.sub(patron, '', hallazgos_limpio, flags=re.IGNORECASE)
            
            # Limpiar espacios y párrafos vacíos
            hallazgos_limpio = re.sub(r'<p></p>', '', hallazgos_limpio)
            hallazgos_limpio = re.sub(r'<p>\s*</p>', '', hallazgos_limpio)
            hallazgos_limpio = hallazgos_limpio.strip()
            
            if hallazgos_limpio != hallazgos_original:
                plantilla.hallazgos_template = hallazgos_limpio
                modificado = True
                print(f"✓ Limpiado hallazgos de '{plantilla.nombre}'")
        
        # Limpiar conclusión
        if plantilla.conclusion_template:
            conclusion_original = plantilla.conclusion_template
            conclusion_limpia = conclusion_original
            
            for patron in patrones:
                conclusion_limpia = re.sub(patron, '', conclusion_limpia, flags=re.IGNORECASE)
            
            # Limpiar espacios y párrafos vacíos
            conclusion_limpia = re.sub(r'<p></p>', '', conclusion_limpia)
            conclusion_limpia = re.sub(r'<p>\s*</p>', '', conclusion_limpia)
            conclusion_limpia = conclusion_limpia.strip()
            
            if conclusion_limpia != conclusion_original:
                plantilla.conclusion_template = conclusion_limpia
                modificado = True
                print(f"✓ Limpiado conclusión de '{plantilla.nombre}'")
        
        if modificado:
            plantilla.save()
            plantillas_modificadas += 1
    
    print(f"\n✅ Limpieza completada. {plantillas_modificadas} plantillas modificadas.")

if __name__ == '__main__':
    print("🧹 Limpiando encabezados duplicados de plantillas...")
    print()
    limpiar_encabezados()