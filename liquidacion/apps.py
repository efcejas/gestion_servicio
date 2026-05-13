from django.apps import AppConfig


class LiquidacionConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'liquidacion'
    
    def ready(self):
        """
        Registra los signals cuando la app está lista.
        Los signals automatizan comportamientos: recálculo de montos, validaciones, auditoría.
        """
        import liquidacion.signals  # noqa: F401

