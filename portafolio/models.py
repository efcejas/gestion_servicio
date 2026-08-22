import uuid
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.db import models

from .storage import PrivatePortfolioStorage


private_portfolio_storage = PrivatePortfolioStorage()


def upload_evidencia_actividad(instance, filename):
    extension = Path(filename).suffix.lower()
    return (
        f'portafolio/actividades/{instance.actividad.residente_id}/'
        f'{instance.actividad_id}/{uuid.uuid4().hex}{extension}'
    )


class ActividadCurricular(models.Model):
    TIPO_CHOICES = [
        ('CURSO', 'Curso'),
        ('CONGRESO_JORNADA', 'Congreso o jornada'),
        ('ATENEO_PRESENTACION', 'Ateneo o presentación'),
        ('TRABAJO_CIENTIFICO', 'Trabajo científico, publicación o póster'),
        ('ACTIVIDAD_DOCENTE', 'Actividad docente'),
        ('ROTACION_EXTERNA', 'Rotación externa'),
        ('OTRA', 'Otra actividad curricular'),
    ]
    ESTADO_CHOICES = [
        ('BORRADOR', 'Borrador'),
        ('ENVIADA', 'Enviada para revisión'),
        ('VALIDADA', 'Validada'),
        ('OBSERVADA', 'Observada'),
    ]

    residente = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='actividades_curriculares',
        limit_choices_to={'rol': 'medico_residente'},
    )
    tipo = models.CharField(max_length=30, choices=TIPO_CHOICES)
    titulo = models.CharField(max_length=200)
    institucion = models.CharField(max_length=200, blank=True)
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField(blank=True, null=True)
    descripcion = models.TextField(blank=True)
    enlace = models.URLField(blank=True)
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default='BORRADOR',
        db_index=True,
    )
    observacion_docente = models.TextField(blank=True)
    revisada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='actividades_curriculares_revisadas',
    )
    creada_en = models.DateTimeField(auto_now_add=True)
    actualizada_en = models.DateTimeField(auto_now=True)
    enviada_en = models.DateTimeField(blank=True, null=True)
    revisada_en = models.DateTimeField(blank=True, null=True)

    class Meta:
        verbose_name = 'Actividad curricular'
        verbose_name_plural = 'Actividades curriculares'
        ordering = ['-fecha_inicio', '-creada_en']
        indexes = [
            models.Index(
                fields=['residente', 'estado', 'fecha_inicio'],
                name='port_act_res_estado_fecha_idx',
            ),
        ]

    def __str__(self):
        return f'{self.residente.get_full_name()} · {self.titulo}'

    def clean(self):
        super().clean()
        if self.fecha_fin and self.fecha_fin < self.fecha_inicio:
            raise ValidationError(
                {'fecha_fin': 'La fecha de finalización no puede ser anterior al inicio.'}
            )

    @property
    def puede_editar_residente(self):
        return self.estado in {'BORRADOR', 'OBSERVADA'}


class DocumentoActividadCurricular(models.Model):
    TIPO_CHOICES = [
        ('CERTIFICADO', 'Certificado'),
        ('CONSTANCIA', 'Constancia'),
        ('PROGRAMA', 'Programa'),
        ('EVALUACION', 'Evaluación'),
        ('OTRO', 'Otro documento'),
    ]
    EXTENSIONES_PERMITIDAS = [
        'jpg',
        'jpeg',
        'png',
        'webp',
        'heic',
        'heif',
        'pdf',
        'doc',
        'docx',
        'ppt',
        'pptx',
        'xls',
        'xlsx',
    ]

    actividad = models.ForeignKey(
        ActividadCurricular,
        on_delete=models.CASCADE,
        related_name='documentos',
    )
    archivo = models.FileField(
        upload_to=upload_evidencia_actividad,
        storage=private_portfolio_storage,
        validators=[FileExtensionValidator(EXTENSIONES_PERMITIDAS)],
        max_length=500,
    )
    tipo = models.CharField(
        max_length=20,
        choices=TIPO_CHOICES,
        default='CERTIFICADO',
    )
    nombre_original = models.CharField(max_length=255)
    tipo_mime = models.CharField(max_length=150, blank=True)
    tamanio_bytes = models.PositiveBigIntegerField(default=0)
    sha256 = models.CharField(max_length=64, blank=True)
    subido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='documentos_curriculares_subidos',
    )
    subido_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Documento de actividad curricular'
        verbose_name_plural = 'Documentos de actividades curriculares'
        ordering = ['subido_en']

    def __str__(self):
        return self.nombre_original
