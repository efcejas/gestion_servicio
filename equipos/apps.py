"""
Configuración de la app 'equipos'.
Gestiona el inventario de equipos de imágenes médicas.
"""

from django.apps import AppConfig


class EquiposConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'equipos'
    verbose_name = 'Gestión de Equipos'
