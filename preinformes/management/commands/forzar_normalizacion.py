from django.core.management.base import BaseCommand
from preinformes.models import RevisionPreinforme, normalize_html_content


class Command(BaseCommand):
    help = 'Forzar normalización de un preinforme específico'

    def add_arguments(self, parser):
        parser.add_argument('numero_estudio', type=str)

    def handle(self, *args, **options):
        numero = options['numero_estudio']
        
        try:
            r = RevisionPreinforme.objects.filter(preinforme__numero_estudio=numero).first()
            
            if not r:
                self.stdout.write(self.style.ERROR(f'❌ No encontrado: {numero}'))
                return
            
            html_original = r.informe_final_html
            
            self.stdout.write(f'\n📄 Preinforme: {numero}')
            self.stdout.write(f'\n📊 Original:')
            self.stdout.write(f'   {len(html_original)} caracteres')
            self.stdout.write(f'   {html_original.count("<p>")} <p>')
            self.stdout.write(f'   {html_original.count("&nbsp;")} &nbsp;')
            
            # Aplicar normalización
            html_normalizado = normalize_html_content(html_original)
            
            self.stdout.write(f'\n📊 Normalizado:')
            self.stdout.write(f'   {len(html_normalizado)} caracteres')
            self.stdout.write(f'   {html_normalizado.count("<p>")} <p>')
            self.stdout.write(f'   {html_normalizado.count("&nbsp;")} &nbsp;')
            
            if html_normalizado != html_original:
                self.stdout.write(self.style.WARNING(f'\n⚠️  HTML cambió ({len(html_original)} → {len(html_normalizado)} chars)'))
                
                # Guardar
                r.informe_final_html = html_normalizado
                r.save()
                self.stdout.write(self.style.SUCCESS('✅ Guardado'))
            else:
                self.stdout.write(self.style.SUCCESS('\n✅ Sin cambios necesarios'))
            
            # Mostrar primeros 500 caracteres
            self.stdout.write('\n📝 HTML normalizado (primeros 500 chars):')
            self.stdout.write('-'*80)
            self.stdout.write(html_normalizado[:500])
            self.stdout.write('\n' + '-'*80)
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'\n❌ Error: {str(e)}'))
            import traceback
            traceback.print_exc()
