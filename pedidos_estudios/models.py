"""
Modelos para la gestión de pedidos de estudios médicos recibidos por email.
"""
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.validators import EmailValidator

User = get_user_model()


class PacienteEstudio(models.Model):
    """
    Información del paciente asociado a un pedido de estudio.
    Puede ser temporal si no existe en el sistema principal.
    """
    # Identificación
    nombre_completo = models.CharField(max_length=255)
    dni = models.CharField(max_length=20, blank=True, null=True)
    historia_clinica = models.CharField(max_length=50, blank=True, null=True, unique=True)
    
    # Datos de contacto
    telefono = models.CharField(max_length=50, blank=True, null=True)
    email = models.EmailField(blank=True, null=True, validators=[EmailValidator()])
    
    # Datos clínicos
    fecha_nacimiento = models.DateField(blank=True, null=True)
    obra_social = models.CharField(max_length=200, blank=True, null=True)
    numero_afiliado = models.CharField(max_length=100, blank=True, null=True)
    
    # Ubicación en el sanatorio
    piso = models.CharField(max_length=10, blank=True, null=True)
    habitacion = models.CharField(max_length=20, blank=True, null=True)
    cama = models.CharField(max_length=10, blank=True, null=True)
    
    # Metadata
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'pedidos_pacientes_estudio'
        verbose_name = 'Paciente de Estudio'
        verbose_name_plural = 'Pacientes de Estudios'
        ordering = ['-fecha_creacion']
    
    def __str__(self):
        ubicacion = f" - Hab. {self.habitacion}" if self.habitacion else ""
        return f"{self.nombre_completo}{ubicacion}"


class TipoEstudio(models.Model):
    """
    Catálogo de tipos de estudios médicos disponibles.
    """
    MODALIDADES = [
        ('RX', 'Radiografía'),
        ('TC', 'Tomografía Computada'),
        ('RM', 'Resonancia Magnética'),
        ('US', 'Ecografía'),
        ('MN', 'Medicina Nuclear'),
        ('OT', 'Otros'),
    ]
    
    nombre = models.CharField(max_length=255, unique=True)
    modalidad = models.CharField(max_length=2, choices=MODALIDADES, default='OT')
    descripcion = models.TextField(blank=True)
    codigo_interno = models.CharField(max_length=50, blank=True, unique=True)
    
    # Responsables
    medico_responsable = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='estudios_responsable',
        limit_choices_to={'groups__name__in': ['Staff Médico', 'Médicos']}
    )
    email_notificacion = models.EmailField(
        blank=True, 
        help_text="Email alternativo para notificaciones de este tipo de estudio"
    )
    
    # Configuración
    requiere_preparacion = models.BooleanField(default=False)
    tiempo_estimado = models.IntegerField(
        default=30, 
        help_text="Tiempo estimado en minutos"
    )
    activo = models.BooleanField(default=True)
    
    # Metadata
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'pedidos_tipos_estudio'
        verbose_name = 'Tipo de Estudio'
        verbose_name_plural = 'Tipos de Estudios'
        ordering = ['modalidad', 'nombre']
    
    def __str__(self):
        return f"{self.get_modalidad_display()} - {self.nombre}"


