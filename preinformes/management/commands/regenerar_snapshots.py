from django.core.management.base import BaseCommand
from preinformes.models import RevisionPreinforme, Preinforme


class Command(BaseCommand):
    help = 'Regenera snapshots de preinformes con el nuevo formato (solo borrador/pendiente_revision)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Muestra qué se haría sin hacer cambios',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        # Solo procesar preinformes en estados tempranos
        estados_validos = ['borrador', 'pendiente_revision']
        
        # Buscar revisiones de preinformes en estos estados
        revisiones = RevisionPreinforme.objects.filter(
            preinforme__estado__in=estados_validos
        ).select_related('preinforme', 'preinforme__plantilla_utilizada', 'preinforme__tipo_estudio')
        
        total = revisiones.count()
        self.stdout.write(f'\n🔍 Encontradas {total} revisiones en estados: {", ".join(estados_validos)}\n')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('⚠️  Modo DRY-RUN: No se harán cambios reales\n'))
        
        regenerados = 0
        saltados = 0
        
        for revision in revisiones:
            preinforme = revision.preinforme
            titulo_actual = ''
            
            # Determinar título
            if preinforme.plantilla_utilizada:
                titulo_actual = preinforme.plantilla_utilizada.nombre
            else:
                titulo_actual = preinforme.tipo_estudio.nombre
            
            self.stdout.write(f'\n📄 Preinforme #{preinforme.numero_estudio}')
            self.stdout.write(f'   Título: {titulo_actual}')
            self.stdout.write(f'   Estado: {preinforme.get_estado_display()}')
            
            if not dry_run:
                try:
                    # Regenerar snapshot
                    nuevo_snapshot = revision.generar_informe_original_residente()
                    revision.informe_residente_snapshot = nuevo_snapshot
                    
                    # Si el informe final aún no fue modificado por staff, regenerarlo también
                    if revision.informe_final_html == revision.informe_residente_snapshot or not revision.informe_final_html:
                        revision.informe_final_html = nuevo_snapshot
                    
                    revision.save()
                    regenerados += 1
                    self.stdout.write(self.style.SUCCESS(f'   ✅ Regenerado'))
                except Exception as e:
                    saltados += 1
                    self.stdout.write(self.style.ERROR(f'   ❌ Error: {str(e)}'))
            else:
                self.stdout.write(self.style.WARNING('   ⏭️  Se regeneraría (dry-run)'))
        
        self.stdout.write('\n' + '='*60)
        if dry_run:
            self.stdout.write(self.style.WARNING(f'\n📊 Resumen (DRY-RUN):'))
            self.stdout.write(f'   Total encontradas: {total}')
        else:
            self.stdout.write(self.style.SUCCESS(f'\n📊 Resumen:'))
            self.stdout.write(f'   ✅ Regeneradas: {regenerados}')
            self.stdout.write(f'   ⏭️  Saltadas (errores): {saltados}')
            self.stdout.write(f'   📦 Total procesadas: {total}')
        
        self.stdout.write('\n')
