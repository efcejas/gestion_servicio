# -*- coding: utf-8 -*-
"""
Comando de simulación: escenarios de ausencia y propuesta de cobertura.

Simula que el profesional asignado a un bloque reporta ausencia y muestra
los candidatos sugeridos por el motor de cobertura (consultorios/services.py).

Uso:
    python manage.py simular_ausencia_cobertura
    python manage.py simular_ausencia_cobertura --bloque <id>
    python manage.py simular_ausencia_cobertura --todos
    python manage.py simular_ausencia_cobertura --seed-si-falta
"""

from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from consultorios.models import BloqueHorario, EstadoBloque, TipoLista
from consultorios.services import (
    BloqueNoCubreError,
    SinResidentesDisponiblesError,
    bloques_con_cobertura_posible,
    sugerir_cobertura,
)


SEPARADOR = '─' * 70


class Command(BaseCommand):
    help = (
        'Simula escenarios de ausencia y propone coberturas por residentes. '
        'Útil para validar el motor de cobertura antes de implementar UI.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--bloque',
            type=int,
            metavar='ID',
            help='Simula ausencia solo para el bloque con este ID.',
        )
        parser.add_argument(
            '--todos',
            action='store_true',
            help='Simula ausencia para todos los bloques con cobertura habilitada.',
        )
        parser.add_argument(
            '--seed-si-falta',
            action='store_true',
            help='Si no hay bloques demo, ejecuta cargar_consultorios_ejemplo antes de simular.',
        )

    def handle(self, *args, **options):
        self.stdout.write('\n' + SEPARADOR)
        self.stdout.write(self.style.SUCCESS('SIMULADOR DE AUSENCIAS — CONSULTORIOS ECOGRAFÍA'))
        self.stdout.write(SEPARADOR)

        # --- Verificar existencia de datos demo ---
        bloques_disponibles = bloques_con_cobertura_posible()

        if not bloques_disponibles:
            if options['seed_si_falta']:
                self.stdout.write(self.style.WARNING(
                    '\nNo hay bloques con cobertura habilitada. '
                    'Ejecutando cargar_consultorios_ejemplo primero...\n'
                ))
                from django.core.management import call_command
                call_command('cargar_consultorios_ejemplo')
                bloques_disponibles = bloques_con_cobertura_posible()
            else:
                raise CommandError(
                    'No hay bloques con permite_cobertura_residente=True. '
                    'Ejecutá primero: python manage.py cargar_consultorios_ejemplo\n'
                    'O usá --seed-si-falta para hacerlo automáticamente.'
                )

        # --- Seleccionar bloque(s) a simular ---
        if options['bloque']:
            try:
                bloque = BloqueHorario.objects.select_related(
                    'consultorio', 'profesional_interno', 'profesional_externo'
                ).get(pk=options['bloque'])
            except BloqueHorario.DoesNotExist:
                raise CommandError(f"No existe un bloque con ID={options['bloque']}.")
            bloques_a_simular = [bloque]

        elif options['todos']:
            bloques_a_simular = bloques_disponibles

        else:
            # Default: mostrar menú con los bloques disponibles
            bloques_a_simular = self._seleccionar_bloque_interactivo(bloques_disponibles)

        if not bloques_a_simular:
            self.stdout.write(self.style.WARNING('No se seleccionó ningún bloque. Saliendo.'))
            return

        # --- Simular cada bloque ---
        fecha_simulada = timezone.now().date() + timedelta(days=3)  # próximo turno realista

        for bloque in bloques_a_simular:
            self._simular_bloque(bloque, fecha_simulada)

        self.stdout.write('\n' + SEPARADOR)
        self.stdout.write(self.style.SUCCESS('Simulación completada.'))
        self.stdout.write(
            self.style.WARNING('NOTA: coberturas_previas_dia usa historial confirmado real de AusenciaCobertura.')
        )

    def _seleccionar_bloque_interactivo(self, bloques):
        """Muestra lista y permite elegir por número."""
        self.stdout.write(self.style.WARNING('\nBloques disponibles para simular ausencia:\n'))

        bloques_indexados = []
        for i, b in enumerate(bloques, start=1):
            tipo_label = b.get_tipo_lista_display() if hasattr(b, 'get_tipo_lista_display') else b.tipo_lista
            self.stdout.write(
                f"  [{i}] ID={b.pk} · {b.consultorio.nombre} · "
                f"{b.get_dia_semana_display()} {b.hora_inicio}-{b.hora_fin} · "
                f"{b.nombre_profesional()} · {tipo_label}"
            )
            bloques_indexados.append(b)

        self.stdout.write(f"  [0] Simular TODOS ({len(bloques_indexados)} bloques)\n")

        try:
            eleccion = input('Elegí un número (Enter = todos): ').strip()
        except (EOFError, KeyboardInterrupt):
            return bloques_indexados

        if eleccion == '' or eleccion == '0':
            return bloques_indexados

        try:
            idx = int(eleccion) - 1
            if 0 <= idx < len(bloques_indexados):
                return [bloques_indexados[idx]]
            else:
                self.stdout.write(self.style.ERROR('Número fuera de rango.'))
                return []
        except ValueError:
            self.stdout.write(self.style.ERROR('Entrada inválida.'))
            return []

    def _simular_bloque(self, bloque, fecha):
        """Simula la ausencia de un bloque y muestra la propuesta de cobertura."""
        profesional = bloque.nombre_profesional()
        tipo_label = bloque.get_tipo_lista_display()

        self.stdout.write(f'\n{SEPARADOR}')
        self.stdout.write(self.style.HTTP_INFO(
            f'AUSENCIA SIMULADA: {profesional}'
        ))
        self.stdout.write(
            f'  Bloque ID={bloque.pk} · {bloque.consultorio.nombre} · '
            f'{bloque.get_dia_semana_display()} {bloque.hora_inicio}-{bloque.hora_fin}'
        )
        self.stdout.write(
            f'  Tipo lista: {tipo_label} · '
            f'Actividad: {bloque.get_tipo_actividad_display()} · '
            f'Prioridad cobertura: {bloque.prioridad_cobertura}'
        )
        if bloque.competencia_requerida:
            self.stdout.write(f'  Competencia requerida: {bloque.competencia_requerida}')
        self.stdout.write(f'  Fecha simulada: {fecha}')

        # Llamar al servicio
        try:
            resultado = sugerir_cobertura(bloque, fecha=fecha)
        except BloqueNoCubreError as exc:
            self.stdout.write(self.style.ERROR(f'\n  ✗ {exc}'))
            return
        except SinResidentesDisponiblesError as exc:
            self.stdout.write(self.style.ERROR(f'\n  ✗ Sin candidatos: {exc}'))
            return

        # Advertencias
        for adv in resultado['advertencias']:
            self.stdout.write(self.style.WARNING(f'\n  ⚠  {adv}'))

        # Candidatos sugeridos
        candidatos = resultado['candidatos']
        if not candidatos:
            self.stdout.write(self.style.ERROR('\n  Sin candidatos para este bloque.'))
            return

        self.stdout.write(self.style.SUCCESS(
            f'\n  Candidatos sugeridos ({len(candidatos)}):')
        )
        for rank, c in enumerate(candidatos, start=1):
            self.stdout.write(
                f'    {rank}. {c["nombre"]} · {c["justificacion"]}'
                + (f' · coberturas previas ese día: {c["coberturas_previas_dia"]}' if c['coberturas_previas_dia'] else '')
            )
