from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group


GRUPOS = [
    'Administrativo - Docencia',
    'Administrativo - Sanatorio (pedidos)',
]


class Command(BaseCommand):
    help = 'Crea los grupos de Django para perfiles administrativos si no existen'

    def handle(self, *args, **options):
        creados = 0
        ya_existian = 0

        for nombre in GRUPOS:
            grupo, created = Group.objects.get_or_create(name=nombre)
            if created:
                creados += 1
                self.stdout.write(self.style.SUCCESS(f'✓ Grupo creado: "{nombre}"'))
            else:
                ya_existian += 1
                self.stdout.write(self.style.WARNING(f'· Ya existía: "{nombre}"'))

        self.stdout.write(
            self.style.SUCCESS(
                f'\nResumen: {creados} creados, {ya_existian} ya existían.'
            )
        )
        if creados > 0:
            self.stdout.write(
                '\nPodés asignar usuarios desde el panel de administración en:\n'
                'Admin → Autenticación y autorización → Usuarios → [usuario] → Grupos'
            )
