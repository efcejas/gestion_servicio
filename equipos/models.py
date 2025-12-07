"""
Modelos para gestión de equipos de imágenes médicas.
"""

from django.db import models


class AreaServicio(models.TextChoices):
    """Áreas del servicio de imágenes."""
    TOMOGRAFIA = 'TOM', 'Tomografía'
    RESONANCIA = 'RM', 'Resonancia Magnética'
    RADIOLOGIA = 'RX', 'Radiología'
    ECOGRAFIA = 'ECO', 'Ecografía'
    OTRO = 'OTRO', 'Otro'


class EquipoImagen(models.Model):
    """
    Representa un equipo de imágenes médicas.
    
    Ejemplos: Tomógrafo Siemens, Resonador Philips, Ecógrafo GE, etc.
    """
    # Información básica
    nombre = models.CharField(
        max_length=200,
        help_text="Nombre identificativo del equipo (ej: 'Tomógrafo Principal')"
    )
    area = models.CharField(
        max_length=10,
        choices=AreaServicio.choices,
        default=AreaServicio.OTRO,
        help_text="Área del servicio a la que pertenece"
    )
    
    # Información técnica
    fabricante = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Fabricante del equipo (ej: Siemens, Philips, GE)"
    )
    modelo = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Modelo específico del equipo"
    )
    numero_serie = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Número de serie",
        help_text="Número de serie del equipo"
    )
    
    # Ubicación y fechas
    ubicacion = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name="Ubicación",
        help_text="Ubicación física del equipo (ej: 'Piso 2, Sala A')"
    )
    fecha_instalacion = models.DateField(
        blank=True,
        null=True,
        verbose_name="Fecha de instalación",
        help_text="Fecha en que se instaló el equipo"
    )
    ultimo_mantenimiento = models.DateField(
        blank=True,
        null=True,
        verbose_name="Último mantenimiento",
        help_text="Fecha del último mantenimiento realizado"
    )
    
    # Estado y observaciones
    en_servicio = models.BooleanField(
        default=True,
        help_text="¿El equipo está actualmente en servicio?"
    )
    observaciones = models.TextField(
        blank=True,
        null=True,
        help_text="Observaciones adicionales sobre el equipo"
    )
    
    # Metadatos
    fecha_creacion = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de creación"
    )
    fecha_modificacion = models.DateTimeField(
        auto_now=True,
        verbose_name="Última modificación"
    )
    
    class Meta:
        verbose_name = "Equipo de Imágenes"
        verbose_name_plural = "Equipos de Imágenes"
        ordering = ['area', 'nombre']
        indexes = [
            models.Index(fields=['area', 'en_servicio']),
        ]
    
    def __str__(self):
        """Representación en string del equipo."""
        estado = "✓" if self.en_servicio else "✗"
        return f"[{estado}] {self.nombre} - {self.get_area_display()}"
