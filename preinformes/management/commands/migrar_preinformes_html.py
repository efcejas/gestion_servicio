from django.core.management.base import BaseCommand
from preinformes.models import Preinforme

class Command(BaseCommand):
    help = 'Migra preinformes con campos legacy (tecnica/hallazgos/conclusion) al nuevo campo informe_html'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simula la migración sin guardar cambios',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        # Buscar preinformes que NO tienen informe_html pero SÍ tienen datos legacy
        preinformes_legacy = Preinforme.objects.filter(
            informe_html__isnull=True
        ).filter(
            tecnica__isnull=False
        ) | Preinforme.objects.filter(
            informe_html__isnull=True
        ).filter(
            hallazgos__isnull=False
        )
        
        total = preinformes_legacy.count()
        
        if total == 0:
            self.stdout.write(self.style.SUCCESS('✅ No hay preinformes para migrar'))
            return
        
        self.stdout.write(f"\n{'='*60}")
        self.stdout.write(f"📋 Preinformes a migrar: {total}")
        self.stdout.write(f"{'='*60}\n")
        
        migrados = 0
        for preinforme in preinformes_legacy:
            html_generado = preinforme.get_informe_html_or_legacy()
            
            self.stdout.write(f"📄 {preinforme.numero_estudio} - {len(html_generado)} caracteres")
            
            if not dry_run:
                preinforme.informe_html = html_generado
                preinforme.save(update_fields=['informe_html'])
                migrados += 1
        
        if dry_run:
            self.stdout.write(self.style.WARNING(f"\n⚠️  DRY RUN: Se migrarían {total} preinformes"))
            self.stdout.write(self.style.WARNING("Ejecuta sin --dry-run para aplicar cambios"))
        else:
            self.stdout.write(self.style.SUCCESS(f"\n✅ Migrados {migrados} preinformes exitosamente"))
