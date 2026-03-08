#!/usr/bin/env python
"""Test script para verificar la conversión de HTML a texto NetTerm"""

import os
import django
import re

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_servicio.settings')
django.setup()

from django.utils.html import strip_tags
from preinformes.models import Preinforme

# Buscar un preinforme NetTerm finalizado
preinforme = Preinforme.objects.filter(
    sistema_destino='netterm',
    estado='finalizado'
).first()

if not preinforme or not hasattr(preinforme, 'revision'):
    print("❌ No se encontró un preinforme NetTerm finalizado")
    exit(1)

html_original = preinforme.revision.informe_final_html

print("=" * 80)
print("HTML ORIGINAL (primeros 300 chars):")
print("=" * 80)
print(html_original[:300])
print("\n")

# Aplicar la conversión igual que en views.py
texto_con_saltos = html_original

# Los </p> generan doble salto
texto_con_saltos = texto_con_saltos.replace('</p>', '\n\n').replace('</P>', '\n\n')

# Los <br> generan un salto simple
texto_con_saltos = re.sub(r'<br\s*/?>', '\n', texto_con_saltos, flags=re.IGNORECASE)

# Los </div> y otros bloques generan un salto
texto_con_saltos = texto_con_saltos.replace('</div>', '\n').replace('</DIV>', '\n')

# Los encabezados generan doble salto
texto_con_saltos = re.sub(r'</h[1-6]>', '\n\n', texto_con_saltos, flags=re.IGNORECASE)

# Lista items generan salto
texto_con_saltos = texto_con_saltos.replace('</li>', '\n').replace('</LI>', '\n')

# Ahora eliminar todas las etiquetas HTML restantes
informe_texto = strip_tags(texto_con_saltos)

# Limpiar exceso de saltos (máximo 2 consecutivos)
while '\n\n\n' in informe_texto:
    informe_texto = informe_texto.replace('\n\n\n', '\n\n')

# Limpiar espacios y tabs al final
informe_texto = informe_texto.strip()

print("=" * 80)
print("TEXTO CONVERTIDO (primeros 400 chars):")
print("=" * 80)
print(informe_texto[:400])
print("\n")

print("=" * 80)
print("ANÁLISIS:")
print("=" * 80)
print(f"Longitud HTML: {len(html_original)} chars")
print(f"Longitud texto: {len(informe_texto)} chars")
print(f"Número de saltos de línea: {informe_texto.count(chr(10))}")
print(f"Primer carácter: {repr(informe_texto[0])} (ord: {ord(informe_texto[0])})")
print(f"Primeros 5 chars: {repr(informe_texto[:5])}")
print("\n")

print("=" * 80)
print("MUESTRA CON \\n VISIBLES:")
print("=" * 80)
print(repr(informe_texto[:200]))
