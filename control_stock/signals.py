from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import MovimientoStock, StockPorArea


@receiver(post_save, sender=MovimientoStock)
def verificar_stock_minimo(sender, instance, created, **kwargs):
    """
    Después de registrar un movimiento, comprueba si el stock bajó
    del mínimo configurado y envía alerta por email al responsable del área.
    """
    if not created:
        return

    try:
        stock = StockPorArea.objects.select_related(
            'producto', 'area', 'area__responsable'
        ).get(producto=instance.producto, area=instance.area)
    except StockPorArea.DoesNotExist:
        return

    if stock.bajo_minimo and stock.producto.stock_minimo > 0:
        from .services import enviar_alerta_stock_bajo
        enviar_alerta_stock_bajo(stock)
