from django.core.management.base import BaseCommand
from preinformes.models import RevisionPreinforme
import re

class Command(BaseCommand):
    help = 'Verifica el HTML guardado en revision.informe_final_html'

    def add_arguments(self, parser):
        parser.add_argument('preinforme_id', type=int, help='ID del preinforme')

    def handle(self, *args, **options):
        preinforme_id = options['preinforme_id']
        
        try:
            revision = RevisionPreinforme.objects.get(preinforme_id=preinforme_id)
            
            html = revision.informe_final_html or ""
            
            # Contar elementos
            p_count = html.count('<p>')
            br_count = html.count('<br>')
            nbsp_count = html.count('&nbsp;')
            empty_p = len(re.findall(r'<p>\s*</p>', html))
            empty_p_nbsp = html.count('<p>&nbsp;</p>')
            ul_count = html.count('<ul>')
            ol_count = html.count('<ol>')
            li_count = html.count('<li>')
            
            self.stdout.write("\n" + "="*70)
            self.stdout.write(f"📋 REVISIÓN DEL PREINFORME ID: {preinforme_id}")
            self.stdout.write("="*70 + "\n")
            
            self.stdout.write(f"Total caracteres: {len(html)}")
            self.stdout.write(f"")
            self.stdout.write(f"📊 CONTEO DE ELEMENTOS:")
            self.stdout.write(f"  <p> tags:          {p_count}")
            self.stdout.write(f"  <br> tags:         {br_count}")
            self.stdout.write(f"  &nbsp;:            {nbsp_count}")
            self.stdout.write(f"  <p></p> vacíos:    {empty_p}")
            self.stdout.write(f"  <p>&nbsp;</p>:     {empty_p_nbsp}")
            self.stdout.write(f"  <ul> listas:       {ul_count}")
            self.stdout.write(f"  <ol> numeradas:    {ol_count}")
            self.stdout.write(f"  <li> items:        {li_count}")
            
            self.stdout.write(f"\n📄 PRIMEROS 800 CARACTERES:")
            self.stdout.write("-"*70)
            self.stdout.write(html[:800])
            self.stdout.write("-"*70)
            
            # Análisis
            self.stdout.write(f"\n✅ ANÁLISIS:")
            if p_count > 0:
                self.stdout.write(self.style.SUCCESS(f"  ✓ Tiene {p_count} párrafos <p>"))
            else:
                self.stdout.write(self.style.ERROR("  ✗ NO tiene párrafos <p>"))
            
            if br_count == 0:
                self.stdout.write(self.style.SUCCESS("  ✓ No tiene <br> (correcto)"))
            else:
                self.stdout.write(self.style.WARNING(f"  ⚠ Tiene {br_count} tags <br>"))
            
            if empty_p_nbsp > 0:
                self.stdout.write(self.style.WARNING(f"  ⚠ Tiene {empty_p_nbsp} párrafos <p>&nbsp;</p> (pueden causar problemas visuales)"))
            else:
                self.stdout.write(self.style.SUCCESS("  ✓ No tiene <p>&nbsp;</p>"))
            
            self.stdout.write("")
            
        except RevisionPreinforme.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'❌ No existe revisión para preinforme ID {preinforme_id}'))
