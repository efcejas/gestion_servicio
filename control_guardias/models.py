from decimal import Decimal

from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.db import models
from django.utils import timezone


def upload_certificado_ausencia(instance, filename):
    return f"control_guardias/ausencias/{instance.residente_id}/{filename}"


def upload_documento_ausencia(instance, filename):
    return f"control_guardias/ausencias/{instance.ausencia_id}/{filename}"


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
    certificado = models.FileField(
        upload_to=upload_certificado_ausencia,
        blank=True,
        null=True,
        validators=[
            FileExtensionValidator(
                allowed_extensions=[
                    'jpg', 'jpeg', 'png', 'webp', 'pdf', 'doc', 'docx', 'heic', 'heif'
                ]
            )
        ],
        help_text='Adjuntar certificado (imagen, PDF o documento).'
    )
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

    @property
    def documentos_respaldo(self):
        """Lista unificada de documentos (campo legado + adjuntos múltiples)."""
        items = []
        if self.certificado:
            nombre = self.certificado.name.split('/')[-1]
            items.append({'url': self.certificado.url, 'nombre': nombre})
        for doc in self.documentos.all():
            nombre = doc.archivo.name.split('/')[-1]
            items.append({'url': doc.archivo.url, 'nombre': nombre})
        return items


class AusenciaDocumento(models.Model):
    """Documentos adjuntos asociados a una ausencia (permite múltiples archivos)."""

    TIPO_CHOICES = [
        ('CERTIFICADO', 'Certificado'),
        ('ESTUDIO', 'Estudio/Informe'),
        ('NOTA', 'Nota administrativa'),
        ('OTRO', 'Otro'),
    ]

    ausencia = models.ForeignKey(
        AusenciaResidente,
        on_delete=models.CASCADE,
        related_name='documentos'
    )
    archivo = models.FileField(
        upload_to=upload_documento_ausencia,
        validators=[
            FileExtensionValidator(
                allowed_extensions=['jpg', 'jpeg', 'png', 'webp', 'pdf', 'doc', 'docx', 'heic', 'heif']
            )
        ],
        help_text='Documento respaldatorio adjunto a la ausencia.'
    )
    tipo_documento = models.CharField(max_length=20, choices=TIPO_CHOICES, default='CERTIFICADO')
    observacion = models.CharField(max_length=200, blank=True)
    fecha_subida = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Documento de ausencia'
        verbose_name_plural = 'Documentos de ausencias'
        ordering = ['-fecha_subida']

    def __str__(self):
        return f"Documento {self.get_tipo_documento_display()} - Ausencia #{self.ausencia_id}"


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


class AjusteCuotaGuardia(models.Model):
    """
    Ajuste a la cuota mensual de guardias de un residente.
    CARRYOVER: guardia eliminada por excepción trasladada al mes siguiente.
    PENALIZACION: guardia extra asignada como penalización.
    El algoritmo de distribución suma estos ajustes a la cuota base.
    """
    TIPO_CHOICES = [
        ('CARRYOVER', 'Traslado del mes anterior'),
        ('PENALIZACION', 'Guardia extra por penalización'),
    ]

    residente = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='ajustes_cuota_guardias'
    )
    mes = models.PositiveSmallIntegerField(help_text='Mes al que aplica el ajuste (1-12).')
    anio = models.PositiveIntegerField(help_text='Año al que aplica el ajuste.')
    cantidad = models.PositiveSmallIntegerField(
        default=1,
        help_text='Guardias adicionales que se suman a la cuota base del residente para ese mes.'
    )
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    motivo = models.TextField(blank=True)
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='ajustes_cuota_creados'
    )
    guardia_origen = models.ForeignKey(
        AsignacionGuardia,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ajuste_cuota_generado',
        help_text='Guardia que originó este ajuste (trazabilidad).'
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Ajuste de cuota de guardia'
        verbose_name_plural = 'Ajustes de cuota de guardias'
        ordering = ['-creado_en']

    def __str__(self):
        return (
            f"{self.get_tipo_display()} — {self.residente.get_full_name()} "
            f"+{self.cantidad} guardia(s) ({self.mes:02d}/{self.anio})"
        )


class RotacionExterna(models.Model):
    """
    Período de rotación externa de un residente (carga manual del jefe).
    Residentes activos en rotación reciben preferencia de jueves en el
    algoritmo de distribución, ya que tienen disponibilidad reducida entre semana.
    """
    residente = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='rotaciones_externas'
    )
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()
    descripcion = models.CharField(
        max_length=200,
        blank=True,
        help_text='Ej: Rotación Clínica Médica HIBA'
    )
    activo = models.BooleanField(
        default=True,
        help_text='Desmarcar para ignorar esta rotación sin eliminarla del historial.'
    )
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='rotaciones_creadas'
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Rotación externa'
        verbose_name_plural = 'Rotaciones externas'
        ordering = ['-fecha_inicio']

    def __str__(self):
        return (
            f"{self.residente.get_full_name()} — "
            f"{self.fecha_inicio.strftime('%d/%m/%Y')} al {self.fecha_fin.strftime('%d/%m/%Y')}"
        )


