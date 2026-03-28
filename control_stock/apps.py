from django.apps import AppConfig


class ControlStockConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'control_stock'
    verbose_name = 'Control de Stock'

    def ready(self):
        import control_stock.signals  # noqa: F401
