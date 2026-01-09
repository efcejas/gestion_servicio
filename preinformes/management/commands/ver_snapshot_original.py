from django.core.management.base import BaseCommand
from preinformes.models import Preinforme

class Command(BaseCommand):
    help = 'Ver el HTML del snapshot original del residente'

    def add_arguments(self, parser):
        parser.add_argument('preinforme_id', type=int, help='ID del preinforme')

    def handle(self, *args, **options):
        preinforme_id = options['preinforme_id']
        
        try:
            preinforme = Preinforme.objects.get(id=preinforme_id)
            html = preinforme.informe_residente_snapshot
            
            if not html:
                self.stdout.write(self.style.WARNING('No hay snapshot guardado, generando...'))
                html = preinforme.generar_informe_original_residente()
            
            self.stdout.write("=== INFORME ORIGINAL RESIDENTE (SNAPSHOT) ===\n")
            self.stdout.write(f"Primeros 1000 caracteres:\n{html[:1000]}\n")
            self.stdout.write(f"\nTotal: {len(html)} caracteres")
            self.stdout.write(f"Párrafos <p>: {html.count('<p>')}")
            self.stdout.write(f"BR tags: {html.count('<br>')}")
            self.stdout.write(f"nbsp: {html.count('&nbsp;')}")
            self.stdout.write(f"<p>&nbsp;</p>: {html.count('<p>&nbsp;</p>')}")
            
        except Preinforme.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Preinforme ID {preinforme_id} no encontrado'))
