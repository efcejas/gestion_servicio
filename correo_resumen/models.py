from django.db import models


class CorreoSincronizacion(models.Model):
    ESTADOS = [
        ('OK', 'Correcta'),
        ('ERROR', 'Con error'),
        ('SIN_CONFIG', 'Sin configurar'),
    ]

    cuenta = models.CharField(max_length=255, default='inbox-principal')
    proveedor = models.CharField(max_length=20, default='IMAP')
    estado = models.CharField(max_length=20, choices=ESTADOS, default='OK')
    mensaje = models.CharField(max_length=255, blank=True)
    correos_leidos = models.PositiveIntegerField(default=0)
    correos_nuevos = models.PositiveIntegerField(default=0)
    iniciado_en = models.DateTimeField(auto_now_add=True)
    finalizado_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-iniciado_en']
        verbose_name = 'Sincronización de correo'
        verbose_name_plural = 'Sincronizaciones de correo'

    def __str__(self):
        return f'{self.cuenta} · {self.get_estado_display()}'


class CorreoResumen(models.Model):
    PRIORIDADES = [
        ('URGENTE', 'Urgente'),
        ('ALTA', 'Alta'),
        ('NORMAL', 'Normal'),
        ('BAJA', 'Baja'),
    ]

    CATEGORIAS = [
        ('DIRECCION', 'Dirección'),
        ('AUDITORIA', 'Auditoría'),
        ('SOPORTE', 'Soporte'),
        ('OPERATIVO', 'Operativo'),
        ('RRHH', 'RRHH'),
        ('OTRO', 'Otro'),
    ]

    ESTADOS_ATENCION = [
        ('pendiente', 'Pendiente'),
        ('en_curso', 'En curso'),
        ('resuelto', 'Resuelto'),
    ]

    cuenta = models.CharField(max_length=255, default='inbox-principal')
    proveedor = models.CharField(max_length=20, default='IMAP')
    remote_uid = models.CharField(max_length=255)
    message_id = models.CharField(max_length=255)
    thread_id = models.CharField(max_length=255, blank=True)
    remitente = models.CharField(max_length=255, blank=True)
    remitente_nombre = models.CharField(max_length=255, blank=True)
    asunto = models.CharField(max_length=500)
    fecha_email = models.DateTimeField()
    snippet = models.TextField(blank=True)
    cuerpo_texto = models.TextField(blank=True)
    leido = models.BooleanField(default=False)
    tiene_adjuntos = models.BooleanField(default=False)
    cantidad_adjuntos = models.PositiveIntegerField(default=0)
    score_importancia = models.PositiveSmallIntegerField(default=0)
    prioridad_sugerida = models.CharField(max_length=10, choices=PRIORIDADES, default='NORMAL')
    categoria = models.CharField(max_length=20, choices=CATEGORIAS, default='OTRO')
    requiere_accion = models.BooleanField(default=False)
    requiere_respuesta = models.BooleanField(default=False)
    fecha_compromiso = models.DateTimeField(null=True, blank=True)
    estado_atencion = models.CharField(
        max_length=20,
        choices=ESTADOS_ATENCION,
        default='pendiente'
    )
    evidencia_fecha = models.TextField(blank=True)
    resumen_ejecutivo = models.CharField(max_length=280, blank=True)
    resumen_ia = models.TextField(blank=True)
    acciones_sugeridas = models.JSONField(default=list, blank=True)
    datos_raw = models.JSONField(default=dict, blank=True)
    sincronizado_en = models.DateTimeField(auto_now=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha_email', '-score_importancia']
        verbose_name = 'Correo resumido'
        verbose_name_plural = 'Correos resumidos'
        constraints = [
            models.UniqueConstraint(
                fields=['cuenta', 'message_id'],
                name='correo_resumen_unique_cuenta_message_id',
            )
        ]
        indexes = [
            models.Index(fields=['-fecha_email']),
            models.Index(fields=['leido', 'score_importancia']),
            models.Index(fields=['prioridad_sugerida']),
            models.Index(fields=['requiere_respuesta', 'estado_atencion', '-fecha_email']),
            models.Index(fields=['fecha_compromiso', 'estado_atencion']),
        ]

    def __str__(self):
        return f'{self.asunto[:60]}'

    @property
    def remitente_visible(self):
        return self.remitente_nombre or self.remitente or 'Sin remitente'
