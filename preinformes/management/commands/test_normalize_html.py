from django.core.management.base import BaseCommand
from preinformes.models import normalize_html_content


class Command(BaseCommand):
    help = 'Prueba la función normalize_html_content con diferentes casos'

    def handle(self, *args, **options):
        test_cases = [
            {
                'nombre': 'Texto plano con \\n',
                'input': 'Línea 1\nLínea 2\nLínea 3',
                'esperado': 'Múltiples <p>'
            },
            {
                'nombre': 'Un <p> con <br>',
                'input': '<p>Línea 1<br>Línea 2<br>Línea 3</p>',
                'esperado': 'Múltiples <p>'
            },
            {
                'nombre': 'Un <p> con \\n',
                'input': '<p>Línea 1\nLínea 2\nLínea 3</p>',
                'esperado': 'Múltiples <p>'
            },
            {
                'nombre': 'Múltiples <p> con <br> dentro',
                'input': '<p>Párrafo 1 línea 1<br>Párrafo 1 línea 2</p><p>Párrafo 2</p>',
                'esperado': 'Todos los <br> convertidos a <p>'
            },
            {
                'nombre': 'Un <p> con <br/> (self-closing)',
                'input': '<p>Línea 1<br/>Línea 2<br />Línea 3</p>',
                'esperado': 'Múltiples <p>'
            },
            {
                'nombre': 'Múltiples <p> con <p>&nbsp;</p> vacíos',
                'input': '<p>Párrafo 1</p><p>&nbsp;</p><p>Párrafo 2</p><p>&nbsp;</p><p>Párrafo 3</p>',
                'esperado': 'Solo <p> con contenido real'
            },
            {
                'nombre': 'Párrafos vacíos variados',
                'input': '<p>Real</p><p></p><p> </p><p>&nbsp;</p><p>Real 2</p>',
                'esperado': 'Solo 2 <p> con contenido'
            },
        ]
        
        self.stdout.write('\n' + '='*80)
        self.stdout.write(self.style.SUCCESS('\n🧪 PRUEBAS DE NORMALIZE_HTML_CONTENT\n'))
        self.stdout.write('='*80 + '\n')
        
        for i, test in enumerate(test_cases, 1):
            self.stdout.write(f'\n📝 Test {i}: {test["nombre"]}')
            self.stdout.write(f'   Esperado: {test["esperado"]}')
            
            self.stdout.write('\n   INPUT:')
            self.stdout.write(f'   {repr(test["input"])}')
            
            resultado = normalize_html_content(test['input'])
            
            self.stdout.write('\n   OUTPUT:')
            self.stdout.write(f'   {repr(resultado)}')
            
            # Análisis
            p_count = resultado.count('<p>')
            br_count = resultado.count('<br')
            
            self.stdout.write('\n   📊 Análisis:')
            self.stdout.write(f'      - Párrafos <p>: {p_count}')
            self.stdout.write(f'      - Tags <br>: {br_count}')
            
            if br_count > 0:
                self.stdout.write(self.style.WARNING('      ⚠️  Aún contiene <br> tags'))
            else:
                self.stdout.write(self.style.SUCCESS('      ✅ No contiene <br> tags'))
            
            if p_count > 1:
                self.stdout.write(self.style.SUCCESS('      ✅ Múltiples párrafos creados'))
            else:
                self.stdout.write(self.style.WARNING('      ⚠️  Solo un párrafo'))
            
            self.stdout.write('\n' + '-'*80)
        
        self.stdout.write('\n' + '='*80)
        self.stdout.write(self.style.SUCCESS('\n✅ PRUEBAS COMPLETADAS\n'))
        self.stdout.write('='*80 + '\n')
