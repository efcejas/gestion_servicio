"""
Management command para procesar pedidos via scheduler/cron.
Versión silenciosa optimizada para ejecución automática.
"""
from django.core.management.base import BaseCommand
from pedidos_estudios.services.procesador import ProcesadorPedidos
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Procesa pedidos automáticamente (para cron/scheduler)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--max-emails',
            type=int,
            default=10,
            help='Máximo de emails a procesar'
        )
        parser.add_argument(
            '--silent',
            action='store_true',
            help='Modo silencioso (solo errores)'
        )

    def handle(self, *args, **options):
        max_emails = options['max_emails']
        silent = options['silent']
        
        procesador = ProcesadorPedidos()
        
        try:
            resultado = procesador.procesar_emails_pendientes(
                max_emails=max_emails,
                marcar_como_leido=True  # En producción SÍ marca como leído
            )
            
            # Log estructurado para monitoreo
            logger.info(
                f"Procesamiento automático: "
                f"procesados={resultado['procesados']}, "
                f"exitosos={resultado['exitosos']}, "
                f"errores={resultado['errores']}, "
                f"duplicados={resultado.get('duplicados', 0)}"
            )
            
            if not silent:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✓ Procesados: {resultado['exitosos']}/{resultado['procesados']}"
                    )
                )
                
        except Exception as e:
            logger.error(f"Error en procesamiento automático: {e}", exc_info=True)
            if not silent:
                self.stdout.write(self.style.ERROR(f"✗ Error: {e}"))
