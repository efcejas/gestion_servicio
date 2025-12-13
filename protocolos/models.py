from django.db import models
from django.utils.text import slugify


class Modalidad(models.Model):
    """Modalidad de imagen (TC, RM, RX, US, etc.)"""
    codigo = models.CharField(max_length=10, unique=True, verbose_name='Código')
    nombre = models.CharField(max_length=100, verbose_name='Nombre')

    class Meta:
        verbose_name = 'Modalidad'
        verbose_name_plural = 'Modalidades'
        ordering = ['codigo']

    def __str__(self):
        return f'{self.codigo} - {self.nombre}'


class RegionAnatomica(models.Model):
    """Región anatómica (Tórax, Abdomen, TAP, etc.)"""
    nombre = models.CharField(max_length=100, unique=True, verbose_name='Nombre')
    codigo = models.CharField(max_length=20, unique=True, verbose_name='Código')

    class Meta:
        verbose_name = 'Región Anatómica'
        verbose_name_plural = 'Regiones Anatómicas'
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


class Tag(models.Model):
    """Etiquetas para clasificar protocolos (TEP, Dolor abdominal, etc.)"""
    nombre = models.CharField(max_length=100, unique=True, verbose_name='Nombre')
    slug = models.SlugField(max_length=120, unique=True, blank=True, verbose_name='Slug')

    class Meta:
        verbose_name = 'Etiqueta'
        verbose_name_plural = 'Etiquetas'
        ordering = ['nombre']

    def __str__(self):
        return self.nombre

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.nombre)
        super().save(*args, **kwargs)


class Protocolo(models.Model):
    """Protocolo radiológico completo"""
    # Clasificación básica
    modalidad = models.ForeignKey(
        Modalidad,
        on_delete=models.PROTECT,
        verbose_name='Modalidad',
        related_name='protocolos'
    )
    region = models.ForeignKey(
        RegionAnatomica,
        on_delete=models.PROTECT,
        verbose_name='Región',
        related_name='protocolos'
    )
    nombre = models.CharField(max_length=200, verbose_name='Nombre del protocolo')
    descripcion = models.TextField(blank=True, verbose_name='Descripción', help_text='Texto para residentes')
    tags = models.ManyToManyField(Tag, blank=True, verbose_name='Etiquetas', related_name='protocolos')

    # Contraste
    requiere_contraste_ev = models.BooleanField(default=False, verbose_name='Requiere contraste EV')
    requiere_contraste_oral = models.BooleanField(default=False, verbose_name='Requiere contraste oral')
    requiere_ayuno = models.BooleanField(default=True, verbose_name='Requiere ayuno')

    # Preparación del paciente
    calibre_via_minimo = models.CharField(
        max_length=20,
        blank=True,
        verbose_name='Calibre vía mínimo',
        help_text='Ej: 20G, 18G'
    )
    sitio_via_preferido = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Sitio vía preferido',
        help_text='Ej: Fosa antecubital'
    )
    preparacion_paciente = models.TextField(
        blank=True,
        verbose_name='Preparación del paciente',
        help_text='Instrucciones detalladas de preparación'
    )

    # Cobertura y notas
    cobertura_global = models.TextField(
        blank=True,
        verbose_name='Cobertura global',
        help_text='Límites anatómicos generales del estudio'
    )
    notas_docentes = models.TextField(
        blank=True,
        verbose_name='Notas docentes',
        help_text='Información adicional para residentes'
    )

    # Estado
    es_activo = models.BooleanField(default=True, verbose_name='Activo')

    class Meta:
        verbose_name = 'Protocolo'
        verbose_name_plural = 'Protocolos'
        ordering = ['modalidad', 'region', 'nombre']

    def __str__(self):
        return f'{self.modalidad.codigo} - {self.region.nombre}: {self.nombre}'


class FaseAdquisicion(models.Model):
    """Fase de adquisición dentro de un protocolo"""
    TIPO_FASE_CHOICES = [
        ('SIN', 'Sin contraste'),
        ('ART', 'Arterial'),
        ('PORT', 'Portal'),
        ('TARD', 'Tardía'),
        ('OTRA', 'Otra'),
    ]

    protocolo = models.ForeignKey(
        Protocolo,
        on_delete=models.CASCADE,
        related_name='fases',
        verbose_name='Protocolo'
    )
    orden = models.IntegerField(default=0, verbose_name='Orden')
    nombre = models.CharField(max_length=100, verbose_name='Nombre de la fase')
    tipo_fase = models.CharField(
        max_length=10,
        choices=TIPO_FASE_CHOICES,
        verbose_name='Tipo de fase'
    )
    region = models.ForeignKey(
        RegionAnatomica,
        on_delete=models.PROTECT,
        verbose_name='Región',
        related_name='fases'
    )
    delay_segundos = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='Delay (segundos)',
        help_text='Delay respecto a inyección de contraste'
    )

    # Cobertura específica de esta fase
    cobertura_desde = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Cobertura desde',
        help_text='Ej: Apex pulmonar'
    )
    cobertura_hasta = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Cobertura hasta',
        help_text='Ej: Sínfisis púbica'
    )

    # Detalles técnicos
    ventanas_recomendadas = models.TextField(
        blank=True,
        verbose_name='Ventanas recomendadas',
        help_text='Ej: Parénquima, mediastino, ósea'
    )
    detalles_tecnicos = models.TextField(
        blank=True,
        verbose_name='Detalles técnicos',
        help_text='kVp, mAs, grosor de corte, etc.'
    )
    notas_para_residente = models.TextField(
        blank=True,
        verbose_name='Notas para residente',
        help_text='Información adicional sobre esta fase'
    )

    class Meta:
        verbose_name = 'Fase de Adquisición'
        verbose_name_plural = 'Fases de Adquisición'
        ordering = ['orden']

    def __str__(self):
        return f'{self.protocolo.nombre} - {self.nombre} ({self.get_tipo_fase_display()})'
