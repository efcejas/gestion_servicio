from django.core.management.base import BaseCommand
from pedidos_estudios.models import PedidoEstudio, TipoEstudio


class Command(BaseCommand):
    help = 'Listar y corregir pedidos con inconsistenc ias en tipo de estudio'

    def handle(self, *args, **options):
        self.stdout.write("Buscando pedidos recientes...")
        self.stdout.write("=" * 80)
        
        # Ver últimos pedidos
        pedidos = PedidoEstudio.objects.all().order_by('-id')[:10]
        
        for p in pedidos:
            tipo = p.tipo_estudio.nombre if p.tipo_estudio else "Sin tipo"
            self.stdout.write(f"\n#{p.id}: {p.paciente.nombre_completo}")
            self.stdout.write(f"   Tipo: {tipo}")
            self.stdout.write(f"   Desc: {p.descripcion_estudio[:70]}")
        
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write("Buscando inconsistencias venoso/arterial...")
        self.stdout.write("=" * 80 + "\n")
        
        # Buscar pedidos con "venoso" en descripción pero tipo "Arterial"
        pedidos_problema = PedidoEstudio.objects.filter(
            descripcion_estudio__icontains='venoso',
            tipo_estudio__nombre__icontains='Arterial'
        )
        
        if pedidos_problema.exists():
            self.stdout.write(self.style.WARNING(
                f"Encontrados {pedidos_problema.count()} pedidos con inconsistencia (venoso → arterial):"
            ))
            
            tipo_correcto = TipoEstudio.objects.filter(nombre__icontains='Venoso de MMII').first()
            
            for p in pedidos_problema:
                self.stdout.write(f"\n#{p.id}: {p.paciente.nombre_completo}")
                self.stdout.write(f"   Tipo actual: {p.tipo_estudio.nombre}")
                self.stdout.write(f"   Descripción: {p.descripcion_estudio}")
                
                if tipo_correcto:
                    p.tipo_estudio = tipo_correcto
                    p.save()
                    self.stdout.write(self.style.SUCCESS(
                        f"   ✅ CORREGIDO a: {tipo_correcto.nombre}"
                    ))
        else:
            self.stdout.write(self.style.SUCCESS(
                "✓ No se encontraron inconsistencias de venoso → arterial"
            ))
        
        # Buscar la inversa
        pedidos_problema2 = PedidoEstudio.objects.filter(
            descripcion_estudio__icontains='arterial',
            tipo_estudio__nombre__icontains='Venoso'
        )
        
        if pedidos_problema2.exists():
            self.stdout.write(self.style.WARNING(
                f"\nEncontrados {pedidos_problema2.count()} pedidos con inconsistencia (arterial → venoso):"
            ))
            
            tipo_correcto = TipoEstudio.objects.filter(nombre__icontains='Arterial de MMII').first()
            
            for p in pedidos_problema2:
                self.stdout.write(f"\n#{p.id}: {p.paciente.nombre_completo}")
                self.stdout.write(f"   Tipo actual: {p.tipo_estudio.nombre}")
                self.stdout.write(f"   Descripción: {p.descripcion_estudio}")
                
                if tipo_correcto:
                    p.tipo_estudio = tipo_correcto
                    p.save()
                    self.stdout.write(self.style.SUCCESS(
                        f"   ✅ CORREGIDO a: {tipo_correcto.nombre}"
                    ))
        else:
            self.stdout.write(self.style.SUCCESS(
                "✓ No se encontraron inconsistencias de arterial → venoso"
            ))
        
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(self.style.SUCCESS("✅ Proceso completado"))
