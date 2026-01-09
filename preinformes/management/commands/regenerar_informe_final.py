from django.core.management.base import BaseCommand
from preinformes.models import RevisionPreinforme, normalize_html_content

class Command(BaseCommand):
    help = 'Forzar regeneración del informe final desde snapshot normalizado'

    def add_arguments(self, parser):
        parser.add_argument('preinforme_id', type=int, help='ID del preinforme')

    def handle(self, *args, **options):
        preinforme_id = options['preinforme_id']
        
        try:
            revision = RevisionPreinforme.objects.get(preinforme_id=preinforme_id)
            
            self.stdout.write(f"\n=== ANTES ===")
            self.stdout.write(f"informe_final_html: {len(revision.informe_final_html or '')} chars")
            self.stdout.write(f"<p>: {(revision.informe_final_html or '').count('<p>')}")
            self.stdout.write(f"<br>: {(revision.informe_final_html or '').count('<br>')}")
            self.stdout.write(f"&nbsp;: {(revision.informe_final_html or '').count('&nbsp;')}")
            
            # Regenerar desde snapshot
            if revision.informe_residente_snapshot:
                nuevo_html = normalize_html_content(revision.informe_residente_snapshot)
            else:
                self.stdout.write(self.style.WARNING("No hay snapshot, generando desde cero..."))
                revision.crear_snapshot_residente()
                nuevo_html = normalize_html_content(revision.informe_residente_snapshot)
            
            revision.informe_final_html = nuevo_html
            revision.save()
            
            self.stdout.write(f"\n=== DESPUÉS ===")
            self.stdout.write(f"informe_final_html: {len(revision.informe_final_html)} chars")
            self.stdout.write(f"<p>: {revision.informe_final_html.count('<p>')}")
            self.stdout.write(f"<br>: {revision.informe_final_html.count('<br>')}")
            self.stdout.write(f"&nbsp;: {revision.informe_final_html.count('&nbsp;')}")
            
            self.stdout.write(self.style.SUCCESS(f'\n✅ Regenerado informe_final_html para preinforme {preinforme_id}'))
            
        except RevisionPreinforme.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'RevisionPreinforme para preinforme ID {preinforme_id} no encontrada'))
