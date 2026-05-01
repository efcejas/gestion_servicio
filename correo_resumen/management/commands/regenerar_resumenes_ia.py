from django.core.management.base import BaseCommand

from correo_resumen.models import CorreoHilo
from correo_resumen.services import _generar_resumen_hilo_ia
from correo_resumen.exceptions import ResumenIAError


class Command(BaseCommand):
    help = 'Regenera el resumen IA de los hilos de correo existentes.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--max-hilos', type=int, default=None,
            help='Máximo de hilos a procesar (default: todos)'
        )
        parser.add_argument(
            '--solo-pendientes', action='store_true',
            help='Solo hilos sin resumen IA (resumen_ia_generado=False)'
        )

    def handle(self, *args, **options):
        qs = CorreoHilo.objects.all().order_by('-fecha_ultimo_email')

        if options['solo_pendientes']:
            qs = qs.filter(resumen_ia_generado=False)

        if options['max_hilos']:
            qs = qs[:options['max_hilos']]

        total = qs.count()
        self.stdout.write(f'Procesando {total} hilo(s)...')

        ok = 0
        errores = 0
        sin_correos = 0

        for hilo in qs:
            try:
                resumen = _generar_resumen_hilo_ia(hilo)
                if resumen:
                    hilo.resumen_hilo = resumen
                    hilo.resumen_ia_generado = True
                    hilo.save(update_fields=['resumen_hilo', 'resumen_ia_generado'])
                    ok += 1
                    self.stdout.write(f'  ✓ [{hilo.asunto_normalizado[:50]}] → {resumen[:80]}')
                else:
                    sin_correos += 1
                    self.stdout.write(self.style.WARNING(f'  - [{hilo.asunto_normalizado[:50]}] sin correos o IA deshabilitada'))
            except ResumenIAError as exc:
                errores += 1
                self.stderr.write(f'  ✗ Error en hilo {hilo.pk}: {exc}')

        self.stdout.write(self.style.SUCCESS(
            f'\nListo: {ok} resúmenes generados, {sin_correos} sin datos, {errores} errores.'
        ))