class PedidoEstudio(models.Model):
    """
    Pedido de estudio médico recibido por email.
    """
    ESTADOS = [
        ('PENDIENTE', 'Pendiente'),
        ('PROCESANDO', 'En Procesamiento'),
        ('PROGRAMADO', 'Programado'),
        ('REALIZADO', 'Realizado'),
        ('CANCELADO', 'Cancelado'),
        ('ERROR', 'Error en Procesamiento'),
    ]
    
    PRIORIDADES = [
        ('URGENTE', 'Urgente'),
        ('ALTA', 'Alta'),
        ('NORMAL', 'Normal'),
        ('BAJA', 'Baja'),
    ]
    
    # Relaciones
    paciente = models.ForeignKey(
        PacienteEstudio, 
        on_delete=models.CASCADE, 
        related_name='pedidos'
    )
    tipo_estudio = models.ForeignKey(
        TipoEstudio, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='pedidos'
    )
    medico_solicitante = models.CharField(max_length=255)
    medico_asignado = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='estudios_asignados'
    )
    
    # Datos del pedido
    descripcion_estudio = models.TextField(
        help_text="Descripción del estudio solicitado (texto libre del email)"
    )
    indicacion_clinica = models.TextField(
        blank=True,
        default='',
        help_text="Motivo o indicación clínica del estudio"
    )
    observaciones = models.TextField(blank=True, default='')
    
    # Estado y prioridad
    estado = models.CharField(max_length=20, choices=ESTADOS, default='PENDIENTE')
    prioridad = models.CharField(max_length=10, choices=PRIORIDADES, default='NORMAL')
    
    # Fechas
    fecha_solicitud = models.DateTimeField(default=timezone.now)
    fecha_programada = models.DateTimeField(blank=True, null=True)
    fecha_realizacion = models.DateTimeField(blank=True, null=True)
    
    # Datos del email original
    email_message_id = models.CharField(
        max_length=255, 
        blank=True, 
        unique=True,
        help_text="Message-ID del email original"
    )
    email_asunto = models.CharField(max_length=500, blank=True)
    email_remitente = models.EmailField(blank=True)
    email_fecha = models.DateTimeField(blank=True, null=True)
    datos_raw = models.JSONField(
        default=dict,
        blank=True,
        help_text="Datos crudos del email para análisis posterior"
    )
    
    # Control de procesamiento
    procesado_automaticamente = models.BooleanField(default=False)
    requiere_revision = models.BooleanField(
        default=True,
        help_text="Indica si requiere revisión manual antes de procesar"
    )
    revisado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pedidos_revisados'
    )
    fecha_revision = models.DateTimeField(blank=True, null=True)
    
    # Notificaciones
    notificacion_enviada = models.BooleanField(default=False)
    fecha_notificacion = models.DateTimeField(blank=True, null=True)
    
    # Metadata
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)
    creado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pedidos_creados'
    )
    
    class Meta:
        db_table = 'pedidos_estudios'
        verbose_name = 'Pedido de Estudio'
        verbose_name_plural = 'Pedidos de Estudios'
        ordering = ['-fecha_solicitud', '-prioridad']
        indexes = [
            models.Index(fields=['-fecha_solicitud']),
            models.Index(fields=['estado']),
            models.Index(fields=['email_message_id']),
        ]
    
    def __str__(self):
        tipo = self.tipo_estudio or "Estudio"
        return f"{tipo} - {self.paciente.nombre_completo} ({self.get_estado_display()})"
    
    def marcar_como_procesado(self, usuario=None):
        """Marca el pedido como procesado y actualiza las fechas."""
        self.estado = 'PROCESANDO'
        self.revisado_por = usuario
        self.fecha_revision = timezone.now()
        self.requiere_revision = False
        self.save()
    
    def programar_estudio(self, fecha, usuario=None):
        """Programa el estudio para una fecha específica."""
        self.fecha_programada = fecha
        self.estado = 'PROGRAMADO'
        if usuario:
            self.medico_asignado = usuario
        self.save()
    
    def marcar_como_realizado(self):
        """Marca el estudio como realizado."""
        self.estado = 'REALIZADO'
        self.fecha_realizacion = timezone.now()
        self.save()


class AdjuntoEmail(models.Model):
    """
    Archivos adjuntos del email (estudios previos, órdenes, etc.)
    """
    pedido = models.ForeignKey(
        PedidoEstudio,
        on_delete=models.CASCADE,
        related_name='adjuntos'
    )
    
    nombre_archivo = models.CharField(max_length=255)
    archivo = models.FileField(upload_to='pedidos_estudios/adjuntos/%Y/%m/')
    tipo_mime = models.CharField(max_length=100, blank=True)
    tamaño = models.IntegerField(help_text="Tamaño en bytes")
    
    # Metadata
    fecha_subida = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'pedidos_adjuntos_email'
        verbose_name = 'Adjunto de Email'
        verbose_name_plural = 'Adjuntos de Emails'
    
    def __str__(self):
        return f"{self.nombre_archivo} ({self.pedido.id})"


class LogProcesamientoEmail(models.Model):
    """
    Registro de procesamiento de emails para auditoría y debugging.
    """
    RESULTADO = [
        ('EXITO', 'Éxito'),
        ('ERROR', 'Error'),
        ('PARCIAL', 'Procesamiento Parcial'),
        ('DUPLICADO', 'Email Duplicado'),
    ]
    
    # Datos del email
    email_message_id = models.CharField(max_length=255)
    email_asunto = models.CharField(max_length=500)
    email_remitente = models.EmailField()
    email_fecha = models.DateTimeField()
    
    # Resultado del procesamiento
    resultado = models.CharField(max_length=20, choices=RESULTADO)
    pedido_creado = models.ForeignKey(
        PedidoEstudio,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='logs_procesamiento'
    )
    
    # Detalles
    mensaje = models.TextField(blank=True)
    datos_extraidos = models.JSONField(
        default=dict,
        blank=True,
        help_text="Datos extraídos del email"
    )
    errores = models.JSONField(
        default=list,
        blank=True,
        help_text="Lista de errores encontrados"
    )
    
    # Metadata
    fecha_procesamiento = models.DateTimeField(auto_now_add=True)
    tiempo_procesamiento = models.FloatField(
        default=0,
        help_text="Tiempo de procesamiento en segundos"
    )
    
    class Meta:
        db_table = 'pedidos_log_procesamiento'
        verbose_name = 'Log de Procesamiento'
        verbose_name_plural = 'Logs de Procesamiento'
        ordering = ['-fecha_procesamiento']
    
    def __str__(self):
        return f"{self.email_asunto} - {self.get_resultado_display()}"
