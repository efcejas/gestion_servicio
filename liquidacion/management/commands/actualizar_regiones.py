from django.core.management.base import BaseCommand
from liquidacion.models import RegistroEstudiosPorMedico


class Command(BaseCommand):
    help = '''
    Actualiza cantidad_regiones y recalcula montos basándose en los estudios seleccionados.
    IMPORTANTE: A partir de v3.3, cantidad_regiones es informativo y el monto se calcula
    sumando el precio de cada estudio individual (sin multiplicar por cantidad_regiones).
    '''

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
        parser.add_argument(
            '--recalcular-todo',
            action='store_true',
            help='Recalcula montos de TODOS los registros (incluso si regiones están correctas)'
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        pk = options.get('pk')
        recalcular_todo = options.get('recalcular_todo', False)
        
        self.stdout.write(self.style.WARNING(
            '🔄 Recalculando cantidad de regiones y montos...\n'
        ))
        
        if pk:
            registros = RegistroEstudiosPorMedico.objects.filter(pk=pk)
        else:
            registros = RegistroEstudiosPorMedico.objects.all()
        
        total_registros = registros.count()
        actualizados_regiones = 0
        actualizados_montos = 0
        sin_cambios = 0
        
        for registro in registros:
            # Calcular cantidad_regiones sumando conteo_regiones_default de cada estudio
            regiones_esperadas = sum([e.conteo_regiones_default for e in registro.estudio.all()])
            regiones_actuales = registro.cantidad_regiones
            
            cambio_regiones = regiones_esperadas != regiones_actuales and regiones_esperadas > 0
            
            # Determinar si debemos recalcular este registro
            debe_actualizar = cambio_regiones or recalcular_todo
            
            if debe_actualizar:
                estudios_nombres = [e.nombre for e in registro.estudio.all()]
                
                if dry_run:
                    monto_nuevo = registro.calcular_monto() if cambio_regiones else registro.monto_calculado
                    self.stdout.write(
                        f"📝 ID {registro.pk} - {registro.medico.get_full_name()}\n"
                    )
                    if cambio_regiones:
                        self.stdout.write(
                            f"   Regiones: {regiones_actuales} → {regiones_esperadas}\n"
                        )
                    self.stdout.write(
                        f"   Estudios: {', '.join(estudios_nombres)}\n"
                        f"   Monto: ${registro.monto_calculado} → ${monto_nuevo}\n"
                    )
                else:
                    # Actualizar cantidad_regiones si cambió
                    if cambio_regiones:
                        registro.cantidad_regiones = regiones_esperadas
                        registro.save(update_fields=['cantidad_regiones'])
                        actualizados_regiones += 1
                    
                    # Recalcular monto (ahora NO multiplica por cantidad_regiones)
                    monto_anterior = registro.monto_calculado
                    registro.monto_calculado = registro.calcular_monto()
                    registro.save(update_fields=['monto_calculado'])
                    actualizados_montos += 1
                    
                    mensaje = f"✅ ID {registro.pk}"
                    if cambio_regiones:
                        mensaje += f": {regiones_actuales} → {regiones_esperadas} regiones"
                    if monto_anterior != registro.monto_calculado:
                        mensaje += f"\n   Monto: ${monto_anterior} → ${registro.monto_calculado}"
                    else:
                        mensaje += f"\n   Monto: ${registro.monto_calculado} (sin cambios)"
                    
                    self.stdout.write(self.style.SUCCESS(mensaje + '\n'))
            else:
                sin_cambios += 1
        
        self.stdout.write('\n' + '=' * 60)
        mensaje_final = f"✅ Procesados: {total_registros} registros\n"
        mensaje_final += f"   • Regiones actualizadas: {actualizados_regiones}\n"
        mensaje_final += f"   • Montos recalculados: {actualizados_montos}\n"
        mensaje_final += f"   • Sin cambios: {sin_cambios}"
        
        self.stdout.write(self.style.SUCCESS(mensaje_final))
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    '\n⚠️  Modo dry-run: No se guardaron cambios.\n'
                    '   Ejecuta sin --dry-run para aplicar los cambios.'
                )
            )
        
        if not recalcular_todo and actualizados_montos == 0:
            self.stdout.write(
                self.style.WARNING(
                    '\n💡 SUGERENCIA: Si actualizaste la lógica de cálculo, ejecuta:\n'
                    '   python manage.py actualizar_regiones --recalcular-todo\n'
                    '   para recalcular TODOS los montos con la nueva lógica.'
                )
            )

