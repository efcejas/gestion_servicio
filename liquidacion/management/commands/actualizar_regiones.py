from django.core.management.base import BaseCommand
from liquidacion.models import RegistroEstudiosPorMedico


class Command(BaseCommand):
    help = 'Actualiza cantidad_regiones basándose en los estudios seleccionados'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Muestra qué cambiaría sin actualizar la base de datos'
        )
        parser.add_argument(
            '--pk',
            type=int,
            help='ID específico del registro a actualizar'
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        pk = options.get('pk')
        
        self.stdout.write(self.style.WARNING(
            '🔄 Recalculando cantidad de regiones...\n'
        ))
        
        if pk:
            registros = RegistroEstudiosPorMedico.objects.filter(pk=pk)
        else:
            registros = RegistroEstudiosPorMedico.objects.all()
        
        total_registros = registros.count()
        actualizados = 0
        sin_cambios = 0
        
        for registro in registros:
            # Calcular cantidad_regiones sumando conteo_regiones_default de cada estudio
            regiones_esperadas = sum([e.conteo_regiones_default for e in registro.estudio.all()])
            regiones_actuales = registro.cantidad_regiones
            
            if regiones_esperadas != regiones_actuales and regiones_esperadas > 0:
                actualizados += 1
                
                estudios_nombres = [e.nombre for e in registro.estudio.all()]
                
                if dry_run:
                    self.stdout.write(
                        f"📝 ID {registro.pk} - {registro.medico.get_full_name()}: "
                        f"{regiones_actuales} → {regiones_esperadas} regiones\n"
                        f"   Estudios: {', '.join(estudios_nombres)}\n"
                    )
                else:
                    # Actualizar cantidad_regiones
                    registro.cantidad_regiones = regiones_esperadas
                    registro.save(update_fields=['cantidad_regiones'])
                    
                    # Recalcular monto (porque depende de cantidad_regiones)
                    monto_anterior = registro.monto_calculado
                    registro.monto_calculado = registro.calcular_monto()
                    registro.save(update_fields=['monto_calculado'])
                    
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"✅ ID {registro.pk}: {regiones_actuales} → {regiones_esperadas} regiones\n"
                            f"   Monto: ${monto_anterior} → ${registro.monto_calculado}\n"
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
