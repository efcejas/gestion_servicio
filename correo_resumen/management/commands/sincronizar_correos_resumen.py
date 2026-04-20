from django.core.management.base import BaseCommand

from correo_resumen.services import sincronizar_correos_resumen


class Command(BaseCommand):
    help = 'Sincroniza correos importantes para el dashboard administrativo'

    def add_arguments(self, parser):
        parser.add_argument('--max-emails', type=int, default=None)

    def handle(self, *args, **options):
        resultado = sincronizar_correos_resumen(max_emails=options['max_emails'])
        if resultado['exito']:
            self.stdout.write(self.style.SUCCESS(resultado['mensaje']))
        else:
            self.stdout.write(self.style.WARNING(resultado['mensaje']))
