from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from .storage import EvaluacionesMediaStorage


class Examen(models.Model):
    BORRADOR = 'BORRADOR'
    PUBLICADO = 'PUBLICADO'
    CERRADO = 'CERRADO'
    ARCHIVADO = 'ARCHIVADO'
    ESTADO_CHOICES = [
        (BORRADOR, 'Borrador'),
        (PUBLICADO, 'Publicado'),
        (CERRADO, 'Cerrado'),
        (ARCHIVADO, 'Archivado'),
    ]
    ANIOS_RESIDENCIA = [
        ('R1', 'R1'),
        ('R2', 'R2'),
        ('R3', 'R3'),
        ('R4', 'R4'),
    ]
    TODOS = 'TODOS'
    ANIOS = 'ANIOS'
    RESIDENTES = 'RESIDENTES'
    MODO_DESTINATARIOS_CHOICES = [
        (TODOS, 'Todos los residentes activos'),
        (ANIOS, 'Uno o varios años de residencia'),
        (RESIDENTES, 'Residentes específicos'),
    ]
    INICIO_AUTOMATICO = 'AUTOMATICO'
    INICIO_MANUAL = 'MANUAL'
    MODO_INICIO_CHOICES = [
        (INICIO_AUTOMATICO, 'Automático por fecha'),
        (INICIO_MANUAL, 'Manual por docente'),
    ]

    titulo = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True)
    instrucciones = models.TextField(blank=True)
    ciclo_lectivo = models.CharField(max_length=20, default='SIN_DEFINIR')
    modo_destinatarios = models.CharField(
        max_length=12,
        choices=MODO_DESTINATARIOS_CHOICES,
        default=TODOS,
    )
    modo_inicio = models.CharField(
        max_length=12,
        choices=MODO_INICIO_CHOICES,
        default=INICIO_AUTOMATICO,
    )
    creador = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='examenes_creados',
    )
    anios_destinatarios = models.JSONField(default=list, blank=True)
    residentes_destinatarios = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name='examenes_asignados',
    )
    estado = models.CharField(
        max_length=12,
        choices=ESTADO_CHOICES,
        default=BORRADOR,
    )
    fecha_apertura = models.DateTimeField()
    fecha_vencimiento = models.DateTimeField()
    fecha_publicacion = models.DateTimeField(blank=True, null=True)
    iniciado_en = models.DateTimeField(blank=True, null=True)
    fecha_cierre = models.DateTimeField(blank=True, null=True)
    resultados_publicados_en = models.DateTimeField(blank=True, null=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-creado_en']
        indexes = [
            models.Index(fields=['estado', 'fecha_apertura']),
            models.Index(fields=['creador', 'estado']),
        ]

    def __str__(self):
        return self.titulo

    def clean(self):
        super().clean()
        if self.fecha_vencimiento <= self.fecha_apertura:
            raise ValidationError({
                'fecha_vencimiento': 'Debe ser posterior a la fecha de apertura.',
            })
        if not isinstance(self.anios_destinatarios, list):
            raise ValidationError({
                'anios_destinatarios': 'Debe ser una lista de años de residencia.',
            })
        anios_invalidos = set(self.anios_destinatarios) - {
            anio for anio, _ in self.ANIOS_RESIDENCIA
        }
        if anios_invalidos:
            raise ValidationError({
                'anios_destinatarios': 'Contiene años de residencia no válidos.',
            })
        if self.modo_destinatarios == self.TODOS:
            if self.anios_destinatarios:
                raise ValidationError('El modo Todos no admite filtros adicionales.')
        elif self.modo_destinatarios == self.ANIOS:
            if not self.anios_destinatarios:
                raise ValidationError('Seleccioná al menos un año de residencia.')
        elif self.modo_destinatarios == self.RESIDENTES:
            if self.anios_destinatarios:
                raise ValidationError('El modo por residentes no admite años seleccionados.')

    @property
    def puntaje_maximo(self):
        return sum(pregunta.puntaje for pregunta in self.preguntas.all())

    def esta_disponible_para(self, usuario, ahora=None):
        ahora = ahora or timezone.now()
        if self.estado != self.PUBLICADO:
            return False
        if not usuario.es_residente_activo():
            return False
        asignado = self.destinatarios_asignados.filter(residente=usuario).exists()
        if not asignado or not (self.fecha_apertura <= ahora < self.fecha_vencimiento):
            return False
        if self.modo_inicio == self.INICIO_MANUAL and self.iniciado_en is None:
            return False
        return True

    @property
    def estado_operativo(self):
        if self.estado == self.BORRADOR:
            return 'Borrador'
        if self.estado == self.CERRADO:
            return 'Cerrado'
        if self.estado == self.ARCHIVADO:
            return 'Archivado'
        ahora = timezone.now()
        if self.fecha_apertura > ahora:
            return 'Programado'
        if self.modo_inicio == self.INICIO_MANUAL and self.iniciado_en is None:
            return 'Programado'
        if self.estado == self.PUBLICADO and self.fecha_vencimiento > ahora:
            return 'En curso'
        return self.get_estado_display()


class DestinatarioExamen(models.Model):
    examen = models.ForeignKey(
        Examen,
        on_delete=models.CASCADE,
        related_name='destinatarios_asignados',
    )
    residente = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='asignaciones_examenes',
    )
    anio_residencia_al_asignar = models.CharField(max_length=2)
    ciclo_lectivo = models.CharField(max_length=20)
    criterio_origen = models.CharField(max_length=12, choices=Examen.MODO_DESTINATARIOS_CHOICES)
    asignado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['examen', 'residente'],
                name='unique_destinatario_examen_residente',
            ),
        ]
        indexes = [
            models.Index(fields=['examen', 'anio_residencia_al_asignar']),
            models.Index(fields=['residente', 'ciclo_lectivo']),
        ]

    def __str__(self):
        return f'{self.examen} - {self.residente}'


