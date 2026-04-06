from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone


class ConfiguracionTipoGuardia(models.Model):
    """
    Define los tipos de guardia disponibles.
    Los jefes/instructores configuran aquí los días y horarios válidos.
    """
    nombre = models.CharField(max_length=100, unique=True)
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()
    dias_semana = models.CharField(
        max_length=20,
        help_text='Días aplicables separados por coma. Valores: L,M,X,J,V,S,D'
    )
    aplica_feriados = models.BooleanField(
        default=False,
        help_text='Si está activo, este tipo de guardia también aplica en feriados.'
    )
    activo = models.BooleanField(default=True)
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='tipos_guardia_creados'
    )

    class Meta:
        verbose_name = 'Tipo de guardia'
        verbose_name_plural = 'Tipos de guardia'
        ordering = ['nombre']

    def __str__(self):
        return f"{self.nombre} ({self.hora_inicio.strftime('%H:%M')} - {self.hora_fin.strftime('%H:%M')})"

    @property
    def duracion_horas(self):
        """Calcula la duración en horas, soportando turnos que cruzan la medianoche."""
        inicio = timezone.datetime.combine(timezone.datetime.today(), self.hora_inicio)
        fin = timezone.datetime.combine(timezone.datetime.today(), self.hora_fin)
        if fin <= inicio:
            fin += timezone.timedelta(days=1)
        return (fin - inicio).total_seconds() / 3600


class Feriado(models.Model):
    """Días feriados configurados por jefes/instructores."""
    fecha = models.DateField(unique=True)
    descripcion = models.CharField(max_length=200, blank=True)

    class Meta:
        verbose_name = 'Feriado'
        verbose_name_plural = 'Feriados'
        ordering = ['fecha']

    def __str__(self):
        return f"{self.fecha.strftime('%d/%m/%Y')} - {self.descripcion or 'Feriado'}"


class CuotaMensualGuardia(models.Model):
    """
    Cuota mensual de guardias por año de residencia.
    Configurable por jefes/instructores. Soporta atenuante de antigüedad.
    """
    ANIO_CHOICES = [
        ('R1', 'Primer año (R1)'),
        ('R2', 'Segundo año (R2)'),
        ('R3', 'Tercer año (R3)'),
        ('R4', 'Cuarto año (R4)'),
    ]

    anio_residencia = models.CharField(max_length=10, choices=ANIO_CHOICES, unique=True)
    guardias_por_mes = models.PositiveIntegerField(
        help_text='Cantidad base de guardias mensuales para este año de residencia.'
    )
    atenuante_porcentaje = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text='Porcentaje de reducción sobre la cuota base. Ej: 25 → la cuota efectiva es un 25% menor.'
    )

    class Meta:
        verbose_name = 'Cuota mensual de guardias'
        verbose_name_plural = 'Cuotas mensuales de guardias'
        ordering = ['anio_residencia']

    def __str__(self):
        return f"{self.get_anio_residencia_display()}: {self.guardias_efectivas} guardias/mes"

    @property
    def guardias_efectivas(self):
        """Cuota real aplicando el atenuante de antigüedad."""
        reduccion = self.guardias_por_mes * (self.atenuante_porcentaje / Decimal('100'))
        return max(0, int(self.guardias_por_mes - reduccion))


class AsignacionGuardia(models.Model):
    """
    Asignación de un turno de guardia a un residente.
    Núcleo del sistema de gestión de guardias.
    """
    ESTADO_CHOICES = [
        ('BORRADOR', 'Borrador'),
        ('PUBLICADA', 'Publicada'),
        ('CUMPLIDA', 'Cumplida'),
        ('AUSENTE', 'Ausente'),
        ('REASIGNADA', 'Reasignada'),
    ]

    residente = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='guardias_asignadas',
        limit_choices_to={'rol': 'medico_residente'}
    )
    tipo_guardia = models.ForeignKey(
        ConfiguracionTipoGuardia,
        on_delete=models.PROTECT,
        related_name='asignaciones'
    )
    fecha = models.DateField()
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='BORRADOR')
    es_feriado = models.BooleanField(
        default=False,
        help_text='Marcado automáticamente si la fecha coincide con un feriado registrado.'
    )
    creada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='guardias_creadas'
    )
    notas = models.TextField(blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Asignación de guardia'
        verbose_name_plural = 'Asignaciones de guardias'
        ordering = ['fecha', 'tipo_guardia']
        constraints = [
            models.UniqueConstraint(
                fields=['residente', 'fecha', 'tipo_guardia'],
                name='unique_residente_fecha_tipo'
            )
        ]

    def __str__(self):
        feriado = ' [FERIADO]' if self.es_feriado else ''
        return f"{self.residente.get_full_name()} - {self.fecha.strftime('%d/%m/%Y')}{feriado} - {self.tipo_guardia}"

    def save(self, *args, **kwargs):
        self.es_feriado = Feriado.objects.filter(fecha=self.fecha).exists()
        super().save(*args, **kwargs)


class AusenciaResidente(models.Model):
    """Ausencia reportada por un residente que afecta guardias ya asignadas."""
    MOTIVO_CHOICES = [
        ('ENFERMEDAD', 'Enfermedad'),
        ('VACACIONES', 'Vacaciones'),
        ('LICENCIA', 'Licencia'),
        ('OTRO', 'Otro'),
    ]
    ESTADO_CHOICES = [
        ('PENDIENTE', 'Pendiente de resolución'),
        ('RESUELTA', 'Resuelta'),
    ]

    residente = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='ausencias'
    )
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()
    motivo = models.CharField(max_length=20, choices=MOTIVO_CHOICES)
    descripcion = models.TextField(blank=True)
    guardias_afectadas = models.ManyToManyField(
        AsignacionGuardia,
        blank=True,
        related_name='ausencias'
    )
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='PENDIENTE')
    reportada_en = models.DateTimeField(auto_now_add=True)
    resuelta_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ausencias_resueltas'
    )

    class Meta:
        verbose_name = 'Ausencia de residente'
        verbose_name_plural = 'Ausencias de residentes'
        ordering = ['-reportada_en']

    def __str__(self):
        return (
            f"{self.residente.get_full_name()} - "
            f"{self.get_motivo_display()} ({self.fecha_inicio} → {self.fecha_fin})"
        )


