from django.db import models
from django.conf import settings

class EventoServicio(models.Model):
    TIPO_EVENTO_CHOICES = [
        ('cancelado', 'Estudio cancelado'),
        ('demorado', 'Estudio demorado'),
        ('pendiente', 'Estudio pendiente'),
        ('tecnico', 'Problema técnico'),
        ('conflicto', 'Conflicto o situación interpersonal'),
        ('otro', 'Otro')
    ]

    ESTADO_CHOICES = [
        ('abierto', 'Abierto'),
        ('en_revision', 'En revisión'),
        ('resuelto', 'Resuelto'),
    ]

    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='eventos_creados'
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    tipo_evento = models.CharField(max_length=20, choices=TIPO_EVENTO_CHOICES)
    descripcion = models.TextField()
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='abierto')

    # Campos opcionales
    sector_de_pedido = models.CharField(max_length=100, blank=True, null=True)
    nombre_paciente = models.CharField(max_length=100, blank=True, null=True)
    dni_paciente = models.CharField(max_length=20, blank=True, null=True)
    estudio_relacionado = models.CharField(max_length=150, blank=True, null=True)

    def __str__(self):
        return f"[{self.get_tipo_evento_display()}] {self.descripcion[:40]}..."

    @property
    def ultima_nota(self):
        """
        Devuelve el objeto de la última nota asociada al evento.
        Si no hay notas, devuelve None.
        """
        return self.notas.order_by('-fecha').first()

    def save(self, *args, **kwargs):
        usuario = kwargs.pop('usuario', None)
        if self.pk:
            original = EventoServicio.objects.get(pk=self.pk)
            if original.estado != self.estado:
                HistorialEvento.objects.create(
                    evento=self,
                    usuario=usuario,
                    cambio='estado',
                    valor_anterior=original.estado,
                    valor_nuevo=self.estado
                )
            if original.tipo_evento != self.tipo_evento:
                HistorialEvento.objects.create(
                    evento=self,
                    usuario=usuario,
                    cambio='tipo_evento',
                    valor_anterior=original.tipo_evento,
                    valor_nuevo=self.tipo_evento
                )
        super().save(*args, **kwargs)

class NotaEvento(models.Model):
    evento = models.ForeignKey(EventoServicio, on_delete=models.CASCADE, related_name='notas')
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notas_evento'
    )
    fecha = models.DateTimeField(auto_now_add=True)
    comentario = models.TextField()

    def __str__(self):
        return f"Nota por {self.creado_por} el {self.fecha.strftime('%d/%m/%Y %H:%M')}"

class HistorialEvento(models.Model):
    evento = models.ForeignKey(EventoServicio, on_delete=models.CASCADE, related_name='historial')
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='historial_eventos'
    )
    fecha = models.DateTimeField(auto_now_add=True)
    cambio = models.CharField(max_length=50)  # 'estado' o 'tipo_evento'
    valor_anterior = models.CharField(max_length=50, blank=True, null=True)
    valor_nuevo = models.CharField(max_length=50, blank=True, null=True)

    def __str__(self):
        return f"Cambio en {self.cambio} por {self.usuario} el {self.fecha.strftime('%d/%m/%Y %H:%M')}"