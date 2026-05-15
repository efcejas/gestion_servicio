from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from liquidacion.models import GrupoTarifario, TarifaGrupoTarifario


class Command(BaseCommand):
    help = 'Carga tarifas iniciales por grupo tarifario usando valores base vigentes.'

    TARIFAS_BASE = {
        'TOM_SIMPLE': (Decimal('4000.00'), Decimal('4000.00')),
        'TOM_CONTRASTE': (Decimal('5000.00'), Decimal('5000.00')),
        'TOM_SIN_CONTRASTE': (Decimal('4000.00'), Decimal('4000.00')),
        'TOM_ANGIO': (Decimal('7000.00'), Decimal('7000.00')),
        'RES_SIMPLE': (Decimal('5000.00'), Decimal('5000.00')),
        'RES_ANGIO': (Decimal('8000.00'), Decimal('8000.00')),
        'ECO_ECOGRAFIA': (Decimal('8500.00'), Decimal('10000.00')),
        'ECO_DOPPLER': (Decimal('8500.00'), Decimal('10000.00')),
        'RAD_RADIOGRAFIA': (Decimal('3000.00'), Decimal('3000.00')),
        'MAM_MAMOGRAFIA': (Decimal('7000.00'), Decimal('8500.00')),
    }

    def add_arguments(self, parser):
        parser.add_argument(
            '--vigencia-desde',
            help='Fecha de vigencia desde en formato YYYY-MM-DD. Default: hoy.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Muestra qué tarifas se crearían sin escribir en la base de datos',
        )

    def handle(self, *args, **options):
        if options['vigencia_desde']:
            try:
                vigencia_desde = timezone.datetime.strptime(options['vigencia_desde'], '%Y-%m-%d').date()
            except ValueError as exc:
                raise CommandError(f'Formato inválido para --vigencia-desde: {exc}')
        else:
            vigencia_desde = timezone.localdate()

        dry_run = options['dry_run']

        creadas = 0
        actualizadas = 0
        omitidas = 0

        self.stdout.write(self.style.WARNING(f'⏳ Cargando tarifas iniciales con vigencia {vigencia_desde}...'))

        for codigo_grupo, (precio_cober, precio_otras_os) in self.TARIFAS_BASE.items():
            try:
                grupo = GrupoTarifario.objects.get(codigo=codigo_grupo)
            except GrupoTarifario.DoesNotExist:
                omitidas += 1
                self.stdout.write(self.style.WARNING(f'⚠️ Grupo no encontrado, se omite: {codigo_grupo}'))
                continue

            defaults = {
                'vigencia_hasta': None,
                'precio_cober': precio_cober,
                'precio_otras_os': precio_otras_os,
                'motivo_actualizacion': 'Seed inicial de tarifas base EGES',
                'actualizado_por': None,
            }

            if dry_run:
                existe = TarifaGrupoTarifario.objects.filter(grupo_tarifario=grupo, vigencia_desde=vigencia_desde).exists()
                estado = 'actualizaría' if existe else 'crearía'
                self.stdout.write(
                    f'📝 {estado.upper()}: {codigo_grupo} desde {vigencia_desde} '
                    f'(${precio_cober} / ${precio_otras_os})'
                )
                continue

            tarifa, created = TarifaGrupoTarifario.objects.update_or_create(
                grupo_tarifario=grupo,
                vigencia_desde=vigencia_desde,
                defaults=defaults,
            )

            if created:
                creadas += 1
                self.stdout.write(self.style.SUCCESS(f'✅ Creada: {tarifa}'))
            else:
                actualizadas += 1
                self.stdout.write(self.style.SUCCESS(f'🔄 Actualizada: {tarifa}'))

        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(
            self.style.SUCCESS(
                f'Resumen: creadas={creadas}, actualizadas={actualizadas}, omitidas={omitidas}'
            )
        )

        if dry_run:
            self.stdout.write(self.style.WARNING('Modo dry-run: no se aplicaron cambios.'))