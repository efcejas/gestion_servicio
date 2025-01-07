from django.db import models
from django.conf import settings

from django.db import models

class Tarea(models.Model):
    PRIORIDAD_CHOICES = [
        (1, 'Alta'),
        (2, 'Media'),
        (3, 'Baja'),
    ]
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    titulo = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True, null=True)
    estado = models.CharField(max_length=20, choices=[('pendiente', 'Pendiente'), ('en proceso', 'En proceso'), ('completada', 'Completada')])
    prioridad = models.PositiveSmallIntegerField(choices=PRIORIDAD_CHOICES)
    fecha_limite = models.DateField(blank=True, null=True)

    def prioridad_color(self):
        """Devuelve un color de Bootstrap según la prioridad"""
        if self.prioridad == 1:
            return 'danger'  # Rojo para prioridad alta
        elif self.prioridad == 2:
            return 'warning'  # Amarillo para prioridad media
        return 'success'  # Verde para prioridad baja

    def __str__(self):
        return self.titulo
