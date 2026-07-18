from django.core.management.base import BaseCommand

from accounts.services import procesar_cierre_residencia


class Command(BaseCommand):
    help = 'Procesa el cierre anual: promoción, repetición o egreso de residentes'

    def add_arguments(self, parser):
        parser.add_argument('--cierre', type=int, help='Año del cierre del 31 de julio a procesar.')
        parser.add_argument('--dry-run', action='store_true', help='Muestra los cambios sin guardarlos.')

    def handle(self, *args, **options):
        resultado = procesar_cierre_residencia(
            cierre_anio=options['cierre'],
            dry_run=options['dry_run'],
        )
        prefijo = '[SIMULACIÓN] ' if options['dry_run'] else ''
        self.stdout.write(f"{prefijo}Cierre académico {resultado['cierre']}")

        for residente, anterior, nuevo in resultado['promovidos']:
            self.stdout.write(self.style.SUCCESS(
                f'  {residente.get_full_name() or residente.username}: {anterior} → {nuevo}'
            ))
        for residente, anio in resultado['repetidores']:
            self.stdout.write(self.style.WARNING(
                f'  {residente.get_full_name() or residente.username}: repite {anio}'
            ))
        for residente in resultado['egresados']:
            self.stdout.write(self.style.SUCCESS(
                f'  {residente.get_full_name() or residente.username}: R4 → EGRESADO'
            ))

        self.stdout.write(
            f"Promovidos: {len(resultado['promovidos'])} | "
            f"Repiten: {len(resultado['repetidores'])} | "
            f"Egresados: {len(resultado['egresados'])} | "
            f"Sin cambios: {len(resultado['omitidos'])}"
        )
