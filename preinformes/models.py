from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from django_ckeditor_5.fields import CKEditor5Field

User = get_user_model()


class TipoEstudio(models.Model):
    """Tipo de estudio radiológico (RX, TC, RM, ECO, etc.)"""
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(blank=True, null=True)
    activo = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = "Tipo de Estudio"
        verbose_name_plural = "Tipos de Estudios"
        ordering = ['nombre']
    
    def __str__(self):
        return self.nombre


class Region(models.Model):
    """Región anatómica del estudio"""
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(blank=True, null=True)
    activo = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = "Región"
        verbose_name_plural = "Regiones"
        ordering = ['nombre']
    
    def __str__(self):
        return self.nombre


class PlantillaPreinforme(models.Model):
    """Plantillas precargadas para preinformes"""
    nombre = models.CharField(max_length=200)
    tipo_estudio = models.ForeignKey(TipoEstudio, on_delete=models.CASCADE)
    region = models.ForeignKey(Region, on_delete=models.CASCADE)
    
    # Campos separados para cada sección
    tecnica_template = CKEditor5Field(
        config_name='default',
        verbose_name="Plantilla de Técnica",
        help_text="Plantilla para la sección de técnica",
        blank=True
    )
    hallazgos_template = CKEditor5Field(
        config_name='default', 
        verbose_name="Plantilla de Hallazgos",
        help_text="Plantilla para la sección de hallazgos",
        blank=True
    )
    conclusion_template = CKEditor5Field(
        config_name='default',
        verbose_name="Plantilla de Conclusión", 
        help_text="Plantilla para la sección de conclusión",
        blank=True
    )
    
    # Mantener campo legacy para compatibilidad
    contenido = models.TextField(
        help_text="Plantilla base del preinforme (campo legacy)",
        blank=True
    )
    
    activa = models.BooleanField(default=True)
    creada_por = models.ForeignKey(User, on_delete=models.CASCADE)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Plantilla de Preinforme"
        verbose_name_plural = "Plantillas de Preinformes"
        unique_together = ['nombre', 'tipo_estudio', 'region']
        ordering = ['tipo_estudio__nombre', 'region__nombre', 'nombre']
    
    def __str__(self):
        return f"{self.tipo_estudio.nombre} - {self.region.nombre} - {self.nombre}"


class Preinforme(models.Model):
    """Preinforme realizado por un residente"""
    
    ESTADO_CHOICES = [
        ('borrador', 'Borrador'),
        ('pendiente_revision', 'Pendiente de Revisión'),
        ('en_revision', 'En Revisión'),
        ('revisado', 'Revisado'),
        ('finalizado', 'Finalizado'),
    ]
    
    # Identificación del estudio
    residente = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='preinformes_realizados'
    )
    numero_estudio = models.CharField(
        max_length=50, 
        help_text="Número del estudio en el sistema EGES"
    )
    tipo_estudio = models.ForeignKey(TipoEstudio, on_delete=models.CASCADE)
    region = models.ForeignKey(Region, on_delete=models.CASCADE)
    plantilla_utilizada = models.ForeignKey(
        PlantillaPreinforme, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True
    )
    
    # Datos del paciente
    apellido_paciente = models.CharField(max_length=100)
    nombre_paciente = models.CharField(max_length=100)
    dni_paciente = models.CharField(
        max_length=20, 
        help_text="DNI o documento de identidad del paciente",
        null=True,
        blank=True,
        default='00000000'
    )
    edad_paciente = models.PositiveIntegerField()
    sexo_paciente = models.CharField(
        max_length=1, 
        choices=[('M', 'Masculino'), ('F', 'Femenino'), ('O', 'Otro')]
    )
    
    # Contenido del preinforme
    tecnica = CKEditor5Field(
        config_name='default',
        help_text="Descripción de la técnica utilizada"
    )
    hallazgos = CKEditor5Field(
        config_name='default',
        help_text="Hallazgos encontrados por el residente"
    )
    conclusion = CKEditor5Field(
        config_name='default',
        help_text="Conclusión del residente"
    )
    
    # Estado y revisión
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='borrador')
    revisor = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='preinformes_revisados'
    )
    
    # Timestamps
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)
    fecha_envio_revision = models.DateTimeField(null=True, blank=True)
    fecha_inicio_revision = models.DateTimeField(null=True, blank=True)
    fecha_finalizacion = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = "Preinforme"
        verbose_name_plural = "Preinformes"
        ordering = ['-fecha_creacion']
    
    def __str__(self):
        return f"{self.numero_estudio} - {self.apellido_paciente}, {self.nombre_paciente} ({self.residente.username})"
    
    def enviar_a_revision(self):
        """Envía el preinforme para revisión"""
        self.estado = 'pendiente_revision'
        self.fecha_envio_revision = timezone.now()
        self.save()
    
    def iniciar_revision(self, revisor):
        """Inicia la revisión por parte del staff"""
        self.estado = 'en_revision'
        self.revisor = revisor
        self.fecha_inicio_revision = timezone.now()
        self.save()
    
    def finalizar_revision(self):
        """Finaliza la revisión"""
        self.estado = 'finalizado'
        self.fecha_finalizacion = timezone.now()
        self.save()


