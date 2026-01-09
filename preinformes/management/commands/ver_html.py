from django.core.management.base import BaseCommand
from preinformes.models import RevisionPreinforme


class Command(BaseCommand):
    help = 'Ver HTML de un preinforme específico'

    def add_arguments(self, parser):
        parser.add_argument('numero_estudio', type=str, help='Número de estudio')

    def handle(self, *args, **options):
        numero = options['numero_estudio']
        
        try:
            r = RevisionPreinforme.objects.filter(preinforme__numero_estudio=numero).first()
            
            if not r:
                self.stdout.write(self.style.ERROR(f'❌ No se encontró revisión para {numero}'))
                return
            
            html = r.informe_final_html
            
            self.stdout.write('='*80)
            self.stdout.write(f'\n📄 Preinforme: {numero}')
            self.stdout.write('='*80)
            self.stdout.write('\n📊 Análisis:')
            self.stdout.write(f'   Total caracteres: {len(html)}')
            self.stdout.write(f'   Párrafos <p>: {html.count("<p>")}')
            self.stdout.write(f'   Tags <br>: {html.count("<br")}')
            
            self.stdout.write('\n📝 Primeros 800 caracteres:')
            self.stdout.write('-'*80)
            self.stdout.write(html[:800])
            self.stdout.write('\n' + '-'*80)
            
            # Ver estructura
            if '<p>' in html:
                primer_p = html.find('<p>')
                segundo_p = html.find('<p>', primer_p + 1)
                if segundo_p > 0:
                    self.stdout.write(f'\n✅ Primer <p> en posición {primer_p}')
                    self.stdout.write(f'✅ Segundo <p> en posición {segundo_p}')
                    self.stdout.write(f'   Distancia: {segundo_p - primer_p} caracteres')
                else:
                    self.stdout.write(self.style.WARNING('\n⚠️  Solo hay UN tag <p>'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'\n❌ Error: {str(e)}'))
