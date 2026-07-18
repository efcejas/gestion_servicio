from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from preinformes.asistente_service import (
    AsistenteRadiologicoBot,
    VERSION_RUBRICA_EVALUACION_FINAL,
)
from preinformes.models import RevisionPreinforme


class Command(BaseCommand):
    help = (
        'Reevalua evaluaciones IA finales antiguas con puntaje bajo. '
        'Por defecto solo lista los candidatos.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--umbral',
            type=float,
            default=5,
            help='Puntaje maximo a reevaluar (por defecto: 5).',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=None,
            help='Cantidad maxima de evaluaciones a procesar.',
        )
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Ejecuta las llamadas de IA y guarda los resultados.',
        )
        parser.add_argument(
            '--incluir-rubrica-actual',
            action='store_true',
            help='Incluye evaluaciones que ya usan la rubrica actual.',
        )

    def handle(self, *args, **options):
        umbral = options['umbral']
        limite = options['limit']
        aplicar = options['apply']
        incluir_actuales = options['incluir_rubrica_actual']

        if umbral < 1 or umbral > 10:
            raise CommandError('--umbral debe estar entre 1 y 10.')
        if limite is not None and limite < 1:
            raise CommandError('--limit debe ser mayor que cero.')

        revisiones = RevisionPreinforme.objects.exclude(
            evaluacion_ia_final={}
        ).select_related(
            'preinforme__residente',
            'preinforme__tipo_estudio',
            'preinforme__region',
            'revisor',
        ).order_by('evaluacion_ia_final_generada_en', 'pk')

        candidatas = []
        for revision in revisiones:
            evaluacion = revision.evaluacion_ia_final
            if not isinstance(evaluacion, dict):
                continue
            puntaje = evaluacion.get('puntaje_global')
            if not isinstance(puntaje, (int, float)) or puntaje > umbral:
                continue
            if (
                not incluir_actuales
                and evaluacion.get('version_rubrica') == VERSION_RUBRICA_EVALUACION_FINAL
            ):
                continue
            candidatas.append(revision)
            if limite and len(candidatas) >= limite:
                break

        self.stdout.write(
            f'Candidatas: {len(candidatas)} evaluacion(es) con puntaje <= {umbral:g}.'
        )
        for revision in candidatas:
            puntaje = revision.evaluacion_ia_final.get('puntaje_global')
            self.stdout.write(
                f'  Revision {revision.pk} | estudio {revision.preinforme.numero_estudio} '
                f'| residente {revision.preinforme.residente.username} | {puntaje}/10'
            )

        if not aplicar:
            self.stdout.write(self.style.WARNING(
                'Vista previa: no se hicieron llamadas de IA ni cambios. '
                'Use --apply para reevaluar.'
            ))
            return

        bot = AsistenteRadiologicoBot()
        if not bot.client:
            raise CommandError('El asistente IA no esta disponible o no tiene API configurada.')

        actualizadas = 0
        errores = 0
        for revision in candidatas:
            evaluacion_anterior = revision.evaluacion_ia_final.copy()
            puntaje_anterior = evaluacion_anterior.get('puntaje_global')
            resultado = bot.generar_evaluacion_final_revision(revision)

            if not resultado.get('success'):
                errores += 1
                revision.evaluacion_ia_final_error = (
                    resultado.get('error') or 'No se pudo reevaluar.'
                )
                revision.save(update_fields=['evaluacion_ia_final_error'])
                self.stderr.write(self.style.ERROR(
                    f'  Revision {revision.pk}: {revision.evaluacion_ia_final_error}'
                ))
                continue

            evaluacion_nueva = resultado.get('evaluacion') or {}
            puntaje_nuevo = evaluacion_nueva.get('puntaje_global')
            evaluacion_nueva['auditoria_reevaluacion'] = {
                'fecha': timezone.now().isoformat(),
                'motivo': f'Puntaje historico menor o igual a {umbral:g}',
                'puntaje_anterior': puntaje_anterior,
                'evaluacion_anterior': evaluacion_anterior,
            }
            revision.evaluacion_ia_final = evaluacion_nueva
            revision.evaluacion_ia_final_generada_en = timezone.now()
            revision.evaluacion_ia_final_error = ''
            revision.save(update_fields=[
                'evaluacion_ia_final',
                'evaluacion_ia_final_generada_en',
                'evaluacion_ia_final_error',
            ])
            actualizadas += 1
            self.stdout.write(self.style.SUCCESS(
                f'  Revision {revision.pk}: {puntaje_anterior}/10 -> {puntaje_nuevo}/10'
            ))

        self.stdout.write(self.style.SUCCESS(
            f'Reevaluacion terminada: {actualizadas} actualizada(s), {errores} error(es).'
        ))
