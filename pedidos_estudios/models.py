from django.db import models
from django.conf import settings

class PedidoEstudio(models.Model):
    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('en_proceso', 'En proceso'),
        ('realizado', 'Realizado'),
    ]

    nombre_paciente = models.CharField(max_length=100)
    dni_paciente = models.CharField(max_length=20, blank=True, null=True)
    tipo_estudio = models.CharField(max_length=150)
    sector_solicitante = models.CharField(max_length=100)
    medico_solicitante = models.CharField(max_length=100, blank=True, null=True)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='pendiente')

    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_recepcion = models.DateTimeField(blank=True, null=True)
    fecha_realizacion = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"{self.nombre_paciente} - {self.tipo_estudio} ({self.get_estado_display()})"

class PedidoEstudioNota(models.Model):
    pedido = models.ForeignKey(PedidoEstudio, on_delete=models.CASCADE, related_name='notas')
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    fecha = models.DateTimeField(auto_now_add=True)
    comentario = models.TextField()

    def __str__(self):
        return f"Nota de {self.creado_por} el {self.fecha.strftime('%d/%m/%Y %H:%M')}"