class Pregunta(models.Model):
    OPCION_UNICA = 'OPCION_UNICA'
    OPCION_MULTIPLE = 'OPCION_MULTIPLE'
    VERDADERO_FALSO = 'VERDADERO_FALSO'
    DESARROLLO = 'DESARROLLO'
    TIPO_CHOICES = [
        (OPCION_UNICA, 'Opción única'),
        (OPCION_MULTIPLE, 'Opción múltiple'),
        (VERDADERO_FALSO, 'Verdadero o falso'),
        (DESARROLLO, 'Respuesta desarrollada'),
    ]

    examen = models.ForeignKey(
        Examen,
        on_delete=models.CASCADE,
        related_name='preguntas',
    )
    texto = models.TextField()
    imagen = models.ImageField(
        upload_to='preguntas/',
        storage=EvaluacionesMediaStorage(),
        blank=True,
        null=True,
    )
    orden = models.PositiveIntegerField()
    puntaje = models.DecimalField(max_digits=6, decimal_places=2, default=1)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default=OPCION_UNICA)

    class Meta:
        ordering = ['orden', 'pk']
        constraints = [
            models.UniqueConstraint(
                fields=['examen', 'orden'],
                name='unique_pregunta_orden_examen',
            ),
        ]

    def __str__(self):
        return f'{self.examen}: pregunta {self.orden}'

    def _examen_esta_congelado(self):
        return self.examen_id and Examen.objects.exclude(
            estado=Examen.BORRADOR,
        ).filter(pk=self.examen_id).exists()

    def save(self, *args, **kwargs):
        if self._examen_esta_congelado():
            raise ValidationError('No se puede modificar una pregunta publicada.')
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self._examen_esta_congelado():
            raise ValidationError('No se puede eliminar una pregunta publicada.')
        return super().delete(*args, **kwargs)

    def clean(self):
        super().clean()
        if self.puntaje <= 0:
            raise ValidationError({'puntaje': 'El puntaje debe ser mayor que cero.'})


class PreguntaImagen(models.Model):
    pregunta = models.ForeignKey(
        Pregunta,
        on_delete=models.CASCADE,
        related_name='imagenes',
    )
    archivo = models.ImageField(
        upload_to='preguntas/galeria/',
        storage=EvaluacionesMediaStorage(),
    )
    orden = models.PositiveIntegerField(default=1)
    texto_alternativo = models.CharField(max_length=200, blank=True)
    creada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['orden', 'pk']
        constraints = [
            models.UniqueConstraint(
                fields=['pregunta', 'orden'],
                name='unique_pregunta_imagen_orden',
            ),
        ]

    def __str__(self):
        return f'Imagen {self.orden} - {self.pregunta}'

    def _examen_esta_congelado(self):
        return Examen.objects.exclude(
            estado=Examen.BORRADOR,
        ).filter(preguntas__pk=self.pregunta_id).exists()

    def save(self, *args, **kwargs):
        if self.pregunta_id and self._examen_esta_congelado():
            raise ValidationError('No se puede modificar una imagen publicada.')
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self._examen_esta_congelado():
            raise ValidationError('No se puede eliminar una imagen publicada.')
        return super().delete(*args, **kwargs)


