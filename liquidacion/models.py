from django.db import models
from django.utils import timezone

class Medico(models.Model):
    nombre = models.CharField(max_length=50, verbose_name='Nombre')
    apellido = models.CharField(max_length=50, verbose_name='Apellido')
    matricula = models.CharField(max_length=6, verbose_name='Matrícula', unique=True, blank=True, null=True)

    class Meta:
        verbose_name = 'Médico'
        verbose_name_plural = 'Médicos'

    def __str__(self):
        return f'{self.nombre} {self.apellido}'

class Estudios(models.Model):
    nombre = models.CharField(max_length=150, unique=True, verbose_name='Nombre del estudio')
    TIPO_ESTUDIO_CHOICES = (
        ('ECO', 'Ecografía'),
        ('RAD', 'Radiografía'),
        ('TOM', 'Tomografía'),
        ('RES', 'Resonancia Magnética'),
        )
    tipo = models.CharField(max_length=3, choices=TIPO_ESTUDIO_CHOICES, default='ECO', verbose_name='Tipo de estudio')
    conteo_regiones = models.IntegerField(verbose_name='Cantidad de regiones')

    class Meta:
        verbose_name = 'Estudio'
        verbose_name_plural = 'Estudios'

    def __str__(self):
        return f'{self.nombre}'
