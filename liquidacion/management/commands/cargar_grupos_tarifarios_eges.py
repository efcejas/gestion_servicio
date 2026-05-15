import os

import pandas as pd
from django.core.management.base import BaseCommand, CommandError

from liquidacion.models import GrupoTarifario


DEFAULT_INPUT_FILE = os.path.join("docs", "eges_excels", "eges_grupos_propuestos.csv")


class Command(BaseCommand):
    help = 'Carga o actualiza grupos tarifarios propuestos desde el resumen EGES.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--archivo',
            default=DEFAULT_INPUT_FILE,
            help='CSV con los grupos propuestos generado por scripts/proponer_grupos_tarifarios_eges.py',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Muestra qué se crearían o actualizarían sin escribir en la base de datos',
        )

    def handle(self, *args, **options):
        archivo = os.path.abspath(options['archivo'])
        dry_run = options['dry_run']

        if not os.path.exists(archivo):
            raise CommandError(f'No se encontró el archivo: {archivo}')

        try:
            df = pd.read_csv(archivo)
        except Exception as exc:
            raise CommandError(f'No se pudo leer el CSV: {exc}')

        requeridas = {'grupo_codigo_propuesto', 'grupo_nombre_propuesto', 'modalidad'}
        faltantes = requeridas - set(df.columns)
        if faltantes:
            raise CommandError(f'Faltan columnas requeridas: {", ".join(sorted(faltantes))}')

        creados = 0
        actualizados = 0
        sin_cambios = 0

        self.stdout.write(self.style.WARNING('⏳ Cargando grupos tarifarios propuestos...'))

        for _, fila in df.iterrows():
            codigo = str(fila['grupo_codigo_propuesto']).strip()
            nombre = str(fila['grupo_nombre_propuesto']).strip()
            modalidad = str(fila['modalidad']).strip()

            defaults = {
                'nombre': nombre,
                'modalidad': modalidad,
                'activo': True,
            }

            if dry_run:
                existe = GrupoTarifario.objects.filter(codigo=codigo).exists()
                estado = 'actualizaría' if existe else 'crearía'
                self.stdout.write(f'📝 {estado.upper()}: {codigo} - {nombre} ({modalidad})')
                continue

            grupo, created = GrupoTarifario.objects.update_or_create(
                codigo=codigo,
                defaults=defaults,
            )

            if created:
                creados += 1
                self.stdout.write(self.style.SUCCESS(f'✅ Creado: {grupo.codigo} - {grupo.nombre}'))
            else:
                if grupo.nombre == nombre and grupo.modalidad == modalidad and grupo.activo:
                    sin_cambios += 1
                else:
                    actualizados += 1
                self.stdout.write(self.style.SUCCESS(f'🔄 Actualizado: {grupo.codigo} - {grupo.nombre}'))

        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(
            self.style.SUCCESS(
                f'Proceso finalizado: creados={creados}, actualizados={actualizados}, sin_cambios={sin_cambios}'
            )
        )

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    'Modo dry-run: no se aplicaron cambios. Ejecuta sin --dry-run para persistir.'
                )
            )