class Opcion(models.Model):
    pregunta = models.ForeignKey(
        Pregunta,
        on_delete=models.CASCADE,
        related_name='opciones',
    )
    texto = models.TextField()
    orden = models.PositiveIntegerField()
    es_correcta = models.BooleanField(default=False)

    class Meta:
        ordering = ['orden', 'pk']
        constraints = [
            models.UniqueConstraint(
                fields=['pregunta', 'orden'],
                name='unique_opcion_orden_pregunta',
            ),
        ]

    def __str__(self):
        return f'{self.pregunta} - opción {self.orden}'

    def _examen_esta_congelado(self):
        return self.pregunta_id and Examen.objects.exclude(
            estado=Examen.BORRADOR,
        ).filter(preguntas__pk=self.pregunta_id).exists()

    def save(self, *args, **kwargs):
        if self._examen_esta_congelado():
            raise ValidationError('No se puede modificar una opción publicada.')
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self._examen_esta_congelado():
            raise ValidationError('No se puede eliminar una opción publicada.')
        return super().delete(*args, **kwargs)


class IntentoExamen(models.Model):
    INICIADO = 'INICIADO'
    ENTREGADO = 'ENTREGADO'
    CORREGIDO = 'CORREGIDO'
    PENDIENTE_CORRECCION = 'PENDIENTE_CORRECCION'
    ANULADO = 'ANULADO'
    ESTADO_CHOICES = [
        (INICIADO, 'Iniciado'),
        (ENTREGADO, 'Entregado'),
        (CORREGIDO, 'Corregido'),
        (PENDIENTE_CORRECCION, 'Pendiente de corrección'),
        (ANULADO, 'Anulado'),
    ]

    examen = models.ForeignKey(
        Examen,
        on_delete=models.PROTECT,
        related_name='intentos',
    )
    residente = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='intentos_examenes',
    )
    estado = models.CharField(max_length=22, choices=ESTADO_CHOICES, default=INICIADO)
    iniciado_en = models.DateTimeField(auto_now_add=True)
    entregado_en = models.DateTimeField(blank=True, null=True)
    puntaje_obtenido = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True)
    porcentaje = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    nota_final = models.DecimalField(max_digits=4, decimal_places=2, blank=True, null=True)
    resultado_publicado_en = models.DateTimeField(blank=True, null=True)
    anulado_en = models.DateTimeField(blank=True, null=True)
    anulado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name='intentos_anulados',
    )
    motivo_anulacion = models.TextField(blank=True)
    recuperado_en = models.DateTimeField(blank=True, null=True)
    recuperado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name='intentos_recuperados',
    )
    motivo_recuperacion = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['examen', 'residente'],
                name='unique_intento_examen_residente',
            ),
        ]
        indexes = [
            models.Index(fields=['examen', 'estado']),
            models.Index(fields=['residente', 'estado']),
        ]

    def __str__(self):
        return f'{self.examen} - {self.residente}'


class Respuesta(models.Model):
    intento = models.ForeignKey(
        IntentoExamen,
        on_delete=models.CASCADE,
        related_name='respuestas',
    )
    pregunta = models.ForeignKey(
        Pregunta,
        on_delete=models.PROTECT,
        related_name='respuestas',
    )
    texto_desarrollo = models.TextField(blank=True)
    puntaje_obtenido = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    es_correcta = models.BooleanField(default=False)
    requiere_correccion = models.BooleanField(default=False)
    comentario_docente = models.TextField(blank=True)
    respondida_en = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['intento', 'pregunta'],
                name='unique_respuesta_intento_pregunta',
            ),
        ]

    def __str__(self):
        return f'{self.intento} - {self.pregunta}'

    def clean(self):
        super().clean()
        if self.intento_id and self.pregunta_id:
            if self.intento.examen_id != self.pregunta.examen_id:
                raise ValidationError({
                    'pregunta': 'La pregunta debe pertenecer al examen del intento.',
                })


class RespuestaOpcion(models.Model):
    respuesta = models.ForeignKey(
        Respuesta,
        on_delete=models.CASCADE,
        related_name='opciones_elegidas',
    )
    opcion = models.ForeignKey(
        Opcion,
        on_delete=models.PROTECT,
        related_name='respuestas_seleccionadas',
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['respuesta', 'opcion'],
                name='unique_respuesta_opcion',
            ),
        ]

    def clean(self):
        super().clean()
        if self.respuesta_id and self.opcion_id:
            respuesta = self.respuesta
            if respuesta.pregunta_id != self.opcion.pregunta_id:
                raise ValidationError({
                    'opcion': 'La opción debe pertenecer a la pregunta respondida.',
                })
