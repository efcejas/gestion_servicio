from preinformes.models import Preinforme
import re
from django.utils.html import strip_tags

p = Preinforme.objects.filter(sistema_destino='netterm', estado='finalizado').first()

if p and hasattr(p, 'revision'):
    html = p.revision.informe_final_html
    
    # Aplicar conversión
    texto = html.replace('</p>', '\n\n').replace('</P>', '\n\n')
    texto = re.sub(r'<br\s*/?>', '\n', texto, flags=re.IGNORECASE)
    texto = texto.replace('</div>', '\n').replace('</DIV>', '\n')
    texto = re.sub(r'</h[1-6]>', '\n\n', texto, flags=re.IGNORECASE)
    texto = texto.replace('</li>', '\n').replace('</LI>', '\n')
    texto = strip_tags(texto)
    
    while '\n\n\n' in texto:
        texto = texto.replace('\n\n\n', '\n\n')
    
    texto = texto.strip()
    
    print('='*60)
    print('RESULTADO (primeros 300 chars):')
    print('='*60)
    print(texto[:300])
    print()
    print('='*60)
    print('CON \\n VISIBLES:')
    print('='*60)
    print(repr(texto[:200]))
    print()
    print(f'Total saltos de línea: {texto.count(chr(10))}')
else:
    print('No se encontró preinforme NetTerm')
