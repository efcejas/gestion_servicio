"""
Management command para procesar emails de pedidos de estudios.

Uso:
    python manage.py procesar_pedidos_email
    python manage.py procesar_pedidos_email --max-emails 20
    python manage.py procesar_pedidos_email --no-notificar
"""
import logging
from django.core.management.base import BaseCommand
from pedidos_estudios.services.procesador import ProcesadorPedidos

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Procesa emails pendientes de pedidos de estudios desde Gmail'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--max-emails',
            type=int,
            default=10,
            help='Número máximo de emails a procesar'
        )
        
        parser.add_argument(
            '--no-notificar',
            action='store_true',
            help='No enviar notificaciones por email'
        )
        
        parser.add_argument(
            '--no-marcar-leido',
            action='store_true',
            help='No marcar emails como leídos'
        )
    
    def handle(self, *args, **options):
        max_emails = options['max_emails']
        enviar_notificaciones = not options['no_notificar']
        marcar_leido = not options['no_marcar_leido']
        
        self.stdout.write(
            self.style.SUCCESS(f'Iniciando procesamiento de hasta {max_emails} emails...')
        )
        
        try:
            procesador = ProcesadorPedidos()
            
            stats = procesador.procesar_emails_pendientes(
                max_emails=max_emails,
                marcar_como_leido=marcar_leido,
                enviar_notificaciones=enviar_notificaciones
            )
            
            # Mostrar resultados
            self.stdout.write(
                self.style.SUCCESS('\n=== Resumen del Procesamiento ===')
            )
            self.stdout.write(f"Emails procesados: {stats['procesados']}")
            self.stdout.write(
                self.style.SUCCESS(f"✓ Exitosos: {stats['exitosos']}")
            )
            
            if stats['duplicados'] > 0:
                self.stdout.write(
                    self.style.WARNING(f"⚠ Duplicados: {stats['duplicados']}")
                )
            
            if stats['errores'] > 0:
                self.stdout.write(
                    self.style.ERROR(f"✗ Errores: {stats['errores']}")
                )
            
            self.stdout.write(
                self.style.SUCCESS('\nProcesamiento completado.')
            )
        
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'\nError durante el procesamiento: {str(e)}')
            )
            logger.error(f"Error en comando procesar_pedidos_email: {e}", exc_info=True)
            raise
