from django.core.management.base import BaseCommand
from liquidacion.models import RegistroEstudiosPorMedico


class Command(BaseCommand):
    help = 'Recalcula los montos de todos los registros existentes (suma correcta de múltiples estudios)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Muestra qué cambiaría sin actualizar la base de datos'
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        
        self.stdout.write(self.style.WARNING(
            '🔄 Recalculando montos de registros...\n'
        ))
        
        registros = RegistroEstudiosPorMedico.objects.all()
        total_registros = registros.count()
        actualizados = 0
        sin_cambios = 0
        
        for registro in registros:
            monto_anterior = registro.monto_calculado
            monto_nuevo = registro.calcular_monto()
            
            if monto_anterior != monto_nuevo:
                actualizados += 1
                
                if dry_run:
                    self.stdout.write(
                        f"📝 ID {registro.pk} - {registro.medico.get_full_name()}: "
                        f"${monto_anterior} → ${monto_nuevo} "
                        f"({', '.join([e.nombre for e in registro.estudio.all()])})"
                    )
                else:
                    registro.monto_calculado = monto_nuevo
                    registro.save(update_fields=['monto_calculado'])
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"✅ ID {registro.pk}: ${monto_anterior} → ${monto_nuevo}"
                        )
                    )
            else:
                sin_cambios += 1
        
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(
            self.style.SUCCESS(
                f"✅ Procesados: {total_registros} registros\n"
                f"   • Actualizados: {actualizados}\n"
                f"   • Sin cambios: {sin_cambios}"
            )
        )
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    '\n⚠️  Modo dry-run: No se guardaron cambios.\n'
                    '   Ejecuta sin --dry-run para aplicar los cambios.'
                )
            )
