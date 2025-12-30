"""
Comando de Django para reclasificar todas las filas EGES existentes.
Útil cuando se actualizan las keywords de detección de insumos.
"""
from django.core.management.base import BaseCommand
from eges_import.models import EgesRow, ImportBatch


class Command(BaseCommand):
    help = 'Reclasifica todas las filas EGES (modalidad e insumo) con la lógica actualizada'

    def add_arguments(self, parser):
        parser.add_argument(
            '--batch',
            type=int,
            help='Reclasificar solo un batch específico (ID)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Mostrar lo que se haría sin guardar cambios',
        )

    def handle(self, *args, **options):
        batch_id = options.get('batch')
        dry_run = options.get('dry_run')
        
        # Filtrar filas
        if batch_id:
            filas = EgesRow.objects.filter(batch_id=batch_id)
            self.stdout.write(f"Reclasificando Batch #{batch_id}...")
        else:
            filas = EgesRow.objects.all()
            self.stdout.write(f"Reclasificando TODAS las filas...")
        
        total = filas.count()
        self.stdout.write(f"Total de filas a procesar: {total}\n")
        
        # Contadores
        cambios_insumo = 0
        cambios_modalidad = 0
        
        # Estadísticas
        insumos_detectados = []
        estudios_reclasificados = []
        
        for idx, fila in enumerate(filas, 1):
            # Progreso cada 100 filas
            if idx % 100 == 0:
                self.stdout.write(f"Procesadas {idx}/{total} filas...")
            
            # Guardar estado original
            insumo_original = fila.es_insumo
            modalidad_original = fila.modalidad
            
            # Reclasificar usando la lógica actualizada
            nuevo_insumo = fila.clasificar_insumo()
            nueva_modalidad = fila.clasificar_modalidad()
            
            # Detectar cambios
            if nuevo_insumo != insumo_original:
                cambios_insumo += 1
                if nuevo_insumo:  # Se detectó como insumo (antes era estudio)
                    insumos_detectados.append(fila.servicio)
            
            if nueva_modalidad != modalidad_original:
                cambios_modalidad += 1
                estudios_reclasificados.append({
                    'servicio': fila.servicio,
                    'antes': modalidad_original,
                    'despues': nueva_modalidad
                })
            
            # Guardar si no es dry-run
            if not dry_run:
                fila.es_insumo = nuevo_insumo
                fila.modalidad = nueva_modalidad
                fila.save(update_fields=['es_insumo', 'modalidad'])
        
        # Recalcular métricas de los batches afectados
        if not dry_run:
            if batch_id:
                batches = [ImportBatch.objects.get(id=batch_id)]
            else:
                batches = ImportBatch.objects.all()
            
            for batch in batches:
                batch.calcular_metricas()
        
        # Reporte final
        self.stdout.write("\n" + "="*70)
        self.stdout.write(self.style.SUCCESS(f"✓ Reclasificación completada"))
        self.stdout.write("="*70)
        
        self.stdout.write(f"\n📊 Estadísticas:")
        self.stdout.write(f"   Total procesado: {total} filas")
        self.stdout.write(f"   Cambios en clasificación de insumos: {cambios_insumo}")
        self.stdout.write(f"   Cambios en modalidad: {cambios_modalidad}")
        
        if cambios_insumo > 0:
            self.stdout.write(f"\n🔍 Insumos detectados (primeros 20):")
            for servicio in insumos_detectados[:20]:
                self.stdout.write(f"   • {servicio}")
            if len(insumos_detectados) > 20:
                self.stdout.write(f"   ... y {len(insumos_detectados) - 20} más")
        
        if cambios_modalidad > 0:
            self.stdout.write(f"\n🏥 Estudios reclasificados (primeros 10):")
            for item in estudios_reclasificados[:10]:
                self.stdout.write(
                    f"   • {item['servicio'][:50]}: "
                    f"{item['antes']} → {item['despues']}"
                )
        
        # Estado final
        if not dry_run:
            total_insumos = EgesRow.objects.filter(es_insumo=True).count()
            total_estudios = EgesRow.objects.filter(es_insumo=False).count()
            
            self.stdout.write(f"\n📈 Estado final de la base de datos:")
            self.stdout.write(f"   Estudios: {total_estudios}")
            self.stdout.write(f"   Insumos: {total_insumos}")
            self.stdout.write(f"   Total: {total_estudios + total_insumos}")
            
            # Recalcular métricas
            self.stdout.write(f"\n♻️ Métricas de batches recalculadas")
        else:
            self.stdout.write(self.style.WARNING(f"\n⚠️ Dry-run: No se guardaron cambios"))
            self.stdout.write("   Ejecuta sin --dry-run para aplicar los cambios")