class SolicitudCambioGuardia(models.Model):
    """
    Solicitud de intercambio de guardia entre dos residentes.
    Flujo: residente A solicita → residente B acepta → jefe/instructor valida.
    """
    ESTADO_CHOICES = [
        ('PENDIENTE_RECEPTOR', 'Esperando aceptación del receptor'),
        ('PENDIENTE_JEFE', 'Esperando validación de jefe/instructor'),
        ('APROBADA', 'Aprobada'),
        ('RECHAZADA', 'Rechazada'),
        ('CANCELADA', 'Cancelada por el solicitante'),
    ]

    solicitante = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='cambios_solicitados'
    )
    receptor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='cambios_recibidos'
    )
    guardia_solicitante = models.ForeignKey(
        AsignacionGuardia,
        on_delete=models.CASCADE,
        related_name='cambios_como_origen'
    )
    guardia_receptor = models.ForeignKey(
        AsignacionGuardia,
        on_delete=models.CASCADE,
        related_name='cambios_como_destino'
    )
    estado = models.CharField(max_length=30, choices=ESTADO_CHOICES, default='PENDIENTE_RECEPTOR')
    notas_solicitante = models.TextField(blank=True)
    notas_jefe = models.TextField(blank=True)
    revisado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cambios_revisados'
    )
    fecha_solicitud = models.DateTimeField(auto_now_add=True)
    fecha_resolucion = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Solicitud de cambio de guardia'
        verbose_name_plural = 'Solicitudes de cambio de guardia'
        ordering = ['-fecha_solicitud']

    def __str__(self):
        return (
            f"Cambio: {self.solicitante.get_full_name()} ↔ {self.receptor.get_full_name()} "
            f"({self.get_estado_display()})"
        )


class NotificacionGuardia(models.Model):
    """
    Inbox interno de notificaciones para el sistema de guardias.
    Se genera automáticamente ante eventos relevantes (asignación, cambio, ausencia, etc.).
    """
    TIPO_CHOICES = [
        ('ASIGNACION', 'Nueva guardia asignada'),
        ('PUBLICACION', 'Guardias del mes publicadas'),
        ('CAMBIO_SOLICITADO', 'Solicitud de cambio recibida'),
        ('CAMBIO_ACEPTADO', 'Tu propuesta de cambio fue aceptada'),
        ('CAMBIO_APROBADO', 'Cambio aprobado por jefe/instructor'),
        ('CAMBIO_RECHAZADO', 'Cambio rechazado'),
        ('AUSENCIA_RESUELTA', 'Tu ausencia fue procesada'),
        ('GUARDIA_REASIGNADA', 'Una de tus guardias fue reasignada'),
    ]

    destinatario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notificaciones_guardias'
    )
    tipo = models.CharField(max_length=30, choices=TIPO_CHOICES)
    mensaje = models.TextField()
    leida = models.BooleanField(default=False)
    fecha = models.DateTimeField(auto_now_add=True)
    asignacion = models.ForeignKey(
        AsignacionGuardia,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='notificaciones'
    )
    solicitud_cambio = models.ForeignKey(
        SolicitudCambioGuardia,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='notificaciones'
    )

    class Meta:
        verbose_name = 'Notificación de guardia'
        verbose_name_plural = 'Notificaciones de guardias'
        ordering = ['-fecha']

    def __str__(self):
        estado = '✓' if self.leida else '●'
        return f"[{estado}] {self.destinatario.get_full_name()} - {self.get_tipo_display()}"
