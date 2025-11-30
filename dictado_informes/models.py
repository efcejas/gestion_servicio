from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


class TipoEstudio(models.TextChoices):
    """Tipos de estudios de diagnóstico por imágenes"""
    RESONANCIA = 'RES', 'Resonancia Magnética'
    TOMOGRAFIA = 'TOM', 'Tomografía'
    RADIOGRAFIA = 'RAD', 'Radiografía'
    ECOGRAFIA = 'ECO', 'Ecografía'
    MAMOGRAFIA = 'MAM', 'Mamografía'
    DENSITOMETRIA = 'DEN', 'Densitometría'
    OTRO = 'OTR', 'Otro'


class EstadoInforme(models.TextChoices):
    """Estados del informe durante el proceso"""
    BORRADOR = 'BOR', 'Borrador'
    EN_REVISION = 'REV', 'En Revisión'
    FINALIZADO = 'FIN', 'Finalizado'
    FIRMADO = 'FIR', 'Firmado'


class PlantillaInforme(models.Model):
    """Plantillas predefinidas para diferentes tipos de estudios"""
    nombre = models.CharField(max_length=200, verbose_name="Nombre de la Plantilla")
    tipo_estudio = models.CharField(
        max_length=3,
        choices=TipoEstudio.choices,
        verbose_name="Tipo de Estudio"
    )
    contenido = models.TextField(verbose_name="Contenido de la Plantilla")
    variables = models.JSONField(
        default=dict,
        blank=True,
        help_text="Variables que se pueden completar: {paciente}, {edad}, {fecha}, etc.",
        verbose_name="Variables"
    )
    activa = models.BooleanField(default=True, verbose_name="Activa")
    creada_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='plantillas_creadas',
        verbose_name="Creada por"
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creación")
    fecha_modificacion = models.DateTimeField(auto_now=True, verbose_name="Última Modificación")

    class Meta:
        verbose_name = "Plantilla de Informe"
        verbose_name_plural = "Plantillas de Informes"
        ordering = ['tipo_estudio', 'nombre']

    def __str__(self):
        return f"{self.get_tipo_estudio_display()} - {self.nombre}"


class Informe(models.Model):
    """Informe médico generado por dictado con IA"""
    # Datos del paciente
    nombre_paciente = models.CharField(max_length=200, verbose_name="Nombre del Paciente")
    apellido_paciente = models.CharField(max_length=200, verbose_name="Apellido del Paciente")
    dni_paciente = models.CharField(max_length=20, blank=True, verbose_name="DNI")
    edad_paciente = models.PositiveIntegerField(null=True, blank=True, verbose_name="Edad")
    fecha_nacimiento = models.DateField(null=True, blank=True, verbose_name="Fecha de Nacimiento")
    
    # Datos del estudio
    tipo_estudio = models.CharField(
        max_length=3,
        choices=TipoEstudio.choices,
        verbose_name="Tipo de Estudio"
    )
    numero_estudio = models.CharField(max_length=50, blank=True, verbose_name="Número de Estudio")
    fecha_estudio = models.DateField(default=timezone.now, verbose_name="Fecha del Estudio")
    region_anatomica = models.CharField(max_length=200, blank=True, verbose_name="Región Anatómica")
    
    # Contenido del informe
    indicacion_clinica = models.TextField(blank=True, verbose_name="Indicación Clínica")
    tecnica = models.TextField(blank=True, verbose_name="Técnica")
    hallazgos = models.TextField(verbose_name="Hallazgos")
    conclusion = models.TextField(verbose_name="Conclusión")
    
    # Estado y control
    estado = models.CharField(
        max_length=3,
        choices=EstadoInforme.choices,
        default=EstadoInforme.BORRADOR,
        verbose_name="Estado"
    )
    plantilla_usada = models.ForeignKey(
        PlantillaInforme,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='informes',
        verbose_name="Plantilla Usada"
    )
    
    # Médico responsable
    medico = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='informes_dictados',
        verbose_name="Médico Informante"
    )
    medico_firma = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='informes_firmados',
        verbose_name="Médico que Firma"
    )
    fecha_firma = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de Firma")
    
    # Metadatos
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creación")
    fecha_modificacion = models.DateTimeField(auto_now=True, verbose_name="Última Modificación")
    
    # IA y procesamiento
    procesado_con_ia = models.BooleanField(default=False, verbose_name="Procesado con IA")
    confianza_ia = models.FloatField(
        null=True,
        blank=True,
        help_text="Nivel de confianza de la IA (0-1)",
        verbose_name="Confianza IA"
    )
    sugerencias_ia = models.JSONField(
        default=dict,
        blank=True,
        help_text="Sugerencias de mejora de la IA",
        verbose_name="Sugerencias IA"
    )
    
    # Notas adicionales
    notas_privadas = models.TextField(
        blank=True,
        help_text="Notas privadas del médico (no aparecen en el informe final)",
        verbose_name="Notas Privadas"
    )

    class Meta:
        verbose_name = "Informe Médico"
        verbose_name_plural = "Informes Médicos"
        ordering = ['-fecha_estudio', '-fecha_creacion']
        permissions = [
            ("can_dictate", "Puede dictar informes"),
            ("can_sign", "Puede firmar informes"),
            ("can_use_ai", "Puede usar IA para informes"),
        ]

    def __str__(self):
        return f"{self.get_tipo_estudio_display()} - {self.apellido_paciente}, {self.nombre_paciente} ({self.fecha_estudio})"

    def firmar(self, medico):
        """Firma el informe"""
        self.estado = EstadoInforme.FIRMADO
        self.medico_firma = medico
        self.fecha_firma = timezone.now()
        self.save()

    def nombre_completo_paciente(self):
        """Retorna el nombre completo del paciente"""
        return f"{self.apellido_paciente}, {self.nombre_paciente}"


class AudioTranscripcion(models.Model):
    """Almacena los audios dictados y sus transcripciones"""
    informe = models.ForeignKey(
        Informe,
        on_delete=models.CASCADE,
        related_name='audios',
        verbose_name="Informe"
    )
    archivo_audio = models.FileField(
        upload_to='dictados/%Y/%m/%d/',
        verbose_name="Archivo de Audio"
    )
    duracion_segundos = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Duración (segundos)"
    )
    
    # Transcripción
    texto_original = models.TextField(
        blank=True,
        help_text="Transcripción literal del audio",
        verbose_name="Texto Original"
    )
    texto_mejorado = models.TextField(
        blank=True,
        help_text="Texto mejorado por IA",
        verbose_name="Texto Mejorado por IA"
    )
    
    # Metadatos del procesamiento
    servicio_transcripcion = models.CharField(
        max_length=50,
        blank=True,
        help_text="Whisper, Azure Speech, etc.",
        verbose_name="Servicio de Transcripción"
    )
    confianza_transcripcion = models.FloatField(
        null=True,
        blank=True,
        help_text="Nivel de confianza de la transcripción (0-1)",
        verbose_name="Confianza"
    )
    
    # Control
    procesado = models.BooleanField(default=False, verbose_name="Procesado")
    fecha_grabacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Grabación")
    fecha_transcripcion = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Fecha de Transcripción"
    )
    
    # Usuario
    grabado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='audios_grabados',
        verbose_name="Grabado por"
    )

    class Meta:
        verbose_name = "Audio de Dictado"
        verbose_name_plural = "Audios de Dictados"
        ordering = ['-fecha_grabacion']

    def __str__(self):
        return f"Audio {self.id} - {self.informe} ({self.fecha_grabacion.strftime('%d/%m/%Y %H:%M')})"
