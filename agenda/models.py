from django.db import models
from django.conf import settings


class AgendaItem(models.Model):
    """
    Modelo para items de agenda: citas, reuniones, llamadas, recordatorios.
    """
    TIPO_CHOICES = [
        ('CITA', 'Cita'),
        ('REUNION', 'Reunión'),
        ('LLAMADA', 'Llamada'),
        ('RECORDATORIO', 'Recordatorio'),
        ('OTRO', 'Otro'),
    ]

    titulo = models.CharField(max_length=200)
    fecha = models.DateField()
    hora_inicio = models.TimeField(null=True, blank=True)
    hora_fin = models.TimeField(null=True, blank=True)
    descripcion = models.TextField(blank=True)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='OTRO')
    es_importante = models.BooleanField(default=False)
    completado = models.BooleanField(default=False)
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='agenda_items'
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['fecha', 'hora_inicio', 'titulo']
        verbose_name = 'Item de Agenda'
        verbose_name_plural = 'Items de Agenda'

    def __str__(self):
        return f"{self.titulo} - {self.fecha}"


class NotaPersonal(models.Model):
    """
    Modelo para notas personales, ideas rápidas, pendientes.
    """
    titulo = models.CharField(max_length=200, blank=True)
    contenido = models.TextField()
    fijada = models.BooleanField(default=False)
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notas_personales'
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-fijada', '-actualizado_en']
        verbose_name = 'Nota Personal'
        verbose_name_plural = 'Notas Personales'

    def __str__(self):
        return self.titulo if self.titulo else f"Nota del {self.creado_en.strftime('%d/%m/%Y')}"
