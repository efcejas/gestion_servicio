from django.core.management.base import BaseCommand
from accounts.models import CustomUser

class Command(BaseCommand):
    help = 'Actualiza el año de residencia para todos los residentes activos'

    def handle(self, *args, **options):
        residentes = CustomUser.objects.filter(rol='medico_residente', fecha_ingreso_residencia__isnull=False)
        
        actualizados = 0
        for residente in residentes:
            anio_anterior = residente.anio_residencia
            residente.actualizar_anio_residencia()
            
            if anio_anterior != residente.anio_residencia:
                actualizados += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f'✓ {residente.get_full_name()} ({residente.username}): {anio_anterior or "Sin asignar"} → {residente.anio_residencia}'
                    )
                )
        
        if actualizados == 0:
            self.stdout.write(self.style.WARNING('No se encontraron residentes que requieran actualización'))
        else:
            self.stdout.write(
                self.style.SUCCESS(f'\n✓ Se actualizaron {actualizados} residentes de {residentes.count()} total')
            )