class RevisionPreinforme(models.Model):
    """Revisión y correcciones realizadas por el staff"""
    preinforme = models.OneToOneField(
        Preinforme, 
        on_delete=models.CASCADE, 
        related_name='revision'
    )
    revisor = models.ForeignKey(User, on_delete=models.CASCADE)
    
    # Snapshot del informe original del residente (para comparaciones futuras)
    informe_residente_snapshot = models.TextField(
        blank=True,
        help_text="Snapshot del informe completo del residente al momento de la revisión"
    )
    
    # Informe final editado por el staff (HTML único)
    informe_final_html = CKEditor5Field(
        config_name='default',
        verbose_name="Informe Final (Staff)",
        help_text="Informe final editado por el staff - se inicializa con el contenido del residente",
        blank=True
    )
    
    # Comentarios generales
    comentarios_generales = models.TextField(
        blank=True, 
        null=True,
        help_text="Comentarios y sugerencias para el residente"
    )
    
    # Puntuación opcional
    puntuacion = models.PositiveIntegerField(
        null=True, 
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="Puntuación del 1 al 10 (opcional)"
    )
    

    
    # Timestamps
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Revisión de Preinforme"
        verbose_name_plural = "Revisiones de Preinformes"
    
    def __str__(self):
        return f"Revisión de {self.preinforme.numero_estudio} por {self.revisor.username}"
    
    def generar_informe_original_residente(self):
        """Genera el informe completo del residente con títulos HTML"""
        informe_html = f"""
<h3>TÉCNICA</h3>
{self.preinforme.tecnica}

<h3>HALLAZGOS</h3>
{self.preinforme.hallazgos}

<h3>CONCLUSIÓN</h3>
{self.preinforme.conclusion}
        """
        return informe_html.strip()
    
    def crear_snapshot_residente(self):
        """Crea un snapshot del informe original del residente"""
        if not self.informe_residente_snapshot:
            self.informe_residente_snapshot = self.generar_informe_original_residente()
            self.save()
    
    def inicializar_informe_final(self, save=True):
        """Inicializa el informe final del staff con el contenido del residente"""
        if not self.informe_final_html:
            # Preferir snapshot si existe, sino generar
            self.informe_final_html = self.informe_residente_snapshot or self.generar_informe_original_residente()
            if save:
                self.save()
    
    def inicializar_revision(self, save=True):
        """Inicializa la revisión creando snapshot y preparando informe final"""
        self.crear_snapshot_residente()
        self.inicializar_informe_final(save=save)
        return self.informe_final_html


class HistorialEstudios(models.Model):
    """Estadísticas y historial de estudios por residente"""
    residente = models.OneToOneField(
        User, 
        on_delete=models.CASCADE, 
        related_name='historial_estudios'
    )
    total_preinformes = models.PositiveIntegerField(default=0)
    preinformes_finalizados = models.PositiveIntegerField(default=0)
    promedio_puntuacion = models.DecimalField(
        max_digits=3, 
        decimal_places=1, 
        null=True, 
        blank=True
    )
    fecha_ultimo_preinforme = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = "Historial de Estudios"
        verbose_name_plural = "Historiales de Estudios"
    
    def __str__(self):
        return f"Historial de {self.residente.username}"
    
    def actualizar_estadisticas(self):
        """Actualiza las estadísticas del residente"""
        preinformes = Preinforme.objects.filter(residente=self.residente)
        self.total_preinformes = preinformes.count()
        self.preinformes_finalizados = preinformes.filter(estado='finalizado').count()
        
        if self.total_preinformes > 0:
            self.fecha_ultimo_preinforme = preinformes.latest('fecha_creacion').fecha_creacion
        
        # Calcular promedio de puntuaciones
        puntuaciones = preinformes.filter(
            revision__puntuacion__isnull=False
        ).values_list('revision__puntuacion', flat=True)
        
        if puntuaciones:
            self.promedio_puntuacion = sum(puntuaciones) / len(puntuaciones)
        
        self.save()