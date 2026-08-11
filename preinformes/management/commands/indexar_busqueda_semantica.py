from django.core.management.base import BaseCommand, CommandError

from preinformes.busqueda_semantica_service import BusquedaSemanticaInformes
from preinformes.models import RevisionPreinforme


class Command(BaseCommand):
    help = 'Genera embeddings anonimizados para informes definitivos aprobados.'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=0)
        parser.add_argument('--batch-size', type=int, default=50)
        parser.add_argument('--force', action='store_true')

    def handle(self, *args, **options):
        servicio = BusquedaSemanticaInformes()
        if not servicio.client:
            raise CommandError('Falta OPENAI_API_KEY para generar embeddings.')

        queryset = RevisionPreinforme.objects.filter(
            preinforme__estado='finalizado',
            preinforme__es_registro_demo=False,
            preinforme__residente__rol='medico_residente',
        ).select_related(
            'preinforme__tipo_estudio',
            'preinforme__region',
        ).order_by('pk')

        limite = max(0, options['limit'])
        if limite:
            queryset = queryset[:limite]

        batch_size = max(1, min(options['batch_size'], 100))
        total = 0
        lote = []
        for revision in queryset.iterator(chunk_size=batch_size):
            lote.append(revision)
            if len(lote) == batch_size:
                total += servicio.indexar_revisiones(lote, forzar=options['force'])
                self.stdout.write(f'Indexados: {total}')
                lote = []
        if lote:
            total += servicio.indexar_revisiones(lote, forzar=options['force'])

        self.stdout.write(self.style.SUCCESS(f'Indexación semántica completa: {total} informes.'))
