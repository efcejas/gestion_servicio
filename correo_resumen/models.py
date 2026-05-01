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


class CorreoHilo(models.Model):
    """
    Agrupa CorreoResumen en hilos (conversaciones).
    Se genera automáticamente al sincronizar basado en asunto normalizado + ventana temporal.
    """
    PRIORIDADES = [
        ('URGENTE', 'Urgente'),
        ('ALTA', 'Alta'),
        ('NORMAL', 'Normal'),
        ('BAJA', 'Baja'),
    ]

    ESTADOS_ATENCION = [
        ('pendiente', 'Pendiente'),
        ('en_curso', 'En curso'),
        ('resuelto', 'Resuelto'),
    ]

    cuenta = models.CharField(max_length=255, default='inbox-principal')
    asunto_normalizado = models.CharField(max_length=500, db_index=True)
    participantes = models.JSONField(default=dict, blank=True)  # {"carolina": "carolina@...", ...}
    correos = models.ManyToManyField(CorreoResumen, related_name='hilo')
    
    fecha_primer_email = models.DateTimeField()
    fecha_ultimo_email = models.DateTimeField()
    
    resumen_hilo = models.TextField(blank=True)
    prioridad_hilo = models.CharField(max_length=10, choices=PRIORIDADES, default='NORMAL')
    estado_hilo = models.CharField(
        max_length=20,
        choices=ESTADOS_ATENCION,
        default='pendiente'
    )
    requiere_respuesta = models.BooleanField(default=False)
    fecha_compromiso = models.DateTimeField(null=True, blank=True)
    fecha_seguimiento = models.DateTimeField(null=True, blank=True)
    resumen_ia_generado = models.BooleanField(default=False)
    
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-fecha_ultimo_email', '-prioridad_hilo']
        verbose_name = 'Hilo de correo'
        verbose_name_plural = 'Hilos de correo'
        constraints = [
            models.UniqueConstraint(
                fields=['cuenta', 'asunto_normalizado'],
                name='correo_hilo_unique_cuenta_asunto',
            )
        ]
        indexes = [
            models.Index(fields=['cuenta', 'asunto_normalizado']),
            models.Index(fields=['estado_hilo', '-fecha_ultimo_email']),
            models.Index(fields=['requiere_respuesta', 'estado_hilo']),
            models.Index(fields=['fecha_compromiso', 'estado_hilo']),
            models.Index(fields=['fecha_seguimiento', 'estado_hilo']),
        ]

    def __str__(self):
        return f'{self.asunto_normalizado[:60]} ({self.correos.count()} correos)'

    @property
    def cantidad_correos(self):
        return self.correos.count()

    @property
    def participantes_lista(self):
        return list(self.participantes.keys()) if self.participantes else []

    @property
    def es_urgente(self):
        return self.prioridad_hilo == 'URGENTE'

    @property
    def compromiso_vencido(self):
        from django.utils import timezone
        return bool(self.fecha_compromiso and self.fecha_compromiso < timezone.now())

    @property
    def seguimiento_vencido(self):
        from django.utils import timezone
        return bool(self.fecha_seguimiento and self.fecha_seguimiento < timezone.now())
