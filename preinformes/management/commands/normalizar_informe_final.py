from django.core.management.base import BaseCommand
from preinformes.models import RevisionPreinforme, normalize_html_content


class Command(BaseCommand):
    help = 'Regenera informe_final_html aplicando normalize_html_content (para preinformes en revisión)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Muestra qué se haría sin hacer cambios',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Procesa TODOS los estados (no solo borrador/pendiente)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        force = options['force']
        
        # Estados a procesar
        if force:
            estados_validos = ['borrador', 'pendiente_revision', 'en_revision']
            self.stdout.write(self.style.WARNING('⚠️  Modo FORCE: procesando todos los estados'))
        else:
            estados_validos = ['borrador', 'pendiente_revision']
        
        # Buscar revisiones
        revisiones = RevisionPreinforme.objects.filter(
            preinforme__estado__in=estados_validos
        ).select_related('preinforme', 'preinforme__plantilla_utilizada', 'preinforme__tipo_estudio')
        
        total = revisiones.count()
        self.stdout.write(f'\n🔍 Encontradas {total} revisiones en estados: {", ".join(estados_validos)}\n')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('⚠️  Modo DRY-RUN: No se harán cambios reales\n'))
        
        procesados = 0
        mejorados = 0
        sin_cambios = 0
        
        for revision in revisiones:
            preinforme = revision.preinforme
            
            self.stdout.write(f'\n📄 Preinforme #{preinforme.numero_estudio}')
            self.stdout.write(f'   Estado: {preinforme.get_estado_display()}')
            
            if revision.informe_final_html:
                html_original = revision.informe_final_html
                
                # Analizar HTML original
                br_count_original = html_original.count('<br')
                p_count_original = html_original.count('<p>')
                nbsp_count_original = html_original.count('&nbsp;')
                
                self.stdout.write(f'   Original: {p_count_original} <p>, {br_count_original} <br>, {nbsp_count_original} &nbsp;')
                
                # Aplicar normalización
                html_normalizado = normalize_html_content(html_original)
                
                # Analizar HTML normalizado
                br_count_nuevo = html_normalizado.count('<br')
                p_count_nuevo = html_normalizado.count('<p>')
                nbsp_count_nuevo = html_normalizado.count('&nbsp;')
                
                self.stdout.write(f'   Normalizado: {p_count_nuevo} <p>, {br_count_nuevo} <br>, {nbsp_count_nuevo} &nbsp;')
                
                # Verificar si hubo mejora
                if (br_count_nuevo < br_count_original or 
                    p_count_nuevo > p_count_original or 
                    nbsp_count_nuevo < nbsp_count_original or
                    html_normalizado != html_original):
                    if not dry_run:
                        revision.informe_final_html = html_normalizado
                        revision.save()
                        self.stdout.write(self.style.SUCCESS('   ✅ Mejorado y guardado'))
                        mejorados += 1
                    else:
                        self.stdout.write(self.style.WARNING('   ⏭️  Se mejoraría (dry-run)'))
                        mejorados += 1
                else:
                    self.stdout.write(self.style.SUCCESS('   ⏸️  Sin cambios necesarios'))
                    sin_cambios += 1
                
                procesados += 1
            else:
                self.stdout.write('   ⏭️  Sin informe_final_html')
        
        self.stdout.write('\n' + '='*60)
        if dry_run:
            self.stdout.write(self.style.WARNING(f'\n📊 Resumen (DRY-RUN):'))
        else:
            self.stdout.write(self.style.SUCCESS(f'\n📊 Resumen:'))
        
        self.stdout.write(f'   ✅ Mejorados: {mejorados}')
        self.stdout.write(f'   ⏸️  Sin cambios: {sin_cambios}')
        self.stdout.write(f'   📦 Total procesados: {procesados}/{total}')
        self.stdout.write('\n')
