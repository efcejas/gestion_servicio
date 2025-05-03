from django.db import models
from django.conf import settings

class PedidoEstudio(models.Model):
    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('en_proceso', 'En proceso'),
        ('realizado', 'Realizado'),
    ]
    
    MODALIDAD_CHOICES = [
        ('TC', 'Tomografía Computada'),
        ('RM', 'Resonancia Magnética'),
        ('ECO', 'Ecografía'),
    ]
    
    PRIORIDAD_CHOICES = [
        ('urgente', 'Urgente'),
        ('media', 'Media'),
        ('baja', 'Baja'),
    ]

    nombre_paciente = models.CharField(max_length=100)
    dni_paciente = models.CharField(max_length=20, blank=True, null=True)
    modalidad = models.CharField(max_length=3, choices=MODALIDAD_CHOICES, default='TC')
    tipo_estudio = models.CharField(max_length=150)
    sector_solicitante = models.CharField(max_length=100)
    medico_solicitante = models.CharField(max_length=100, blank=True, null=True)
    prioridad = models.CharField(max_length=10, choices=PRIORIDAD_CHOICES, default='media')
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='pendiente')

    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_recepcion = models.DateTimeField(blank=True, null=True)
    fecha_realizacion = models.DateTimeField(blank=True, null=True)
    
    def save(self, *args, **kwargs):
        usuario = kwargs.pop('usuario', None)  # Extraer el usuario si se pasa
        valor_anterior = None
    
        if self.pk:  # Si el objeto ya existe en la base de datos
            valor_anterior = PedidoEstudio.objects.get(pk=self.pk).estado
    
        super().save(*args, **kwargs)  # Guardar el nuevo estado
    
        if usuario and valor_anterior != self.estado:  # Registrar solo si hubo un cambio
            HistorialPedidoEstudio.objects.create(
                pedido=self,
                usuario=usuario,
                cambio='estado',
                valor_anterior=valor_anterior,
                valor_nuevo=self.estado,
            )

    def __str__(self):
        return f"{self.nombre_paciente} - {self.tipo_estudio} ({self.get_estado_display()})"

class PedidoEstudioNota(models.Model):
    pedido = models.ForeignKey(PedidoEstudio, on_delete=models.CASCADE, related_name='notas')
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    fecha = models.DateTimeField(auto_now_add=True)
    comentario = models.TextField()

    def __str__(self):
        return f"Nota de {self.creado_por} el {self.fecha.strftime('%d/%m/%Y %H:%M')}"

class HistorialPedidoEstudio(models.Model):
    TIPO_CAMBIO_CHOICES = [
        ('estado', 'Cambio de estado'),
        ('prioridad', 'Cambio de prioridad'),
        ('modalidad', 'Cambio de modalidad'),
        ('visualizacion', 'Visualización del pedido'),
        ('otro', 'Otro cambio'),
    ]

    pedido = models.ForeignKey(PedidoEstudio, on_delete=models.CASCADE, related_name='historial')
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='historial_pedidos'
    )
    fecha = models.DateTimeField(auto_now_add=True)
    cambio = models.CharField(max_length=50, choices=TIPO_CAMBIO_CHOICES)
    valor_anterior = models.CharField(max_length=100, blank=True, null=True)
    valor_nuevo = models.CharField(max_length=100, blank=True, null=True)
    es_visualizacion = models.BooleanField(default=False)

    def get_valor_anterior_display(self):
        """Convierte el valor anterior en su representación legible."""
        if self.cambio == 'estado':
            estado_dict = dict(PedidoEstudio.ESTADO_CHOICES)
            return estado_dict.get(self.valor_anterior, self.valor_anterior)
        return self.valor_anterior

    def get_valor_nuevo_display(self):
        """Convierte el valor nuevo en su representación legible."""
        if self.cambio == 'estado':
            estado_dict = dict(PedidoEstudio.ESTADO_CHOICES)
            return estado_dict.get(self.valor_nuevo, self.valor_nuevo)
        return self.valor_nuevo