class SolicitudSlotVacante(models.Model):
    """
    Solicitud de un residente para mover su guardia a un slot vacío del mismo mes.
    No requiere contraparte (≠ cambio bilateral). La cuota queda neutra:
    el residente cede la guardia del día X y toma el slot libre del día Y.
    Al aprobarse: guardia_ceder → REASIGNADA + nueva AsignacionGuardia PUBLICADA.
    """
    ESTADO_CHOICES = [
        ('PENDIENTE', 'Pendiente de validación'),
        ('APROBADA', 'Aprobada'),
        ('RECHAZADA', 'Rechazada'),
        ('CANCELADA', 'Cancelada por el solicitante'),
    ]

    solicitante = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='solicitudes_slot_vacante'
    )
    guardia_ceder = models.ForeignKey(
        AsignacionGuardia,
        on_delete=models.CASCADE,
        related_name='solicitudes_slot_vacante_origen',
        help_text='Guardia que el residente cede (día X).'
    )
    slot_fecha = models.DateField(help_text='Fecha del slot vacante destino (día Y).')
    slot_tipo_guardia = models.ForeignKey(
        ConfiguracionTipoGuardia,
        on_delete=models.CASCADE,
        related_name='solicitudes_slot_vacante',
        help_text='Tipo del slot vacante destino.'
    )
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='PENDIENTE')
    notas_solicitante = models.TextField(blank=True)
    notas_jefe = models.TextField(blank=True)
    revisado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='slots_vacantes_revisados'
    )
    guardia_creada = models.ForeignKey(
        AsignacionGuardia,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='solicitud_slot_vacante_origen',
        help_text='AsignacionGuardia creada al aprobar (trazabilidad).'
    )
    fecha_solicitud = models.DateTimeField(auto_now_add=True)
    fecha_resolucion = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Solicitud de slot vacante'
        verbose_name_plural = 'Solicitudes de slot vacante'
        ordering = ['-fecha_solicitud']
        constraints = [
            models.UniqueConstraint(
                fields=['guardia_ceder'],
                condition=models.Q(estado='PENDIENTE'),
                name='uniq_slot_pendiente_por_guardia',
            ),
            models.UniqueConstraint(
                fields=['slot_fecha', 'slot_tipo_guardia'],
                condition=models.Q(estado='PENDIENTE'),
                name='uniq_slot_destino_pendiente',
            ),
        ]

    @property
    def demorada(self):
        """Indica que una solicitud pendiente lleva al menos 24 horas sin resolver."""
        return (
            self.estado == 'PENDIENTE'
            and self.fecha_solicitud <= timezone.now() - timezone.timedelta(hours=24)
        )

    def __str__(self):
        return (
            f"Slot vacante: {self.solicitante.get_full_name()} "
            f"[{self.guardia_ceder.fecha.strftime('%d/%m/%Y')} → {self.slot_fecha.strftime('%d/%m/%Y')}] "
            f"({self.get_estado_display()})"
        )
