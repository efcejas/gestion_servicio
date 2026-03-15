"""
Comando para generar un token de acceso al portal del director.

Uso:
    python manage.py generar_token_director
    python manage.py generar_token_director --etiqueta "Director 2026"
    python manage.py generar_token_director --listar
    python manage.py generar_token_director --desactivar <id>
"""
from django.core.management.base import BaseCommand
from django.conf import settings
from eges_import.models import DirectorToken


class Command(BaseCommand):
    help = 'Gestiona los tokens de acceso al portal del director'

    def add_arguments(self, parser):
        parser.add_argument(
            'etiqueta',
            nargs='?',
            type=str,
            default='Director',
            help='Nombre descriptivo del token (ej: "Director 2026")',
        )
        parser.add_argument(
            '--listar',
            action='store_true',
            help='Listar todos los tokens existentes',
        )
        parser.add_argument(
            '--desactivar',
            type=int,
            help='Desactivar un token por su ID',
        )

    def handle(self, *args, **options):
        # ── Listar tokens
        if options.get('listar'):
            tokens = DirectorToken.objects.all()
            if not tokens:
                self.stdout.write("No hay tokens creados todavía.")
                return
            self.stdout.write(f"\n{'ID':>4}  {'Etiqueta':<25}  {'Activo':^6}  {'Último acceso'}")
            self.stdout.write("-" * 70)
            for t in tokens:
                activo = '✓' if t.activo else '✗'
                ultimo = t.fecha_ultimo_acceso.strftime('%d/%m/%Y %H:%M') if t.fecha_ultimo_acceso else 'Nunca'
                self.stdout.write(f"{t.id:>4}  {t.nombre_etiqueta:<25}  {activo:^6}  {ultimo}")
            self.stdout.write("")
            return

        # ── Desactivar token
        if options.get('desactivar'):
            token_id = options['desactivar']
            try:
                t = DirectorToken.objects.get(id=token_id)
                t.activo = False
                t.save(update_fields=['activo'])
                self.stdout.write(self.style.WARNING(
                    f"Token #{token_id} ({t.nombre_etiqueta}) desactivado."
                ))
            except DirectorToken.DoesNotExist:
                self.stderr.write(f"No existe un token con ID {token_id}.")
            return

        # ── Crear nuevo token
        etiqueta = options['etiqueta']
        token = DirectorToken.objects.create(nombre_etiqueta=etiqueta)

        # Construir la URL
        base_url = getattr(settings, 'BASE_URL', 'http://localhost:8000')
        url = f"{base_url}/eges/director/{token.token}/"

        self.stdout.write("\n" + "=" * 70)
        self.stdout.write(self.style.SUCCESS(f"✓ Token generado para: {etiqueta}"))
        self.stdout.write("=" * 70)
        self.stdout.write(f"\n  Token ID : #{token.id}")
        self.stdout.write(f"  UUID     : {token.token}")
        self.stdout.write(f"\n  URL del portal del director:")
        self.stdout.write(self.style.SUCCESS(f"\n  {url}\n"))
        self.stdout.write("  Compartí este enlace con el director.")
        self.stdout.write("  Para desactivarlo: python manage.py generar_token_director --desactivar " + str(token.id))
        self.stdout.write("")
