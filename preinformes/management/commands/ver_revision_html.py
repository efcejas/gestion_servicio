from django.core.management.base import BaseCommand
from preinformes.models import RevisionPreinforme

class Command(BaseCommand):
    help = 'Ver el HTML de la revisión actual'

    def add_arguments(self, parser):
        parser.add_argument('preinforme_id', type=int, help='ID del preinforme')

    def handle(self, *args, **options):
        preinforme_id = options['preinforme_id']
        
        try:
            revision = RevisionPreinforme.objects.get(preinforme_id=preinforme_id)
            
            self.stdout.write("\n=== SNAPSHOT RESIDENTE ===")
            snapshot = revision.informe_residente_snapshot or "NO HAY SNAPSHOT"
            self.stdout.write(f"Primeros 800 chars:\n{snapshot[:800]}\n")
            self.stdout.write(f"<p>: {snapshot.count('<p>')}, <br>: {snapshot.count('<br>')}, &nbsp;: {snapshot.count('&nbsp;')}")
            
            self.stdout.write("\n=== INFORME FINAL HTML (lo que ve el editor) ===")
            final = revision.informe_final_html or "VACÍO"
            self.stdout.write(f"Primeros 800 chars:\n{final[:800]}\n")
            self.stdout.write(f"<p>: {final.count('<p>')}, <br>: {final.count('<br>')}, &nbsp;: {final.count('&nbsp;')}")
            
        except RevisionPreinforme.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'RevisionPreinforme para preinforme ID {preinforme_id} no encontrada'))
